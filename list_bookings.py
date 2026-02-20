#!/usr/bin/env python3
"""List all bookings in Square Production."""

import requests

ACCESS_TOKEN = "EAAAl1_zkoWSi9MIBhzh4BzMV-YZmIgFVpXCx89eTnboFQDTru-1cke4WfxmrXgM"
LOCATION_ID = "LGHY7R3KJADYX"

# Simple GET request
response = requests.get(
    f"https://connect.squareup.com/v2/bookings?location_id={LOCATION_ID}&limit=50",
    headers={
        "Square-Version": "2024-01-18",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
)

if response.status_code == 200:
    data = response.json()
    bookings = data.get("bookings", [])

    if not bookings:
        print("No bookings found.")
    else:
        active = [b for b in bookings if b.get('status') in ['ACCEPTED', 'PENDING']]
        cancelled = [b for b in bookings if b.get('status') == 'CANCELLED']

        print(f"\n找到 {len(bookings)} 个预订 ({len(active)} 活跃, {len(cancelled)} 已取消):\n")

        for booking in bookings:
            status = booking.get('status', 'UNKNOWN')
            status_icon = "✓" if status in ['ACCEPTED', 'PENDING'] else "✗"

            print(f"{status_icon} 预订ID: {booking.get('id')}")
            print(f"  状态: {status}")
            print(f"  时间: {booking.get('start_at')}")
            print(f"  客户ID: {booking.get('customer_id')}")
            print(f"  备注: {booking.get('customer_note', 'N/A')}")
            print("-" * 50)
else:
    print(f"Error: {response.status_code}")
    print(response.text)
