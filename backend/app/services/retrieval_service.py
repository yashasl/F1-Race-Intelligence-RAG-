"""Retrieval service backed by the existing Pinecone + SentenceTransformer pipeline.

Read-only: importing this module never re-ingests data. The heavy embedding model
is loaded lazily on the first chat request.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Make the pipeline modules at the project root importable when uvicorn is
# started from backend/.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ..core.config import (  # noqa: E402
    EMBEDDING_MODEL_NAME,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_NAMESPACE,
)

logger = logging.getLogger("f1rag.retrieval")

_embedding_service = None


def _get_embedding_service():
    """Load the SentenceTransformer model once per process."""
    global _embedding_service

    if _embedding_service is None:
        from embedding_service import EmbeddingService

        service = EmbeddingService(model_name=EMBEDDING_MODEL_NAME)
        service.load_model()
        _embedding_service = service
    return _embedding_service


def generate_query_embedding(query: str) -> np.ndarray:
    """Generate a normalized 384-dimensional embedding for the query."""
    service = _get_embedding_service()
    model = service.load_model()
    embedding = model.encode([query], convert_to_numpy=True)[0]

    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm

    return embedding


def query_pinecone(
    embedding: np.ndarray,
    index_name: str = PINECONE_INDEX_NAME,
    namespace: str = PINECONE_NAMESPACE,
    top_k: int = 5,
    filter_metadata: Optional[Dict] = None,
) -> List[Dict[str, Any]]:
    """Query the Pinecone index and return normalized match dicts."""
    if not PINECONE_API_KEY:
        raise RuntimeError("PINECONE_API_KEY is not configured")

    from pinecone_store import PineconeStore

    store = PineconeStore(
        api_key=PINECONE_API_KEY,
        index_name=index_name,
        namespace=namespace,
    )
    if not store.initialize() or store.index is None:
        raise RuntimeError(f"Could not connect to Pinecone index '{index_name}'")

    query_kwargs: Dict[str, Any] = {
        "vector": embedding.tolist(),
        "top_k": top_k,
        "namespace": namespace,
        "include_metadata": True,
    }
    if filter_metadata:
        query_kwargs["filter"] = filter_metadata

    response = store.index.query(**query_kwargs)

    matches = []
    for match in getattr(response, "matches", []) or []:
        metadata = dict(getattr(match, "metadata", {}) or {})
        text = metadata.get("text", "") or ""
        matches.append(
            {
                "id": getattr(match, "id", ""),
                "score": float(getattr(match, "score", 0.0) or 0.0),
                "metadata": metadata,
                "text": text,
                "is_empty_text": not text.strip(),
            }
        )

    logger.info("Retrieved %d Pinecone matches (top_k=%d)", len(matches), top_k)
    return matches


def filter_empty_text_matches(
    matches: List[Dict],
) -> Tuple[List[Dict], int]:
    """Drop matches whose metadata has no usable text."""
    filtered = []
    empty_count = 0
    for match in matches:
        text = (match.get("metadata", {}) or {}).get("text", "") or ""
        if text.strip():
            match["text"] = text
            filtered.append(match)
        else:
            empty_count += 1
            logger.warning(
                "Filtering out match %s with empty text metadata",
                match.get("id", "?"),
            )
    return filtered, empty_count


def retrieve_f1_context(
    query: str,
    top_k: int = 5,
    filter_season: Optional[int] = None,
    filter_driver: Optional[str] = None,
    filter_constructor: Optional[str] = None,
    filter_race: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the retrieval pipeline and build prompt-ready context."""
    embedding = generate_query_embedding(query)

    pinecone_filter: Dict[str, Any] = {}
    if filter_season is not None:
        pinecone_filter["season"] = str(filter_season)
    if filter_driver is not None:
        pinecone_filter["driver_id"] = str(filter_driver)
    if filter_constructor is not None:
        pinecone_filter["constructor_id"] = str(filter_constructor)
    if filter_race is not None:
        pinecone_filter["race_id"] = str(filter_race)

    matches = query_pinecone(
        embedding=embedding,
        index_name=PINECONE_INDEX_NAME,
        namespace=PINECONE_NAMESPACE,
        top_k=top_k,
        filter_metadata=pinecone_filter or None,
    )

    filtered_matches, empty_count = filter_empty_text_matches(matches)

    context_parts = []
    metadata_summary = []
    for match in filtered_matches:
        text = match.get("text", "")
        metadata = match.get("metadata", {}) or {}
        if not text:
            continue

        race_name = metadata.get("race_name", metadata.get("race", "N/A"))
        context_parts.append(
            f"[{metadata.get('document_type', '')} - {race_name} "
            f"{metadata.get('season', '')}] {text}"
        )
        metadata_summary.append(
            {
                "vector_id": match.get("id", ""),
                "score": match.get("score", 0),
                "document_type": metadata.get("document_type", ""),
                "season": metadata.get("season", ""),
                "race": race_name,
                "driver": metadata.get(
                    "driver_forename", metadata.get("driver", "")
                ),
                "constructor": metadata.get(
                    "constructor_name", metadata.get("constructor", "")
                ),
                "text": text[:200] + ("..." if len(text) > 200 else ""),
            }
        )

    return {
        "matches": filtered_matches,
        "context_text": "\n\n".join(context_parts),
        "total_retrieved": len(filtered_matches),
        "filtered_out_empty_text": empty_count,
        "metadata_summary": metadata_summary,
        "query": query,
    }
