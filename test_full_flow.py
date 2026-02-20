#!/usr/bin/env python3
"""Test complete booking flow with proactive behavior."""

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


async def test_complete_flow():
    """Test complete booking flow."""
    print("=" * 70)
    print("Complete Booking Flow Test")
    print("=" * 70)
    print()

    agent = BookingAgent()

    # Simulate a complete conversation
    conversation = [
        "Hi, I'd like to make a reservation",
        "6pm?",  # Should check immediately with defaults
        "John Smith",  # Name
        "415-555-0123",  # Phone
    ]

    print(f"Agent: {agent.get_greeting()}\n")

    for user_input in conversation:
        print(f"You: {user_input}")
        response = await agent.process_message(user_input)
        print(f"Agent: {response}\n")

        # Show booking info after each turn
        if any(agent.booking_info.values()):
            filled = {k: v for k, v in agent.booking_info.items() if v}
            print(f"[Booking info: {filled}]\n")

    # Show today's bookings at the end
    await show_todays_bookings()

    print("=" * 70)
    print("Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_complete_flow())
