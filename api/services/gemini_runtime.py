"""Configure google-generativeai for API routes (env-only; no Streamlit secrets)."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from integrations.env_loader import env_str


def gemini_model_name() -> str:
    return env_str("GEMINI_MODEL", "gemini-2.5-flash")


def configure_genai_from_env() -> Tuple[Optional[Any], str]:
    """Returns (genai module or None, error message if unusable)."""
    try:
        import google.generativeai as genai
    except ImportError:
        return None, "Install google-generativeai."
    key = env_str("GEMINI_API_KEY") or env_str("GOOGLE_API_KEY")
    if not key:
        return None, "Set GEMINI_API_KEY or GOOGLE_API_KEY."
    genai.configure(api_key=key)
    return genai, ""
