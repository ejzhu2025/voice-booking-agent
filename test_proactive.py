#!/usr/bin/env python3
"""Test proactive availability checking behavior."""

import asyncio
from agents.booking_agent import BookingAgent


async def test_proactive_behavior():
    """Test that agent immediately checks availability with defaults."""
    print("=" * 60)
    print("Testing Proactive Availability Checking")
    print("=" * 60)
    print()

    agent = BookingAgent()

    # Test 1: User says "6pm?" - should check availability with today + 2 people
    print("Test 1: User asks '6pm?'")
    print("-" * 60)
    print(f"Agent: {agent.get_greeting()}")
    print()

    user_input = "6pm?"
    print(f"You: {user_input}")
    response = await agent.process_message(user_input)
    print(f"\nAgent: {response}\n")
    print(f"Booking info captured: {agent.booking_info}")
    print()
    print()

    # Test 2: User says "table for 4 tomorrow at 7pm" - should check immediately
    agent.reset()
    print("Test 2: User says 'table for 4 tomorrow at 7pm'")
    print("-" * 60)
    print(f"Agent: {agent.get_greeting()}")
    print()

    user_input = "table for 4 tomorrow at 7pm"
    print(f"You: {user_input}")
    response = await agent.process_message(user_input)
    print(f"\nAgent: {response}\n")
    print(f"Booking info captured: {agent.booking_info}")
    print()
    print()

    # Test 3: User says "tomorrow?" - should ask for time (since no time given)
    agent.reset()
    print("Test 3: User asks 'tomorrow?'")
    print("-" * 60)
    print(f"Agent: {agent.get_greeting()}")
    print()

    user_input = "tomorrow?"
    print(f"You: {user_input}")
    response = await agent.process_message(user_input)
    print(f"\nAgent: {response}\n")
    print(f"Booking info captured: {agent.booking_info}")
    print()
    print()

    print("=" * 60)
    print("Tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_proactive_behavior())
