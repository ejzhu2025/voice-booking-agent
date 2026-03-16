"""Square Bookings + Orders API Service - Using REST API directly."""

import uuid
from datetime import datetime, timedelta
from typing import Optional
import requests
from utils.config import config

# Menu price table (cents). Key = lowercase name fragment.
_MENU_PRICES = {
    # Wings
    "wings small":   1655, "wings medium":  2995, "wings large":   4235,
    # Boneless
    "boneless small":1695, "boneless medium":3190,"boneless large": 4395,
    # Drumsticks
    "drumsticks small":1585,"drumsticks medium":2995,"drumsticks large":4135,
    "drums small":   1585, "drums medium":   2995, "drums large":    4135,
    # Combo
    "combo small":   1655, "combo medium":   2995, "combo large":    4235,
    # Strips
    "strips small":  1760, "strips medium":  3190, "strips large":   4450,
    # Main dishes
    "tteokbokki":    1580, "japchae":        1760, "buldak":         1980,
    "bulgogi":       2085, "chicken katsu":  1475, "katsu":          1475,
}

def _price_cents(name: str, size: str = "") -> int:
    """Look up price in cents. Returns 0 if unknown (allows order to proceed)."""
    key = f"{name.lower()} {size.lower()}".strip()
    if key in _MENU_PRICES:
        return _MENU_PRICES[key]
    # Try name only
    for k, v in _MENU_PRICES.items():
        if name.lower() in k:
            return v
    return 0


