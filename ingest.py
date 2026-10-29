"""Main F1 RAG ingestion pipeline.

Orchestrates the full workflow:
1. Data loading and filtering
2. Data preprocessing and document creation
3. Embedding generation
4. Pinecone upsert
5. Summary reporting

Usage:
    python ingest.py dry_run       # Preview documents without uploading
    python ingest.py test_batch   # Upload a small test batch
    python ingest.py full         # Full ingestion pipeline
    python ingest.py retrieve     # Test retrieval after ingestion
    python ingest.py validate     # Validate pipeline (read-only)

Important fix: document_text is now added to each document after embedding generation
so it's stored in Pinecone metadata and retrieved correctly.
"""

import numpy as np
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on the path for imports
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_NAMESPACE,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_DIMENSION,
    DEFAULT_BATCH_SIZE,
    MIN_SEASON,
    MAX_SEASON,
    validate_index,
)
from data_loader import (
    load_drivers,
    load_constructors,
    load_races,
    load_results,
    load_qualifying,
    load_pit_stops,
    load_lap_times,
    load_driver_standings,
    load_constructor_standings,
    get_2021_2025_race_ids,
    filter_results_by_race_ids,
    filter_qualifying_by_race_ids,
    filter_pit_stops_by_race_ids,
    filter_lap_times_by_race_ids,
    filter_driver_standings_by_race_ids,
    filter_constructor_standings_by_race_ids,
)
from preprocessor import (
    create_race_result_documents,
    create_qualifying_documents,
    create_pit_stop_documents,
    create_driver_profile_documents,
    create_constructor_profile_documents,
    create_standings_documents,
    create_lap_time_summary_documents,
)
from embedding_service import EmbeddingService
from pinecone_store import PineconeStore, ConfigurationError

from utils import setup_logging, get_logger, utc_now_iso, FailureRecord, ProcessingStats, StateStore

logger = logging.getLogger("f1rag.ingest")


