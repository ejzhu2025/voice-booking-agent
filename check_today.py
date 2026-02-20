#!/usr/bin/env python3
"""Quick check of today's bookings."""

import requests
from datetime import datetime, timedelta

ACCESS_TOKEN = "EAAAl1_zkoWSi9MIBhzh4BzMV-YZmIgFVpXCx89eTnboFQDTru-1cke4WfxmrXgM"
LOCATION_ID = "LGHY7R3KJADYX"

print("=" * 60)
print("今天的活跃预订")
print("=" * 60)

response = requests.get(
    f"https://connect.squareup.com/v2/bookings?location_id={LOCATION_ID}&limit=100",
    headers={
        "Square-Version": "2024-01-18",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }
)

if response.status_code != 200:
    print("Error fetching bookings")
    exit(1)

data = response.json()
all_bookings = data.get("bookings", [])
today_str = datetime.now().strftime("%Y-%m-%d")

today_bookings = []
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
            today_bookings.append({
                "time": local_dt.strftime("%H:%M"),
                "party_size": b.get("customer_note", "").replace("Party size: ", ""),
                "booking_id": b.get("id"),
                "customer_id": b.get("customer_id"),
            })
    except:
        pass

print(f"\n总数: {len(today_bookings)} 个\n")

if not today_bookings:
    print("今天没有活跃预订")
else:
    for booking in today_bookings:
        # Get customer name
        customer_name = "Unknown"
        try:
            cust_resp = requests.get(
                f"https://connect.squareup.com/v2/customers/{booking['customer_id']}",
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

        print(f"  {booking['time']} | {booking['party_size']}人 | {customer_name}")
        print(f"    ID: {booking['booking_id']}")
        print()

print("=" * 60)
