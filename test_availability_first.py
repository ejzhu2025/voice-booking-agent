#!/usr/bin/env python3
"""Test that agent checks availability first when user asks about date+party size."""

import asyncio
from agents.booking_agent import BookingAgent


async def test_availability_first():
    """Test that agent checks availability before asking for time."""
    print("=" * 70)
    print("Testing: Check Availability FIRST")
    print("=" * 70)
    print()

    # Test 1: User asks "do you have a table for 3 tonight?"
    print("Test 1: User asks 'do you have a table for 3 tonight?'")
    print("-" * 70)
    agent = BookingAgent()
    print(f"Agent: {agent.get_greeting()}")
    print()

    print("You: do you have a table for 3 tonight?")
    response = await agent.process_message("do you have a table for 3 tonight?")
    print(f"Agent: {response}")
    print(f"Booking info: {agent.booking_info}\n")
    print()

    # Test 2: User asks "availability for 4 tomorrow?"
    print("Test 2: User asks 'availability for 4 tomorrow?'")
    print("-" * 70)
    agent = BookingAgent()
    print(f"Agent: {agent.get_greeting()}")
    print()

    print("You: do you have availability for 4 tomorrow?")
    response = await agent.process_message("do you have availability for 4 tomorrow?")
    print(f"Agent: {response}")
    print(f"Booking info: {agent.booking_info}\n")
    print()

    # Test 3: User says "table for 2 tonight"
    print("Test 3: User says 'table for 2 tonight'")
    print("-" * 70)
    agent = BookingAgent()
    print(f"Agent: {agent.get_greeting()}")
    print()

    print("You: I need a table for 2 tonight")
    response = await agent.process_message("I need a table for 2 tonight")
    print(f"Agent: {response}")
    print(f"Booking info: {agent.booking_info}\n")
    print()

    print("=" * 70)
    print("Expected: Agent should check availability and list available times")
    print("NOT ask 'what time would you like?'")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_availability_first())
