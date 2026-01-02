"""
Semantic Cache - Cache LLM responses for similar queries.

Reduces latency and cost by returning cached responses for
semantically similar queries (not just exact matches).

Expected hit rate: 20-40% for typical chatbot workloads.
"""

import logging
import numpy as np
import sqlite3
import json
from typing import Optional, Dict, Tuple
from datetime import datetime, UTC, timedelta
from dataclasses import dataclass
import threading

from core.embeddings import get_embedding, cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached query-response pair."""
    query: str
    response: str
    topic: str
    embedding: np.ndarray
    created_at: datetime
    hit_count: int = 0


class SemanticCache:
    """
    Semantic similarity-based cache for LLM responses.

    Stores query embeddings and returns cached responses when
    a new query is sufficiently similar to a cached one.
    """

    def __init__(
        self,
        db_path: str = None,
        similarity_threshold: float = 0.92,
        max_entries: int = 1000,
        ttl_hours: int = 24
    ):
        """
        Initialize semantic cache.

        Args:
            db_path: Path to SQLite database
            similarity_threshold: Min similarity to consider a cache hit (0.92 = very similar)
            max_entries: Maximum cache entries per topic
            ttl_hours: Time-to-live for cache entries
        """
        from core.config import config
        self.db_path = db_path or config.db_path
        self.similarity_threshold = similarity_threshold
        self.max_entries = max_entries
        self.ttl_hours = ttl_hours
        self._lock = threading.Lock()

        # In-memory cache: {topic: [(embedding, cache_id), ...]}
        self._embeddings: Dict[str, list] = {}
        self._loaded_topics: set = set()

        self._init_schema()
        logger.info(f"SemanticCache initialized (threshold={similarity_threshold}, ttl={ttl_hours}h)")

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        """Initialize cache schema."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS semantic_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TEXT NOT NULL,
                hit_count INTEGER DEFAULT 0,
                last_hit_at TEXT
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_topic
            ON semantic_cache(topic)
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_created
            ON semantic_cache(created_at)
        """)

        conn.commit()
        conn.close()

    def _load_topic_embeddings(self, topic: str):
        """Load embeddings for a topic into memory."""
        if topic in self._loaded_topics:
            return

        with self._lock:
            if topic in self._loaded_topics:
                return

            conn = self._get_conn()
            cur = conn.cursor()

            # Get non-expired entries
            cutoff = (datetime.now(UTC) - timedelta(hours=self.ttl_hours)).isoformat()
            cur.execute("""
                SELECT id, embedding FROM semantic_cache
                WHERE topic = ? AND created_at > ?
            """, (topic, cutoff))

            embeddings = []
            for row in cur.fetchall():
                emb = np.frombuffer(row['embedding'], dtype=np.float32)
                embeddings.append((emb, row['id']))

            self._embeddings[topic] = embeddings
            self._loaded_topics.add(topic)
            conn.close()

            logger.debug(f"Loaded {len(embeddings)} cache embeddings for topic '{topic}'")

    def get(self, query: str, topic: str) -> Optional[str]:
        """
        Get cached response for a query.

        Args:
            query: User query
            topic: Topic namespace

        Returns:
            Cached response if similar query found, None otherwise
        """
        self._load_topic_embeddings(topic)

        if topic not in self._embeddings or not self._embeddings[topic]:
            return None

        # Get query embedding
        query_emb = get_embedding(query)

        # Find most similar cached query
        best_similarity = 0.0
        best_cache_id = None

        for emb, cache_id in self._embeddings[topic]:
            similarity = cosine_similarity(query_emb, emb)
            if similarity > best_similarity:
                best_similarity = similarity
                best_cache_id = cache_id

        # Check threshold
        if best_similarity < self.similarity_threshold:
            logger.debug(f"Cache miss for '{query[:50]}...' (best sim: {best_similarity:.3f})")
            return None

        # Fetch cached response
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("SELECT response FROM semantic_cache WHERE id = ?", (best_cache_id,))
        row = cur.fetchone()

        if row:
            # Update hit count
            cur.execute("""
                UPDATE semantic_cache
                SET hit_count = hit_count + 1, last_hit_at = ?
                WHERE id = ?
            """, (datetime.now(UTC).isoformat(), best_cache_id))
            conn.commit()

            logger.info(f"Cache HIT for '{query[:50]}...' (sim: {best_similarity:.3f})")
            conn.close()
            return row['response']

        conn.close()
        return None

    def set(self, query: str, response: str, topic: str):
        """
        Cache a query-response pair.

        Args:
            query: User query
            response: LLM response
            topic: Topic namespace
        """
        # Generate embedding
        embedding = get_embedding(query)

        conn = self._get_conn()
        cur = conn.cursor()

        # Check if we need to evict old entries
        cur.execute("SELECT COUNT(*) as count FROM semantic_cache WHERE topic = ?", (topic,))
        count = cur.fetchone()['count']

        if count >= self.max_entries:
            # Delete oldest entries (LRU based on last_hit_at or created_at)
            cur.execute("""
                DELETE FROM semantic_cache WHERE id IN (
                    SELECT id FROM semantic_cache
                    WHERE topic = ?
                    ORDER BY COALESCE(last_hit_at, created_at) ASC
                    LIMIT ?
                )
            """, (topic, count - self.max_entries + 10))  # Delete 10 extra for headroom

        # Insert new entry
        cur.execute("""
            INSERT INTO semantic_cache (topic, query, response, embedding, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            topic,
            query,
            response,
            embedding.tobytes(),
            datetime.now(UTC).isoformat()
        ))

        new_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Update in-memory index
        with self._lock:
            if topic not in self._embeddings:
                self._embeddings[topic] = []
            self._embeddings[topic].append((embedding, new_id))

        logger.debug(f"Cached response for '{query[:50]}...' in topic '{topic}'")

    def invalidate(self, topic: str = None):
        """
        Invalidate cache entries.

        Args:
            topic: Topic to invalidate (None = all topics)
        """
        conn = self._get_conn()
        cur = conn.cursor()

        if topic:
            cur.execute("DELETE FROM semantic_cache WHERE topic = ?", (topic,))
            with self._lock:
                self._embeddings.pop(topic, None)
                self._loaded_topics.discard(topic)
        else:
            cur.execute("DELETE FROM semantic_cache")
            with self._lock:
                self._embeddings.clear()
                self._loaded_topics.clear()

        conn.commit()
        conn.close()
        logger.info(f"Cache invalidated (topic={topic or 'all'})")

    def cleanup_expired(self):
        """Remove expired cache entries."""
        cutoff = (datetime.now(UTC) - timedelta(hours=self.ttl_hours)).isoformat()

        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM semantic_cache WHERE created_at < ?", (cutoff,))
        deleted = cur.rowcount
        conn.commit()
        conn.close()

        # Clear in-memory cache to force reload
        with self._lock:
            self._embeddings.clear()
            self._loaded_topics.clear()

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired cache entries")

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) as total, SUM(hit_count) as hits FROM semantic_cache")
        row = cur.fetchone()

        cur.execute("SELECT topic, COUNT(*) as count FROM semantic_cache GROUP BY topic")
        by_topic = {r['topic']: r['count'] for r in cur.fetchall()}

        conn.close()

        return {
            "total_entries": row['total'] or 0,
            "total_hits": row['hits'] or 0,
            "by_topic": by_topic,
            "similarity_threshold": self.similarity_threshold,
            "ttl_hours": self.ttl_hours
        }


# Singleton instance
_cache_instance: Optional[SemanticCache] = None


def get_cache() -> SemanticCache:
    """Get the global SemanticCache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SemanticCache()
    return _cache_instance
