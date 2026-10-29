"""Backend configuration for the F1 Performance Analytics Platform.

Reads environment variables from the project root .env file (same .env as the
original pipeline) and optionally from backend/.env. Never hardcode API keys.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger("f1rag.config")

# backend/app/core/config.py -> backend/app -> backend -> project root
CORE_DIR = Path(__file__).resolve().parent
APP_DIR = CORE_DIR.parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Load the project root .env first, then backend/.env (backend values win only
# when they are explicitly present).
for env_file in (PROJECT_ROOT / ".env", BACKEND_DIR / ".env"):
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)

DATA_DIR = PROJECT_ROOT / "data"

# Gemini API configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Pinecone configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "f1-racing")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "f1-2021-2025")

# Embedding model configuration (must match the ingestion pipeline)
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# API configuration
API_V1_STR = "/api/v1"
PROJECT_NAME = "F1 Performance Analytics - Historical Race Intelligence"

# Missing credentials are non-fatal: the API still serves dashboard, race and
# driver data. Only the AI chat endpoint requires Gemini/Pinecone.
if not GEMINI_API_KEY:
    logger.warning(
        "GEMINI_API_KEY is not set - the /api/chat endpoint will report that "
        "AI chat is disabled."
    )
if not PINECONE_API_KEY:
    logger.warning(
        "PINECONE_API_KEY is not set - the /api/chat endpoint cannot retrieve "
        "vector context."
    )
