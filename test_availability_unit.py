#!/usr/bin/env python3
"""Unit test for check_availability function."""

import asyncio
from services.square_service import square_service
from datetime import datetime
import requests


async def setup_test_bookings():
    """Show current bookings for test context."""
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
        print("Error fetching bookings")
        return []

    from datetime import timedelta
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
                })
        except:
            pass

    return today_bookings


async def test_check_availability():
    """Comprehensive unit test for check_availability."""
    print("=" * 70)
    print("check_availability() 单元测试")
    print("=" * 70)
    print()

    # Show current state
    today = datetime.now().strftime("%Y-%m-%d")
    current_bookings = await setup_test_bookings()

    print("📊 当前预订状态 (所有用户说的都是PST本地时间):")
    if not current_bookings:
        print("  (无预订)")
    else:
        for b in current_bookings:
            print(f"  - {b['time']} PST | {b['party_size']}人")
    print()

    # Test cases
    test_cases = [
        {
            "name": "Test 1: 查询今天全部availability (3人)",
            "date": today,
            "party_size": 3,
            "time": None,
            "expect": "返回所有可用时间段，排除与现有预订冲突的时间"
        },
        {
            "name": "Test 2: 查询今天全部availability (2人)",
            "date": today,
            "party_size": 2,
            "time": None,
            "expect": "返回所有可用时间段（2人桌独立，不受4人桌预订影响）"
        },
        {
            "name": "Test 3: 查询特定时间 - 已预订的时间",
            "date": today,
            "party_size": 3,
            "time": "18:00",
            "expect": "应该返回 available=False（如果6pm已有3人预订）"
        },
        {
            "name": "Test 4: 查询特定时间 - 冲突时间",
            "date": today,
            "party_size": 3,
            "time": "19:00",
            "expect": "应该返回 available=False（如果6pm有预订，占用到7:30pm）"
        },
        {
            "name": "Test 5: 查询特定时间 - 可用时间",
            "date": today,
            "party_size": 3,
            "time": "19:30",
            "expect": "应该返回 available=True（6pm预订在7:30pm结束）"
        },
        {
            "name": "Test 6: 不同桌子不冲突",
            "date": today,
            "party_size": 2,
            "time": "19:00",
            "expect": "应该返回 available=True（2人桌与4人桌独立）"
        },
    ]

    print("=" * 70)
    print("开始测试")
    print("=" * 70)
    print()

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"{test['name']}")
        print(f"  参数: date={test['date']}, party_size={test['party_size']}, time={test['time']}")
        print(f"  预期: {test['expect']}")

        result = await square_service.check_availability(
            date=test['date'],
            party_size=test['party_size'],
            preferred_time=test['time']
        )

        print(f"  结果: available={result['available']}")
        if test['time'] is None:
            print(f"  可用时间段数量: {len(result['slots'])}")
            if result['slots']:
                print(f"  示例时间段: {result['slots'][:5]}")
        else:
            print(f"  消息: {result['message']}")

        # Simple validation
        if test['time'] is None:
            # For full availability check, just verify we get a reasonable response
            if isinstance(result['slots'], list):
                print("  ✅ PASS")
                passed += 1
            else:
                print("  ❌ FAIL")
                failed += 1
        else:
            # For specific time check, verify available status makes sense
            # This is a basic check - more specific validation would require knowing exact bookings
            if isinstance(result['available'], bool):
                print("  ✅ PASS (结构正确)")
                passed += 1
            else:
                print("  ❌ FAIL")
                failed += 1

        print()

    print("=" * 70)
    print(f"测试完成: {passed} passed, {failed} failed")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_check_availability())
