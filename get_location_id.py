#!/usr/bin/env python3
"""Get Square Location ID using requests."""

import requests

ACCESS_TOKEN = "EAAAl5V08SwPUxNhQttNPExZfDiFo8T1H-h1R5DsC1h8yN93GfI2lId32EtfiG_8"

response = requests.get(
    "https://connect.squareupsandbox.com/v2/locations",
    headers={
        "Square-Version": "2024-01-18",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
)

if response.status_code == 200:
    data = response.json()
    locations = data.get('locations', [])

    print(f"\nFound {len(locations)} location(s):\n")
    for loc in locations:
        print(f"Name: {loc.get('name')}")
        print(f"Location ID: {loc.get('id')}")
        print("-" * 50)
else:
    print(f"Error: {response.status_code}")
    print(response.text)
