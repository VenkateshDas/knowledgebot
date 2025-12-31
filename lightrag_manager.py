"""
LightRAG Manager - Manages per-topic knowledge base instances.

Handles:
- Per-topic LightRAG instance initialization
- URL content indexing (automatic)
- User message indexing (agent-driven)
- Knowledge retrieval with source tracking

Supports two modes:
- Development: File-based storage (JSON, NetworkX, NanoVectorDB)
- Production: Database storage (PostgreSQL + Neo4j) - Zero-cost with Supabase + Neo4j Aura Free
"""

import logging
import asyncio
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import json

from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc

from core.config import config

logger = logging.getLogger(__name__)

# Import production storage backends if in production mode
if config.lightrag_production:
    try:
        from config.lightrag_production import (
            get_kv_storage,
            get_vector_storage,
            get_graph_storage,
            get_doc_status_storage,
            validate_config
        )
        logger.info("Production storage backends loaded successfully")
    except ImportError as e:
        logger.error(
            f"Failed to import production storage backends: {e}\n"
            "Install dependencies: uv sync --extra production"
        )
        raise

# Known topics for pre-initialization
KNOWN_TOPICS = [
    "Journal", "Health", "Wealth", "Rants",
    "Ideas", "AI Engineering", "Career", "General"
]


