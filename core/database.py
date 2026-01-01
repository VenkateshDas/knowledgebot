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

    # Create indexed URLs tracking table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS indexed_urls (
        url TEXT NOT NULL,
        original_url TEXT NOT NULL,
        topic_name TEXT NOT NULL,
        first_indexed_at TEXT NOT NULL,
        first_message_id INTEGER NOT NULL,
        last_seen_at TEXT,
        times_shared INTEGER DEFAULT 1,
        PRIMARY KEY (url, topic_name),
        FOREIGN KEY (first_message_id) REFERENCES messages(id)
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


def check_url_indexed(url: str, topic_name: str) -> Optional[dict]:
    """
    Check if URL already indexed in topic.

    Args:
        url: The URL to check (will be normalized)
        topic_name: Topic to check in

    Returns:
        Dict with indexed info + cached summary if found, None otherwise
    """
    from core.url_utils import normalize_url

    normalized = normalize_url(url)
    try:
        with db_session() as cur:
            cur.execute("""
                SELECT
                    iu.url, iu.original_url, iu.first_indexed_at,
                    iu.times_shared, iu.last_seen_at,
                    usc.summary, usc.scraped_at
                FROM indexed_urls iu
                LEFT JOIN url_scrape_cache usc ON iu.original_url = usc.url
                WHERE iu.url = ? AND iu.topic_name = ?
            """, (normalized, topic_name))
            row = cur.fetchone()

            if row:
                return {
                    'normalized_url': row[0],
                    'original_url': row[1],
                    'first_indexed_at': row[2],
                    'times_shared': row[3],
                    'last_seen_at': row[4],
                    'summary': row[5],
                    'scraped_at': row[6],
                    'topic_name': topic_name
                }
    except Exception as e:
        logger.error(f"Error checking indexed URL: {e}")

    return None


def mark_url_indexed(url: str, topic_name: str, message_id: int) -> None:
    """
    Mark URL as indexed (called by indexing worker).

    Args:
        url: The URL that was indexed
        topic_name: Topic it was indexed in
        message_id: ID of the message containing the URL
    """
    from core.url_utils import normalize_url

    normalized = normalize_url(url)
    now = datetime.now(UTC).isoformat()

    try:
        with db_session() as cur:
            cur.execute("""
                INSERT INTO indexed_urls
                (url, original_url, topic_name, first_indexed_at, first_message_id, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(url, topic_name) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    times_shared = times_shared + 1
            """, (normalized, url, topic_name, now, message_id, now))
        logger.debug(f"Marked URL as indexed: {url} in {topic_name}")
    except Exception as e:
        logger.error(f"Error marking URL as indexed: {e}")


def increment_url_share_count(url: str, topic_name: str) -> int:
    """
    Update when URL shared again (called by message handler).

    Args:
        url: The URL that was shared
        topic_name: Topic it was shared in

    Returns:
        Updated share count, or 0 if URL not found
    """
    from core.url_utils import normalize_url

    normalized = normalize_url(url)
    now = datetime.now(UTC).isoformat()

    try:
        with db_session() as cur:
            cur.execute("""
                UPDATE indexed_urls
                SET times_shared = times_shared + 1,
                    last_seen_at = ?
                WHERE url = ? AND topic_name = ?
            """, (now, normalized, topic_name))

            if cur.rowcount == 0:
                logger.warning(f"Attempted to increment share count for non-existent URL: {url}")
                return 0

            # Get updated count
            cur.execute("""
                SELECT times_shared FROM indexed_urls
                WHERE url = ? AND topic_name = ?
            """, (normalized, topic_name))
            row = cur.fetchone()
            new_count = row[0] if row else 0

            logger.debug(f"Incremented share count for {url} to {new_count}")
            return new_count
    except Exception as e:
        logger.error(f"Error incrementing share count: {e}")
        return 0