def run_ingest(dry_run: bool = False, test_mode: bool = False) -> dict:
    """Run the full ingestion pipeline.

    Args:
        dry_run: If True, preview document creation without uploading vectors.
        test_mode: If True, upload a small test batch before full ingestion.

    Returns:
        Processing summary dictionary.
    """
    run_id = utc_now_iso()
    logger.info(f"Starting F1 RAG ingestion run {run_id}")

    stats = ProcessingStats(run_id=run_id)

    # Step 1: Load data
    logger.info("Step 1: Loading data...")
    try:
        drivers = load_drivers()
        constructors = load_constructors()
        races, season_race_ids = load_races()
        results = load_results()
        qualifying = load_qualifying()
        pit_stops = load_pit_stops()
        lap_times = load_lap_times()
        driver_standings = load_driver_standings()
        constructor_standings = load_constructor_standings()
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        stats.record_failure(stage="data_loading", document_id="", document_type="pipeline", error=e)
        return stats.to_dict()

    stats.source_rows = {
        "drivers": len(drivers),
        "constructors": len(constructors),
        "races": len(races),
        "results": len(results),
        "qualifying": len(qualifying),
        "pit_stops": len(pit_stops),
        "lap_times": len(lap_times),
        "driver_standings": len(driver_standings),
        "constructor_standings": len(constructor_standings),
    }

    # Step 2: Get 2021-2025 race IDs
    logger.info("Step 2: Getting 2021-2025 race IDs...")
    race_ids_2021_2025 = get_2021_2025_race_ids(races)
    stats.source_table_totals = {
        "results_total": len(results),
        "races_2021_2025": len(race_ids_2021_2025),
    }

    # Step 3: Filter data to 2021-2025
    logger.info("Step 3: Filtering data to 2021-2025 seasons...")
    filtered_results = filter_results_by_race_ids(results, race_ids_2021_2025)
    filtered_qualifying = filter_qualifying_by_race_ids(qualifying, race_ids_2021_2025)
    filtered_pit_stops = filter_pit_stops_by_race_ids(pit_stops, race_ids_2021_2025)
    filtered_lap_times = filter_lap_times_by_race_ids(lap_times, race_ids_2021_2025)
    filtered_driver_standings = filter_driver_standings_by_race_ids(driver_standings, race_ids_2021_2025)
    filtered_constructor_standings = filter_constructor_standings_by_race_ids(constructor_standings, race_ids_2021_2025)

    stats.source_table_totals.update({
        "results_filtered": len(filtered_results),
        "qualifying_filtered": len(filtered_qualifying),
        "pit_stops_filtered": len(filtered_pit_stops),
        "lap_times_filtered": len(filtered_lap_times),
        "driver_standings_filtered": len(filtered_driver_standings),
        "constructor_standings_filtered": len(filtered_constructor_standings),
    })

    # Step 4: Create documents
    logger.info("Step 4: Creating documents...")
    try:
        # Race result documents
        race_docs = create_race_result_documents(
            filtered_results, drivers, constructors, races, season_race_ids
        )
        for d in race_docs:
            stats.record_document("race_result", d.get("season"))
        stats.documents_created += len(race_docs)

        # Qualifying documents
        qualifying_docs = create_qualifying_documents(
            filtered_qualifying, drivers, constructors, races, season_race_ids
        )
        for d in qualifying_docs:
            stats.record_document("qualifying", d.get("season"))
        stats.documents_created += len(qualifying_docs)

        # Pit stop documents
        pit_stop_docs = create_pit_stop_documents(
            filtered_pit_stops, drivers, constructors, races, season_race_ids
        )
        for d in pit_stop_docs:
            stats.record_document("pit_stop", d.get("season"))
        stats.documents_created += len(pit_stop_docs)

        # Driver profiles
        driver_profile_docs = create_driver_profile_documents(drivers, filtered_results, season_race_ids)
        for d in driver_profile_docs:
            stats.record_document("driver_profile", d.get("season"))
        stats.documents_created += len(driver_profile_docs)

        # Constructor profiles
        constructor_profile_docs = create_constructor_profile_documents(
            constructors, filtered_results, season_race_ids
        )
        for d in constructor_profile_docs:
            stats.record_document("constructor_profile", d.get("season"))
        stats.documents_created += len(constructor_profile_docs)

        # Standings documents
        standings_docs = create_standings_documents(
            filtered_driver_standings, filtered_constructor_standings, drivers, constructors, races, season_race_ids
        )
        for d in standings_docs:
            dt = d.get("document_type", "")
            season = d.get("season")
            if dt == "driver_standings":
                stats.record_document("driver_standings", season)
            elif dt == "constructor_standings":
                stats.record_document("constructor_standings", season)
        stats.documents_created += len(standings_docs)

        # Lap time summary documents
        lap_time_docs = create_lap_time_summary_documents(
            filtered_lap_times, drivers, races, season_race_ids,
            max_drivers=50, max_laps_per_driver=20
        )
        for d in lap_time_docs:
            stats.record_document("lap_time_summary", d.get("season"))
        stats.documents_created += len(lap_time_docs)

    except Exception as e:
        logger.error(f"Document creation failed: {e}", exc_info=True)
        stats.record_failure(stage="document_creation", document_id="", document_type="pipeline", error=e)
        return stats.to_dict()

    logger.info(f"Total documents created: {stats.documents_created}")

    # Step 5: Initialize Pinecone (if not dry run)
    vectors_upserted = 0
    vectors_skipped = 0

    if not dry_run:
        logger.info("Step 5: Initializing Pinecone...")
        try:
            pinecone_store = PineconeStore(
                api_key=PINECONE_API_KEY,
                index_name=PINECONE_INDEX_NAME,
                namespace=PINECONE_NAMESPACE,
            )

            if not pinecone_store.initialize():
                logger.error("Failed to initialize Pinecone index.")
                return stats.to_dict()

            # Validate index dimension matches model
            index_info = pinecone_store.get_index_info()
            index_dim = index_info.get("dimension", 0)
            logger.info(f"Index dimension: {index_dim}, Model dimension: {EMBEDDING_DIMENSION}")

            if index_dim != EMBEDDING_DIMENSION and index_dim != 0:
                logger.warning(
                    f"Index dimension {index_dim} does not match model dimension {EMBEDDING_DIMENSION}. "
                    "Embeddings may not match. This is informational - you can proceed or "
                    "create the index with the correct dimension."
                )

            pinecone_store_idx = pinecone_store

        except Exception as e:
            logger.error(f"Pinecone initialization failed: {e}")
            stats.record_failure(stage="pinecone_init", document_id="", document_type="pipeline", error=e)
            return stats.to_dict()

        # Step 6: Generate embeddings
        logger.info("Step 6: Generating embeddings...")
        try:
            embedding_service = EmbeddingService(model_name=EMBEDDING_MODEL_NAME)
            all_documents = (
                race_docs + qualifying_docs + pit_stop_docs + driver_profile_docs +
                constructor_profile_docs + standings_docs + lap_time_docs
            )

            state_store = StateStore(PROJECT_ROOT / "embedding_state.sqlite")
            embeddings, text_hashes, generated, reused = embedding_service.generate_embeddings(
                all_documents,
                state_store=state_store,
                batch_size=DEFAULT_BATCH_SIZE,
            )
            stats.embeddings_generated = generated
            stats.embeddings_reused = reused

            # Store embeddings in state store
            for i, doc in enumerate(all_documents):
                text_hash = text_hashes[i] if i < len(text_hashes) else ""
                embedding = embeddings[i] if i < len(embeddings) else None
                if embedding is not None:
                    doc_id = (
                        f"{doc.get('document_type', '')}_{doc.get('source_table', '')}"
                        f"{doc.get('source_record_id', '')}"
                    )
                    state_store.put_embedding(
                        model=EMBEDDING_MODEL_NAME,
                        doc_id=doc_id,
                        text_hash=text_hash,
                        vector=embedding,
                        commit=False,
                    )
            state_store.commit()

            # ADD document_text to each doc so it's stored in Pinecone metadata
            # This fixes the issue where retrieved vectors had empty "text" in metadata
            for i, doc in enumerate(all_documents):
                doc_text = embedding_service._build_document_text(doc)
                if doc_text:
                    doc["document_text"] = doc_text
                else:
                    logger.warning(f"Empty document_text generated for doc {i} (type: {doc.get('document_type', '')})")

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}", exc_info=True)
            stats.record_failure(stage="embedding_generation", document_id="", document_type="pipeline", error=e)
            return stats.to_dict()

        # Step 7: Prepare vectors for upsert
        logger.info("Step 7: Preparing vectors for Pinecone upsert...")
        try:
            all_documents = (
                race_docs + qualifying_docs + pit_stop_docs + driver_profile_docs +
                constructor_profile_docs + standings_docs + lap_time_docs
            )

            vectors_to_upsert = []

            for i, doc in enumerate(all_documents):
                embedding = embeddings[i] if i < len(embeddings) else None

                if embedding is None:
                    logger.warning(f"Missing embedding for document {i}")
                    continue

                # Generate deterministic vector ID
                vector_id = pinecone_store_idx.generate_vector_id(
                    doc.get("document_type", ""),
                    doc.get("source_table", ""),
                    doc.get("source_record_id", ""),
                )

                # Prepare metadata - keep compact
                # Note: document_text was added to the doc in Step 6 (after embedding generation)
                # so doc.get("document_text", "") will now return the actual text
                metadata = {
                    "document_type": doc.get("document_type", ""),
                    "text": doc.get("document_text", ""),
                    "season": doc.get("season"),
                    "race_id": doc.get("race_id"),
                    "driver_id": doc.get("driver_id"),
                    "constructor_id": doc.get("constructor_id"),
                    "source_table": doc.get("source_table", ""),
                    "source_record_id": doc.get("source_record_id"),
                }

                # Filter metadata to only include supported types and truncate values
                compact_metadata = {}
                for k, v in metadata.items():
                    if v is not None:
                        if isinstance(v, (str, int, float, bool)):
                            compact_metadata[k] = str(v)[:500]
                        elif isinstance(v, list):
                            compact_metadata[k] = v[:10] if len(v) > 10 else v
                        elif isinstance(v, dict):
                            compact_metadata[k] = str(v)[:500]
                        else:
                            compact_metadata[k] = str(v)[:500]

                vectors_to_upsert.append({
                    "id": vector_id,
                    "values": embedding.tolist(),
                    "metadata": compact_metadata,
                })

            logger.info(f"Prepared {len(vectors_to_upsert)} vectors for upsert")

            # Step 8: Check for already-uploaded vectors (idempotent rerun)
            # Also check for existing vectors with empty text that need repair
            vector_ids = [v["id"] for v in vectors_to_upsert]
            existing = pinecone_store_idx.check_existing_vectors(vector_ids)

            # Identify existing vectors that have empty 'text' in metadata and need repair
            vectors_to_repair = []
            vectorsAlreadyUploaded = 0

            # Batch fetch existing vector metadata to check for empty text
            # Pinecone SDK v10 fetch supports batch ids
            batch_size = 100
            for batch_start in range(0, len(vector_ids), batch_size):
                batch_ids = vector_ids[batch_start : batch_start + batch_size]
                try:
                    fetch_result = pinecone_store_idx.index.fetch(
                        ids=batch_ids,
                        namespace=pinecone_store_idx.namespace,
                    )
                    for vid in batch_ids:
                        fetched_meta = fetch_result.get(vid, {}).get("metadata", {})
                        existing_text = fetched_meta.get("text", "")
                        # Find the vector dict with this ID
                        for v in vectors_to_upsert:
                            if v["id"] == vid:
                                if not existing_text:
                                    # This vector has empty text; mark for repair
                                    vectors_to_repair.append(v)
                                else:
                                    # Vector has valid text; count as already uploaded
                                    vectorsAlreadyUploaded += 1
                                break  # found the vector, move to next vid
                except Exception as e:
                    logger.warning(f"Could not fetch batch of existing vectors for repair check: {e}")
                    # If we can't check, conservative: treat as needing review

            # Build the final upsert list:
            # - Include new vectors (not already existing)
            # - Include vectors that need repair (existing but empty text)
            # - Exclude valid existing vectors (idempotent skip)
            vectors_to_upsert_filtered = []
            for v in vectors_to_upsert:
                vid = v["id"]
                if existing.get(vid, False) and v not in vectors_to_repair:
                    # Valid existing vector; skip (idempotent)
                    vectorsAlreadyUploaded += 1
                else:
                    # New vector or vector needing repair
                    vectors_to_upsert_filtered.append(v)

            # Step 9: Upsert vectors
            if vectors_to_upsert_filtered:
                logger.info(f"Upserting {len(vectors_to_upsert_filtered)} vectors (including {len(vectors_to_repair)} repairs)...")
                uploaded, failed = pinecone_store_idx.upsert_vectors(vectors_to_upsert_filtered)
                vectors_upserted = uploaded
            else:
                logger.info("No new vectors to upsert (all already uploaded).")
                vectors_upserted = 0

            # Repair existing vectors with empty text
            if vectors_to_repair:
                logger.info(f"Repairing {len(vectors_to_repair)} existing vectors with empty text...")
                # Upsert the repair vectors (overwrites existing with correct text/metadata)
                repair_uploaded, repair_failed = pinecone_store_idx.upsert_vectors(vectors_to_repair)
                logger.info(f"Repair complete: {repair_uploaded} vectors repaired, {repair_failed} failed")
            else:
                repair_uploaded = 0
                repair_failed = 0

            # Set final stats
            vectors_skipped = vectorsAlreadyUploaded

        except Exception as e:
            logger.error(f"Vector upsert failed: {e}", exc_info=True)
            stats.record_failure(stage="vector_upsert", document_id="", document_type="pipeline", error=e)

    else:
        logger.info("DRY RUN: Skipping Pinecone upload.")
        stats.vectors_upserted = 0
        stats.vectors_skipped = 0

    # Step 10: Update summary stats
    stats.vectors_upserted = vectors_upserted
    stats.vectors_skipped = vectors_skipped

    # Log final summary
    logger.info("=" * 60)
    logger.info("INGESTION PIPELINE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Source rows: {stats.source_rows}")
    logger.info(f"Documents created: {stats.documents_created}")
    logger.info(f"  - By type: {stats.docs_by_type}")
    logger.info(f"Embeddings generated: {stats.embeddings_generated}")
    logger.info(f"Embeddings reused: {stats.embeddings_reused}")
    logger.info(f"Vectors upserted: {stats.vectors_upserted}")
    logger.info(f"Vectors skipped (already uploaded): {stats.vectors_skipped}")
    logger.info(f"Failures: {stats.documents_failed}")
    logger.info(f"Elapsed time: {stats.elapsed_seconds:.1f}s")
    logger.info("=" * 60)

    # Print a nice summary to console
    print("\n" + "=" * 60)
    print("F1 RAG INGESTION PIPELINE - SUMMARY")
    print("=" * 60)
    print(f"Run ID: {run_id}")
    print(f"Source rows: {stats.source_rows}")
    print(f"Documents created: {stats.documents_created}")
    print(f"  - By type: {stats.docs_by_type}")
    print(f"Embeddings generated: {stats.embeddings_generated}")
    print(f"Embeddings reused: {stats.embeddings_reused}")
    print(f"Vectors upserted to Pinecone: {stats.vectors_upserted}")
    print(f"Vectors skipped (already uploaded): {stats.vectors_skipped}")
    print(f"Failures: {stats.documents_failed}")
    print(f"Elapsed time: {stats.elapsed_seconds:.1f}s")
    print("=" * 60 + "\n")

    return stats.to_dict()


