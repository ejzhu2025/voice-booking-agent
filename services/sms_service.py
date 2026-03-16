"""Twilio SMS notifications for order and booking confirmations."""

from twilio.rest import Client
from utils.config import config


def _client() -> Client:
    return Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)


def _normalize(phone: str) -> str:
    """Ensure E.164 format (+1XXXXXXXXXX for US numbers)."""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return phone  # already formatted or international


async def send_order_confirmation(
    customer_phone: str,
    customer_name: str,
    order_id: str,
    items_summary: list[str],
    pickup_time: str,
    total: str = "",
) -> bool:
    """Send SMS confirmation after a pickup order is placed."""
    try:
        items_text = "\n".join(f"  • {i}" for i in items_summary)
        total_line = f"\nTotal: {total}" if total else ""
        body = (
            f"Bonchon Order Confirmed! 🍗\n"
            f"Order #{order_id}\n"
            f"{items_text}{total_line}\n"
            f"Pickup: {pickup_time}\n"
            f"See you soon, {customer_name}!"
        )
        _client().messages.create(
            to=_normalize(customer_phone),
            from_=config.TWILIO_PHONE_NUMBER,
            body=body,
        )
        print(f"[SMS] Order confirmation sent to {customer_phone}")
        return True
    except Exception as e:
        print(f"[SMS] Failed to send order SMS: {e}")
        return False


async def send_booking_confirmation(
    customer_phone: str,
    customer_name: str,
    booking_id: str,
    date: str,
    time: str,
    party_size: int,
) -> bool:
    """Send SMS confirmation after a table reservation is made."""
    try:
        body = (
            f"Bonchon Reservation Confirmed! 🍗\n"
            f"Confirmation: {booking_id}\n"
            f"Date: {date} at {time}\n"
            f"Party of {party_size}\n"
            f"Name: {customer_name}\n"
            f"Questions? Call us back anytime."
        )
        _client().messages.create(
            to=_normalize(customer_phone),
            from_=config.TWILIO_PHONE_NUMBER,
            body=body,
        )
        print(f"[SMS] Booking confirmation sent to {customer_phone}")
        return True
    except Exception as e:
        print(f"[SMS] Failed to send booking SMS: {e}")
        return False
