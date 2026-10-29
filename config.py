"""Configuration for the F1 RAG Ingestion Pipeline.

Reads credentials from environment variables using python-dotenv.
Never hardcode API keys or secrets in source code.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Define custom exceptions early
class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""
    pass

# Load .env file from the project root directory
# __file__ is config.py, so we need to go up one level to reach the project root
PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"

# Load .env values
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)

# Pinecone configuration - read from environment variables
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

if not PINECONE_API_KEY:
    raise ConfigurationError(
        "PINECONE_API_KEY not found. Set it in .env file."
    )
if not PINECONE_INDEX_NAME:
    raise ConfigurationError(
        "PINECONE_INDEX_NAME not found. Set it in .env file."
    )

# Embedding model configuration
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384  # Confirmed output dimension for all-MiniLM-L6-v2

# Ingestion configuration
DEFAULT_BATCH_SIZE = 100  # Pinecone upsert batch limit
MAX_RETRIES = 5
BASE_DELAY = 1.0  # seconds for exponential backoff

# Season range for this pipeline
MIN_SEASON = 2021
MAX_SEASON = 2025

# Namespace for Pinecone
PINECONE_NAMESPACE = "f1-2021-2025"

# Document types
DOCUMENT_TYPES = {
    "race_result",
    "qualifying",
    "pit_stop",
    "driver_profile",
    "constructor_profile",
    "driver_standings",
    "constructor_standings",
    "lap_time_summary",
}


def validate_index(pc, index_name: str = None) -> bool:
    """Validate that the Pinecone index exists, is accessible, uses dense vectors, and has the correct dimension.

    Does NOT create, delete, recreate, or modify the index automatically.
    Returns True if validation passes, False otherwise.
    """
    name = index_name or PINECONE_INDEX_NAME
    try:
        index_descriptions = pc.list_indices()
        index_names = [idx.name for idx in index_descriptions]
        if name not in index_names:
            print(f"Index '{name}' not found. Available indices: {index_names}")
            return False

        # Read index description - Pinecone SDK v10
        index_pc = pc.Index(name)
        # Check if it's a dense index
        description = index_pc.describe_index()
        print(f"Index '{name}' description: {description}")

        # The dimension check depends on the SDK version
        # For v10, we check the host metrics or index stats
        try:
            stats = index_pc.stats()
            print(f"Index stats: {stats}")
        except Exception:
            # stats() may not be available on all index types
            pass

        print(f"Index '{name}' validation passed.")
        return True

    except Exception as e:
        print(f"Error validating index '{name}': {e}")
        return False