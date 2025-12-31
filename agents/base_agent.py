"""
Base agent class providing common functionality for all specialized agents.

All agents inherit from this class to get:
- Session management
- Common tool registration
- Agno agent creation and configuration
"""

import logging
from typing import List, Optional
from datetime import datetime

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openrouter import OpenRouter

from core.config import config
from tools.common_tools import web_search, web_scrape
from tools.rag_tools import knowledge_retrieve, knowledge_index, set_rag_context, clear_rag_context

logger = logging.getLogger(__name__)


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
    Get minimal instructions about available tools.

    Tools are self-documenting via docstrings, so we only provide
    critical behavioral guidance here to reduce token usage.

    Returns:
        Minimal tool usage guidance
    """
    return """
TOOL USAGE GUIDELINES:
- web_search: Use for ANY question needing current info. Always use ENGLISH queries.
- web_scrape: Use whenever user provides a URL.
- knowledge_retrieve: Use when user references past conversations or asks "remember when..."
- knowledge_index: Only for HIGH-VALUE user insights/decisions/goals. Be selective.

CRITICAL: If uncertain, search rather than guess. Use tools proactively.
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
            db_file=config.db_path,
            session_table=f"{topic_name.lower().replace(' ', '_')}_agent_sessions"
        )

        # Create model with OpenRouter
        model_params = {
            "id": config.openrouter_model,
        }

        # Add reasoning support for MiniMax models (if using MiniMax)
        if "minimax" in config.openrouter_model.lower():
            model_params["reasoning_effort"] = "medium"  # Balance between quality and speed
            logger.info("Configured MiniMax model with reasoning_effort=medium for interleaved thinking")

        self.model = OpenRouter(**model_params)
        logger.info(f"Configured agent with model: {config.openrouter_model}")

        # Agent will be created lazily
        self._agent: Optional[Agent] = None

    def get_tools(self) -> List:
        """
        Get tools available to this agent.

        Base implementation provides common tools (web search, web scraping, knowledge base).
        Subclasses can override to add specialized tools.

        Returns:
            List of tool functions
        """
        return [web_search, web_scrape, knowledge_retrieve, knowledge_index]

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

    def run(self, message: str, thread_id: Optional[int] = None, message_id: Optional[int] = None) -> str:
        """
        Process a message and generate response.

        Args:
            message: User message text
            thread_id: Optional thread ID (unused - Agno handles context via session)
            message_id: Optional database message ID for RAG context

        Returns:
            Agent response text
        """
        try:
            # Set RAG context for knowledge_index tool
            if message_id:
                set_rag_context(
                    topic_name=self.topic_name,
                    username=f"user_{self.user_id}",
                    timestamp=datetime.now().isoformat(),
                    message_id=message_id,
                    user_message=message
                )

            logger.info(f"{self.name}: Processing message (session: {self.session_id})")

            # Run agent (Agno handles conversation history via add_history_to_context)
            response = self.agent.run(message)

            # Extract content
            if hasattr(response, 'content'):
                result = response.content.strip() if response.content else ""
            elif isinstance(response, str):
                result = response.strip()
            else:
                logger.warning(f"Unexpected response format: {type(response)}")
                result = str(response).strip()

            # Debug logging for empty responses
            if not result:
                logger.error("Agent returned EMPTY response!")
                logger.error(f"Model: {config.openrouter_model}")
                logger.error(f"Response type: {type(response)}")

                if hasattr(response, 'content'):
                    logger.error(f"Content value: {repr(response.content)}")

                # Return a fallback message instead of empty string
                result = "I apologize, I encountered an issue generating a response. Please try rephrasing your question or try again."

            # Clear RAG context
            clear_rag_context()

            return result

        except Exception as e:
            logger.error(f"{self.name} failed to process message: {e}", exc_info=True)
            clear_rag_context()  # Clear context even on error
            return "I encountered an error processing your message. Please try again."

    def clear_memory(self) -> bool:
        """
        Clear agent's session memory.

        Returns:
            True if successful, False otherwise
        """
        from core.database import db_session

        try:
            table_name = f"{self.topic_name.lower().replace(' ', '_')}_agent_sessions"

            with db_session() as cur:
                cur.execute(f"""
                    DELETE FROM {table_name}
                    WHERE session_id = ?
                """, (self.session_id,))
                rows_deleted = cur.rowcount

            logger.info(f"Cleared memory for {self.name} ({rows_deleted} rows)")
            self._agent = None  # Reset agent instance
            return True

        except Exception as e:
            logger.error(f"Failed to clear memory: {e}")
            return False
