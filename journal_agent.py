"""
Compassionate Journal Listener Agent using Agno framework.

This module configures an empathetic AI agent that responds to journal entries
with psychological insight and compassion, while maintaining conversational memory.
"""

import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openrouter import OpenRouter
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Get configuration from environment
# Note: OPENROUTER_API_KEY should be set in .env file
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-3-flash-preview")
DB_FILE = "bot.db"

# Agent instructions - designed for empathetic psychological support
COMPASSIONATE_INSTRUCTIONS = """You are a warm, empathetic listener trained in psychology and compassionate communication.

Your role is to:
- Listen deeply and validate emotions without judgment
- Reflect back what you hear to show understanding
- Ask gentle, open-ended questions when appropriate (but not always)
- Recognize patterns and themes across journal entries
- Offer supportive insights, not solutions or advice
- Use a warm, conversational tone like a trusted friend
- Keep responses concise (2-4 sentences maximum)
- Never diagnose or provide medical advice
- Avoid clichés like "I'm sorry you're going through this"
- Be authentic and human in your responses

Remember: You're a companion for self-reflection, not a therapist. Your goal is to help the person feel heard, understood, and supported in their journaling practice.

When the person shares something:
- Acknowledge their feelings first
- Reflect what you understand
- Ask a gentle question to deepen reflection (optional, don't overdo it)
- Keep it brief and genuine

Example tone:
- "That sounds really challenging, especially the part about feeling unsupported. What's helping you get through it?"
- "I hear the frustration in that. Sometimes those moments really stick with us."
- "It makes sense you'd feel that way. How are you taking care of yourself through this?"
"""


def create_journal_agent(user_id: int, chat_id: int) -> Agent:
    """
    Create a configured Agno agent for compassionate journal listening.

    Args:
        user_id: Telegram user ID for session identification
        chat_id: Telegram chat ID for session identification

    Returns:
        Configured Agno Agent instance with memory and context management
    """

    # Create session ID combining user and chat
    session_id = f"user_{user_id}_chat_{chat_id}"

    # Configure SQLite database for agent sessions
    db = SqliteDb(
        db_file=DB_FILE,
        session_table="journal_agent_sessions"
    )

    # Create OpenRouter model instance
    model = OpenRouter(id=OPENROUTER_MODEL)

    # Create and configure the agent
    agent = Agent(
        name="Compassionate Journal Listener",
        model=model,
        instructions=COMPASSIONATE_INSTRUCTIONS,

        # Memory and session configuration
        add_history_to_context=True,  # Include chat history in context
        num_history_runs=10,  # Last 10 message pairs
        session_id=session_id,
        db=db,

        # Response settings
        markdown=False,  # Plain text for Telegram compatibility
    )

    logger.info(f"Created journal agent for session: {session_id}")
    return agent


def get_compassionate_response(user_id: int, chat_id: int, message: str) -> str:
    """
    Get a compassionate response from the journal agent.

    Args:
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        message: The journal entry text

    Returns:
        Compassionate response text

    Raises:
        Exception: If agent fails to generate response
    """
    try:
        agent = create_journal_agent(user_id, chat_id)

        # Run the agent with the message
        response = agent.run(message)

        # Extract the content from the response
        if hasattr(response, 'content'):
            return response.content.strip()
        elif isinstance(response, str):
            return response.strip()
        else:
            # Fallback if response format is unexpected
            logger.warning(f"Unexpected response format: {type(response)}")
            return str(response).strip()

    except Exception as e:
        logger.error(f"Failed to get compassionate response: {e}", exc_info=True)
        # Provide a graceful fallback
        return "Thank you for sharing. I'm here to listen."


# Test function for development
def test_agent():
    """Test the journal agent with sample entries."""
    user_id = 123456
    chat_id = 789012

    test_messages = [
        "Had a rough day at work today. My manager criticized my code in front of the team.",
        "Feeling better now. I talked to my manager privately and we cleared things up.",
        "Grateful for my team's support through this whole situation.",
    ]

    print("=== Testing Compassionate Journal Agent ===\n")

    for msg in test_messages:
        print(f"User: {msg}")
        response = get_compassionate_response(user_id, chat_id, msg)
        print(f"Agent: {response}\n")


if __name__ == "__main__":
    # Load environment variables if running standalone
    from dotenv import load_dotenv
    load_dotenv()

    # Run test
    test_agent()
