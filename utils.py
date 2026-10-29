"""Shared utilities: logging, retries, deterministic IDs, and resumable state.

This module deliberately contains no credential values and never logs secrets.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import random
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence, TypeVar

import numpy as np

T = TypeVar("T")

LOGGER_NAME = "f1rag"


class PipelineError(RuntimeError):
    """Base class for expected pipeline failures."""


class ConfigurationError(PipelineError):
    """Raised when required configuration is missing or invalid."""


def configure_console() -> None:
    """Make Windows consoles render the UTF-8 names present in the CSVs."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def setup_logging(log_dir: Path, level: str = "INFO") -> logging.Logger:
    """Configure one idempotent console + rotating-file logger."""
    configure_console()
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = RotatingFileHandler(
        log_dir / "ingest.log",
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_slug(value: str, max_length: int = 120) -> str:
    """Return a deterministic, Pinecone-safe slug.

    Pinecone accepts arbitrary strings, but restricting IDs to an alphanumeric
    subset keeps them easy to inspect and avoids quoting surprises.
    """
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_")
    if not slug:
        slug = "unknown"
    if len(slug) > max_length:
        digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:10]
        slug = f"{slug[: max_length - 11]}_{digest}"
    return slug


def make_vector_id(
    document_type: str,
    source_table: str,
    source_record_id: str,
    version: str = "f1v1",
) -> str:
    """Build a deterministic, unique vector ID.

    Re-running the pipeline produces the same ID for the same logical record,
    which makes Pinecone upserts idempotent.
    """
    return safe_slug(
        f"{version}_{document_type}_{source_table}_{source_record_id}",
        max_length=200,
    )


def iter_batches(items: Iterable[T], size: int) -> Iterator[list[T]]:
    if size <= 0:
        raise ValueError("batch size must be positive")
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _status_code(exc: BaseException) -> int | None:
    for attr in ("status_code", "status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def is_retryable(exc: BaseException) -> bool:
    """Retry network, rate-limit, and 5xx failures; never retry auth/validation."""
    if isinstance(exc, (ValueError, TypeError, KeyError, ConfigurationError)):
        return False
    status = _status_code(exc)
    if status is not None:
        return status in {408, 409, 425, 429, 500, 502, 503, 504}
    name = type(exc).__name__.lower()
    retry_markers = (
        "timeout",
        "connection",
        "ratelimit",
        "rate_limit",
        "serviceunavailable",
        "internalserver",
        "temporarily",
        "throttl",
        "reset",
        "unavailable",
    )
    if any(marker in name for marker in retry_markers):
        return True
    # Pinecone SDK exceptions often carry the real cause in the message.
    message = str(exc).lower()
    return any(marker in message for marker in ("timed out", "connection reset", "too many requests"))


def retry_call(
    func: Callable[[], T],
    *,
    description: str,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    logger: logging.Logger | None = None,
) -> T:
    """Call ``func`` with exponential backoff and jitter."""
    log = logger or get_logger()
    attempts = max(1, max_attempts)
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except BaseException as exc:  # re-raised below
            last_exc = exc
            if attempt >= attempts or not is_retryable(exc):
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay = delay * (0.75 + random.random() * 0.5)
            log.warning(
                "%s failed (attempt %d/%d): %s: %s. Retrying in %.1fs.",
                description,
                attempt,
                attempts,
                type(exc).__name__,
                str(exc)[:500],
                delay,
            )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def fmt_number(value: Any, decimals: int = 2) -> str | None:
    """Format a numeric source value without inventing precision."""
    if value is None or is_missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value).strip() or None
    if not math.isfinite(number):
        return None
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    text = f"{number:.{decimals}f}".rstrip("0").rstrip(".")
    return text or "0"


def format_lap_milliseconds(value: Any) -> str | None:
    """Format milliseconds as m:ss.mmm (or h:mm:ss.mmm for long durations)."""
    if value is None or is_missing(value):
        return None
    try:
        ms = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    if ms < 0:
        return None
    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}.{millis:03d}"
    return f"{minutes}:{seconds:02d}.{millis:03d}"


def is_missing(value: Any) -> bool:
    """Null-like check that works for pandas/numpy scalars without importing pandas."""
    if value is None:
        return True
    try:
        result = value != value  # NaN is not equal to itself
        if isinstance(result, bool) and result:
            return True
    except Exception:
        pass
    text = str(value).strip()
    return text in {"", "\\N", "NA", "N/A", "nan", "None", "<NA>"}


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(temp, path)


