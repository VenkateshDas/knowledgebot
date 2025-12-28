#!/usr/bin/env python3
"""
Verify that all agents have current date/time in their instructions.
"""

from agents.general_agent import GeneralAgent
from agents.ai_engineering_agent import AIEngineeringAgent
from agents.ideas_agent import IdeasAgent
from agents.wealth_agent import WealthAgent
from agents.health_agent import HealthAgent
from agents.career_agent import CareerAgent
from agents.rants_agent import RantsAgent
from agents.journal_agent import JournalAgent

# Test user/chat IDs
TEST_USER_ID = 12345
TEST_CHAT_ID = 67890

def verify_agent_datetime(agent_class, agent_name):
    """Check if an agent has datetime context in instructions."""
    print(f"\n{'='*80}")
    print(f"Testing: {agent_name}")
    print('='*80)

    # Create agent instance
    agent = agent_class(user_id=TEST_USER_ID, chat_id=TEST_CHAT_ID)

    # Check instructions
    instructions = agent.instructions

    # Look for datetime indicators
    has_today = "Today is" in instructions
    has_current_time = "Current time:" in instructions

    # Display first 300 characters
    print(f"\nFirst 300 characters of instructions:")
    print("-" * 80)
    print(instructions[:300])
    print("-" * 80)

    # Verification
    if has_today and has_current_time:
        print(f"✅ PASS: {agent_name} has date and time context")
        return True
    else:
        print(f"❌ FAIL: {agent_name} missing datetime context")
        print(f"   - Has 'Today is': {has_today}")
        print(f"   - Has 'Current time:': {has_current_time}")
        return False

def main():
    """Test all agents."""
    print("=" * 80)
    print("AGENT DATETIME VERIFICATION")
    print("=" * 80)

    agents = [
        (GeneralAgent, "General Agent"),
        (AIEngineeringAgent, "AI Engineering Agent"),
        (IdeasAgent, "Ideas Agent"),
        (WealthAgent, "Wealth Agent"),
        (HealthAgent, "Health Agent"),
        (CareerAgent, "Career Agent"),
        (RantsAgent, "Rants Agent"),
        (JournalAgent, "Journal Agent"),
    ]

    results = []
    for agent_class, name in agents:
        result = verify_agent_datetime(agent_class, name)
        results.append((name, result))

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} agents have datetime context")

    if passed == total:
        print("\n🎉 All agents are properly configured with date/time!")
    else:
        print(f"\n⚠️  {total - passed} agent(s) need fixing")

if __name__ == "__main__":
    main()
