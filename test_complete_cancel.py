#!/usr/bin/env python3
"""Test complete cancellation flow."""

import asyncio
from agents.booking_agent import BookingAgent


async def test_complete_cancel():
    """Test complete cancellation flow."""
    print("=" * 70)
    print("完整取消预订流程测试")
    print("=" * 70)
    print()

    agent = BookingAgent()

    conversation = [
        "I want to cancel my booking",
        "yuhuan",
        "today",
    ]

    print(f"Agent: {agent.get_greeting()}\n")

    for user_input in conversation:
        print(f"You: {user_input}")
        response = await agent.process_message(user_input)
        print(f"Agent: {response}\n")

    print("=" * 70)
    print("预期流程:")
    print("1. Agent问姓名 ✓")
    print("2. Agent问日期 ✓")
    print("3. Agent找到预订并确认")
    print("4. Agent取消预订")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_complete_cancel())