class LightRAGManager:
    """
    Manages per-topic LightRAG instances for knowledge indexing and retrieval.

    Each topic (Journal, Health, Wealth, etc.) gets its own isolated knowledge base.
    """

    def __init__(self, working_dir: str = None):
        """
        Initialize LightRAG manager.

        Args:
            working_dir: Base directory for storing RAG data (only used in dev mode)
        """
        self.production_mode = config.lightrag_production
        self.working_dir = Path(working_dir or config.lightrag_working_dir)

        # Shared cache for LightRAG instances (NOT thread-local anymore)
        # Since we use run_coroutine_threadsafe, all async operations run in main loop
        self._rag_instances: Dict[str, LightRAG] = {}
        self._initialization_lock = asyncio.Lock()
        self._initialized = False

        if self.production_mode:
            # Validate production configuration
            try:
                validate_config()
                logger.info("✅ LightRAG Manager initialized in PRODUCTION mode (Supabase + Neo4j)")
            except ValueError as e:
                logger.error(f"❌ Production configuration invalid: {e}")
                raise
        else:
            # Development mode - use file storage
            self.working_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"⚙️  LightRAG Manager initialized in DEVELOPMENT mode (file-based)")
            logger.info(f"   Working directory: {self.working_dir}")

    def _get_topic_dir(self, topic_name: str) -> Path:
        """
        Get storage directory for a specific topic.

        Args:
            topic_name: Name of the topic

        Returns:
            Path to topic directory
        """
        # Sanitize topic name for filesystem
        safe_name = topic_name.lower().replace(" ", "_").replace("/", "_")
        topic_dir = self.working_dir / safe_name
        topic_dir.mkdir(parents=True, exist_ok=True)
        return topic_dir

    async def _create_llm_func(self):
        """Create LLM function for LightRAG using OpenRouter."""
        async def llm_model_func(
            prompt, system_prompt=None, history_messages=[], **kwargs
        ) -> str:
            return await openai_complete_if_cache(
                config.lightrag_llm_model,
                prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                api_key=config.openrouter_api_key,
                base_url=config.openrouter_base_url,
                **kwargs
            )
        return llm_model_func

    async def _create_embedding_func(self):
        """Create embedding function for LightRAG using OpenRouter."""
        async def embedding_func(texts: List[str]) -> List[List[float]]:
            return await openai_embed(
                texts,
                model=config.lightrag_embedding_model,
                api_key=config.openrouter_api_key,
                base_url=config.openrouter_base_url
            )
        return EmbeddingFunc(
            embedding_dim=1536,  # text-embedding-3-small dimension
            max_token_size=8192,
            func=embedding_func
        )

    async def get_rag_for_topic(self, topic_name: str) -> LightRAG:
        """
        Get or create LightRAG instance for a topic.

        Uses shared cache - all instances are reused across calls.

        Args:
            topic_name: Name of the topic

        Returns:
            LightRAG instance for the topic
        """
        # Fast path: check cache without lock
        if topic_name in self._rag_instances:
            return self._rag_instances[topic_name]

        # Slow path: initialize with lock
        async with self._initialization_lock:
            # Double-check after acquiring lock
            if topic_name in self._rag_instances:
                return self._rag_instances[topic_name]

            logger.info(f"Initializing LightRAG instance for topic: {topic_name}")

            # Create LLM and embedding functions
            llm_func = await self._create_llm_func()
            embedding_func = await self._create_embedding_func()

            if self.production_mode:
                # Production: Use database storage (Supabase + Neo4j)
                logger.info(f"  Using production storage backends for '{topic_name}'")

                # Create dummy working directory (required by LightRAG even with custom storage)
                dummy_dir = self.working_dir / f"_prod_{topic_name}"
                dummy_dir.mkdir(parents=True, exist_ok=True)

                # Use workspace for topic isolation
                workspace = f"telegram_bot_{topic_name}"

                rag = LightRAG(
                    working_dir=str(dummy_dir),  # Required but not used with database storage
                    llm_model_func=llm_func,
                    embedding_func=embedding_func,
                    workspace=workspace,  # Topic isolation via workspace
                    kv_storage="PGKVStorage",  # PostgreSQL KV storage
                    vector_storage="PGVectorStorage",  # pgvector storage
                    graph_storage="Neo4JStorage",  # Neo4j graph storage
                    doc_status_storage="PGDocStatusStorage"  # PostgreSQL doc status
                )
            else:
                # Development: Use file storage (JSON, NetworkX, NanoVectorDB)
                topic_dir = self._get_topic_dir(topic_name)
                logger.info(f"  Using file storage: {topic_dir}")

                rag = LightRAG(
                    working_dir=str(topic_dir),
                    llm_model_func=llm_func,
                    embedding_func=embedding_func,
                )

            # Initialize storage
            await rag.initialize_storages()

            # Cache instance
            self._rag_instances[topic_name] = rag

            logger.info(f"✓ LightRAG instance created for topic: {topic_name}")
            return rag

    async def warm_up(self, topics: List[str] = None) -> None:
        """
        Pre-initialize LightRAG instances for faster first queries.

        Should be called during bot startup to avoid initialization delays.

        Args:
            topics: List of topic names to initialize. Defaults to KNOWN_TOPICS.
        """
        topics_to_init = topics or KNOWN_TOPICS

        logger.info(f"Warming up LightRAG instances for {len(topics_to_init)} topics...")

        # Initialize topics concurrently but with a limit to avoid overwhelming DB
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent initializations

        async def init_topic(topic: str):
            async with semaphore:
                try:
                    await self.get_rag_for_topic(topic)
                    logger.info(f"  ✓ Warmed up: {topic}")
                except Exception as e:
                    logger.error(f"  ✗ Failed to warm up {topic}: {e}")

        await asyncio.gather(*[init_topic(t) for t in topics_to_init])

        self._initialized = True
        logger.info(f"LightRAG warm-up complete. {len(self._rag_instances)} instances ready.")

    def is_warmed_up(self) -> bool:
        """Check if warm-up has completed."""
        return self._initialized

    async def index_url_content(
        self,
        topic_name: str,
        url: str,
        content: str,
        summary: str,
        timestamp: str,
        username: str = None,
        tags: List[str] = None
    ) -> bool:
        """
        Index scraped URL content (automatic indexing).

        Args:
            topic_name: Topic to index under
            url: Original URL
            content: Full scraped content (markdown)
            summary: LLM-generated summary
            timestamp: When the URL was shared
            username: User who shared the URL (optional)
            tags: Optional tags extracted from context

        Returns:
            True if successful, False otherwise
        """
        try:
            rag = await self.get_rag_for_topic(topic_name)

            # Format tags with hashtags for better entity extraction
            tags_line = ""
            if tags:
                tags_line = f"TAGS: #{' #'.join(tags)}\n"

            # Format content with prominent metadata for better extraction
            indexed_content = f"""
=== SCRAPED WEB CONTENT ===
SOURCE_TYPE: URL
URL: {url}
SHARED_BY: {username or 'unknown'}
TIMESTAMP: {timestamp}
{tags_line}
--- SUMMARY ---
{summary}

--- FULL CONTENT ---
{content[:15000]}
=== END CONTENT ===
"""

            # Index to LightRAG
            await rag.ainsert(indexed_content)

            logger.info(f"Indexed URL content to '{topic_name}': {url[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to index URL content: {e}", exc_info=True)
            return False

    async def index_user_message(
        self,
        topic_name: str,
        message: str,
        username: str,
        timestamp: str,
        content_type: str = "insight",
        tags: List[str] = None
    ) -> bool:
        """
        Index user message content (agent-driven, selective).

        Only called when agent decides the message has value.

        Args:
            topic_name: Topic to index under
            message: User message or extracted content
            username: User who sent the message
            timestamp: When the message was sent
            content_type: Type of content (insight, decision, preference, etc.)
            tags: Optional tags for categorization

        Returns:
            True if successful, False otherwise
        """
        try:
            rag = await self.get_rag_for_topic(topic_name)

            # Format tags
            tags_line = ""
            if tags:
                tags_line = f"TAGS: #{' #'.join(tags)}\n"

            # Format content with metadata for extraction
            indexed_content = f"""
=== USER MESSAGE ===
SOURCE_TYPE: USER_MESSAGE
CONTENT_TYPE: {content_type.upper()}
FROM: {username}
TIMESTAMP: {timestamp}
{tags_line}
--- CONTENT ---
{message}
=== END MESSAGE ===
"""

            # Index to LightRAG
            await rag.ainsert(indexed_content)

            logger.info(f"Indexed user message ({content_type}) to '{topic_name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to index user message: {e}", exc_info=True)
            return False

    async def query(
        self,
        topic_name: str,
        query: str,
        mode: str = None,
        top_k: int = None
    ) -> Dict:
        """
        Query the knowledge base for a topic.

        Args:
            topic_name: Topic to query
            query: Search query
            mode: Search mode (hybrid, local, global, naive) - defaults to config
            top_k: Number of results - defaults to config

        Returns:
            Dict with results, sources, and formatted context
        """
        try:
            rag = await self.get_rag_for_topic(topic_name)

            # Use configured defaults if not specified
            search_mode = mode or config.lightrag_default_mode
            k = top_k or config.lightrag_top_k

            logger.info(f"Querying topic '{topic_name}' with mode '{search_mode}': {query}")

            # Query LightRAG
            result = await rag.aquery(
                query,
                param=QueryParam(mode=search_mode, top_k=k)
            )

            # Extract sources (URLs and message types)
            sources = self._extract_sources(result)

            # Format for agent consumption
            formatted_context = self._format_results_for_agent(result, sources)

            return {
                "raw_result": result,
                "sources": sources,
                "context": formatted_context,
                "mode": search_mode,
                "query": query
            }

        except Exception as e:
            logger.error(f"Failed to query knowledge base: {e}", exc_info=True)
            return {
                "raw_result": "",
                "sources": [],
                "context": f"Error retrieving from knowledge base: {str(e)}",
                "mode": mode or config.lightrag_default_mode,
                "query": query
            }

    def _extract_sources(self, result: str) -> List[Dict]:
        """
        Extract source information from result.

        Args:
            result: Raw LightRAG result

        Returns:
            List of source dictionaries
        """
        sources = []

        # Handle None or empty results
        if not result:
            return sources

        # Look for URL patterns
        import re
        url_pattern = r'URL:\s*(https?://[^\s\n]+)'
        urls = re.findall(url_pattern, str(result))

        for url in urls:
            sources.append({
                "type": "url",
                "url": url.strip()
            })

        # Look for user messages
        user_pattern = r'SOURCE_TYPE:\s*USER_MESSAGE'
        if re.search(user_pattern, str(result)):
            sources.append({
                "type": "user_message"
            })

        return sources

    def _format_results_for_agent(self, result: str, sources: List[Dict]) -> str:
        """
        Format query results for agent consumption.

        Args:
            result: Raw LightRAG result
            sources: Extracted sources

        Returns:
            Formatted context string
        """
        if not result:
            return "No relevant information found in knowledge base."

        # Build context
        context_parts = ["Retrieved from knowledge base:\n"]
        context_parts.append(result)

        # Add source references
        if sources:
            context_parts.append("\n\nSources:")
            for i, source in enumerate(sources, 1):
                if source["type"] == "url":
                    context_parts.append(f"{i}. URL: {source['url']}")
                elif source["type"] == "user_message":
                    context_parts.append(f"{i}. Previous conversation")

        return "\n".join(context_parts)


# Global manager instance
_manager_instance: Optional[LightRAGManager] = None


def get_lightrag_manager() -> LightRAGManager:
    """
    Get global LightRAG manager instance (singleton).

    Returns:
        LightRAGManager instance
    """
    global _manager_instance

    if _manager_instance is None:
        _manager_instance = LightRAGManager()

    return _manager_instance


async def warm_up_lightrag(topics: List[str] = None) -> None:
    """
    Warm up LightRAG instances for faster queries.

    Call this during bot startup.

    Args:
        topics: Topics to pre-initialize. Defaults to known topics.
    """
    manager = get_lightrag_manager()
    await manager.warm_up(topics)
