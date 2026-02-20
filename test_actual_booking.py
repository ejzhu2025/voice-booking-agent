#!/usr/bin/env python3
"""Test that booking actually creates in Square."""

import asyncio
from agents.booking_agent import BookingAgent
from datetime import datetime
import requests


async def show_todays_bookings():
    """Display today's bookings from Square."""
    try:
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
            print("\n[无法获取预订信息]\n")
            return 0

        data = response.json()
        all_bookings = data.get("bookings", [])

        from datetime import datetime as dt, timedelta
        today_str = dt.now().strftime("%Y-%m-%d")

        today_bookings = [
            b for b in all_bookings
            if b.get("start_at", "")[:10] == today_str
            and b.get("status") in ["ACCEPTED", "PENDING"]
        ]

        print(f"\n[今天的活跃预订: {len(today_bookings)} 个]")

        if not today_bookings:
            print()
            return 0

        for booking in today_bookings:
            start_at_str = booking.get("start_at", "")

            try:
                utc_dt = dt.strptime(start_at_str, "%Y-%m-%dT%H:%M:%SZ")
                local_dt = utc_dt - timedelta(hours=8)
                time_display = local_dt.strftime("%H:%M")
            except:
                time_display = start_at_str[11:16]

            party_size = booking.get("customer_note", "").replace("Party size: ", "")
            booking_id = booking.get("id")
            customer_id = booking.get("customer_id")

            customer_name = "Unknown"
            try:
                cust_resp = requests.get(
                    f"https://connect.squareup.com/v2/customers/{customer_id}",
                    headers={
                        "Square-Version": "2024-01-18",
                        "Authorization": f"Bearer {ACCESS_TOKEN}",
                    }
                )
                if cust_resp.status_code == 200:
                    cust_data = cust_resp.json()
                    cust = cust_data.get("customer", {})
                    given = cust.get("given_name", "")
                    family = cust.get("family_name", "")
                    customer_name = f"{given} {family}".strip()
            except:
                pass

            print(f"  - {time_display} | {party_size}人 | {customer_name} | ID:{booking_id}")

        print()
        return len(today_bookings)

    except Exception as e:
        print(f"\n[预订显示错误: {e}]\n")
        return 0


async def test_complete_booking():
    """Test complete booking flow and verify it's created in Square."""
    print("=" * 70)
    print("测试完整预订流程 - 验证Square中是否真的创建了")
    print("=" * 70)
    print()

    # Check initial bookings
    print("📊 预订前的状态:")
    initial_count = await show_todays_bookings()

    print("\n" + "=" * 70)
    print("开始预订对话")
    print("=" * 70)
    print()

    agent = BookingAgent()

    conversation = [
        "I'd like to book a table for 2 tonight at 7pm",
        "Test User",
        "415-555-9999",
    ]

    print(f"Agent: {agent.get_greeting()}\n")

    for user_input in conversation:
        print(f"You: {user_input}")
        response = await agent.process_message(user_input)
        print(f"Agent: {response}\n")

        if any(agent.booking_info.values()):
            filled = {k: v for k, v in agent.booking_info.items() if v}
            print(f"[Booking info: {filled}]\n")

    print("=" * 70)
    print("📊 预订后的状态:")
    final_count = await show_todays_bookings()

    print("=" * 70)
    if final_count > initial_count:
        print("✅ 成功！预订已在Square中创建")
        print(f"   预订数量: {initial_count} → {final_count}")
    else:
        print("❌ 失败！预订没有在Square中创建")
        print(f"   预订数量: {initial_count} → {final_count}")
        print("   Agent可能没有调用create_booking() function")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_complete_booking())
