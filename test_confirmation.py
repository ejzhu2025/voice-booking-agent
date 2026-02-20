#!/usr/bin/env python3
"""Test confirmation flow before creating booking."""

import asyncio
from agents.booking_agent import BookingAgent


async def test_confirmation_flow():
    """Test that agent asks for confirmation before creating booking."""
    print("=" * 70)
    print("测试预订确认流程")
    print("=" * 70)
    print()

    agent = BookingAgent()

    conversation = [
        "I want to book a table for 2 at 8pm tonight",
        "Test User",
        "415-555-1234",
    ]

    print(f"Agent: {agent.get_greeting()}\n")

    for i, user_input in enumerate(conversation, 1):
        print(f"You: {user_input}")
        response = await agent.process_message(user_input)
        print(f"Agent: {response}\n")

        if any(agent.booking_info.values()):
            filled = {k: v for k, v in agent.booking_info.items() if v}
            print(f"[Booking info: {filled}]\n")

    print("=" * 70)
    print("预期行为:")
    print("1. 收集时间、人数 ✓")
    print("2. 检查availability ✓")
    print("3. 问姓名 ✓")
    print("4. 问电话 ✓")
    print("5. 重复信息并问: 'Is this correct?' ← 关键步骤")
    print("6. 等待用户确认")
    print("7. 用户说yes后才调用create_booking()")
    print("=" * 70)
    print()

    # Check if agent is waiting for confirmation
    last_response = response.lower()
    if "confirm" in last_response or "correct" in last_response or "is this" in last_response:
        print("✅ SUCCESS: Agent正在等待确认")
    else:
        print("❌ FAIL: Agent没有要求确认，直接创建了预订")


if __name__ == "__main__":
    asyncio.run(test_confirmation_flow())
