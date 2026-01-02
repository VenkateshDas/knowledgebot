"""
RAG Tools - Knowledge base tools for agents.

Simplified interface using HybridRetriever (BM25 + Vector search).
No more LightRAG, no graph-based entity extraction.
"""

import logging
from typing import List, Optional
from datetime import datetime, UTC
from dataclasses import dataclass
from contextvars import ContextVar

from core.database import db_session
from core.retriever import get_retriever, SearchResult
from core.cache import get_cache

logger = logging.getLogger(__name__)


@dataclass
class RAGContext:
    """Thread-safe context for RAG operations."""
    topic_name: str
    username: str
    timestamp: str
    message_id: int
    user_message: str


# Thread-safe context variable
_rag_context: ContextVar[Optional[RAGContext]] = ContextVar('rag_context', default=None)


def set_rag_context(
    topic_name: str,
    username: str,
    timestamp: str,
    message_id: int,
    user_message: str
):
    """Set context for RAG tools (called by agent before run())."""
    context = RAGContext(
        topic_name=topic_name,
        username=username,
        timestamp=timestamp,
        message_id=message_id,
        user_message=user_message
    )
    _rag_context.set(context)


def get_rag_context() -> Optional[RAGContext]:
    """Get the current RAG context."""
    return _rag_context.get()


def clear_rag_context():
    """Clear RAG context after agent execution."""
    _rag_context.set(None)


def knowledge_retrieve(query: str) -> str:
    """
    Retrieve relevant information from the knowledge base.

    WHEN TO USE:
    - User asks about past content ("what was that article about...")
    - User references previous conversations
    - Need context from earlier sessions

    Args:
        query: Search query

    Returns:
        Relevant context from knowledge base with sources
    """
    try:
        context = get_rag_context()
        if not context or not context.topic_name:
            return "Error: Topic context not set."

        topic = context.topic_name
        logger.info(f"Retrieving from '{topic}': {query[:50]}...")

        # Get retriever and search
        retriever = get_retriever()
        results = retriever.search(query=query, topic=topic, top_k=5)

        if not results:
            return "No relevant information found in knowledge base."

        # Format results
        output = ["Retrieved from knowledge base:\n"]

        for i, result in enumerate(results, 1):
            output.append(f"\n[{i}] {result.content[:500]}...")
            if result.source_url:
                output.append(f"    Source: {result.source_url}")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Error in knowledge_retrieve: {e}", exc_info=True)
        return f"Error retrieving from knowledge base: {str(e)}"


def knowledge_index(
    content: str,
    content_type: str = "insight",
    tags: Optional[List[str]] = None
) -> str:
    """
    Add user message to knowledge base.

    WHEN TO USE:
    - User shares valuable insights or decisions
    - User provides personal context (preferences, goals)
    - Content has future reference value

    WHEN NOT TO USE:
    - Simple questions or casual chat
    - Content already captured in a URL

    Args:
        content: Content to index
        content_type: Type (insight, decision, preference, experience, goal)
        tags: Optional tags for categorization

    Returns:
        Confirmation message
    """
    try:
        context = get_rag_context()
        if not context:
            return "Error: Context not set."

        topic = context.topic_name
        username = context.username
        timestamp = context.timestamp
        message_id = context.message_id

        logger.info(f"Indexing to '{topic}': {content_type}")

        # Format content with metadata
        formatted_content = f"""
[{content_type.upper()}] {content}
From: {username}
Date: {timestamp}
Tags: {', '.join(tags) if tags else 'none'}
"""

        # Get retriever and index
        retriever = get_retriever()
        chunk_id = retriever.index(
            content=formatted_content,
            topic=topic,
            source_type="message",
            metadata={
                "content_type": content_type,
                "username": username,
                "tags": tags,
                "message_id": message_id
            }
        )

        # Mark in database
        try:
            with db_session() as cur:
                cur.execute("""
                    UPDATE messages
                    SET indexed_to_rag = 1, indexed_at = ?, indexed_by = ?
                    WHERE id = ?
                """, (datetime.now(UTC).isoformat(), "agent_decision", message_id))
        except Exception as db_error:
            logger.error(f"Failed to update database: {db_error}")

        tag_str = f" with tags: {', '.join(tags)}" if tags else ""
        return f"Added to knowledge base as '{content_type}'{tag_str}"

    except Exception as e:
        logger.error(f"Error in knowledge_index: {e}", exc_info=True)
        return f"Error indexing: {str(e)}"


def index_url_content(
    topic: str,
    url: str,
    content: str,
    summary: str,
    username: str = None,
    message_id: int = None
) -> bool:
    """
    Index URL content to knowledge base (called by indexing worker).

    Args:
        topic: Topic namespace
        url: Original URL
        content: Full scraped content
        summary: Summary of content
        username: User who shared it
        message_id: Database message ID

    Returns:
        True if successful
    """
    try:
        # Format content for indexing
        formatted_content = f"""
URL: {url}
Summary: {summary}

Full Content:
{content[:10000]}
"""

        retriever = get_retriever()
        retriever.index(
            content=formatted_content,
            topic=topic,
            source_type="url",
            source_url=url,
            metadata={
                "username": username,
                "message_id": message_id,
                "summary": summary
            }
        )

        logger.info(f"Indexed URL to '{topic}': {url[:50]}...")
        return True

    except Exception as e:
        logger.error(f"Error indexing URL: {e}", exc_info=True)
        return False
