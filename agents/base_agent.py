"""
Base agent class providing common functionality for all specialized agents.

All agents inherit from this class to get:
- Session management
- Context retrieval from database
- Common tool registration
- Agno agent creation and configuration
"""

import os
import sqlite3
import logging
from typing import List, Dict, Optional
from datetime import datetime
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openrouter import OpenRouter
from tools.common_tools import web_search, web_scrape

logger = logging.getLogger(__name__)

# Configuration
DB_PATH = "bot.db"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.1")


def get_current_datetime_context() -> str:
    """
    Get formatted current date and time for agent context.

    Returns:
        Formatted string with current day, date, and time
    """
    now = datetime.now()
    day_of_week = now.strftime("%A")
    date_str = now.strftime("%B %d, %Y")
    time_str = now.strftime("%I:%M %p")

    return f"Today is {day_of_week}, {date_str}. Current time: {time_str}."


def get_tool_instructions() -> str:
    """
    Get instructions about available tools for the agent.

    Returns:
        Formatted string describing available tools
    """
    return """
# AVAILABLE TOOLS

You have access to the following tools. Use them proactively when needed:

## web_search(query: str, max_results: int = 6) -> str
**Purpose**: Perform real-time web search using Parallel AI Search API.

**When to use**:
- Answering questions requiring current/real-time information
- Verifying factual claims, statistics, dates, version numbers
- Finding recent news, events, or developments
- Checking prices, rates, market data, weather
- User asks "what's the latest..." or references current events
- You detect uncertainty in your knowledge - ALWAYS search rather than guess

**How to use**: Call `web_search(query="your search query")`

**QUERY FORMULATION BEST PRACTICES**:

1. **Always use ENGLISH queries** - Even for non-English locations
   - ✅ GOOD: "current weather Berlin Germany today"
   - ❌ BAD: "Wetter Berlin heute" (German)

2. **For weather queries, ALWAYS include**:
   - Location name in English
   - "current" or "today" or "now"
   - Current date (you know today's date)
   - Example: "weather Paris France today December 24 2025"
   - Example: "current temperature Tokyo Japan right now"

3. **For financial/market data**:
   - Use ticker symbols when possible
   - Include "current price" or "latest"
   - Example: "Bitcoin price USD current December 2025"

4. **For news/events**:
   - Include the year/month
   - Use "latest" or "recent"
   - Example: "latest iPhone release 2025"

5. **Verify freshness of results**:
   - Check if search results contain dates
   - If results seem outdated (wrong month/season), try a different query
   - For weather: Temperature should match the season

**CRITICAL**:
- If a question requires current information, YOU MUST call web_search FIRST before responding
- Do not apologize for limitations - just use the tool
- If search results seem stale, reformulate your query and search again
- Use max_results=6 for better coverage

**Examples**:
- web_search(query="current weather Magdeburg Germany December 24 2025")
- web_search(query="latest AI developments December 2025")
- web_search(query="Bitcoin price USD today")

## web_scrape(url: str) -> str
**Purpose**: Scrape and summarize content from a specific URL.

**When to use**:
- User provides a URL in their message
- Need to extract content from a specific webpage
- Analyzing articles, documentation, or web pages

**How to use**: Call `web_scrape(url="https://example.com")`
Example: web_scrape(url="https://example.com/article")

**IMPORTANT**: Always use these tools when appropriate. They provide real, current information that enhances your responses.
"""