class JsonlWriter:
    """Append-only failure/provenance log; safe to keep across runs."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


@dataclass
class FailureRecord:
    stage: str
    document_id: str
    document_type: str
    error_type: str
    error: str
    occurred_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "document_id": self.document_id,
            "document_type": self.document_type,
            "error_type": self.error_type,
            "error": self.error[:2000],
            "occurred_at": self.occurred_at,
        }


class StateStore:
    """SQLite-backed resumability for embeddings and confirmed uploads.

    - Embeddings are reused only when the document text hash matches.
    - A vector is considered uploaded only after Pinecone confirms the upsert.
    - Nothing here deletes vectors or namespaces.
    """

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._conn = sqlite3.connect(str(path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                model TEXT NOT NULL,
                doc_id TEXT NOT NULL,
                text_sha256 TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                vector BLOB NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (model, doc_id)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                index_name TEXT NOT NULL,
                namespace TEXT NOT NULL,
                vector_id TEXT NOT NULL,
                model TEXT NOT NULL,
                text_sha256 TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL,
                PRIMARY KEY (index_name, namespace, vector_id)
            )
            """
        )
        self._conn.commit()

    def get_embedding(
        self, model: str, doc_id: str, text_hash: str, expected_dimension: int
    ) -> np.ndarray | None:
        row = self._conn.execute(
            "SELECT text_sha256, dimension, vector FROM embeddings WHERE model=? AND doc_id=?",
            (model, doc_id),
        ).fetchone()
        if row is None:
            return None
        stored_hash, dimension, blob = row
        if stored_hash != text_hash or int(dimension) != expected_dimension:
            return None
        vector = np.frombuffer(blob, dtype=np.float32).copy()
        if vector.shape != (expected_dimension,):
            return None
        return vector

    def put_embedding(
        self,
        model: str,
        doc_id: str,
        text_hash: str,
        vector: np.ndarray,
        *,
        commit: bool = False,
    ) -> None:
        vector = np.asarray(vector, dtype=np.float32)
        self._conn.execute(
            """
            INSERT INTO embeddings(model, doc_id, text_sha256, dimension, vector, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(model, doc_id) DO UPDATE SET
                text_sha256=excluded.text_sha256,
                dimension=excluded.dimension,
                vector=excluded.vector,
                updated_at=excluded.updated_at
            """,
            (model, doc_id, text_hash, int(vector.shape[0]), vector.tobytes(), utc_now_iso()),
        )
        if commit:
            self._conn.commit()

    def is_uploaded(
        self,
        index_name: str,
        namespace: str,
        model: str,
        vector_id: str,
        text_hash: str,
    ) -> bool:
        row = self._conn.execute(
            """
            SELECT text_sha256, model FROM uploads
            WHERE index_name=? AND namespace=? AND vector_id=?
            """,
            (index_name, namespace, vector_id),
        ).fetchone()
        if row is None:
            return False
        stored_hash, stored_model = row
        return stored_hash == text_hash and stored_model == model

    def mark_uploaded(
        self,
        index_name: str,
        namespace: str,
        model: str,
        vector_id: str,
        text_hash: str,
        dimension: int,
        *,
        commit: bool = False,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO uploads(index_name, namespace, vector_id, model, text_sha256, dimension, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(index_name, namespace, vector_id) DO UPDATE SET
                model=excluded.model,
                text_sha256=excluded.text_sha256,
                dimension=excluded.dimension,
                uploaded_at=excluded.uploaded_at
            """,
            (index_name, namespace, vector_id, model, text_hash, int(dimension), utc_now_iso()),
        )
        if commit:
            self._conn.commit()

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.commit()
        self._conn.close()

    def stats(self) -> dict[str, int]:
        embeddings = self._conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        uploads = self._conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0]
        return {"cached_embeddings": int(embeddings), "confirmed_uploads": int(uploads)}


@dataclass
class ProcessingStats:
    run_id: str
    started_at: str = field(default_factory=utc_now_iso)
    started_monotonic: float = field(default_factory=time.monotonic)
    source_rows: dict[str, int] = field(default_factory=dict)
    source_table_totals: dict[str, int] = field(default_factory=dict)
    documents_created: int = 0
    documents_skipped_confirmed: int = 0
    documents_failed: int = 0
    embeddings_generated: int = 0
    embeddings_reused: int = 0
    embeddings_failed: int = 0
    vectors_upserted: int = 0
    vectors_skipped: int = 0
    upsert_failed: int = 0
    docs_by_type: dict[str, int] = field(default_factory=dict)
    docs_by_type_season: dict[str, dict[str, int]] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)

    def record_document(self, document_type: str, season: int | None) -> None:
        self.documents_created += 1
        self.docs_by_type[document_type] = self.docs_by_type.get(document_type, 0) + 1
        season_key = str(season) if season is not None else "all"
        per_type = self.docs_by_type_season.setdefault(document_type, {})
        per_type[season_key] = per_type.get(season_key, 0) + 1

    def record_failure(
        self,
        *,
        stage: str,
        document_id: str,
        document_type: str,
        error: BaseException | str,
        max_kept: int = 500,
    ) -> None:
        if stage == "embedding":
            self.embeddings_failed += 1
        elif stage == "upsert":
            self.upsert_failed += 1
        self.documents_failed += 1
        if len(self.failures) < max_kept:
            failure = FailureRecord(
                stage=stage,
                document_id=document_id,
                document_type=document_type,
                error_type=type(error).__name__ if isinstance(error, BaseException) else "Error",
                error=str(error),
            )
            self.failures.append(failure.as_dict())

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_monotonic

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "source_rows_2021_2025": self.source_rows,
            "source_table_totals": self.source_table_totals,
            "documents_created": self.documents_created,
            "documents_by_type": self.docs_by_type,
            "documents_by_type_and_season": self.docs_by_type_season,
            "documents_skipped_already_uploaded": self.documents_skipped_confirmed,
            "documents_failed": self.documents_failed,
            "embeddings_generated": self.embeddings_generated,
            "embeddings_reused_from_cache": self.embeddings_reused,
            "embeddings_failed": self.embeddings_failed,
            "vectors_upserted": self.vectors_upserted,
            "vectors_skipped_already_uploaded": self.vectors_skipped,
            "vectors_failed": self.upsert_failed,
            "failures": self.failures,
        }


def chunks_cover_all(total: int, sizes: Sequence[int]) -> bool:
    """Small helper used by tests/validation of batch planning."""
    return sum(sizes) == total