class SquareBookingService:
    """Handle restaurant availability and bookings via Square REST API."""

    def __init__(self):
        self.access_token = config.SQUARE_ACCESS_TOKEN
        self.location_id = config.SQUARE_LOCATION_ID

        if config.SQUARE_ENVIRONMENT == "sandbox":
            self.base_url = "https://connect.squareupsandbox.com"
        else:
            self.base_url = "https://connect.squareup.com"

        self.headers = {
            "Square-Version": "2024-01-18",
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def check_availability(
        self,
        date: str,  # YYYY-MM-DD
        party_size: int,
        preferred_time: Optional[str] = None,  # HH:MM
    ) -> dict:
        """Check available time slots based on existing bookings and restaurant capacity."""
        try:
            # Restaurant capacity: 1x table for 2, 1x table for 4
            # Dining duration: 90 minutes

            # Get all bookings for this date
            response = requests.get(
                f"{self.base_url}/v2/bookings?location_id={self.location_id}&limit=100",
                headers=self.headers,
            )

            if response.status_code != 200:
                return {
                    "available": False,
                    "slots": [],
                    "message": "Error fetching bookings",
                }

            data = response.json()
            all_bookings = data.get("bookings", [])

            # Filter active bookings for this date
            target_bookings = []
            for booking in all_bookings:
                if booking.get("status") not in ["ACCEPTED", "PENDING"]:
                    continue

                start_at = booking.get("start_at", "")
                if not start_at:
                    continue

                # Convert UTC to Pacific time
                try:
                    from zoneinfo import ZoneInfo
                    utc_dt = datetime.strptime(start_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=ZoneInfo("UTC"))
                    local_dt = utc_dt.astimezone(ZoneInfo("America/Los_Angeles"))
                    booking_date = local_dt.strftime("%Y-%m-%d")
                    local_time = local_dt.strftime("%H:%M")
                except:
                    continue

                if booking_date == date:
                    party_size_str = booking.get("customer_note", "")
                    try:
                        booked_party_size = int(party_size_str.replace("Party size: ", ""))
                    except:
                        booked_party_size = 2

                    target_bookings.append({
                        "time": local_time,
                        "party_size": booked_party_size,
                    })

            # Calculate available slots
            # Operating hours: 14:00-22:00 (2pm-10pm), 30min intervals
            available_slots = []
            for hour in range(14, 22):
                for minute in [0, 30]:
                    check_time = f"{hour:02d}:{minute:02d}"

                    # Check if this slot can accommodate the party
                    can_book = self._can_book_at_time(check_time, party_size, target_bookings)

                    if can_book:
                        available_slots.append(check_time)

            # If preferred_time specified, check if it's available
            if preferred_time:
                if preferred_time in available_slots:
                    return {
                        "available": True,
                        "slots": available_slots,
                        "message": f"Available at {preferred_time}",
                    }
                else:
                    return {
                        "available": False,
                        "slots": available_slots,
                        "message": f"{preferred_time} is not available",
                    }

            # Return all available slots
            if available_slots:
                return {
                    "available": True,
                    "slots": available_slots,
                    "message": f"Found {len(available_slots)} available time slots",
                }
            else:
                return {
                    "available": False,
                    "slots": [],
                    "message": "No availability for this date",
                }

        except Exception as e:
            return {
                "available": False,
                "slots": [],
                "message": f"Error: {str(e)}",
            }

    def _can_book_at_time(self, check_time: str, party_size: int, existing_bookings: list) -> bool:
        """Check if we can book at a specific time given existing bookings."""
        # Restaurant capacity: maximum 50 people at once
        if party_size > 50:
            return False  # Exceeds restaurant capacity

        # Otherwise available (no table-level tracking)
        return True

    async def create_booking(
        self,
        date: str,  # YYYY-MM-DD
        time: str,  # HH:MM
        party_size: int,
        customer_name: str,
        customer_phone: str,
        customer_email: Optional[str] = None,
    ) -> dict:
        """Create a reservation."""
        try:
            # First, create or find customer
            customer_result = await self._get_or_create_customer(
                name=customer_name,
                phone=customer_phone,
                email=customer_email,
            )

            if not customer_result.get("success"):
                return {
                    "success": False,
                    "message": customer_result.get("message", "Failed to create customer"),
                }

            customer_id = customer_result["customer_id"]

            # Create booking
            # IMPORTANT: Convert local time to UTC
            # User's timezone: PST/PDT (UTC-8 or UTC-7)
            # For now, assuming PST (UTC-8)
            from datetime import datetime, timedelta

            # Parse local time
            local_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")

            # Convert Pacific → UTC
            from zoneinfo import ZoneInfo
            local_dt = local_dt.replace(tzinfo=ZoneInfo("America/Los_Angeles"))
            utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

            # Format for Square API
            start_at = utc_dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"

            response = requests.post(
                f"{self.base_url}/v2/bookings",
                headers=self.headers,
                json={
                    "booking": {
                        "location_id": self.location_id,
                        "customer_id": customer_id,
                        "start_at": start_at,
                        "customer_note": f"Party size: {party_size}",
                        "appointment_segments": [
                            {
                                "duration_minutes": 90,  # 1.5 hour dining
                                "service_variation_id": "LPFNCRAESICB2W4U7WUM7QFD",
                                "service_variation_version": 1771271898641,
                                "team_member_id": "TMr0EtehupeqKvro",
                            }
                        ],
                    }
                }
            )

            if response.status_code in [200, 201]:  # 200 OK or 201 Created
                data = response.json()
                booking = data.get("booking", {})
                return {
                    "success": True,
                    "booking_id": booking.get("id"),
                    "confirmation": booking.get("id", "")[:8].upper(),
                    "message": f"Booking confirmed for {party_size} at {time} on {date}",
                }
            else:
                return {
                    "success": False,
                    "message": f"Booking failed: {response.status_code} - {response.text}",
                }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error creating booking: {str(e)}",
            }

    async def _get_or_create_customer(
        self,
        name: str,
        phone: str,
        email: Optional[str] = None,
    ) -> dict:
        """Create or find a customer."""
        try:
            # Try to find existing customer by phone
            response = requests.post(
                f"{self.base_url}/v2/customers/search",
                headers=self.headers,
                json={
                    "query": {
                        "filter": {
                            "phone_number": {"exact": phone}
                        }
                    }
                }
            )

            if response.status_code == 200:
                data = response.json()
                customers = data.get("customers", [])
                if customers:
                    return {
                        "success": True,
                        "customer_id": customers[0]["id"],
                    }

            # Create new customer
            name_parts = name.split(" ", 1)
            given_name = name_parts[0]
            family_name = name_parts[1] if len(name_parts) > 1 else ""

            response = requests.post(
                f"{self.base_url}/v2/customers",
                headers=self.headers,
                json={
                    "given_name": given_name,
                    "family_name": family_name,
                    "phone_number": phone,
                    "email_address": email,
                }
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "customer_id": data["customer"]["id"],
                }
            else:
                return {
                    "success": False,
                    "message": f"Error: {response.text}",
                }

        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }

    async def find_booking_by_name_and_date(
        self,
        customer_name: str,
        date: str,  # YYYY-MM-DD
    ) -> dict:
        """Find active booking by customer name and date."""
        try:
            # Get all bookings for the location
            response = requests.get(
                f"{self.base_url}/v2/bookings?location_id={self.location_id}&limit=100",
                headers=self.headers,
            )

            if response.status_code != 200:
                return {
                    "found": False,
                    "message": "Error fetching bookings",
                }

            data = response.json()
            all_bookings = data.get("bookings", [])

            # Filter by date and status
            target_date = date
            matching_bookings = []

            for booking in all_bookings:
                if booking.get("status") not in ["ACCEPTED", "PENDING"]:
                    continue

                start_at = booking.get("start_at", "")
                if not start_at:
                    continue

                # Convert UTC to Pacific time, then check date
                try:
                    from zoneinfo import ZoneInfo
                    utc_dt = datetime.strptime(start_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=ZoneInfo("UTC"))
                    local_dt = utc_dt.astimezone(ZoneInfo("America/Los_Angeles"))
                    booking_date = local_dt.strftime("%Y-%m-%d")
                except:
                    continue

                if booking_date == target_date:
                    # Get customer info to match name
                    customer_id = booking.get("customer_id")
                    if not customer_id:
                        continue

                    # Fetch customer details to check name
                    try:
                        cust_response = requests.get(
                            f"{self.base_url}/v2/customers/{customer_id}",
                            headers=self.headers,
                        )
                        if cust_response.status_code == 200:
                            cust_data = cust_response.json()
                            customer = cust_data.get("customer", {})
                            given_name = customer.get("given_name", "").lower()
                            family_name = customer.get("family_name", "").lower()
                            full_name = f"{given_name} {family_name}".strip()

                            # Match name (case-insensitive, partial match, ignore spaces)
                            search_name_lower = customer_name.lower().replace(" ", "")
                            given_name_stripped = given_name.replace(" ", "")
                            family_name_stripped = family_name.replace(" ", "")
                            full_name_stripped = full_name.replace(" ", "")
                            if (search_name_lower in given_name_stripped or
                                search_name_lower in family_name_stripped or
                                search_name_lower in full_name_stripped or
                                given_name_stripped in search_name_lower or
                                family_name_stripped in search_name_lower):
                                matching_bookings.append(booking)
                    except:
                        # If can't fetch customer, skip this booking
                        continue

            if not matching_bookings:
                return {
                    "found": False,
                    "message": f"No active bookings found for {date}",
                }

            # Return first matching booking
            booking = matching_bookings[0]
            start_time = booking.get("start_at", "")

            # Convert UTC to local time for display
            try:
                utc_dt = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
                local_dt = utc_dt - timedelta(hours=8)  # UTC to PST
                time_part = local_dt.strftime("%H:%M")
                date_part = local_dt.strftime("%Y-%m-%d")
            except:
                time_part = start_time[11:16] if len(start_time) > 16 else ""
                date_part = start_time[:10] if len(start_time) > 10 else ""

            party_size = booking.get("customer_note", "").replace("Party size: ", "")

            return {
                "found": True,
                "booking_id": booking.get("id"),
                "date": date_part,
                "time": time_part,
                "party_size": party_size,
                "message": f"Found booking for {date_part} at {time_part} for {party_size} people",
            }

        except Exception as e:
            return {
                "found": False,
                "message": f"Error: {str(e)}",
            }

    async def find_booking_by_customer(
        self,
        customer_name: str,
        customer_phone: str,
    ) -> dict:
        """Find active bookings for a customer (legacy method using phone)."""
        try:
            # First find customer by phone
            response = requests.post(
                f"{self.base_url}/v2/customers/search",
                headers=self.headers,
                json={
                    "query": {
                        "filter": {
                            "phone_number": {"exact": customer_phone}
                        }
                    }
                }
            )

            if response.status_code != 200:
                return {
                    "found": False,
                    "message": "Customer not found",
                }

            data = response.json()
            customers = data.get("customers", [])

            if not customers:
                return {
                    "found": False,
                    "message": "No customer found with that phone number",
                }

            customer_id = customers[0]["id"]

            # Get all bookings
            bookings_response = requests.get(
                f"{self.base_url}/v2/bookings?location_id={self.location_id}&limit=100",
                headers=self.headers,
            )

            if bookings_response.status_code != 200:
                return {
                    "found": False,
                    "message": "Error fetching bookings",
                }

            bookings_data = bookings_response.json()
            all_bookings = bookings_data.get("bookings", [])

            # Filter for this customer's active bookings
            customer_bookings = [
                b for b in all_bookings
                if b.get("customer_id") == customer_id
                and b.get("status") in ["ACCEPTED", "PENDING"]
            ]

            if not customer_bookings:
                return {
                    "found": False,
                    "message": "No active bookings found",
                }

            # Return the most recent booking
            booking = customer_bookings[0]
            start_time = booking.get("start_at", "")
            time_part = start_time[11:16] if len(start_time) > 16 else ""
            date_part = start_time[:10] if len(start_time) > 10 else ""

            return {
                "found": True,
                "booking_id": booking.get("id"),
                "date": date_part,
                "time": time_part,
                "party_size": booking.get("customer_note", "").replace("Party size: ", ""),
                "message": f"Found booking for {date_part} at {time_part}",
            }

        except Exception as e:
            return {
                "found": False,
                "message": f"Error: {str(e)}",
            }

    async def create_pickup_order(
        self,
        items: list,
        pickup_time: str,
        customer_name: str,
        customer_phone: str,
        notes: str = "",
    ) -> dict:
        """Create a real pickup order in Square Orders API."""
        try:
            # Build line items
            line_items = []
            for item in items:
                name = item.get("name", "Item")
                size = item.get("size", "")
                sauce = item.get("sauce", "")
                qty = str(item.get("quantity", 1))
                display_name = name
                if size:
                    display_name += f" {size}"
                if sauce:
                    display_name += f" ({sauce})"

                price_cents = _price_cents(name, size)
                line_items.append({
                    "name": display_name,
                    "quantity": qty,
                    "base_price_money": {"amount": price_cents, "currency": "USD"},
                    "note": item.get("notes", ""),
                })

            # Normalize phone
            digits = "".join(c for c in customer_phone if c.isdigit())
            if len(digits) == 10:
                phone_e164 = f"+1{digits}"
            elif len(digits) == 11 and digits.startswith("1"):
                phone_e164 = f"+{digits}"
            else:
                phone_e164 = customer_phone

            # Pickup time: try to parse a human time like "6:00 PM" or "ASAP"
            now = datetime.now()
            if pickup_time.upper() == "ASAP":
                pickup_at = (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")
            else:
                try:
                    t = datetime.strptime(pickup_time, "%I:%M %p")
                    pickup_at = now.replace(hour=t.hour, minute=t.minute, second=0).strftime("%Y-%m-%dT%H:%M:%S")
                except Exception:
                    pickup_at = (now + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")

            order_note = notes or ""

            payload = {
                "idempotency_key": str(uuid.uuid4()),
                "order": {
                    "location_id": self.location_id,
                    "line_items": line_items,
                    "fulfillments": [
                        {
                            "type": "PICKUP",
                            "state": "PROPOSED",
                            "pickup_details": {
                                "recipient": {
                                    "display_name": customer_name,
                                    "phone_number": phone_e164,
                                },
                                "pickup_at": pickup_at,
                                "note": order_note,
                            },
                        }
                    ],
                },
            }

            response = requests.post(
                f"{self.base_url}/v2/orders",
                headers=self.headers,
                json=payload,
            )

            if response.status_code in (200, 201):
                order = response.json().get("order", {})
                order_id = order.get("id", "")[:8].upper()
                total_cents = sum(
                    li.get("total_money", {}).get("amount", 0)
                    for li in order.get("line_items", [])
                )
                return {
                    "success": True,
                    "order_id": order_id,
                    "square_order_id": order.get("id"),
                    "pickup_time": pickup_time,
                    "customer_name": customer_name,
                    "customer_phone": phone_e164,
                    "total": f"${total_cents/100:.2f}" if total_cents else "see receipt",
                    "message": f"Order {order_id} confirmed for {customer_name}, pickup at {pickup_time}",
                }
            else:
                return {
                    "success": False,
                    "message": f"Square order failed ({response.status_code}): {response.text}",
                }

        except Exception as e:
            return {"success": False, "message": f"Error creating order: {str(e)}"}

    async def cancel_booking(self, booking_id: str) -> dict:
        """Cancel an existing booking."""
        try:
            response = requests.post(
                f"{self.base_url}/v2/bookings/{booking_id}/cancel",
                headers=self.headers,
                json={}
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Booking cancelled successfully",
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to cancel: {response.text}",
                }

        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }


# Singleton instance
square_service = SquareBookingService()