class BaseAgent:
    """
    Base class for all specialized agents.

    Provides common infrastructure for agent creation, context management,
    and tool registration.
    """

    def __init__(
        self,
        name: str,
        instructions: str,
        description: str,
        user_id: int,
        chat_id: int,
        topic_name: str
    ):
        """
        Initialize base agent.

        Args:
            name: Agent name
            instructions: System prompt/instructions for the agent
            description: Brief description of agent's role
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            topic_name: Topic name for session identification
        """
        self.name = name
        # Prepend dynamic date/time context and tool instructions
        datetime_context = get_current_datetime_context()
        tool_instructions = get_tool_instructions()
        self.instructions = f"{datetime_context}\n{tool_instructions}\n\n{instructions}"
        self.description = description
        self.user_id = user_id
        self.chat_id = chat_id
        self.topic_name = topic_name

        # Create session ID
        self.session_id = f"{topic_name.lower().replace(' ', '_')}_user_{user_id}_chat_{chat_id}"

        # Configure database
        self.db = SqliteDb(
            db_file=DB_PATH,
            session_table=f"{topic_name.lower().replace(' ', '_')}_agent_sessions"
        )

        # Create model with MiniMax M2.1 specific configuration
        # For MiniMax M2.1: Enable reasoning for interleaved thinking
        model_params = {
            "id": OPENROUTER_MODEL,
        }

        # Add reasoning support for MiniMax M2.1 (required for optimal function calling)
        if "minimax" in OPENROUTER_MODEL.lower():
            model_params["reasoning_effort"] = "medium"  # Balance between quality and speed
            logger.info(f"Configured MiniMax model with reasoning_effort=medium for interleaved thinking")

        self.model = OpenRouter(**model_params)

        # Agent will be created lazily
        self._agent: Optional[Agent] = None

    def get_context_messages(self, thread_id: int, limit: int = 10) -> List[Dict]:
        """
        Retrieve last N messages from this topic for context.

        Args:
            thread_id: Telegram thread/topic ID
            limit: Number of recent messages to retrieve

        Returns:
            List of message dictionaries with content and metadata
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT text, username, created_at, primary_category, secondary_tags
                FROM messages
                WHERE chat_id = ? AND thread_id = ? AND topic_name = ?
                AND text IS NOT NULL AND text != ''
                ORDER BY created_at DESC
                LIMIT ?
            """, (self.chat_id, thread_id, self.topic_name, limit))

            messages = cursor.fetchall()
            conn.close()

            # Format for context (oldest first)
            context = []
            for text, username, created_at, category, tags in reversed(messages):
                context.append({
                    "content": text,
                    "timestamp": created_at,
                    "username": username or "Unknown",
                    "category": category,
                    "tags": tags
                })

            logger.info(f"Retrieved {len(context)} context messages for {self.name}")
            return context

        except Exception as e:
            logger.error(f"Failed to retrieve context: {e}")
            return []

    def get_tools(self) -> List:
        """
        Get tools available to this agent.

        Base implementation provides common tools (web search, web scraping).
        Subclasses can override to add specialized tools.

        Returns:
            List of tool functions
        """
        return [web_search, web_scrape]

    def create_agent(self) -> Agent:
        """
        Create and configure the Agno agent instance.

        Returns:
            Configured Agno Agent
        """
        agent = Agent(
            name=self.name,
            model=self.model,
            instructions=self.instructions,
            description=self.description,

            # Memory and session
            add_history_to_context=True,
            num_history_runs=10,  # Last 10 message pairs
            session_id=self.session_id,
            db=self.db,

            # Tools
            tools=self.get_tools(),
            read_tool_call_history=True,  # Include tool calls in history

            # Response settings
            markdown=False,  # Plain text for Telegram compatibility
        )

        logger.info(f"Created agent: {self.name} (session: {self.session_id})")
        return agent

    @property
    def agent(self) -> Agent:
        """Lazy-load agent instance."""
        if self._agent is None:
            self._agent = self.create_agent()
        return self._agent

    def run(self, message: str, thread_id: Optional[int] = None) -> str:
        """
        Process a message and generate response.

        Args:
            message: User message text
            thread_id: Optional thread ID for context retrieval

        Returns:
            Agent response text
        """
        try:
            # Get context if thread_id provided (for additional info, not required by Agno)
            if thread_id:
                context = self.get_context_messages(thread_id)
                logger.info(f"{self.name}: Processing message with {len(context)} context messages")

            # Run agent
            response = self.agent.run(message)

            # Extract content
            if hasattr(response, 'content'):
                return response.content.strip()
            elif isinstance(response, str):
                return response.strip()
            else:
                logger.warning(f"Unexpected response format: {type(response)}")
                return str(response).strip()

        except Exception as e:
            logger.error(f"{self.name} failed to process message: {e}", exc_info=True)
            return f"I encountered an error processing your message. Please try again."

    def clear_memory(self) -> bool:
        """
        Clear agent's session memory.

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            table_name = f"{self.topic_name.lower().replace(' ', '_')}_agent_sessions"
            cursor.execute(f"""
                DELETE FROM {table_name}
                WHERE session_id = ?
            """, (self.session_id,))

            rows_deleted = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"Cleared memory for {self.name} ({rows_deleted} rows)")
            self._agent = None  # Reset agent instance
            return True

        except Exception as e:
            logger.error(f"Failed to clear memory: {e}")
            return False
