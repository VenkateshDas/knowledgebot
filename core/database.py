"""
Unified database management module.

Provides a single source of truth for:
- Database connection management
- Schema initialization and migrations
- Session context manager
"""

import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, UTC
from typing import Generator, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Database path - loaded lazily from config to avoid circular imports
_db_path: Optional[str] = None


def get_db_path() -> str:
    """Get the database path from configuration."""
    global _db_path
    if _db_path is None:
        from core.config import config
        _db_path = config.db_path
    return _db_path


def set_db_path(path: str) -> None:
    """Set the database path (useful for testing)."""
    global _db_path
    _db_path = path


@contextmanager
def db_session() -> Generator[sqlite3.Cursor, None, None]:
    """
    Context manager for database connections.

    Automatically commits on success and closes connection on exit.

    Usage:
        with db_session() as cur:
            cur.execute("SELECT * FROM messages")
            rows = cur.fetchall()

    Yields:
        sqlite3.Cursor: Database cursor for executing queries
    """
    conn = sqlite3.connect(get_db_path())
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database connections (returns connection, not cursor).

    Useful when you need more control or multiple cursors.

    Yields:
        sqlite3.Connection: Database connection
    """
    conn = sqlite3.connect(get_db_path())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """
    Initialize database schema.

    Creates all required tables and performs migrations for new columns.
    Safe to call multiple times - uses IF NOT EXISTS and handles existing columns.
    """
    logger.info("Initializing database...")

    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()

    # Create topics table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS topics (
        chat_id INTEGER,
        thread_id INTEGER,
        topic_name TEXT,
        updated_at TEXT,
        PRIMARY KEY (chat_id, thread_id)
    )
    """)

    # Create messages table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        thread_id INTEGER,
        topic_name TEXT,
        message_id INTEGER,
        user_id INTEGER,
        username TEXT,
        message_type TEXT,
        text TEXT,
        file_id TEXT,
        file_unique_id TEXT,
        message_link TEXT,
        created_at TEXT
    )
    """)

    # Create URL scrape cache table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS url_scrape_cache (
        url TEXT PRIMARY KEY,
        summary TEXT,
        full_content TEXT,
        scraped_at TEXT
    )
    """)

    conn.commit()

    # Migration: Add new columns to messages table
    new_columns = [
        ("primary_category", "TEXT"),
        ("secondary_tags", "TEXT"),
        ("extracted_link", "TEXT"),
        ("summary", "TEXT"),
        ("indexed_to_rag", "INTEGER DEFAULT 0"),
        ("indexed_at", "TEXT"),
        ("indexed_by", "TEXT")
    ]

    for col_name, col_type in new_columns:
        try:
            cur.execute(f"ALTER TABLE messages ADD COLUMN {col_name} {col_type}")
            logger.info(f"Added column {col_name} to messages table")
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.commit()
    conn.close()

    logger.info(f"Database initialized at: {get_db_path()}")


def save_to_scrape_cache(url: str, summary: str, full_content: str) -> None:
    """
    Save scraped content to the URL cache.

    Args:
        url: The URL that was scraped
        summary: LLM-generated summary of the content
        full_content: Full scraped content (markdown)
    """
    try:
        with db_session() as cur:
            cur.execute("""
                INSERT OR REPLACE INTO url_scrape_cache (url, summary, full_content, scraped_at)
                VALUES (?, ?, ?, ?)
            """, (url, summary, full_content, datetime.now(UTC).isoformat()))
        logger.debug(f"Saved scraped content to cache: {url}")
    except Exception as e:
        logger.error(f"Error saving scraped content to DB: {e}")


def get_from_scrape_cache(url: str) -> Optional[dict]:
    """
    Get cached scraped content for a URL.

    Args:
        url: The URL to look up

    Returns:
        Dict with summary, full_content, url or None if not found
    """
    try:
        with db_session() as cur:
            cur.execute("""
                SELECT summary, full_content
                FROM url_scrape_cache
                WHERE url = ?
            """, (url,))
            row = cur.fetchone()

            if row:
                return {
                    "summary": row[0],
                    "full_content": row[1],
                    "url": url
                }
    except Exception as e:
        logger.error(f"Error fetching scraped content from DB: {e}")

    return None
