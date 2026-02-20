#!/usr/bin/env python3
"""Test complete booking system with custom availability + Square booking."""

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
            return

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
            return

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

    except Exception as e:
        print(f"\n[预订显示错误: {e}]\n")


async def test_complete_system():
    """Test the complete booking system."""
    print("=" * 70)
    print("完整系统测试：自定义Availability逻辑 + Square预订")
    print("=" * 70)
    print()

    agent = BookingAgent()

    # 测试场景：用户想订3个人今晚的位置
    print("场景：用户想订今晚3个人的位置")
    print("-" * 70)

    conversation = [
        "do you have a table for 3 tonight?",  # Agent会用自定义逻辑检查
    ]

    print(f"Agent: {agent.get_greeting()}\n")

    for user_input in conversation:
        print(f"You: {user_input}")
        response = await agent.process_message(user_input)
        print(f"Agent: {response}\n")

        if any(agent.booking_info.values()):
            filled = {k: v for k, v in agent.booking_info.items() if v}
            print(f"[Booking info: {filled}]\n")

    print("\n📊 当前今天的预订情况：")
    await show_todays_bookings()

    print("\n" + "=" * 70)
    print("✓ 系统说明：")
    print("  1. Agent用自定义逻辑计算availability（基于2人桌+4人桌）")
    print("  2. 如果用户确认时间并提供姓名电话")
    print("  3. Agent调用Square API创建预订")
    print("  4. 用户收到Square的短信通知 ✓")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_complete_system())
