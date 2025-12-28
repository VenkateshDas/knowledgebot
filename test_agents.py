"""
Test script for the agent router and specialized agents.

Verifies that all agents are properly configured and can respond to messages.
"""

import asyncio
import logging
from dotenv import load_dotenv
from agent_router import get_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


async def test_all_agents():
    """Test each agent with sample messages."""

    # Test data: (topic_name, test_message)
    test_cases = [
        ("Journal", "Had a challenging day at work today. Feeling overwhelmed with deadlines."),
        ("Health", "Started a new workout routine - 30 minutes of running every morning."),
        ("Wealth", "Tracked my spending this week. Spent $200 on groceries and $150 on dining out."),
        ("Rants", "So frustrated with the slow internet connection! It keeps dropping during calls."),
        ("Ideas", "What if we built a personal AI assistant that learns from your habits and proactively helps?"),
        ("AI Engineering", "Should I use LangGraph or build a custom agent orchestration? Working on a multi-step workflow."),
        ("Career", "Got a job offer with 20% higher salary but it's fully remote. Current job is hybrid with great team."),
        ("General", "What's the capital of France?"),
    ]

    # Mock user/chat IDs for testing
    test_user_id = 123456
    test_chat_id = 789012
    test_thread_id = 1

    router = get_router()

    print("=" * 80)
    print("AGENT ROUTER TEST")
    print("=" * 80)
    print()

    # List available agents
    agents_info = router.list_available_agents()
    print("Available Agents:")
    for topic, info in agents_info.items():
        print(f"  • {topic}: {info['name']} - {info['description']}")
    print()
    print("=" * 80)
    print()

    # Test each agent
    for topic_name, test_message in test_cases:
        print(f"Topic: {topic_name}")
        print(f"Message: {test_message}")
        print()

        try:
            # Route message
            response, _, _ = await router.route_message(
                topic_name=topic_name,
                user_id=test_user_id,
                chat_id=test_chat_id,
                thread_id=test_thread_id,
                text=test_message,
                message_id=None,  # No DB update in test
                categorize_func=None,  # Skip categorization in test
                update_categories_func=None
            )

            print(f"Response: {response}")
            print()
            print("-" * 80)
            print()

        except Exception as e:
            print(f"ERROR: {e}")
            logger.exception(f"Failed to test {topic_name}")
            print()
            print("-" * 80)
            print()

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


async def test_unknown_topic():
    """Test router fallback for unknown topics."""
    print("\n" + "=" * 80)
    print("UNKNOWN TOPIC TEST (should fallback to General agent)")
    print("=" * 80)
    print()

    router = get_router()

    response, _, _ = await router.route_message(
        topic_name="RandomUnknownTopic",
        user_id=123456,
        chat_id=789012,
        thread_id=1,
        text="This is a test message for an unknown topic.",
        message_id=None,
        categorize_func=None,
        update_categories_func=None
    )

    print(f"Topic: RandomUnknownTopic")
    print(f"Message: This is a test message for an unknown topic.")
    print()
    print(f"Response: {response}")
    print()
    print("=" * 80)


if __name__ == "__main__":
    print("\nStarting Agent Router Tests...\n")

    # Run tests
    asyncio.run(test_all_agents())
    asyncio.run(test_unknown_topic())

    print("\n✅ All tests completed!\n")
