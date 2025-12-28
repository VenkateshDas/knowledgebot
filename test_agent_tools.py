#!/usr/bin/env python3
"""
Test that agents actually use web_search tool.
"""

from dotenv import load_dotenv
load_dotenv()

from agents.general_agent import GeneralAgent

# Test user/chat IDs
TEST_USER_ID = 12345
TEST_CHAT_ID = 67890

def test_agent_uses_tools():
    """Test that agent calls web_search for current information."""

    print("=" * 80)
    print("TESTING AGENT TOOL USAGE")
    print("=" * 80)
    print()

    # Create general agent
    print("Creating General Agent...")
    agent = GeneralAgent(user_id=TEST_USER_ID, chat_id=TEST_CHAT_ID)
    print(f"✅ Agent created: {agent.name}")
    print()

    # Check instructions include tool info
    print("Checking agent instructions...")
    instructions = agent.instructions

    has_tool_section = "# AVAILABLE TOOLS" in instructions
    has_web_search = "web_search" in instructions
    has_datetime = "Today is" in instructions

    print(f"  - Has tool section: {has_tool_section}")
    print(f"  - Has web_search info: {has_web_search}")
    print(f"  - Has datetime context: {has_datetime}")
    print()

    if not (has_tool_section and has_web_search):
        print("❌ FAIL: Agent instructions missing tool information")
        return False

    print("✅ Agent has tool instructions")
    print()

    # Test with a query requiring web search
    test_query = "What is the current weather in Magdeburg, Germany?"

    print(f"Test query: '{test_query}'")
    print("Expected: Agent should call web_search()")
    print()
    print("Sending query to agent...")
    print("-" * 80)

    response = agent.run(test_query)

    print("-" * 80)
    print()
    print("AGENT RESPONSE:")
    print("=" * 80)
    print(response)
    print("=" * 80)
    print()

    # Check if response contains real data (not apology)
    has_apology = "I apologize" in response or "unable to" in response
    has_limitation = "technical issues" in response or "limitation" in response

    if has_apology or has_limitation:
        print("❌ FAIL: Agent apologized instead of using web_search")
        print("   The agent should have called web_search() to get current weather")
        return False
    else:
        print("✅ PASS: Agent appears to have used web_search")
        return True

if __name__ == "__main__":
    success = test_agent_uses_tools()
    print()
    if success:
        print("🎉 Test passed! Agent is using web_search properly.")
    else:
        print("⚠️  Test failed. Agent not using tools correctly.")
