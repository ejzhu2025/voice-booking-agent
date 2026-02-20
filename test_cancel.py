#!/usr/bin/env python3
"""Test cancellation flow."""

import asyncio
from agents.booking_agent import BookingAgent


async def test_cancel():
    """Test that cancellation is handled by agent, not transferred."""
    print("=" * 70)
    print("测试取消预订流程")
    print("=" * 70)
    print()

    agent = BookingAgent()

    conversation = [
        "hi i want to cancel my booking",
    ]

    print(f"Agent: {agent.get_greeting()}\n")

    for user_input in conversation:
        print(f"You: {user_input}")
        response = await agent.process_message(user_input)
        print(f"Agent: {response}\n")

    print("=" * 70)
    if "transfer" in response.lower():
        print("❌ 失败：Agent转人工了")
        print("   应该直接问: 'May I have your name?'")
    elif "name" in response.lower():
        print("✅ 成功：Agent开始处理取消流程")
    else:
        print("? 不确定，检查回复")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_cancel())
