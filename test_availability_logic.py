#!/usr/bin/env python3
"""Test the new availability logic."""

import asyncio
from services.square_service import square_service
from datetime import datetime


async def test_availability():
    """Test availability checking."""
    today = datetime.now().strftime("%Y-%m-%d")

    print("=" * 70)
    print(f"Testing Availability Logic for {today}")
    print("=" * 70)
    print()

    # Test 1: Check general availability
    print("Test 1: Check availability for 3 people today")
    print("-" * 70)
    result = await square_service.check_availability(
        date=today,
        party_size=3,
    )
    print(f"Available: {result['available']}")
    print(f"Slots: {result['slots'][:10] if len(result['slots']) > 10 else result['slots']}")
    print(f"Message: {result['message']}")
    print()

    # Test 2: Check specific time
    print("Test 2: Check if 18:00 (6pm) is available for 3 people")
    print("-" * 70)
    result = await square_service.check_availability(
        date=today,
        party_size=3,
        preferred_time="18:00",
    )
    print(f"Available: {result['available']}")
    print(f"All available slots: {result['slots'][:5]}...")
    print(f"Message: {result['message']}")
    print()

    # Test 3: Check for 2 people
    print("Test 3: Check availability for 2 people today")
    print("-" * 70)
    result = await square_service.check_availability(
        date=today,
        party_size=2,
    )
    print(f"Available: {result['available']}")
    print(f"Slots: {result['slots'][:10] if len(result['slots']) > 10 else result['slots']}")
    print(f"Message: {result['message']}")
    print()

    print("=" * 70)
    print("Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_availability())
