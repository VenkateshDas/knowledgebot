"""
Common tools available to all agents.

Provides web search and web scraping capabilities using OpenRouter API,
Firecrawl, and Jina Reader as fallback.
"""

import re
import logging
import requests
from typing import Optional
from collections import OrderedDict
from threading import Lock

from core.config import config
from core.database import save_to_scrape_cache, get_from_scrape_cache
from core.llm_client import get_openai_client

logger = logging.getLogger(__name__)


class LRUCache:
    """Thread-safe LRU cache with configurable max size."""

    def __init__(self, max_size: int = 100):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.lock = Lock()

    def get(self, key: str) -> Optional[dict]:
        """Get item from cache, moving it to end (most recent)."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
            return None

    def set(self, key: str, value: dict) -> None:
        """Set item in cache, evicting oldest if at capacity."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.max_size:
                    # Remove oldest (first) item
                    oldest_key = next(iter(self.cache))
                    del self.cache[oldest_key]
                    logger.debug(f"Evicted oldest cache entry: {oldest_key}")
            self.cache[key] = value

    def __contains__(self, key: str) -> bool:
        with self.lock:
            return key in self.cache


# LRU cache for scraped content (replaces unbounded dict)
_scraped_content_cache = LRUCache(max_size=config.scrape_cache_max_size)


def web_search(query: str, max_results: int = 6) -> str:
    """
    Perform a real web search using Parallel AI Search API.

    Uses Parallel AI's purpose-built search API for AI agents with:
    - Real-time web search results
    - Agentic mode for fast, token-efficient responses
    - High-quality excerpts and source URLs

    Args:
        query: Search query or objective (natural language)
        max_results: Maximum number of results to return (default: 6)

    Returns:
        Formatted search results with excerpts and sources
    """
    if not config.parallel_api_key:
        logger.error("Parallel API key not configured")
        return "Error: PARALLEL_API_KEY not configured in environment variables."

    try:
        logger.info(f"Performing Parallel AI web search for: {query}")

        # Parallel AI Search API endpoint
        search_url = "https://api.parallel.ai/v1beta/search"

        headers = {
            "x-api-key": config.parallel_api_key,
            "Content-Type": "application/json",
            "parallel-beta": "search-extract-2025-10-10"  # Required beta version header
        }

        payload = {
            "objective": query,
            "mode": "agentic",  # Fast, token-efficient mode for agents
            "max_results": max_results,
            "max_chars_per_result": 800  # Balanced excerpt length
        }

        # Make API request with timeout
        response = requests.post(
            search_url,
            json=payload,
            headers=headers,
            timeout=15  # 15 second timeout for fast responses
        )

        if response.status_code != 200:
            error_msg = f"Parallel AI API error: {response.status_code}"
            logger.error(f"{error_msg} - {response.text}")
            return f"Error: {error_msg}"

        data = response.json()

        # Extract results
        results = data.get("results", [])

        if not results:
            logger.warning(f"No search results found for: {query}")
            return f"No search results found for query: {query}"

        # Format results for agent consumption
        formatted_output = []
        formatted_output.append(f"Web search results for: {query}\n")

        for idx, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            excerpts = result.get("excerpts", [])
            publish_date = result.get("publish_date", "")

            # Build result entry
            formatted_output.append(f"\n[{idx}] {title}")
            formatted_output.append(f"URL: {url}")

            if publish_date:
                formatted_output.append(f"Published: {publish_date}")

            # Add excerpts (already optimized by Parallel AI)
            if excerpts:
                formatted_output.append("Key excerpts:")
                for excerpt in excerpts[:3]:  # Top 3 excerpts per result
                    # Handle both dict and string excerpt formats
                    if isinstance(excerpt, dict):
                        excerpt_text = excerpt.get("text", "").strip()
                    elif isinstance(excerpt, str):
                        excerpt_text = excerpt.strip()
                    else:
                        continue

                    if excerpt_text:
                        # Clean and format excerpt
                        formatted_output.append(f"  - {excerpt_text}")

        result_text = "\n".join(formatted_output)

        logger.info(f"Successfully retrieved {len(results)} search results for: {query}")
        return result_text

    except requests.exceptions.Timeout:
        logger.error(f"Web search timeout for: {query}")
        return "Error: Search request timed out. Please try again."

    except requests.exceptions.RequestException as e:
        logger.error(f"Web search request failed: {e}")
        return f"Error: Network request failed - {str(e)}"

    except Exception as e:
        logger.error(f"Unexpected error in web search: {e}", exc_info=True)
        return f"Error performing search: {str(e)}"


