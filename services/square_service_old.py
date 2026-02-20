"""Square Bookings API Service."""

from datetime import datetime, timedelta
from typing import Optional
from square import Square
from square.environment import SquareEnvironment
from utils.config import config


class SquareBookingService:
    """Handle restaurant availability and bookings via Square API."""

    def __init__(self):
        env = SquareEnvironment.SANDBOX if config.SQUARE_ENVIRONMENT == "sandbox" else SquareEnvironment.PRODUCTION
        self.client = Square(
            token=config.SQUARE_ACCESS_TOKEN,
            environment=env,
        )
        self.location_id = config.SQUARE_LOCATION_ID
        self.bookings_api = self.client.bookings

    async def check_availability(
        self,
        date: str,  # YYYY-MM-DD
        party_size: int,
        preferred_time: Optional[str] = None,  # HH:MM
    ) -> dict:
        """
        Check available time slots for a given date.

        Returns:
            {
                "available": True/False,
                "slots": ["18:00", "18:30", "19:00", ...],
                "message": "Human readable message"
            }
        """
        try:
            # Build search query
            start_at = f"{date}T00:00:00Z"
            end_date = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
            end_at = end_date.strftime("%Y-%m-%dT00:00:00Z")

            result = self.bookings_api.search_availability(
                body={
                    "query": {
                        "filter": {
                            "start_at_range": {
                                "start_at": start_at,
                                "end_at": end_at,
                            },
                            "location_id": self.location_id,
                            "segment_filters": [
                                {
                                    "service_variation_id": "ALL",  # Check all services
                                }
                            ],
                        }
                    }
                }
            )

            if result.is_success():
                availabilities = result.body.get("availabilities", [])
                slots = []
                for avail in availabilities:
                    start_time = avail.get("start_at", "")
                    if start_time:
                        # Extract time portion
                        time_part = start_time[11:16]  # HH:MM
                        slots.append(time_part)

                if slots:
                    return {
                        "available": True,
                        "slots": sorted(set(slots)),
                        "message": f"Found {len(slots)} available time slots",
                    }
                else:
                    return {
                        "available": False,
                        "slots": [],
                        "message": "No availability for this date",
                    }
            else:
                return {
                    "available": False,
                    "slots": [],
                    "message": f"Error checking availability: {result.errors}",
                }

        except Exception as e:
            return {
                "available": False,
                "slots": [],
                "message": f"Error: {str(e)}",
            }

    async def create_booking(
        self,
        date: str,  # YYYY-MM-DD
        time: str,  # HH:MM
        party_size: int,
        customer_name: str,
        customer_phone: str,
        customer_email: Optional[str] = None,
    ) -> dict:
        """
        Create a reservation.

        Returns:
            {
                "success": True/False,
                "booking_id": "...",
                "confirmation": "...",
                "message": "Human readable message"
            }
        """
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
            start_at = f"{date}T{time}:00Z"

            result = self.bookings_api.create_booking(
                body={
                    "booking": {
                        "location_id": self.location_id,
                        "customer_id": customer_id,
                        "start_at": start_at,
                        "customer_note": f"Party size: {party_size}",
                        "appointment_segments": [
                            {
                                "duration_minutes": 90,  # Default 1.5 hour reservation
                                "team_member_id": "ANY",
                                "service_variation_id": "ALL",
                            }
                        ],
                    }
                }
            )

            if result.is_success():
                booking = result.body.get("booking", {})
                return {
                    "success": True,
                    "booking_id": booking.get("id"),
                    "confirmation": booking.get("id", "")[:8].upper(),
                    "message": f"Booking confirmed for {party_size} at {time} on {date}",
                }
            else:
                return {
                    "success": False,
                    "message": f"Booking failed: {result.errors}",
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
        """Create or find a customer in Square."""
        try:
            customers_api = self.client.customers

            # Try to find existing customer by phone
            search_result = customers_api.search_customers(
                body={
                    "query": {
                        "filter": {
                            "phone_number": {"exact": phone}
                        }
                    }
                }
            )

            if search_result.is_success():
                customers = search_result.body.get("customers", [])
                if customers:
                    return {
                        "success": True,
                        "customer_id": customers[0]["id"],
                    }

            # Create new customer
            name_parts = name.split(" ", 1)
            given_name = name_parts[0]
            family_name = name_parts[1] if len(name_parts) > 1 else ""

            create_result = customers_api.create_customer(
                body={
                    "given_name": given_name,
                    "family_name": family_name,
                    "phone_number": phone,
                    "email_address": email,
                }
            )

            if create_result.is_success():
                return {
                    "success": True,
                    "customer_id": create_result.body["customer"]["id"],
                }
            else:
                return {
                    "success": False,
                    "message": str(create_result.errors),
                }

        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }

    async def cancel_booking(self, booking_id: str) -> dict:
        """Cancel an existing booking."""
        try:
            result = self.bookings_api.cancel_booking(
                booking_id=booking_id,
                body={}
            )

            if result.is_success():
                return {
                    "success": True,
                    "message": "Booking cancelled successfully",
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to cancel: {result.errors}",
                }

        except Exception as e:
            return {
                "success": False,
                "message": str(e),
            }


# Singleton instance
square_service = SquareBookingService()
