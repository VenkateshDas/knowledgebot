"""
Unified LLM client management.

Provides a single OpenAI client instance for use throughout the application.
"""

import logging
from typing import Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

# Singleton client instance
_client_instance: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """
    Get the global OpenAI client instance (configured for OpenRouter).

    Returns:
        OpenAI: Configured OpenAI client for OpenRouter API
    """
    global _client_instance

    if _client_instance is None:
        from core.config import config

        _client_instance = OpenAI(
            base_url=config.openrouter_base_url,
            api_key=config.openrouter_api_key,
        )
        logger.info(f"Initialized OpenAI client for OpenRouter (model: {config.openrouter_model})")

    return _client_instance


def reset_client() -> None:
    """Reset the client instance (useful for testing)."""
    global _client_instance
    _client_instance = None
