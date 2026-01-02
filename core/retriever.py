"""
Hybrid Retriever - Fast BM25 + Vector search.

Replaces LightRAG with a simpler, faster approach:
- SQLite FTS5 for BM25 keyword search (~5ms)
- In-memory numpy vectors for semantic search (~50-100ms)
- Reciprocal Rank Fusion (RRF) for result merging

No graph database, no entity extraction, no LLM calls during retrieval.
"""

import logging
import sqlite3
import numpy as np
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
import threading

from core.embeddings import get_embedding, batch_cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result."""
    chunk_id: int
    content: str
    topic: str
    score: float
    source_type: str  # "url" or "message"
    source_url: Optional[str] = None
    metadata: Optional[Dict] = None


class HybridRetriever:
    """
    Fast hybrid search combining BM25 and vector similarity.

    Single instance handles all topics via namespace column.
    Thread-safe with in-memory vector index for speed.
    """

    def __init__(self, db_path: str = None):
        """
        Initialize the hybrid retriever.

        Args:
            db_path: Path to SQLite database
        """
        from core.config import config
        self.db_path = db_path or config.db_path
        self._lock = threading.Lock()

        # In-memory vector index: {chunk_id: embedding}
        self._vectors: Dict[int, np.ndarray] = {}
        self._vectors_loaded = False

        # Initialize schema
        self._init_schema()
        logger.info(f"HybridRetriever initialized (db: {self.db_path})")

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        """Initialize database schema with FTS5 for BM25."""
        conn = self._get_conn()
        cur = conn.cursor()

        # Main chunks table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_url TEXT,
                metadata TEXT,
                embedding BLOB,
                created_at TEXT NOT NULL
            )
        """)

        # Create index on topic for fast filtering
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_topic
            ON knowledge_chunks(topic)
        """)

        # FTS5 virtual table for BM25 search
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                content,
                content='knowledge_chunks',
                content_rowid='id',
                tokenize='porter unicode61'
            )
        """)

        # Triggers to keep FTS in sync
        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON knowledge_chunks BEGIN
                INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
            END
        """)

        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON knowledge_chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES('delete', old.id, old.content);
            END
        """)

        cur.execute("""
            CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON knowledge_chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, content) VALUES('delete', old.id, old.content);
                INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
            END
        """)

        conn.commit()
        conn.close()
        logger.info("Knowledge chunks schema initialized")

    def _load_vectors(self):
        """Load all vectors into memory for fast similarity search."""
        if self._vectors_loaded:
            return

        with self._lock:
            if self._vectors_loaded:
                return

            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("SELECT id, embedding FROM knowledge_chunks WHERE embedding IS NOT NULL")

            for row in cur.fetchall():
                if row['embedding']:
                    self._vectors[row['id']] = np.frombuffer(row['embedding'], dtype=np.float32)

            conn.close()
            self._vectors_loaded = True
            logger.info(f"Loaded {len(self._vectors)} vectors into memory")

    def index(
        self,
        content: str,
        topic: str,
        source_type: str,
        source_url: str = None,
        metadata: Dict = None
    ) -> int:
        """
        Index a piece of content.

        Args:
            content: Text content to index
            topic: Topic namespace (e.g., "Journal", "Health")
            source_type: "url" or "message"
            source_url: Original URL if source_type is "url"
            metadata: Additional metadata dict

        Returns:
            Chunk ID
        """
        # Generate embedding
        embedding = get_embedding(content)

        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO knowledge_chunks (topic, content, source_type, source_url, metadata, embedding, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            topic,
            content,
            source_type,
            source_url,
            json.dumps(metadata) if metadata else None,
            embedding.tobytes(),
            datetime.now(UTC).isoformat()
        ))

        chunk_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Update in-memory index
        with self._lock:
            self._vectors[chunk_id] = embedding

        logger.debug(f"Indexed chunk {chunk_id} to topic '{topic}'")
        return chunk_id

    def search(
        self,
        query: str,
        topic: str,
        top_k: int = 5,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
        mode: str = "auto"
    ) -> List[SearchResult]:
        """
        Adaptive search with fast and hybrid modes.

        Modes:
        - "auto": Automatic mode selection based on query (default)
        - "fast": BM25-only for < 5ms latency
        - "hybrid": Full BM25 + Vector search

        Args:
            query: Search query
            topic: Topic to search in
            top_k: Number of results to return
            bm25_weight: Weight for BM25 scores (0-1)
            vector_weight: Weight for vector scores (0-1)
            mode: Search mode ("auto", "fast", "hybrid")

        Returns:
            List of SearchResult objects
        """
        # Auto mode: decide based on query characteristics
        if mode == "auto":
            mode = self._select_search_mode(query)

        # Fast mode: BM25 only (< 5ms)
        if mode == "fast":
            return self._fast_search(query, topic, top_k)

        # Hybrid mode: BM25 + Vector (slower but more semantic)
        self._load_vectors()
        bm25_results = self._bm25_search(query, topic, top_k * 2)
        vector_results = self._vector_search(query, topic, top_k * 2)
        merged = self._rrf_merge(bm25_results, vector_results, bm25_weight, vector_weight)
        return self._fetch_results(merged[:top_k])

    def _select_search_mode(self, query: str) -> str:
        """
        Select search mode based on query characteristics.

        Uses hybrid for:
        - Questions requiring semantic understanding
        - Abstract or conceptual queries
        - Long complex queries

        Uses fast (BM25-only) for:
        - Short keyword queries
        - Specific lookups (URLs, names, dates)
        - Simple retrieval requests
        """
        query_lower = query.lower()
        words = query.split()

        # Semantic patterns that need hybrid (check first)
        semantic_patterns = [
            "similar", "like", "related", "about",
            "meaning", "concept", "idea", "understand",
            "how does", "how do", "how to",
            "what is", "what are", "what does",
            "explain", "describe", "tell me about",
            "why", "compare", "difference",
        ]
        if any(p in query_lower for p in semantic_patterns):
            return "hybrid"

        # Long queries likely need semantic understanding
        if len(words) > 8:
            return "hybrid"

        # Specific patterns that work well with BM25 (fast)
        specific_patterns = [
            "http", "www.", "@",  # URLs, mentions
            "2024", "2025", "2023",  # Years
            ".com", ".org", ".io",  # Domains
        ]
        if any(p in query_lower for p in specific_patterns):
            return "fast"

        # Default: fast for speed (most queries are simple lookups)
        return "fast"

    def _fast_search(self, query: str, topic: str, limit: int) -> List[SearchResult]:
        """
        Fast BM25-only search (< 5ms latency).

        No embedding API calls - pure keyword matching.
        """
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT kc.id, kc.content, kc.topic, kc.source_type, kc.source_url, kc.metadata,
                   bm25(chunks_fts) as score
            FROM chunks_fts
            JOIN knowledge_chunks kc ON chunks_fts.rowid = kc.id
            WHERE chunks_fts MATCH ? AND kc.topic = ?
            ORDER BY score
            LIMIT ?
        """, (query, topic, limit))

        results = []
        for row in cur.fetchall():
            results.append(SearchResult(
                chunk_id=row[0],
                content=row[1],
                topic=row[2],
                score=-row[6],  # BM25 returns negative scores
                source_type=row[3],
                source_url=row[4],
                metadata=json.loads(row[5]) if row[5] else None
            ))

        conn.close()
        logger.debug(f"Fast search: {len(results)} results for '{query[:30]}...'")
        return results

    def _bm25_search(self, query: str, topic: str, limit: int) -> List[Tuple[int, float]]:
        """
        BM25 search using SQLite FTS5.

        Returns list of (chunk_id, bm25_score) tuples.
        """
        conn = self._get_conn()
        cur = conn.cursor()

        # FTS5 BM25 search with topic filter
        cur.execute("""
            SELECT kc.id, bm25(chunks_fts) as score
            FROM chunks_fts
            JOIN knowledge_chunks kc ON chunks_fts.rowid = kc.id
            WHERE chunks_fts MATCH ? AND kc.topic = ?
            ORDER BY score
            LIMIT ?
        """, (query, topic, limit))

        results = [(row['id'], -row['score']) for row in cur.fetchall()]  # BM25 returns negative scores
        conn.close()

        return results

    def _vector_search(self, query: str, topic: str, limit: int) -> List[Tuple[int, float]]:
        """
        Vector similarity search using in-memory numpy.

        Returns list of (chunk_id, similarity_score) tuples.
        """
        if not self._vectors:
            return []

        # Get query embedding
        query_emb = get_embedding(query)

        # Get chunk IDs for this topic
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM knowledge_chunks WHERE topic = ?", (topic,))
        topic_ids = {row['id'] for row in cur.fetchall()}
        conn.close()

        if not topic_ids:
            return []

        # Filter vectors to topic
        filtered_ids = [cid for cid in self._vectors.keys() if cid in topic_ids]
        if not filtered_ids:
            return []

        # Stack vectors for batch operation
        vectors_matrix = np.array([self._vectors[cid] for cid in filtered_ids])

        # Compute similarities
        similarities = batch_cosine_similarity(query_emb, vectors_matrix)

        # Sort and return top results
        results = list(zip(filtered_ids, similarities))
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:limit]

    def _rrf_merge(
        self,
        bm25_results: List[Tuple[int, float]],
        vector_results: List[Tuple[int, float]],
        bm25_weight: float,
        vector_weight: float,
        k: int = 60  # RRF constant
    ) -> List[Tuple[int, float]]:
        """
        Merge results using Reciprocal Rank Fusion.

        RRF score = sum(weight / (k + rank)) for each result list.
        """
        scores: Dict[int, float] = {}

        # Add BM25 scores
        for rank, (chunk_id, _) in enumerate(bm25_results, 1):
            scores[chunk_id] = scores.get(chunk_id, 0) + bm25_weight / (k + rank)

        # Add vector scores
        for rank, (chunk_id, _) in enumerate(vector_results, 1):
            scores[chunk_id] = scores.get(chunk_id, 0) + vector_weight / (k + rank)

        # Sort by combined score
        merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return merged

    def _fetch_results(self, merged: List[Tuple[int, float]]) -> List[SearchResult]:
        """Fetch full result objects for merged IDs."""
        if not merged:
            return []

        conn = self._get_conn()
        cur = conn.cursor()

        results = []
        for chunk_id, score in merged:
            cur.execute("""
                SELECT id, content, topic, source_type, source_url, metadata
                FROM knowledge_chunks WHERE id = ?
            """, (chunk_id,))
            row = cur.fetchone()

            if row:
                results.append(SearchResult(
                    chunk_id=row['id'],
                    content=row['content'],
                    topic=row['topic'],
                    score=score,
                    source_type=row['source_type'],
                    source_url=row['source_url'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else None
                ))

        conn.close()
        return results

    def get_stats(self, topic: str = None) -> Dict:
        """Get retriever statistics."""
        conn = self._get_conn()
        cur = conn.cursor()

        if topic:
            cur.execute("SELECT COUNT(*) as count FROM knowledge_chunks WHERE topic = ?", (topic,))
        else:
            cur.execute("SELECT COUNT(*) as count FROM knowledge_chunks")

        count = cur.fetchone()['count']
        conn.close()

        return {
            "total_chunks": count,
            "vectors_in_memory": len(self._vectors),
            "topic_filter": topic
        }


# Singleton instance
_retriever_instance: Optional[HybridRetriever] = None


def get_retriever() -> HybridRetriever:
    """Get the global HybridRetriever instance."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = HybridRetriever()
    return _retriever_instance
