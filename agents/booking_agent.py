"""
Booking Agent — System prompt, Gemini tool declarations, and tool execution.

The conversation logic runs entirely inside Gemini Live (via GeminiLiveService).
This module provides:
  - get_system_prompt()  → str
  - get_tools()          → list[types.Tool]  (Gemini function declarations)
  - BookingTools         → executes Square API calls when Gemini calls a function
"""

from datetime import datetime
from typing import Optional

from google.genai import types

from services.square_service import square_service


# ── System Prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_TEMPLATE = """You are the phone assistant for Bonchon, a Korean Fried Chicken Restaurant. The caller has ALREADY been greeted — do NOT say any greeting. Go straight to helping them as soon as they speak. Your job is to help callers:
1. Check the menu (items, categories, prices, basic ingredients, spice level, allergens)
2. Place a pickup order (pickup only - no delivery)
3. Make a table reservation (via Square Booking)
4. Answer business hours and basic location questions

You must be friendly, fast, and accurate, and you must confirm critical details (names, phone numbers, times, quantities) before finalizing anything.

LANGUAGE RULE (CRITICAL): Mirror the caller's language exactly. Detect from their first words and maintain it for the entire call.
- Caller speaks English → respond in English
- Caller speaks Mandarin → respond in Mandarin (普通话)
- Caller speaks Cantonese → respond in Cantonese (广东话)
- Caller speaks Spanish → respond in Spanish
- Any other language → respond in that same language
- If the caller switches language mid-call, you switch too.
- NEVER respond in a different language than the one the caller is using.

## Ground Rules
- Pickup only: If a caller requests delivery, tell them the restaurant does not provide delivery directly and suggest ordering via DoorDash or Uber Eats instead.
- No guessing: Do not invent menu items, prices, availability, or policies.
- Always summarize + confirm before submitting a pickup order or reservation.
- If audio is unclear, ask politely to repeat and then read it back.
- Privacy: Collect only what is needed.

## Business Context
- Restaurant name: Bonchon
- Hours: 11:00 AM – 9:00 PM daily (open every day)
- Today's date: {current_date}

## Menu
**Signature Fried Chicken** (includes complimentary pickled radish or coleslaw):
- Sauces available: Soy Garlic, Spicy, Korean

Wings: Small (8pcs/$16.55), Medium (16pcs/$29.95), Large (24pcs/$42.35)
Boneless: Small (12pcs/$16.95), Medium (24pcs/$31.90), Large (36pcs/$43.95)
Drumsticks: Small (4pcs/$15.85), Medium (8pcs/$29.95), Large (12pcs/$41.35)
Combo (Wings & Drums): Small (4W+2D/$16.55), Medium (8W+4D/$29.95), Large (12W+6D/$42.35)
Strips: Small (10pcs/$17.60), Medium (20pcs/$31.90), Large (30pcs/$44.50)

**Main Dishes**:
- Tteokbokki ($15.80): Rice cakes in spicy sauce with fish cakes, mozzarella, veggie potstickers
- Japchae ($17.60): Glass noodles with vegetables and marinated ribeye in Soy Garlic sauce
- Buldak ($19.80, very spicy): Spicy chicken stir-fried with rice cakes, mozzarella. Served with rice
- Bulgogi ($20.85): Marinated USDA beef with mushrooms, scallions. Served with rice
- Chicken Katsu ($14.75): Breaded chicken cutlet with rice, katsu sauce, spicy mayo

## Greeting
"Thanks for calling Bonchon! What can I help you with today?"
(Always mention Bonchon in the greeting so the caller knows which restaurant they reached.)

## Menu Inquiry Handling
1. Respond with ONLY 1-2 items max, very brief
2. Don't mention sizes/prices unless asked
3. Keep it conversational

## Pickup Order Flow
Required info: Items + quantities, pickup time, name, phone

1. If user mentioned an item: Skip to confirming size/sauce
2. For each chicken item: Ask size FIRST, then sauce as two separate questions
3. Pickup time: "When would you like to pick it up?"
4. Contact: Name and phone number. Read back phone digit-by-digit to confirm.
5. Final summary + confirmation before placing order.

## Table Reservation Flow
CRITICAL: Check availability FIRST before collecting name/phone.

1. Collect: party size, date, time
2. Call check_availability
3. If available: collect name and phone, then call create_booking
4. If NOT available: offer alternative times

## Cancellation Flow
1. Ask name → call find_booking(name, today)
2. If not found: ask phone → call find_booking_by_phone
3. Confirm details, then call cancel_booking