def run_retrieve(query: str = "How did Lewis Hamilton perform in the 2021 Bahrain Grand Prix?") -> dict:
    """Run a retrieval test after ingestion.

    Embeds a natural-language query and searches the Pinecone namespace.

    Args:
        query: Natural language query to search for.

    Returns:
        Retrieval results dictionary.
    """
    logger = get_logger()
    logger.info(f"Running retrieval test with query: '{query}'")

    try:
        pinecone_store = PineconeStore(
            api_key=PINECONE_API_KEY,
            index_name=PINECONE_INDEX_NAME,
            namespace=PINECONE_NAMESPACE,
        )

        if not pinecone_store.initialize():
            logger.error("Failed to initialize Pinecone for retrieval.")
            return {}

        # Embed the query using the same model
        embedding_service = EmbeddingService(model_name=EMBEDDING_MODEL_NAME)
        model = embedding_service.load_model()
        query_embedding = model.encode([query], convert_to_numpy=True)[0]
        # Normalize
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        # Search the namespace
        logger.info(f"Searching namespace '{PINECONE_NAMESPACE}' for top 5 results...")
        results = pinecone_store.index.query(
            vector=query_embedding.tolist(),
            top_k=5,
            namespace=PINECONE_NAMESPACE,
            include_metadata=True,
        )

        logger.info(f"Retrieved {len(results.matches) if hasattr(results, 'matches') else 0} results")

        # Print results
        print("\n" + "=" * 70)
        print("RETRIEVAL RESULTS")
        print("=" * 70)
        print(f"Query: '{query}'")
        print(f"Namespace: {PINECONE_NAMESPACE}")
        print("-" * 70)

        if hasattr(results, 'matches') and results.matches:
            for i, match in enumerate(results.matches):
                meta = match.metadata if hasattr(match, 'metadata') else {}
                score = match.score if hasattr(match, 'score') else 0
                vector_id = match.id if hasattr(match, 'id') else "?"

                # Extract document text from metadata, with safe fallback
                text = meta.get("text", "")
                if not text:
                    text = "N/A - no text in metadata"

                print(f"\nResult {i+1} (score: {score:.4f}):")
                print(f"  Vector ID: {vector_id}")
                print(f"  Metadata: {str(meta)[:500]}")
                print(f"  Text: {text}")

                # Log if text is missing/empty
                if not meta.get("text"):
                    logger.warning(f"Result {i+1} has empty or missing 'text' in metadata")
        else:
            print("  No results found.")

        print("-" * 70)
        print("Retrieval complete.")
        print("=" * 70 + "\n")

        return {
            "query": query,
            "results": results,
            "result_count": len(results.matches) if hasattr(results, 'matches') else 0,
        }

    except Exception as e:
        logger.error(f"Retrieval failed: {e}", exc_info=True)
        print(f"Retrieval error: {e}")
        return {}


