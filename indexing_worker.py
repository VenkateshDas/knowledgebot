"""
Indexing Worker - Background worker for automatic URL content indexing.

Monitors the messages table for new URLs and indexes them to LightRAG.
User messages are indexed only via agent decisions (knowledge_index tool).
"""

import logging
import asyncio
from datetime import datetime, timedelta, UTC
from typing import Optional

from core.config import config
from core.database import db_session
from lightrag_manager import get_lightrag_manager
from tools.common_tools import get_scraped_content

logger = logging.getLogger(__name__)


class URLIndexingWorker:
    """
    Background worker that automatically indexes URL content to LightRAG.

    Only handles URLs - user messages are indexed via agent decisions only.
    """

    def __init__(self):
        """Initialize the indexing worker."""
        self.lightrag_manager = get_lightrag_manager()
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        logger.info("URLIndexingWorker initialized")

    async def start(self):
        """
        Start the background indexing worker.

        Polls database for unindexed URLs and processes them.
        """
        if self.is_running:
            logger.warning("Indexing worker already running")
            return

        self.is_running = True
        logger.info("Starting URL indexing worker...")

        while self.is_running:
            try:
                await self._process_pending_urls()
                await asyncio.sleep(config.indexing_poll_interval)
            except Exception as e:
                logger.error(f"Error in indexing worker loop: {e}", exc_info=True)
                await asyncio.sleep(config.indexing_poll_interval * 2)  # Back off on error

    def stop(self):
        """Stop the background indexing worker."""
        logger.info("Stopping URL indexing worker...")
        self.is_running = False

    async def _process_pending_urls(self):
        """Process pending URLs that need indexing."""
        try:
            # Get unindexed URLs from database
            pending_urls = self._get_pending_urls()

            if not pending_urls:
                return

            logger.info(f"Found {len(pending_urls)} URLs to index")

            for url_data in pending_urls:
                try:
                    await self._index_url(url_data)
                except Exception as e:
                    logger.error(f"Failed to index URL {url_data['url']}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error processing pending URLs: {e}", exc_info=True)

    def _get_pending_urls(self) -> list:
        """
        Get URLs that need to be indexed.

        Only processes URLs from messages created in the last 24 hours to avoid
        re-indexing historical data.

        Returns:
            List of dicts with URL data
        """
        try:
            # Only process URLs from the last 24 hours
            cutoff_time = datetime.now(UTC) - timedelta(hours=24)
            cutoff_iso = cutoff_time.isoformat()

            with db_session() as cur:
                cur.execute("""
                    SELECT id, topic_name, extracted_link, username, created_at, summary
                    FROM messages
                    WHERE extracted_link IS NOT NULL
                      AND summary IS NOT NULL
                      AND summary != ''
                      AND (indexed_to_rag IS NULL OR indexed_to_rag = 0)
                      AND created_at >= ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (cutoff_iso, config.indexing_batch_size))

                rows = cur.fetchall()

                return [
                    {
                        "message_id": row[0],
                        "topic_name": row[1],
                        "url": row[2],
                        "username": row[3] or "unknown",
                        "timestamp": row[4],
                        "summary": row[5]
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Error fetching pending URLs: {e}")
            return []

    async def _index_url(self, url_data: dict):
        """
        Index a URL to LightRAG.

        Args:
            url_data: Dictionary with URL information
        """
        url = url_data["url"]
        topic_name = url_data["topic_name"]
        message_id = url_data["message_id"]
        username = url_data["username"]
        timestamp = url_data["timestamp"]
        summary = url_data["summary"]

        logger.info(f"Indexing URL for topic '{topic_name}': {url}")

        # Check if URL already indexed in this topic
        from core.database import check_url_indexed, mark_url_indexed

        if check_url_indexed(url, topic_name):
            logger.info(f"Skipping duplicate URL: {url} in topic {topic_name}")
            self._mark_as_indexed(message_id, "duplicate")
            return

        # Try to get cached content first
        scraped_data = get_scraped_content(url)

        if not scraped_data or not scraped_data.get("full_content"):
            logger.warning(f"No cached content found for {url}, skipping for now")
            # Don't mark as failed - it might get scraped later
            return

        full_content = scraped_data["full_content"]
        if not summary and scraped_data.get("summary"):
            summary = scraped_data["summary"]

        # Index to LightRAG
        success = await self.lightrag_manager.index_url_content(
            topic_name=topic_name,
            url=url,
            content=full_content,
            summary=summary or "No summary available",
            timestamp=timestamp,
            username=username
        )

        if success:
            # Mark as indexed in database
            self._mark_as_indexed(message_id, "auto_url")
            # Track in indexed_urls table
            mark_url_indexed(url, topic_name, message_id)
            logger.info(f"Successfully indexed URL: {url}")
        else:
            logger.error(f"Failed to index URL: {url}")

    def _mark_as_indexed(self, message_id: int, indexed_by: str):
        """
        Mark a message as indexed in the database.

        Args:
            message_id: Database message ID
            indexed_by: Who/what indexed it ("auto_url" or "agent_decision")
        """
        try:
            with db_session() as cur:
                cur.execute("""
                    UPDATE messages
                    SET indexed_to_rag = 1,
                        indexed_at = ?,
                        indexed_by = ?
                    WHERE id = ?
                """, (datetime.now(UTC).isoformat(), indexed_by, message_id))

                logger.debug(f"Marked message {message_id} as indexed ({indexed_by})")

        except Exception as e:
            logger.error(f"Error marking message as indexed: {e}")

    async def backfill_urls(self, topic_name: Optional[str] = None, limit: int = 100):
        """
        Backfill historical URLs.

        Args:
            topic_name: Optional topic filter
            limit: Maximum number of URLs to backfill
        """
        logger.info(f"Starting URL backfill (topic={topic_name}, limit={limit})")

        try:
            # Get historical URLs
            with db_session() as cur:
                if topic_name:
                    cur.execute("""
                        SELECT id, topic_name, extracted_link, username, created_at, summary
                        FROM messages
                        WHERE extracted_link IS NOT NULL
                          AND topic_name = ?
                          AND (indexed_to_rag IS NULL OR indexed_to_rag = 0)
                        ORDER BY created_at ASC
                        LIMIT ?
                    """, (topic_name, limit))
                else:
                    cur.execute("""
                        SELECT id, topic_name, extracted_link, username, created_at, summary
                        FROM messages
                        WHERE extracted_link IS NOT NULL
                          AND (indexed_to_rag IS NULL OR indexed_to_rag = 0)
                        ORDER BY created_at ASC
                        LIMIT ?
                    """, (limit,))

                rows = cur.fetchall()

                urls_to_backfill = [
                    {
                        "message_id": row[0],
                        "topic_name": row[1],
                        "url": row[2],
                        "username": row[3] or "unknown",
                        "timestamp": row[4],
                        "summary": row[5]
                    }
                    for row in rows
                ]

            logger.info(f"Found {len(urls_to_backfill)} URLs to backfill")

            # Process each URL
            for i, url_data in enumerate(urls_to_backfill, 1):
                try:
                    logger.info(f"Backfilling {i}/{len(urls_to_backfill)}: {url_data['url']}")
                    await self._index_url(url_data)
                    await asyncio.sleep(0.5)  # Small delay to avoid rate limiting
                except Exception as e:
                    logger.error(f"Error backfilling URL {url_data['url']}: {e}")

            logger.info(f"Backfill complete: processed {len(urls_to_backfill)} URLs")

        except Exception as e:
            logger.error(f"Error in backfill: {e}", exc_info=True)


# Global worker instance
_worker_instance: Optional[URLIndexingWorker] = None


def get_indexing_worker() -> URLIndexingWorker:
    """
    Get global indexing worker instance (singleton).

    Returns:
        URLIndexingWorker instance
    """
    global _worker_instance

    if _worker_instance is None:
        _worker_instance = URLIndexingWorker()

    return _worker_instance


async def start_indexing_worker():
    """Start the global indexing worker."""
    worker = get_indexing_worker()
    await worker.start()


def stop_indexing_worker():
    """Stop the global indexing worker."""
    if _worker_instance:
        _worker_instance.stop()
