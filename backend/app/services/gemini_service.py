"""Service for interacting with the Google Gemini API."""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import google.generativeai as genai

from ..core.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("f1rag.gemini")

SUPPORTED_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
    "gemini-1.0-pro",
]

DEFAULT_MODEL = GEMINI_MODEL or "gemini-1.5-flash"

_gemini_configured = False


def configure_gemini() -> bool:
    """Configure the Gemini SDK using the API key from the environment."""
    global _gemini_configured

    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set; Gemini service disabled")
        _gemini_configured = False
        return False

    try:
        genai.configure(api_key=api_key)
        _gemini_configured = True
        logger.info("Gemini SDK configured successfully")
        return True
    except Exception as exc:  # pragma: no cover - SDK/network failure
        logger.error("Failed to configure Gemini SDK: %s", exc)
        _gemini_configured = False
        return False


def is_configured() -> bool:
    return _gemini_configured and bool(GEMINI_API_KEY or os.getenv("GEMINI_API_KEY"))


def generate_answer(
    question: str,
    context: str,
    model_name: str = DEFAULT_MODEL,
    system_instruction: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Generate a grounded answer. Returns (answer, error)."""
    if not is_configured():
        return None, "Gemini API not configured - missing GEMINI_API_KEY"

    if not context or not context.strip():
        return None, "No context available - retrieval returned no relevant documents"

    if not question or not question.strip():
        return None, "Empty question provided"

    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction,
        )
        prompt = f"Question: {question}\n\nContext:\n{context}"

        logger.info("Generating Gemini answer with model %s", model_name)
        response = model.generate_content(prompt)

        if getattr(response, "text", None):
            return response.text, None

        feedback = getattr(response, "prompt_feedback", None)
        if feedback:
            return None, f"Gemini blocked the prompt: {feedback}"

        return None, "Gemini returned no text response"

    except Exception as exc:  # pragma: no cover - SDK failure
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        detail = f"Gemini API error: {type(exc).__name__}: {exc}"
        if status == 429:
            detail += " (rate limit exceeded)"
        elif status in (401, 403):
            detail += " (authentication/authorization error)"
        logger.error(detail)
        return None, detail


def format_sources(metadata_summary: List[Dict]) -> List[Dict]:
    """Format source metadata for display in the chat UI."""
    formatted = []
    for source in metadata_summary:
        formatted.append(
            {
                "season": source.get("season", "N/A"),
                "grand_prix": source.get("race", "N/A"),
                "driver": source.get("driver", "N/A"),
                "constructor": source.get("constructor", "N/A"),
                "document_type": source.get("document_type", "N/A"),
                "similarity_score": (
                    f"{source.get('score', 0):.4f}" if source.get("score") else "N/A"
                ),
            }
        )
    return formatted
