"""
Agent Router - Routes messages to appropriate specialized agents.

Implements the router-worker pattern where a central router directs
incoming messages to the appropriate specialized agent based on topic.
"""

import logging
import json
import asyncio
from typing import Optional, Tuple
from agents.journal_agent import JournalAgent
from agents.health_agent import HealthAgent
from agents.wealth_agent import WealthAgent
from agents.rants_agent import RantsAgent
from agents.ideas_agent import IdeasAgent
from agents.ai_engineering_agent import AIEngineeringAgent
from agents.career_agent import CareerAgent
from agents.general_agent import GeneralAgent

logger = logging.getLogger(__name__)


# Topic to Agent Class mapping
AGENT_REGISTRY = {
    "Journal": JournalAgent,
    "Health": HealthAgent,
    "Wealth": WealthAgent,
    "Rants": RantsAgent,
    "Ideas": IdeasAgent,
    "AI Engineering": AIEngineeringAgent,
    "Career": CareerAgent,
    "General": GeneralAgent,
}


class AgentRouter:
    """
    Routes messages to appropriate specialized agents.

    Uses simple topic-based routing: topic name → agent class.
    Falls back to General agent for unknown topics.
    """

    def __init__(self):
        """Initialize router with agent registry."""
        self.agent_registry = AGENT_REGISTRY
        logger.info(f"Router initialized with {len(self.agent_registry)} agents")

    def get_agent_for_topic(
        self,
        topic_name: str,
        user_id: int,
        chat_id: int
    ):
        """
        Get the appropriate agent instance for a topic.

        Args:
            topic_name: Name of the topic
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            Instantiated agent for the topic
        """
        # Normalize topic name
        topic_key = topic_name.strip()

        # Get agent class from registry, fallback to General
        agent_class = self.agent_registry.get(topic_key, GeneralAgent)

        # Instantiate and return
        agent = agent_class(user_id=user_id, chat_id=chat_id)
        logger.info(f"Routed '{topic_name}' → {agent.name}")

        return agent

    async def route_message(
        self,
        topic_name: str,
        user_id: int,
        chat_id: int,
        thread_id: Optional[int],
        text: str,
        message_id: int,
        categorize_func=None,
        update_categories_func=None
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Route a message to the appropriate agent and get response.

        Args:
            topic_name: Name of the topic
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            thread_id: Telegram thread ID
            text: Message text
            message_id: Database message ID
            categorize_func: Optional async categorization function (DEPRECATED - agent handles tagging)
            update_categories_func: Optional function to update categories in DB

        Returns:
            Tuple of (response_text, primary_category, secondary_tags_json)
        """
        try:
            logger.info(f"Routing message to topic: {topic_name}")

            # Get appropriate agent
            agent = self.get_agent_for_topic(topic_name, user_id, chat_id)

            # Get agent response (runs in executor to avoid blocking)
            # Agent handles categorization inline now - single call
            response_text = await asyncio.get_event_loop().run_in_executor(
                None,
                agent.run,
                text,
                thread_id
            )

            # Parse tags from agent response
            parsed_response, tags = self._parse_tags_from_response(response_text)

            # Save to database if function provided
            primary_category = topic_name  # Use topic as primary category
            secondary_tags_json = json.dumps(tags) if tags else None

            if update_categories_func and message_id:
                update_categories_func(message_id, primary_category, secondary_tags_json)

            logger.info(f"Successfully routed message to {agent.name}")
            return parsed_response, primary_category, secondary_tags_json

        except Exception as e:
            logger.error(f"Error routing message: {e}", exc_info=True)
            # Fallback response
            return (
                "I encountered an error processing your message. Please try again.",
                None,
                None
            )

    def _parse_tags_from_response(self, response_text: str) -> Tuple[str, list]:
        """
        Parse tags from agent response.

        Expected format:
        [Agent response]

        Tags: tag1, tag2, tag3

        Args:
            response_text: Agent's full response

        Returns:
            Tuple of (cleaned_response, tags_list)
        """
        import re

        # Look for "Tags:" line at the end
        tags_pattern = r'\n+Tags:\s*(.+?)$'
        match = re.search(tags_pattern, response_text, re.IGNORECASE | re.MULTILINE)

        if match:
            # Extract tags
            tags_text = match.group(1).strip()
            tags = [tag.strip() for tag in tags_text.split(',')]

            # Remove tags line from response
            cleaned_response = re.sub(tags_pattern, '', response_text, flags=re.IGNORECASE | re.MULTILINE).strip()

            # Format response with emoji tags
            formatted_response = f"{cleaned_response}\n\n📁 Tags: {', '.join(tags)}"

            logger.info(f"Parsed tags: {tags}")
            return formatted_response, tags
        else:
            logger.warning("No tags found in agent response")
            return response_text, []

    def _format_response(
        self,
        response_text: str,
        primary_category: Optional[str],
        secondary_tags_json: Optional[str]
    ) -> str:
        """
        Format the final response with agent reply and categories.

        DEPRECATED: Agent now handles tags inline.

        Args:
            response_text: Agent's response
            primary_category: Primary category
            secondary_tags_json: Secondary tags as JSON string

        Returns:
            Formatted response string
        """
        return response_text

    def list_available_agents(self) -> dict:
        """
        Get list of available agents and their descriptions.

        Returns:
            Dictionary mapping topic names to agent descriptions
        """
        agents_info = {}
        for topic_name, agent_class in self.agent_registry.items():
            # Create temporary instance to get description
            temp_agent = agent_class(user_id=0, chat_id=0)
            agents_info[topic_name] = {
                "name": temp_agent.name,
                "description": temp_agent.description
            }

        return agents_info


# Global router instance
_router_instance = None


def get_router() -> AgentRouter:
    """
    Get or create the global router instance.

    Returns:
        AgentRouter instance
    """
    global _router_instance
    if _router_instance is None:
        _router_instance = AgentRouter()
    return _router_instance