## Important Rules
- Do NOT use markdown formatting (**, ##, etc.) — this is voice
- Keep responses EXTREMELY SHORT — max 1-2 sentences
- Ask one question at a time
- Do NOT ask for name/phone until availability is confirmed
- If user changes party size, date, or time → re-check availability

## Phone Number Rules
- If the caller's phone number was provided at the start of the call, USE IT as default — say "I'll use the number you're calling from, [number]. Is that correct?" instead of asking them to say it.
- If no caller ID was provided, ask for the phone number verbally.
- Valid US phone number = exactly 10 digits.
- Read back any phone number digit-by-digit to confirm.

## Escalation
Transfer to human if: angry caller, repeated misunderstandings, severe allergy questions, tool failures."""


def get_system_prompt() -> str:
    from zoneinfo import ZoneInfo
    pacific = ZoneInfo("America/Los_Angeles")
    now = datetime.now(pacific)
    current_date = now.strftime("%Y-%m-%d (%A), %-I:%M %p PT")
    return _SYSTEM_PROMPT_TEMPLATE.format(current_date=current_date)


# ── Gemini Tool Declarations ─────────────────────────────────────────────────

def get_tools() -> list[types.Tool]:
    """Return Gemini function declarations for all booking operations."""
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="create_pickup_order",
                    description="Create a confirmed pickup order after collecting all details and customer confirmation.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "items": types.Schema(
                                type=types.Type.ARRAY,
                                description="List of ordered items",
                                items=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "name": types.Schema(type=types.Type.STRING),
                                        "size": types.Schema(type=types.Type.STRING),
                                        "quantity": types.Schema(type=types.Type.INTEGER),
                                        "sauce": types.Schema(type=types.Type.STRING),
                                        "notes": types.Schema(type=types.Type.STRING),
                                    },
                                    required=["name", "quantity"],
                                ),
                            ),
                            "pickup_time": types.Schema(type=types.Type.STRING, description="e.g. 'ASAP' or '6:00 PM'"),
                            "customer_name": types.Schema(type=types.Type.STRING),
                            "customer_phone": types.Schema(type=types.Type.STRING),
                            "notes": types.Schema(type=types.Type.STRING, description="Allergies, special requests"),
                        },
                        required=["items", "pickup_time", "customer_name", "customer_phone"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="check_availability",
                    description="Check restaurant table availability for a date, time, and party size.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD"),
                            "time": types.Schema(type=types.Type.STRING, description="HH:MM 24-hour, optional"),
                            "party_size": types.Schema(type=types.Type.INTEGER),
                        },
                        required=["date", "party_size"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="create_booking",
                    description="Create a table reservation in Square after availability confirmed and customer details collected.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD"),
                            "time": types.Schema(type=types.Type.STRING, description="HH:MM 24-hour"),
                            "party_size": types.Schema(type=types.Type.INTEGER),
                            "customer_name": types.Schema(type=types.Type.STRING),
                            "customer_phone": types.Schema(type=types.Type.STRING),
                        },
                        required=["date", "time", "party_size", "customer_name", "customer_phone"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="find_booking",
                    description="Find an existing reservation by customer name and date.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "customer_name": types.Schema(type=types.Type.STRING),
                            "date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD"),
                        },
                        required=["customer_name", "date"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="find_booking_by_phone",
                    description="Find an existing reservation by phone number. Use when name search fails.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "customer_phone": types.Schema(type=types.Type.STRING),
                        },
                        required=["customer_phone"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="cancel_booking",
                    description="Cancel a reservation by booking ID obtained from find_booking.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "booking_id": types.Schema(type=types.Type.STRING),
                        },
                        required=["booking_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="transfer_to_human",
                    description="Transfer the call to a human staff member for complaints, complex issues, or tool failures.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "reason": types.Schema(type=types.Type.STRING),
                        },
                        required=["reason"],
                    ),
                ),
            ]
        )
    ]


# ── Tool Execution ───────────────────────────────────────────────────────────

class BookingTools:
    """Executes the actual tool calls against Square API and in-memory store."""

    def __init__(self):
        self.pickup_orders = []

    async def handle(self, name: str, args: dict) -> dict:
        """Dispatch a Gemini function call to the appropriate handler."""
        if name == "create_pickup_order":
            return await self._create_pickup_order(**args)
        elif name == "check_availability":
            # Gemini sends 'time', Square expects 'preferred_time'
            sq_args = {k: v for k, v in args.items() if k != "time"}
            if "time" in args:
                sq_args["preferred_time"] = args["time"]
            return await square_service.check_availability(**sq_args)
        elif name == "create_booking":
            return await square_service.create_booking(**args)
        elif name == "find_booking":
            return await square_service.find_booking_by_name_and_date(**args)
        elif name == "find_booking_by_phone":
            return await square_service.find_booking_by_customer(
                customer_name="", customer_phone=args["customer_phone"]
            )
        elif name == "cancel_booking":
            return await square_service.cancel_booking(args["booking_id"])
        elif name == "transfer_to_human":
            return {"success": True, "transferred": True, "reason": args.get("reason", "")}
        else:
            return {"error": f"Unknown function: {name}"}

    async def _create_pickup_order(
        self,
        items: list,
        pickup_time: str,
        customer_name: str,
        customer_phone: str,
        notes: Optional[str] = None,
    ) -> dict:
        # Create real order in Square Orders API
        result = await square_service.create_pickup_order(
            items=items,
            pickup_time=pickup_time,
            customer_name=customer_name,
            customer_phone=customer_phone,
            notes=notes or "",
        )

        if not result.get("success"):
            return result

        # Build human-readable items summary
        items_summary = []
        for item in items:
            s = f"{item['quantity']}x {item['name']}"
            if item.get("size"):
                s += f" {item['size']}"
            if item.get("sauce"):
                s += f" ({item['sauce']})"
            items_summary.append(s)

        result["items"] = items_summary
        return result


def get_greeting() -> str:
    return "Thanks for calling Bonchon! What can I help you with today?"
