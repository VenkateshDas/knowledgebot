"""
RAG Tools - Knowledge base tools for agents.

Provides two tools:
1. knowledge_retrieve: Query the knowledge base
2. knowledge_index: Add user messages to knowledge base (selective)
"""

import logging
import asyncio
import concurrent.futures
from contextvars import ContextVar
from typing import List, Optional
from datetime import datetime, UTC
from dataclasses import dataclass

from core.database import db_session
from lightrag_manager import get_lightrag_manager

logger = logging.getLogger(__name__)

# Reference to the main event loop (set by set_main_loop at bot startup)
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """
    Set the main event loop reference.

    Must be called from the main thread during bot initialization.
    This allows tools running in executor threads to schedule async work
    back to the main loop where asyncpg pools are bound.

    Args:
        loop: The main event loop
    """
    global _main_loop
    _main_loop = loop
    logger.info("Main event loop reference set for RAG tools")


def get_main_loop() -> Optional[asyncio.AbstractEventLoop]:
    """Get the main event loop reference."""
    return _main_loop


def run_async(coro, timeout: float = 60.0):
    """
    Run an async coroutine from a sync context (thread-safe).

    Uses asyncio.run_coroutine_threadsafe() to schedule the coroutine
    in the main event loop, avoiding "attached to different loop" errors
    with asyncpg connection pools.

    Args:
        coro: Coroutine to run
        timeout: Maximum time to wait for result (seconds)

    Returns:
        Result of the coroutine

    Raises:
        RuntimeError: If main loop not set
        TimeoutError: If operation takes too long
    """
    global _main_loop

    if _main_loop is None:
        # Fallback: try to get running loop (may fail in thread)
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # We're in an async context, just run it
                raise RuntimeError("Cannot call run_async from async context - use await directly")
        except RuntimeError:
            pass

        # Last resort: create new event loop (may cause issues with asyncpg)
        logger.warning("Main loop not set, falling back to new event loop (may cause issues with production storage)")
        return asyncio.run(coro)

    # Schedule coroutine in main loop and wait for result
    future = asyncio.run_coroutine_threadsafe(coro, _main_loop)

    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.error(f"Async operation timed out after {timeout}s")
        future.cancel()
        raise TimeoutError(f"Operation timed out after {timeout}s")


@dataclass
class RAGContext:
    """Thread-safe context for RAG operations."""
    topic_name: str
    username: str
    timestamp: str
    message_id: int
    user_message: str


# Thread-safe context variable (instead of global dict)
_rag_context: ContextVar[Optional[RAGContext]] = ContextVar('rag_context', default=None)


def set_rag_context(
    topic_name: str,
    username: str,
    timestamp: str,
    message_id: int,
    user_message: str
):
    """
    Set context for RAG tools (called by agent before run()).

    Thread-safe implementation using contextvars.

    Args:
        topic_name: Current topic name
        username: Username who sent the message
        timestamp: When the message was sent
        message_id: Database message ID
        user_message: The actual user message text
    """
    context = RAGContext(
        topic_name=topic_name,
        username=username,
        timestamp=timestamp,
        message_id=message_id,
        user_message=user_message
    )
    _rag_context.set(context)


def get_rag_context() -> Optional[RAGContext]:
    """Get the current RAG context (thread-safe)."""
    return _rag_context.get()


def clear_rag_context():
    """Clear RAG context after agent execution."""
    _rag_context.set(None)


def knowledge_retrieve(query: str) -> str:
    """
    Retrieve relevant information from the knowledge base.

    WHEN TO USE:
    - User asks a question about past content
    - Need to recall previously shared URLs or insights
    - User says "remember when..." or "what did I say about..."
    - Context from previous sessions would help your response

    Args:
        query: Search query (user's question)

    Returns:
        Relevant context from knowledge base with sources

    Example:
        User: "What was that article about AI agents you showed me?"

        knowledge_retrieve("article about AI agents")

        Returns:
        "Retrieved from knowledge base:

        [URL]: https://example.com/ai-agents-2025
        [Summary]: Article discusses how AI agents are evolving...

        Sources:
        1. URL: https://example.com/ai-agents-2025"
    """
    try:
        # Get context (thread-safe)
        context = get_rag_context()
        if not context or not context.topic_name:
            return "Error: Unable to retrieve - topic context not set."

        topic_name = context.topic_name
        logger.info(f"Retrieving from knowledge base for topic '{topic_name}': {query}")

        # Get LightRAG manager
        manager = get_lightrag_manager()

        # Run async query in main event loop (required for asyncpg pools)
        result = run_async(
            manager.query(topic_name=topic_name, query=query)
        )

        # Return formatted context
        return result["context"]

    except TimeoutError:
        logger.error("Knowledge retrieval timed out")
        return "Error: Knowledge base query timed out. Please try again."
    except Exception as e:
        logger.error(f"Error in knowledge_retrieve: {e}", exc_info=True)
        return f"Error retrieving from knowledge base: {str(e)}"


