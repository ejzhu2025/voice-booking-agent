#!/usr/bin/env python3
"""
Interactive text-based test for the booking agent.
Run this to test the conversation flow without phone/Twilio.
"""

import asyncio
from agents.booking_agent import BookingAgent
from datetime import datetime, timedelta
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

        # Get today's date string (local time)
        from datetime import datetime as dt
        today_str = dt.now().strftime("%Y-%m-%d")

        today_bookings = []
        for b in all_bookings:
            if b.get("status") not in ["ACCEPTED", "PENDING"]:
                continue

            start_at_str = b.get("start_at", "")
            if not start_at_str:
                continue

            # Convert UTC to local time FIRST, then check date
            try:
                utc_dt = dt.strptime(start_at_str, "%Y-%m-%dT%H:%M:%SZ")
                local_dt = utc_dt - timedelta(hours=8)  # UTC to PST
                local_date_str = local_dt.strftime("%Y-%m-%d")

                if local_date_str == today_str:
                    today_bookings.append(b)
            except:
                pass

        print(f"\n[今天的活跃预订: {len(today_bookings)} 个]")

        if not today_bookings:
            print()
            return

        # Get customer names
        for booking in today_bookings:
            start_at_str = booking.get("start_at", "")

            # Convert UTC to local time
            try:
                utc_dt = dt.strptime(start_at_str, "%Y-%m-%dT%H:%M:%SZ")
                local_dt = utc_dt - timedelta(hours=8)
                time_display = local_dt.strftime("%H:%M")
            except:
                time_display = start_at_str[11:16]

            party_size = booking.get("customer_note", "").replace("Party size: ", "")
            booking_id = booking.get("id")
            customer_id = booking.get("customer_id")

            # Get customer name
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


async def main():
    print("=" * 50)
    print("Restaurant Booking Agent - Text Test Mode")
    print("=" * 50)
    print("Type 'quit' to exit, 'reset' to start over\n")

    agent = BookingAgent()
    print(f"Agent: {agent.get_greeting()}\n")

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                print("Goodbye!")
                break

            if user_input.lower() == "reset":
                agent.reset()
                print(f"\n[Session reset]\nAgent: {agent.get_greeting()}\n")
                continue

            response = await agent.process_message(user_input)
            print(f"\nAgent: {response}\n")

            # Show current booking state
            if any(agent.booking_info.values()):
                filled = {k: v for k, v in agent.booking_info.items() if v}
                print(f"[Booking info: {filled}]")

            # Show today's bookings
            await show_todays_bookings()

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
