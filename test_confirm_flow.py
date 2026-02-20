#!/usr/bin/env python3
"""Test confirmation flow for date/time/party size."""

import asyncio
from agents.booking_agent import BookingAgent


async def test_scenarios():
    """Test different user input scenarios."""
    print("=" * 70)
    print("Testing Booking Confirmation Flow")
    print("=" * 70)
    print()

    # Test 1: User only says time "6pm?"
    print("Test 1: User says '6pm?' (only time)")
    print("-" * 70)
    agent = BookingAgent()
    print(f"Agent: {agent.get_greeting()}")
    print()

    print("You: I want to make a reservation")
    response = await agent.process_message("I want to make a reservation")
    print(f"Agent: {response}\n")

    print("You: 6pm?")
    response = await agent.process_message("6pm?")
    print(f"Agent: {response}")
    print(f"Booking info: {agent.booking_info}\n")
    print()

    # Test 2: User says time + party size "6pm for 2"
    print("Test 2: User says '6pm for 2' (time + party size)")
    print("-" * 70)
    agent = BookingAgent()
    print(f"Agent: {agent.get_greeting()}")
    print()

    print("You: I want to book a table")
    response = await agent.process_message("I want to book a table")
    print(f"Agent: {response}\n")

    print("You: 6pm for 2")
    response = await agent.process_message("6pm for 2")
    print(f"Agent: {response}")
    print(f"Booking info: {agent.booking_info}\n")
    print()

    # Test 3: User says date + time "tomorrow at 7pm"
    print("Test 3: User says 'tomorrow at 7pm' (date + time)")
    print("-" * 70)
    agent = BookingAgent()
    print(f"Agent: {agent.get_greeting()}")
    print()

    print("You: Hi, I need a table")
    response = await agent.process_message("Hi, I need a table")
    print(f"Agent: {response}\n")

    print("You: tomorrow at 7pm")
    response = await agent.process_message("tomorrow at 7pm")
    print(f"Agent: {response}")
    print(f"Booking info: {agent.booking_info}\n")
    print()

    # Test 4: User gives all info "tomorrow at 7pm for 4"
    print("Test 4: User says 'tomorrow at 7pm for 4' (all info)")
    print("-" * 70)
    agent = BookingAgent()
    print(f"Agent: {agent.get_greeting()}")
    print()

    print("You: I want to reserve a table")
    response = await agent.process_message("I want to reserve a table")
    print(f"Agent: {response}\n")

    print("You: tomorrow at 7pm for 4")
    response = await agent.process_message("tomorrow at 7pm for 4")
    print(f"Agent: {response}")
    print(f"Booking info: {agent.booking_info}\n")
    print()

    print("=" * 70)
    print("Tests completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_scenarios())
