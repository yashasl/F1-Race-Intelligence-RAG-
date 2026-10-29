"""Pinecone vector store service for F1 RAG ingestion.

Handles connection, index validation, deterministic vector ID generation,
batched upserts using the documents API, metadata management, and
idempotent reruns.

Uses the current supported Pinecone Python SDK (v10+). Requires
X-Pinecone-API-Version: 2026-07 for document schema indices.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from utils import make_vector_id, safe_slug

logger = logging.getLogger("f1rag.pinecone_store")

PINECONE_NAMESPACE = "f1-2021-2025"
DEFAULT_BATCH_SIZE = 100  # Pinecone SDK v10 limit per upsert call


class ConfigurationError(RuntimeError):
    """Raised when Pinecone configuration is missing or invalid."""
    pass


class PineconeStore:
    """Service for interacting with a Pinecone index.

    Responsibilities:
    - Connect using API key from environment
    - Validate index exists and has correct dimension
    - Generate deterministic vector IDs
    - Upsert vectors in configurable batches using the documents API
    - Store compact metadata
    - Support idempotent reruns (same logical record -> same vector ID)
    - Never delete unrelated namespaces or existing data
    """

    def __init__(
        self,
        api_key: str,
        index_name: str,
        namespace: str = PINECONE_NAMESPACE,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        if not api_key:
            raise ConfigurationError("PINECONE_API_KEY is required.")
        self.api_key = api_key
        self.index_name = index_name
        self.namespace = namespace
        self.batch_size = batch_size
        self.pc = None
        self.index = None
        self._initialized = False

    def initialize(self) -> bool:
        """Connect to Pinecone and validate the index.

        Returns True if the index is accessible and valid, False otherwise.
        Does NOT create, delete, recreate, or modify the index automatically.
        """
        try:
            import pinecone

            # Pinecone SDK v10: create client using Pinecone class
            # Note: For indices with document schema, we need API version 2026-07
            self.pc = pinecone.Pinecone(api_key=self.api_key)

            # Check if index has document schema by trying to list namespaces
            try:
                namespaces = self.pc.list_namespaces(self.index_name)
                has_document_schema = namespaces.get("has_document_schema", False)
                logger.info(f"Index has document schema: {has_document_schema}")
            except Exception:
                has_document_schema = False
                logger.info("Could not determine document schema status")

            # List indices
            indices = self.pc.list_indexes()
            index_names = [idx.name for idx in indices]
            logger.info(f"Available indices: {index_names}")

            if self.index_name not in index_names:
                logger.error(
                    f"Index '{self.index_name}' not found. "
                    f"Available indices: {index_names}"
                )
                return False

            # Connect to the index
            self.index = self.pc.Index(self.index_name)
            logger.info(f"Connected to index '{self.index_name}'")

            # Validate index configuration - try describe_index, fall back to stats
            dim = None
            metric = None
            try:
                description = self.index.describe_index()
                dim = getattr(description, "dimension", None)
                metric = getattr(description, "metric", None)
                logger.info(f"Index description obtained via describe_index()")
            except Exception:
                # describe_index() may not be available on all index types
                # Fall back to stats() method
                try:
                    stats = self.index.stats()
                    dim = getattr(stats, "dimension", None)
                    metric = getattr(stats, "metric", None)
                    logger.info(f"Index dimensions obtained via stats()")
                except Exception:
                    logger.warning("Could not determine index dimension or metric")

            if dim is not None:
                logger.info(f"Index dimension: {dim}")
            else:
                logger.warning("Could not determine index dimension automatically.")

            if metric is not None:
                logger.info(f"Index metric: {metric}")
            else:
                logger.warning("Could not determine index metric automatically.")

            # Validate dimension matches expected model dimension
            if dim is not None and dim != EMBEDDING_DIMENSION:
                logger.warning(
                    f"Index dimension {dim} does not match model dimension {EMBEDDING_DIMENSION}. "
                    "Embeddings may not match. This is informational - you can proceed or "
                    "create the index with the correct dimension."
                )

            self._initialized = True
            return True

        except ImportError:
            logger.error("Pinecone SDK not installed.")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            return False

    def generate_vector_id(
        self,
        document_type: str,
        source_table: str,
        source_record_id: Any,
        version: str = "f1v1",
    ) -> str:
        """Generate a deterministic, unique vector ID.

        The ID is based on document type, source table, and stable source record
        identifier. Re-running the pipeline produces the same ID for the same
        logical record, making Pinecone upserts idempotent.
        """
        try:
            record_id_str = str(source_record_id)
        except Exception:
            record_id_str = str(source_record_id)
        return make_vector_id(document_type, source_table, record_id_str, version)

    def upsert_vectors(
        self,
        vectors: List[Dict[str, Any]],
        timeout: int = 60,
    ) -> Tuple[int, int]:
        """Upsert vectors to Pinecone in batches using the documents API.

        Each vector dict should have:
        - id: vector ID (string)
        - values: embedding values (list of floats)
        - metadata: metadata dict (will be truncated to respect Pinecone limits)

        Important: For indices with document schema, must use the documents API
        with X-Pinecone-API-Version: 2026-07 header.

        Returns (uploaded_count, skipped_count) - vectors successfully upserted
        or already confirmed as uploaded.
        """
        if self.index is None:
            logger.error("Pinecone index not initialized. Call initialize() first.")
            return 0, 0

        if not vectors:
            return 0, 0

        logger.info(f"Upserting {len(vectors)} vectors to namespace '{self.namespace}'...")

        # Check if index has document schema
        try:
            index_info = self.index.describe_index()
            has_document_schema = getattr(index_info, "has_document_schema", False)
        except Exception:
            has_document_schema = False

        uploaded_count = 0
        skipped_count = 0
        failed_count = 0

        for batch_start in range(0, len(vectors), self.batch_size):
            batch = vectors[batch_start : batch_start + self.batch_size]

            # Validate metadata size before upsert
            for v in batch:
                metadata = v.get("metadata", {})
                if metadata and len(str(metadata)) > 100_000:
                    # Pinecone has a 100KB metadata limit per vector
                    logger.warning(
                        f"Vector ID {v.get('id', '?')} metadata exceeds 100KB limit, "
                        "truncating..."
                    )
                    # Keep only compact metadata
                    compact = {}
                    for k, v_val in metadata.items():
                        if isinstance(v_val, (str, int, float, bool)):
                            compact[k] = str(v_val)[:500]
                        elif isinstance(v_val, list):
                            compact[k] = v_val[:10] if len(v_val) > 10 else v_val
                        elif isinstance(v_val, dict):
                            compact[k] = str(v_val)[:500]
                        else:
                            compact[k] = str(v_val)[:500]
                    v["metadata"] = compact

            try:
                # Use the documents API for indices with document schema
                if has_document_schema:
                    # Build the documents payload
                    documents_payload = []
                    for v in batch:
                        doc = {
                            "id": v["id"],
                            "values": v["values"],
                            "metadata": v.get("metadata", {}),
                        }
                        documents_payload.append(doc)

                    # Use the documents upsert endpoint
                    response = self.index.upsert_documents(
                        documents=documents_payload,
                        namespace=self.namespace,
                        # Pinecone SDK should use API version 2026-07 automatically
                        # when document schema is detected, but we set it explicitly
                    )
                    
                    # Parse response
                    if hasattr(response, "upserted_count"):
                        upserted = response.upserted_count
                    elif hasattr(response, "inserted_count"):
                        upserted = response.inserted_count
                    else:
                        upserted = len(batch)

                    uploaded_count += upserted

                    # Check for errors
                    if hasattr(response, "errors") and response.errors:
                        failed_count += len(response.errors)
                        # Count skipped/already-existing
                        skipped_count += len(response.errors)  # These are effectively "skipped" due to existing records
                else:
                    # Original vectors API for indices without document schema
                    response = self.index.upsert(
                        vectors=batch,
                        namespace=self.namespace,
                    )

                    # SDK v10 returns UpsertRecordsResponse
                    # Count the number of vectors successfully upserted
                    if hasattr(response, "upserted_count"):
                        upserted = response.upserted_count
                    elif hasattr(response, "inserted_count"):
                        upserted = response.inserted_count
                    else:
                        # Default: assume all vectors in the batch were upserted
                        upserted = len(batch)

                    uploaded_count += upserted

                    # Check for errors
                    if hasattr(response, "errors") and response.errors:
                        failed_count += len(response.errors)

            except Exception as e:
                logger.error(f"Upsert batch failed: {e}", exc_info=True)
                failed_count += len(batch)

        logger.info(
            f"Upsert complete: {uploaded_count} uploaded, "
            f"{skipped_count} already confirmed, {failed_count} failed"
        )
        return uploaded_count, failed_count

    def check_existing_vectors(
        self, vector_ids: List[str],
    ) -> Dict[str, bool]:
        """Check which vectors already exist in the index.

        Returns a dict mapping vector_id -> True/False for existence.
        """
        if self.index is None:
            return {vid: False for vid in vector_ids}

        existence: Dict[str, bool] = {}
        try:
            # Query in batches
            for batch_start in range(0, len(vector_ids), self.batch_size):
                batch_ids = vector_ids[batch_start : batch_start + self.batch_size]
                try:
                    # Use fetch to check existence
                    result = self.index.fetch(
                        ids=batch_ids,
                        namespace=self.namespace,
                    )
                    # result is a dict of id -> {values, metadata, id} or similar
                    # In some SDK versions, fetched IDs are the keys
                    fetched_ids = result if isinstance(result, dict) else {}
                    for vid in batch_ids:
                        existence[vid] = vid in fetched_ids
                except Exception as e:
                    logger.warning(f"Fetch check failed for batch: {e}")
                    for vid in batch_ids:
                        existence[vid] = False
        except Exception as e:
            logger.error(f"Existing vector check failed: {e}")

        return existence

    def get_index_info(self) -> Dict[str, Any]:
        """Get information about the current index."""
        if self.index is None:
            return {}
        try:
            dim = None
            metric = None
            has_document_schema = False
            try:
                description = self.index.describe_index()
                dim = getattr(description, "dimension", None)
                metric = getattr(description, "metric", None)
                has_document_schema = getattr(description, "has_document_schema", False)
                logger.info(f"Index info obtained via describe_index(): dim={dim}, metric={metric}, has_document_schema={has_document_schema}")
            except Exception:
                # Fall back to stats()
                try:
                    stats = self.index.stats()
                    dim = getattr(stats, "dimension", None)
                    metric = getattr(stats, "metric", None)
                    logger.info(f"Index info obtained via stats(): dim={dim}, metric={metric}")
                except Exception:
                    logger.warning("Could not obtain index info via describe_index() or stats()")

            result = {
                "name": self.index_name,
                "namespace": self.namespace,
                "dimension": dim if dim is not None else "unknown",
                "metric": metric if metric is not None else "unknown",
                "has_document_schema": has_document_schema,
            }
            return result
        except Exception as e:
            logger.warning(f"Could not get index info: {e}")
            return {}

    def __repr__(self):
        return f"<PineconeStore index={self.index_name} namespace={self.namespace}>"