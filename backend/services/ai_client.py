"""Shared OpenAI-compatible client factory.

Centralises API key / base URL / model name resolution so every AI service
uses the same configuration.  A bug fix here applies everywhere.
"""
import os

from openai import OpenAI


def get_client() -> OpenAI:
    """Return a configured OpenAI client.

    Reads from environment variables:
        INTERNAL_API_KEY  – required
        INTERNAL_BASE_URL – optional, defaults to OpenAI public endpoint

    Raises:
        RuntimeError: If INTERNAL_API_KEY is not set.
    """
    api_key = os.environ.get("INTERNAL_API_KEY")
    base_url = os.environ.get("INTERNAL_BASE_URL", "https://api.openai.com/v1")

    if not api_key:
        raise RuntimeError(
            "INTERNAL_API_KEY is not set. Add it to your .env file and restart the server."
        )

    return OpenAI(api_key=api_key, base_url=base_url)


def get_model() -> str:
    """Return the configured model name."""
    return os.environ.get("INTERNAL_MODEL_NAME", "gpt-4o-mini")
