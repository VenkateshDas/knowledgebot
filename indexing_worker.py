"""
Indexing Worker - Background URL content indexing.

Simplified version using HybridRetriever (no LightRAG).
Polls for new URLs and indexes them in batches.
"""

import logging
import asyncio
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict

from core.config import config
from core.database import db_session, mark_url_indexed
from tools.common_tools import get_scraped_content
from tools.rag_tools import index_url_content

logger = logging.getLogger(__name__)


class IndexingWorker:
    """
    Background worker for automatic URL indexing.

    Polls database for URLs with summaries and indexes them
    to the knowledge base in batches.
    """

    def __init__(self):
        """Initialize the worker."""
        self.is_running = False
        self.poll_interval = config.indexing_poll_interval
        self.batch_size = config.indexing_batch_size
        logger.info("IndexingWorker initialized")

    async def start(self):
        """Start the background worker."""
        if self.is_running:
            logger.warning("Worker already running")
            return

        self.is_running = True
        logger.info("Starting IndexingWorker...")

        while self.is_running:
            try:
                await self._process_batch()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval * 2)

    def stop(self):
        """Stop the worker."""
        logger.info("Stopping IndexingWorker...")
        self.is_running = False

    async def _process_batch(self):
        """Process a batch of pending URLs."""
        pending = self._get_pending_urls()

        if not pending:
            return

        logger.info(f"Processing {len(pending)} URLs")

        for url_data in pending:
            try:
                await self._index_url(url_data)
            except Exception as e:
                logger.error(f"Failed to index {url_data['url']}: {e}")

    def _get_pending_urls(self) -> List[Dict]:
        """Get URLs pending indexing."""
        # Only process recent URLs (last 24 hours)
        cutoff = (datetime.now(UTC) - timedelta(hours=24)).isoformat()

        try:
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
                """, (cutoff, self.batch_size))

                return [
                    {
                        "message_id": row[0],
                        "topic": row[1],
                        "url": row[2],
                        "username": row[3] or "unknown",
                        "timestamp": row[4],
                        "summary": row[5]
                    }
                    for row in cur.fetchall()
                ]
        except Exception as e:
            logger.error(f"Error fetching pending URLs: {e}")
            return []

    async def _index_url(self, url_data: Dict):
        """Index a single URL."""
        url = url_data["url"]
        topic = url_data["topic"]
        message_id = url_data["message_id"]

        # Check if already indexed
        from core.database import check_url_indexed
        if check_url_indexed(url, topic):
            logger.info(f"Skipping duplicate: {url}")
            self._mark_indexed(message_id, "duplicate")
            return

        # Get cached content
        scraped = get_scraped_content(url)
        if not scraped or not scraped.get("full_content"):
            logger.warning(f"No cached content for {url}")
            return

        # Index to knowledge base
        success = index_url_content(
            topic=topic,
            url=url,
            content=scraped["full_content"],
            summary=url_data["summary"] or scraped.get("summary", ""),
            username=url_data["username"],
            message_id=message_id
        )

        if success:
            self._mark_indexed(message_id, "auto_url")
            mark_url_indexed(url, topic, message_id)
            logger.info(f"Indexed: {url}")

    def _mark_indexed(self, message_id: int, indexed_by: str):
        """Mark message as indexed in database."""
        try:
            with db_session() as cur:
                cur.execute("""
                    UPDATE messages
                    SET indexed_to_rag = 1, indexed_at = ?, indexed_by = ?
                    WHERE id = ?
                """, (datetime.now(UTC).isoformat(), indexed_by, message_id))
        except Exception as e:
            logger.error(f"Error marking indexed: {e}")


# Singleton
_worker: Optional[IndexingWorker] = None


def get_indexing_worker() -> IndexingWorker:
    """Get global worker instance."""
    global _worker
    if _worker is None:
        _worker = IndexingWorker()
    return _worker
