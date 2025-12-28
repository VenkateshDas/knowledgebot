#!/usr/bin/env python3
"""
Test MiniMax M2.1 function calling with proper configuration.
"""

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from dotenv import load_dotenv
load_dotenv()

from agents.general_agent import GeneralAgent

def test_minimax_configuration():
    """Test that MiniMax M2.1 is properly configured."""

    print("=" * 80)
    print("MINIMAX M2.1 CONFIGURATION TEST")
    print("=" * 80)
    print()

    # Create agent
    print("Creating General Agent with MiniMax M2.1...")
    agent = GeneralAgent(user_id=12345, chat_id=67890)

    # Check model configuration
    print(f"✅ Agent created: {agent.name}")
    print(f"   Model ID: {agent.model.id}")

    # Check if reasoning_effort is configured
    if hasattr(agent.model, 'reasoning_effort'):
        print(f"   Reasoning effort: {agent.model.reasoning_effort}")
    else:
        print(f"   Reasoning effort: Not configured")

    print()

    # Test function calling with weather query
    print("Testing function calling with weather query...")
    print("-" * 80)
    query = "What is the current weather in Berlin, Germany?"
    print(f"Query: {query}")
    print()
    print("⏳ Processing (this may take a moment)...")
    print()

    response = agent.run(query)

    print("-" * 80)
    print("RESPONSE:")
    print("=" * 80)
    print(response)
    print("=" * 80)
    print()

    # Check if response contains real data
    has_apology = "I apologize" in response or "unable to" in response.lower()
    has_technical_issue = "technical" in response.lower() and "issue" in response.lower()

    if has_apology or has_technical_issue:
        print("❌ FAIL: Agent did not use web_search successfully")
        print("   The agent should have called web_search() for current weather")
        return False
    else:
        print("✅ PASS: Agent appears to have successfully used web_search")
        return True

if __name__ == "__main__":
    print()
    success = test_minimax_configuration()
    print()

    if success:
        print("🎉 MiniMax M2.1 is properly configured for function calling!")
    else:
        print("⚠️  MiniMax M2.1 function calling test failed")
        print("   Check logs above for details")