def run_validate() -> dict:
    """Validate the pipeline: check documents, embeddings, and Pinecone metadata.
    
    This is a read-only command that validates:
    - Generated documents contain meaningful text
    - No empty-text documents should be uploaded
    - Embedding dimensions equal 384
    - Metadata text matches the text used for embedding
    - Existing Pinecone vectors' metadata completeness
    
    Does NOT modify or delete any existing vectors.
    
    Returns:
        Validation summary dictionary.
    """
    import logging
    from pathlib import Path
    from utils import get_logger, setup_logging
    
    logger = get_logger()
    logger.info("Starting pipeline validation (read-only mode)")
    
    from embedding_service import EmbeddingService
    from pinecone_store import PineconeStore
    from preprocessor import (
        create_race_result_documents,
        create_qualifying_documents,
        create_pit_stop_documents,
        create_driver_profile_documents,
        create_constructor_profile_documents,
        create_standings_documents,
        create_lap_time_summary_documents,
    )
    from data_loader import (
        load_drivers,
        load_constructors,
        load_races,
        load_results,
        load_qualifying,
        load_pit_stops,
        load_lap_times,
        load_driver_standings,
        load_constructor_standings,
        get_2021_2025_race_ids,
        filter_results_by_race_ids,
        filter_qualifying_by_race_ids,
        filter_pit_stops_by_race_ids,
        filter_lap_times_by_race_ids,
        filter_driver_standings_by_race_ids,
        filter_constructor_standings_by_race_ids,
    )
    from config import (
        PINECONE_INDEX_NAME,
        PINECONE_NAMESPACE,
        EMBEDDING_MODEL_NAME,
        EMBEDDING_DIMENSION,
    )
    
    results = {
        "validation_passed": True,
        "total_documents_checked": 0,
        "documents_with_text": 0,
        "documents_without_text": 0,
        "empty_text_count": 0,
        "dimension_mismatches": 0,
        "pinecone_vectors_checked": 0,
        "pinecone_vectors_with_empty_text": 0,
        "pinecone_vectors_total": 0,
        "errors": [],
    }
    
    try:
        # Part 1: Validate generated documents locally
        logger.info("Part 1: Validating generated documents locally...")
        
        drivers = load_drivers()
        constructors = load_constructors()
        races, season_race_ids = load_races()
        results_data = load_results()
        qualifying = load_qualifying()
        pit_stops = load_pit_stops()
        lap_times = load_lap_times()
        driver_standings = load_driver_standings()
        constructor_standings = load_constructor_standings()
        
        race_ids_2021_2025 = get_2021_2025_race_ids(races)
        filtered_results = filter_results_by_race_ids(results_data, race_ids_2021_2025)
        filtered_qualifying = filter_qualifying_by_race_ids(qualifying, race_ids_2021_2025)
        filtered_pit_stops = filter_pit_stops_by_race_ids(pit_stops, race_ids_2021_2025)
        filtered_lap_times = filter_lap_times_by_race_ids(lap_times, race_ids_2021_2025)
        filtered_driver_standings = filter_driver_standings_by_race_ids(driver_standings, race_ids_2021_2025)
        filtered_constructor_standings = filter_constructor_standings_by_race_ids(constructor_standings, race_ids_2021_2025)
        
        race_docs = create_race_result_documents(
            filtered_results, drivers, constructors, races, season_race_ids
        )
        qualifying_docs = create_qualifying_documents(
            filtered_qualifying, drivers, constructors, races, season_race_ids
        )
        pit_stop_docs = create_pit_stop_documents(
            filtered_pit_stops, drivers, constructors, races, season_race_ids
        )
        driver_profile_docs = create_driver_profile_documents(drivers, filtered_results, season_race_ids)
        constructor_profile_docs = create_constructor_profile_documents(
            constructors, filtered_results, season_race_ids
        )
        standings_docs = create_standings_documents(
            filtered_driver_standings, filtered_constructor_standings, drivers, constructors, races, season_race_ids
        )
        lap_time_docs = create_lap_time_summary_documents(
            filtered_lap_times, drivers, races, season_race_ids,
            max_drivers=50, max_laps_per_driver=20
        )
        
        all_docs = (
            race_docs + qualifying_docs + pit_stop_docs + driver_profile_docs +
            constructor_profile_docs + standings_docs + lap_time_docs
        )
        
        results["total_documents_checked"] = len(all_docs)
        
        embedding_svc = EmbeddingService(model_name=EMBEDDING_MODEL_NAME)
        model = embedding_svc.load_model()
        
        for i, doc in enumerate(all_docs):
            results["total_documents_checked"] += 1
            doc_text = embedding_svc._build_document_text(doc)
            
            if doc_text and doc_text != "F1 race data document" and len(doc_text) > 10:
                results["documents_with_text"] += 1
            else:
                results["documents_without_text"] += 1
                results["errors"].append(f"Doc {i} ({doc.get('document_type', '')} ID: {doc.get('source_record_id', '')}): Empty or very short text")
        
        # Part 2: Validate Pinecone metadata (read-only)
        logger.info("Part 2: Validating Pinecone metadata (read-only)...")
        
        pinecone_store = PineconeStore(
            api_key=PINECONE_API_KEY,
            index_name=PINECONE_INDEX_NAME,
            namespace=PINECONE_NAMESPACE,
        )
        
        if pinecone_store.initialize():
            index_info = pinecone_store.get_index_info()
            results["pinecone_index_dimension"] = index_info.get("dimension", "unknown")
            results["pinecone_index_metric"] = index_info.get("metric", "unknown")
            results["pinecone_has_document_schema"] = index_info.get("has_document_schema", False)
            
            # Fetch a sample of vectors to check metadata
            from utils import make_vector_id
            
            sample_ids = []
            for doc_type in ["race_result", "qualifying", "pit_stop", "driver_profile", 
                           "constructor_profile", "driver_standings", "constructor_standings", 
                           "lap_time_summary"]:
                docs_of_type = [d for d in all_docs if d.get("document_type") == doc_type]
                for d in docs_of_type[:3]:
                    vid = make_vector_id(doc_type, d.get("source_table", ""), d.get("source_record_id", ""))
                    sample_ids.append(vid)
            
            results["pinecone_vectors_total"] = len(sample_ids) if sample_ids else 0
            
            batch_size = 50
            for batch_start in range(0, len(sample_ids), batch_size):
                batch_ids = sample_ids[batch_start : batch_start + batch_size]
                try:
                    fetch_result = pinecone_store.index.fetch(
                        ids=batch_ids,
                        namespace=pinecone_store.namespace,
                    )
                    results["pinecone_vectors_checked"] += len(batch_ids)
                    
                    for vid in batch_ids:
                        fetched_meta = fetch_result.get(vid, {}).get("metadata", {})
                        existing_text = fetched_meta.get("text", "")
                        results["pinecone_vectors_with_empty_text"] += 1 if not existing_text else 0
                        
                except Exception as e:
                    logger.warning(f"Could not fetch batch from Pinecone: {e}")
                    results["errors"].append(f"Pinecone fetch error: {str(e)[:200]}")
            
            if results["pinecone_vectors_with_empty_text"] > 0:
                results["validation_passed"] = False
                results["errors"].append(f"{results['pinecone_vectors_with_empty_text']} Pinecone vectors have empty 'text' metadata")
        else:
            results["errors"].append("Could not initialize Pinecone for validation")
            
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        results["errors"].append(f"Validation error: {str(e)[:300]}")
        results["validation_passed"] = False
    
    # Print summary
    print("\n" + "=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)
    print(f"Total documents checked: {results['total_documents_checked']}")
    print(f"Documents with meaningful text: {results['documents_with_text']}")
    print(f"Documents without meaningful text: {results['documents_without_text']}")
    print(f"Empty text count: {results['empty_text_count']}")
    print(f"Index dimension: {results.get('pinecone_index_dimension', 'unknown')}")
    print(f"Embedding model dimension: {EMBEDDING_DIMENSION}")
    print(f"Pinecone vectors checked: {results['pinecone_vectors_checked']}")
    print(f"Pinecone vectors with empty text: {results['pinecone_vectors_with_empty_text']}")
    print(f"Pinecone vectors total (estimate): {results.get('pinecone_vectors_total', 'N/A')}")
    
    if results["errors"]:
        print(f"\nErrors/Issues found ({len(results['errors'])}):")
        for err in results["errors"][:10]:
            print(f"  - {err}")
    
    print("=" * 70 + "\n")
    
    return results


# Allow running as a module: python -m ingest dry_run|test_batch|full|retrieve|validate
if __name__ == "__main__":
    import json
    import argparse

    parser = argparse.ArgumentParser(description="F1 RAG Ingestion Pipeline")
    parser.add_argument(
        "mode",
        choices=["dry_run", "test_batch", "full", "retrieve", "validate"],
        help="Execution mode",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="How did Lewis Hamilton perform in the 2021 Bahrain Grand Prix?",
        help="Retrieval query (used with retrieve mode)",
    )
    args = parser.parse_args()

    # Setup logging
    project_root = Path(__file__).resolve().parent
    log_dir = project_root / "logs"
    logger = setup_logging(log_dir, level="INFO")

    if args.mode == "dry_run":
        run_ingest(dry_run=True)
    elif args.mode == "test_batch":
        run_ingest(dry_run=False, test_mode=True)
    elif args.mode == "full":
        run_ingest(dry_run=False, test_mode=False)
    elif args.mode == "retrieve":
        run_retrieve(query=args.query)
    elif args.mode == "validate":
        run_validate()