def scrape_with_jina(url: str) -> Optional[str]:
    """
    Scrape web content using Jina Reader API.

    Args:
        url: URL to scrape

    Returns:
        Scraped content as markdown, or None if failed
    """
    try:
        logger.info(f"Scraping with Jina Reader: {url}")
        jina_url = f"https://r.jina.ai/{url}"
        response = requests.get(jina_url, timeout=30)

        if response.status_code == 200:
            content = response.text

            # For LinkedIn, extract the main content after the login page noise
            if "linkedin.com" in url and "Markdown Content:" in content:
                # Find where the actual content starts
                start_idx = content.find("Markdown Content:")
                if start_idx != -1:
                    content = content[start_idx + len("Markdown Content:"):]
                    logger.info("Extracted LinkedIn content after login page")

            return content
        else:
            logger.error(f"Jina Reader failed: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error in Jina scraping: {e}")
        return None


def scrape_with_firecrawl(url: str) -> Optional[str]:
    """
    Scrape web content using Firecrawl API.

    Args:
        url: URL to scrape

    Returns:
        Scraped content as markdown, or None if failed
    """
    if not config.firecrawl_api_key:
        return None

    try:
        logger.info(f"Scraping with Firecrawl: {url}")
        scrape_url = "https://api.firecrawl.dev/v1/scrape"
        headers = {
            "Authorization": f"Bearer {config.firecrawl_api_key}",
            "Content-Type": "application/json"
        }
        payload = {"url": url}

        response = requests.post(scrape_url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get("data", {}).get("markdown", "")

        logger.warning(f"Firecrawl failed for {url}")
        return None

    except Exception as e:
        logger.error(f"Firecrawl error: {e}")
        return None


def get_scraped_content(url: str) -> Optional[dict]:
    """
    Get cached scraped content for a URL.

    Checks in-memory cache first, then database.

    Args:
        url: URL to lookup

    Returns:
        Cached content dict or None
    """
    # Check in-memory LRU cache first
    cached = _scraped_content_cache.get(url)
    if cached:
        return cached

    # Check database cache
    db_cache = get_from_scrape_cache(url)
    if db_cache:
        # Populate in-memory cache for faster subsequent access
        _scraped_content_cache.set(url, db_cache)
        return db_cache

    return None


def web_scrape(url: str) -> str:
    """
    Scrape and summarize web content.

    Uses Firecrawl as primary method, falls back to Jina Reader.
    Always uses Jina for LinkedIn URLs.

    Caches full content for later indexing by the RAG worker.

    Args:
        url: URL to scrape

    Returns:
        Summary text for agent consumption (full content cached internally)
    """
    if not url:
        return "Error: No URL provided."

    if not config.openrouter_api_key:
        return "Error: OpenRouter API key not configured."

    markdown_content = None

    # Use Jina for LinkedIn, otherwise try Firecrawl first
    if "linkedin.com" in url:
        markdown_content = scrape_with_jina(url)
    else:
        markdown_content = scrape_with_firecrawl(url)
        if not markdown_content:
            markdown_content = scrape_with_jina(url)

    if not markdown_content:
        return "Error: Failed to scrape content from URL."

    # Summarize with LLM
    try:
        client = get_openai_client()
        completion = client.chat.completions.create(
            model=config.openrouter_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert summarizer. Create a concise, information-dense summary.\n"
                        "Format as 5-10 bullet points maximum.\n"
                        "Use PLAIN TEXT only - no markdown formatting.\n"
                        "Start each bullet with a dash (-) or bullet (•).\n"
                        "Focus on key insights and actionable information."
                    )
                },
                {
                    "role": "user",
                    "content": markdown_content[:50000]
                }
            ]
        )

        summary = completion.choices[0].message.content
        summary_text = f"Summary of {url}:\n\n{summary}"

        # Cache full content for indexing worker (both in-memory LRU cache and database)
        cache_data = {
            "summary": summary_text,
            "full_content": markdown_content,
            "url": url
        }
        _scraped_content_cache.set(url, cache_data)

        # Persist to database for cross-restart persistence
        save_to_scrape_cache(url, summary_text, markdown_content)

        logger.info(f"Successfully scraped and summarized: {url}")
        return summary_text

    except Exception as e:
        logger.error(f"Error in summary generation: {e}")

        # Cache even if summary fails (both in-memory and database)
        error_summary = f"Error summarizing content: {str(e)}"
        cache_data = {
            "summary": error_summary,
            "full_content": markdown_content,
            "url": url
        }
        _scraped_content_cache.set(url, cache_data)

        # Persist to database
        save_to_scrape_cache(url, error_summary, markdown_content)

        return error_summary


def extract_url_from_text(text: str) -> Optional[str]:
    """
    Extract the first URL from text.

    Args:
        text: Text to search for URLs

    Returns:
        First URL found, or None
    """
    if not text:
        return None

    url_pattern = r'(https?://[^\s]+)'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None
