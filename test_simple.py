#!/usr/bin/env python3
"""Simple test for the exact scenario."""

import asyncio
from agents.booking_agent import BookingAgent


async def test():
    agent = BookingAgent()

    print("=" * 60)
    print(f"Agent: {agent.get_greeting()}\n")

    print("You: i want to book a seat for 3\n")
    response = await agent.process_message("i want to book a seat for 3")
    print(f"Agent: {response}\n")
    print(f"Booking info: {agent.booking_info}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test())