def knowledge_index(
    content: str,
    content_type: str = "insight",
    tags: Optional[List[str]] = None
) -> str:
    """
    Add current user message to knowledge base.

    WHEN TO USE:
    - User shares valuable information, insights, or decisions
    - User provides personal context (preferences, goals, constraints)
    - User shares experiences or lessons learned
    - Content has future reference value

    WHEN NOT TO USE:
    - Simple questions ("What's the weather?")
    - Casual chat ("Thanks!", "OK", "Hmm")
    - Commands or requests without info
    - Content already captured in a URL

    Args:
        content: The user's message to index (or extracted key info)
        content_type: Type of content - "insight", "decision", "preference",
                      "experience", "goal", "constraint"
        tags: Optional tags for categorization (e.g., ["health", "exercise"])

    Returns:
        Confirmation message

    Examples:
        User: "I've decided to focus on health tracking features first because
               user feedback shows it's the #1 requested feature."

        knowledge_index(
            content="Focus on health tracking features first - #1 user request",
            content_type="decision",
            tags=["product", "prioritization", "user-feedback"]
        )

        Returns: "Added to knowledge base as 'decision' with tags: product, prioritization, user-feedback"

        ---

        User: "I've found that I sleep better when I exercise in the morning."

        knowledge_index(
            content="Sleep quality improves with morning exercise",
            content_type="insight",
            tags=["health", "sleep", "exercise"]
        )

        Returns: "Added to knowledge base as 'insight' with tags: health, sleep, exercise"
    """
    try:
        # Get context (thread-safe)
        context = get_rag_context()
        if not context:
            return "Error: Unable to index - context not set properly."

        topic_name = context.topic_name
        username = context.username
        timestamp = context.timestamp
        message_id = context.message_id

        if not all([topic_name, username, timestamp, message_id]):
            return "Error: Unable to index - context not set properly."

        # Validate content_type
        valid_types = ["insight", "decision", "preference", "experience", "goal", "constraint"]
        if content_type not in valid_types:
            logger.warning(f"Invalid content_type '{content_type}', using 'insight'")
            content_type = "insight"

        logger.info(f"Indexing user message for topic '{topic_name}': {content_type}")

        # Get LightRAG manager
        manager = get_lightrag_manager()

        # Run async indexing in main event loop (required for asyncpg pools)
        success = run_async(
            manager.index_user_message(
                topic_name=topic_name,
                message=content,
                username=username,
                timestamp=timestamp,
                content_type=content_type,
                tags=tags or []
            )
        )

        if not success:
            return "Error: Failed to index to knowledge base."

        # Mark in database
        try:
            with db_session() as cur:
                cur.execute(
                    """UPDATE messages
                       SET indexed_to_rag = 1,
                           indexed_at = ?,
                           indexed_by = ?
                       WHERE id = ?""",
                    (datetime.now(UTC).isoformat(), "agent_decision", message_id)
                )
            logger.info(f"Marked message {message_id} as indexed in database")
        except Exception as db_error:
            logger.error(f"Failed to update database: {db_error}")
            # Continue anyway - the content is indexed in LightRAG

        # Format confirmation
        tag_str = f" with tags: {', '.join(tags)}" if tags else ""
        return f"Added to knowledge base as '{content_type}'{tag_str}"

    except TimeoutError:
        logger.error("Knowledge indexing timed out")
        return "Error: Knowledge base indexing timed out. Please try again."
    except Exception as e:
        logger.error(f"Error in knowledge_index: {e}", exc_info=True)
        return f"Error indexing to knowledge base: {str(e)}"
