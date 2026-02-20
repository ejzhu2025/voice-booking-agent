#!/usr/bin/env python3
"""Test smart proactive cancellation flow."""

import asyncio
from agents.booking_agent import BookingAgent


async def test_smart_cancel():
    """Test that agent proactively searches after getting name."""
    print("=" * 70)
    print("智能取消流程测试")
    print("=" * 70)
    print()

    agent = BookingAgent()

    conversation = [
        "I want to cancel my reservation",
        "alice",  # Just the first name
    ]

    print(f"Agent: {agent.get_greeting()}\n")

    for user_input in conversation:
        print(f"You: {user_input}")
        response = await agent.process_message(user_input)
        print(f"Agent: {response}\n")

    print("=" * 70)
    print("预期行为:")
    print("1. Agent问姓名 ✓")
    print("2. 用户说'alice' ✓")
    print("3. Agent立即查找今天的预订 ← 关键")
    print("4. Agent说: 'I found your reservation for today at 9pm for 2.'")
    print("   'Is this the one you'd like to cancel?'")
    print()
    print("新流程 vs 旧流程:")
    print("❌ 旧: 问姓名 → 问日期 → 查找 → 确认")
    print("✅ 新: 问姓名 → 立即查找 → 确认")
    print("=" * 70)
    print()

    last_response = response.lower()
    if "found" in last_response and ("9" in last_response or "21" in last_response):
        print("✅ SUCCESS: Agent主动查找并找到了今天的预订")
    elif "what date" in last_response:
        print("❌ FAIL: Agent还在问日期，没有主动查找")
    else:
        print("? 不确定，请检查回复")


if __name__ == "__main__":
    asyncio.run(test_smart_cancel())
