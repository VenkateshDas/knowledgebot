"""
Centralized configuration management.

All environment variables and configuration constants are loaded here once
and accessed throughout the application via the `config` object.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables once at module import
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Telegram
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "").strip())

    # Database
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "bot.db"))

    # OpenRouter / LLM
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "").strip())
    openrouter_model: str = field(default_factory=lambda: os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.1"))
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Web Services
    firecrawl_api_key: str = field(default_factory=lambda: os.getenv("FIRECRAWL_API_KEY", "").strip())
    parallel_api_key: str = field(default_factory=lambda: os.getenv("PARALLEL_API_KEY", "").strip())

    # LightRAG
    lightrag_working_dir: str = field(default_factory=lambda: os.getenv("LIGHTRAG_WORKING_DIR", "./lightrag_data"))
    lightrag_llm_model: str = field(default_factory=lambda: os.getenv("LIGHTRAG_LLM_MODEL", "minimax/minimax-m2.1"))
    lightrag_embedding_model: str = field(default_factory=lambda: os.getenv("LIGHTRAG_EMBEDDING_MODEL", "openai/text-embedding-3-small"))
    lightrag_default_mode: str = field(default_factory=lambda: os.getenv("LIGHTRAG_DEFAULT_MODE", "hybrid"))
    lightrag_top_k: int = field(default_factory=lambda: int(os.getenv("LIGHTRAG_TOP_K", "5")))
    lightrag_production: bool = field(default_factory=lambda: os.getenv("LIGHTRAG_PRODUCTION", "false").lower() == "true")

    # Indexing Worker
    indexing_poll_interval: int = field(default_factory=lambda: int(os.getenv("INDEXING_POLL_INTERVAL", "10")))
    indexing_batch_size: int = field(default_factory=lambda: int(os.getenv("INDEXING_BATCH_SIZE", "10")))

    # Cache settings
    scrape_cache_max_size: int = field(default_factory=lambda: int(os.getenv("SCRAPE_CACHE_MAX_SIZE", "100")))

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self):
        """Validate required configuration values."""
        errors = []

        if not self.telegram_bot_token:
            errors.append("TELEGRAM_BOT_TOKEN environment variable is required")

        if not self.openrouter_api_key:
            errors.append("OPENROUTER_API_KEY environment variable is required")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)

        # Log optional missing configs as warnings
        if not self.firecrawl_api_key:
            logger.warning("FIRECRAWL_API_KEY not set - will use Jina Reader as fallback for scraping")

        if not self.parallel_api_key:
            logger.warning("PARALLEL_API_KEY not set - web search will not be available")

    @property
    def db_path_resolved(self) -> Path:
        """Get resolved database path."""
        return Path(self.db_path).resolve()

    @property
    def lightrag_working_dir_resolved(self) -> Path:
        """Get resolved LightRAG working directory."""
        return Path(self.lightrag_working_dir).resolve()


# Global configuration instance (singleton)
# Lazy initialization to allow tests to set env vars before config is created
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


# For convenience, expose config directly (lazy loaded on first access)
class _ConfigProxy:
    """Proxy that lazily loads config on first attribute access."""

    _config: Optional[Config] = None

    def __getattr__(self, name: str):
        if self._config is None:
            self._config = get_config()
        return getattr(self._config, name)


config = _ConfigProxy()
