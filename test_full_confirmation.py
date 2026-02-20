#!/usr/bin/env python3
"""Test full confirmation and booking creation flow."""

import asyncio
from agents.booking_agent import BookingAgent
from datetime import datetime
import requests


async def show_bookings_count():
    """Show current booking count."""
    ACCESS_TOKEN = "EAAAl1_zkoWSi9MIBhzh4BzMV-YZmIgFVpXCx89eTnboFQDTru-1cke4WfxmrXgM"
    LOCATION_ID = "LGHY7R3KJADYX"

    response = requests.get(
        f"https://connect.squareup.com/v2/bookings?location_id={LOCATION_ID}&limit=100",
        headers={
            "Square-Version": "2024-01-18",
            "Authorization": f"Bearer {ACCESS_TOKEN}",
        }
    )

    if response.status_code != 200:
        return 0

    from datetime import timedelta
    data = response.json()
    all_bookings = data.get("bookings", [])
    today_str = datetime.now().strftime("%Y-%m-%d")

    count = 0
    for b in all_bookings:
        if b.get("status") not in ["ACCEPTED", "PENDING"]:
            continue

        start_at = b.get("start_at", "")
        if not start_at:
            continue

        try:
            utc_dt = datetime.strptime(start_at, "%Y-%m-%dT%H:%M:%SZ")
            local_dt = utc_dt - timedelta(hours=8)
            local_date = local_dt.strftime("%Y-%m-%d")

            if local_date == today_str:
                count += 1
        except:
            pass

    return count


async def test_full_flow():
    """Test complete flow with confirmation."""
    print("=" * 70)
    print("完整预订流程测试（含确认步骤）")
    print("=" * 70)
    print()

    initial_count = await show_bookings_count()
    print(f"📊 初始预订数: {initial_count}\n")

    agent = BookingAgent()

    conversation = [
        "I want to book a table for 2 at 9pm tonight",
        "Alice Brown",
        "510-555-7890",
        "yes",  # User confirms
    ]

    print(f"Agent: {agent.get_greeting()}\n")

    for user_input in conversation:
        print(f"You: {user_input}")
        response = await agent.process_message(user_input)
        print(f"Agent: {response}\n")

    final_count = await show_bookings_count()
    print(f"📊 最终预订数: {final_count}\n")

    print("=" * 70)
    print("预期流程:")
    print("1. 收集信息 ✓")
    print("2. Agent问: 'Is this correct?' ✓")
    print("3. 用户说: 'yes' ✓")
    print("4. Agent调用create_booking() ← 关键")
    print("5. 预订数量增加 ← 验证")
    print("=" * 70)
    print()

    if final_count > initial_count:
        print("✅ SUCCESS: 预订已创建")
        print(f"   预订数量: {initial_count} → {final_count}")
    else:
        print("❌ FAIL: 预订未创建")
        print(f"   预订数量: {initial_count} → {final_count}")
        print("   Agent可能没有调用create_booking()")


if __name__ == "__main__":
    asyncio.run(test_full_flow())
