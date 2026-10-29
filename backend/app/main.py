"""Main FastAPI application for the F1 Performance Analytics Platform.

Startup does NOT re-ingest data. All operations are read-only with respect to the
existing ingestion pipeline. API keys are never exposed to the frontend.
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import chat, dashboard, drivers
from .core.config import (
    GEMINI_API_KEY,
    PINECONE_API_KEY,
    PROJECT_NAME,
)
from .services.gemini_service import configure_gemini

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("f1rag.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify configuration on startup without re-ingesting any data."""
    if GEMINI_API_KEY:
        configure_gemini()
    else:
        logger.warning("GEMINI_API_KEY not set - /api/chat will be disabled")

    if not PINECONE_API_KEY:
        logger.warning("PINECONE_API_KEY not set - /api/chat cannot retrieve context")

    logger.info("Starting %s", PROJECT_NAME)
    yield
    logger.info("Shutting down F1 Performance Analytics Platform")


app = FastAPI(
    title=PROJECT_NAME,
    description="F1 Performance Analytics - Historical Race Intelligence (2021-2025)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(drivers.router)
app.include_router(chat.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


@app.get("/")
async def root() -> dict:
    return {"message": "F1 Performance Analytics API", "version": "1.0.0"}


@app.get("/api/v1/health", include_in_schema=False)
async def api_health() -> dict:
    return {"status": "healthy", "service": "F1 Performance Analytics API"}
