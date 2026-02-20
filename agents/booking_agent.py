"""Restaurant Booking Agent - Conversation Logic."""

import json
import re
from datetime import datetime, timedelta
from typing import Optional
from openai import AsyncOpenAI
from services.square_service import square_service
from utils.config import config


class BookingAgent:
    """AI agent that handles restaurant booking conversations."""

    def __init__(self):
        self.openai = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self.conversation_history = []
        self.booking_info = {
            "date": None,
            "time": None,
            "party_size": None,
            "customer_name": None,
            "customer_phone": None,
        }
        self.pickup_orders = []  # Store pickup orders in memory

        self.system_prompt = """You are the phone assistant for Bonchon, a Korean Fried Chicken Restaurant. Your job is to help callers:
1. Check the menu (items, categories, prices, basic ingredients, spice level, allergens)
2. Place a pickup order (pickup only - no delivery)
3. Make a table reservation (via Square Booking)
4. Answer business hours and basic location questions

You must be friendly, fast, and accurate, and you must confirm critical details (names, phone numbers, times, quantities) before finalizing anything.

## Ground Rules
- Pickup only: If a caller requests delivery, tell them the restaurant does not provide delivery directly and suggest ordering via DoorDash or Uber Eats instead.
- No guessing: Do not invent menu items, prices, availability, or policies.
- Always summarize + confirm before submitting a pickup order or reservation.
- If audio is unclear, ask politely to repeat and then read it back.
- Privacy: Collect only what's needed.

## Business Context
- Restaurant name: Bonchon
- Menu reference: https://order.bonchon.com/menu/ca-san-jose-n-capitol-ave-2
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

## Business Hours Handling
If asked about hours:
- "Our regular hours are 11:00 AM to 9:00 PM every day."
- "Would you like to place a pickup order or make a reservation?"

If asked "Are you open now?":
- Compare current time (PST) to hours
- "Our regular hours are 11 to 9 daily. If you tell me what time you're planning to come, I can confirm."

## Menu Inquiry Handling
1. Respond with ONLY 1-2 items max, very brief
   - Example: "We have wings or bulgogi. Which sounds good?"
2. Don't mention sizes/prices unless asked
3. If they want more options, give 1-2 more
4. Keep it conversational and brief

IMPORTANT: Ultra-short menu responses - no lists, no details unless asked!

## Pickup Order Flow (Bonchon supports pickup ONLY)
Required info: Items + quantities, pickup time, name, phone, notes (allergies, sauce preference, etc.)

1. Start:
   - If user already mentioned an item (e.g., "I want wings"): Skip to confirming size/sauce
   - If user just says "I want to order": "Great—I can help with a pickup order. What would you like to order?"
2. For each item:
   - If chicken item: Ask size FIRST: "What size?" (Small/Medium/Large)
   - Then ask sauce SEPARATELY: "Which sauce?" (Soy Garlic/Spicy/Korean)
   - Confirm: "Got it - {{size}} {{item}} with {{sauce}}."
   - Then ask: "Anything else?"
   - If yes, repeat for next item
   - If no, proceed to step 3

IMPORTANT: Ask size and sauce as TWO separate questions, not together!
3. Pickup time: "When would you like to pick it up—as soon as possible or a specific time?"
4. Contact: "Can I get your name and phone number for the order?"
   - Read back phone digit-by-digit: "I heard {{phone}}—is that correct?"
5. Final summary + confirmation (use natural language, not bullet points):
   "Just to confirm, you'd like {{items}} for pickup at {{pickup_time}} under the name {{name}}, phone number {{phone}}. Should I place this order for you?"
6. After confirmation: "Done! Your pickup order is confirmed for {{pickup_time}} under {{name}}. Anything else I can help with?"

## Delivery Request Handling (not supported)
If caller asks delivery:
"Bonchon doesn't offer delivery directly. For delivery, please order through DoorDash or Uber Eats. If you'd like, I can help you place a pickup order right now instead."

## Table Reservation Flow (Square Booking)
CRITICAL: Check availability FIRST before collecting name/phone.

Restaurant capacity: Maximum 50 people per reservation. For parties larger than 50, politely decline and suggest they contact the restaurant directly for special event planning.

Required info: Party size, date, time

1. Collect request: "Sure—I can help with a reservation. For how many people, and what date and time?"
2. Confirm: "Got it: {{party_size}} people, {{date}}, {{time}}. Let me check availability."
3. Check availability: call check_availability(date, time, party_size)
4. If available:
   "Great—there's availability at {{date}} {{time}} for {{party_size}}. May I have your name and phone number to complete the reservation?"
   - Read back phone: "I heard {{phone}}—is that correct?"
5. Create reservation: call create_booking(date, time, party_size, name, phone)
6. Confirm: "Your reservation is confirmed: {{name}}, {{party_size}} people, {{date}} at {{time}}. We look forward to seeing you!"
7. If NOT available:
   - Offer alternatives: "I'm sorry, {{time}} is fully booked. We have {{alt1}} and {{alt2}}. Would either work?"
   - If fully booked: "I'm sorry, we're fully booked that day. Would another day work?"

## Cancellation Flow
1. Ask name: "May I have your name?"
2. Search today's booking: call find_booking(name, today)
   - If found: "I found your reservation for today at {{time}} for {{party_size}}. Is this the one you'd like to cancel?"
   - If not found: "I couldn't find a reservation under that name. Could you give me the phone number on the reservation?"
3. If phone provided: call find_booking_by_phone(phone)
4. User confirms: "yes" / "that's right"
5. Cancel: call cancel_booking(booking_id)
6. Confirm: "Your reservation has been cancelled. Thank you for letting us know!"

## Important Rules
✓ NEVER interrupt the user - wait until they finish speaking completely before responding
✓ Do NOT use markdown formatting (**, ##, etc.) in your responses - this is voice conversation, not text
✓ Keep responses EXTREMELY SHORT - maximum 1-2 sentences, preferably just 1 sentence
✓ Avoid listing multiple items - ask one question at a time
✓ Do NOT ask for name/phone until you confirm availability (for reservations)
✓ Always offer alternative times if first choice is unavailable
✓ Be warm, professional, concise
✓ If user changes party size, date, or time → MUST re-check availability

## Phone Number Rules (CRITICAL - READ CAREFULLY)
- A valid US phone number has exactly 10 digits
- When asking for phone number: "What's your phone number?" then WAIT and LISTEN
- Do NOT interrupt while user is saying phone number - they often pause between digit groups
- Users say phone numbers in parts: "six six nine" [pause] "two nine zero" [pause] "nine seven six seven"
- WAIT for complete silence (at least 500ms) before responding
- If you got FEWER than 10 digits, say: "I got {{what_you_heard}}, and the rest?"
- Only confirm AFTER you have all 10 digits

## Escalation / Transfer to Human
Escalate if:
- Caller is angry / complaint / refund disputes
- Multiple misunderstandings due to audio
- Severe allergy questions requiring kitchen confirmation
- Booking/order tool failures after retry

## Response Examples (Keep it SHORT!)

BAD (too long):
"Great! I can help you with that. Let me check our availability for you. For what date and time would you like to make a reservation, and how many people will be joining you?"

GOOD (concise):
"Sure! How many people and what time?"

BAD:
"I found your reservation for today at 6:00 PM for 2 guests. Is this the reservation you would like to cancel?"

GOOD:
"Found it - today at 6 PM for 2. Cancel this one?"

TONE: Friendly, efficient, professional. Always say "please" and "thank you"."""

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "create_pickup_order",
                    "description": "Create a pickup order for the customer. Use this after collecting all order details and getting customer confirmation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string", "description": "Item name (e.g., 'Wings', 'Bulgogi')"},
                                        "size": {"type": "string", "description": "Size (Small/Medium/Large) if applicable"},
                                        "quantity": {"type": "integer", "description": "Quantity"},
                                        "sauce": {"type": "string", "description": "Sauce choice (Soy Garlic/Spicy/Korean) if applicable"},
                                        "notes": {"type": "string", "description": "Special requests for this item"}
                                    },
                                    "required": ["name", "quantity"]
                                },
                                "description": "List of ordered items"
                            },
                            "pickup_time": {"type": "string", "description": "Pickup time (e.g., 'ASAP', '6:00 PM', '18:00')"},
                            "customer_name": {"type": "string", "description": "Customer's name"},
                            "customer_phone": {"type": "string", "description": "Customer's phone number"},
                            "notes": {"type": "string", "description": "Additional order notes (allergies, utensils, etc.)"}
                        },
                        "required": ["items", "pickup_time", "customer_name", "customer_phone"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "transfer_to_human",
                    "description": "Transfer the call to a human staff member. Use this for non-booking requests like complaints, menu questions, or general inquiries.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "Brief reason for transfer (e.g., 'complaint', 'menu question', 'general inquiry')",
                            },
                        },
                        "required": ["reason"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_availability",
                    "description": "Check restaurant availability for a specific date, time, and party size",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {
                                "type": "string",
                                "description": "Date in YYYY-MM-DD format",
                            },
                            "time": {
                                "type": "string",
                                "description": "Time in HH:MM format (24-hour)",
                            },
                            "party_size": {
                                "type": "integer",
                                "description": "Number of guests",
                            },
                        },
                        "required": ["date", "party_size"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_booking",
                    "description": "Create a restaurant reservation in Square. MUST be called immediately after collecting customer name and phone number. This sends SMS confirmation to the customer.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "YYYY-MM-DD"},
                            "time": {"type": "string", "description": "HH:MM (24-hour format)"},
                            "party_size": {"type": "integer", "description": "Number of guests"},
                            "customer_name": {"type": "string", "description": "Full name"},
                            "customer_phone": {"type": "string", "description": "Phone number (any format)"},
                        },
                        "required": ["date", "time", "party_size", "customer_name", "customer_phone"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_booking",
                    "description": "Find a customer's booking by their name and reservation date",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_name": {"type": "string", "description": "Customer's name"},
                            "date": {"type": "string", "description": "Reservation date in YYYY-MM-DD format"},
                        },
                        "required": ["customer_name", "date"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_booking_by_phone",
                    "description": "Find a customer's booking by phone number. Use this when name search fails.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_phone": {"type": "string", "description": "Customer's phone number"},
                        },
                        "required": ["customer_phone"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "cancel_booking",
                    "description": "Cancel an existing reservation by booking ID. Only call this AFTER finding the booking with find_booking.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "booking_id": {"type": "string", "description": "The booking ID from find_booking"},
                        },
                        "required": ["booking_id"],
                    },
                },
            },
        ]

    async def process_message(self, user_message: str) -> str:
        """
        Process user message and return agent response.

        This handles the full conversation flow including function calls.
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message,
        })

        # Inject current date into system prompt
        current_date = datetime.now().strftime("%Y-%m-%d (%A)")
        system_prompt_with_date = self.system_prompt.format(current_date=current_date)

        # Get LLM response
        response = await self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt_with_date},
                *self.conversation_history,
            ],
            tools=self.tools,
            tool_choice="auto",
        )

        message = response.choices[0].message

        # Handle function calls
        if message.tool_calls:
            # Add assistant message with tool calls
            self.conversation_history.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in message.tool_calls
                ],
            })

            # Execute each function call
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                # Call the appropriate function
                if func_name == "create_pickup_order":
                    result = await self._create_pickup_order(**func_args)
                elif func_name == "transfer_to_human":
                    result = await self._transfer_to_human(**func_args)
                elif func_name == "check_availability":
                    result = await self._check_availability(**func_args)
                elif func_name == "create_booking":
                    result = await self._create_booking(**func_args)
                elif func_name == "find_booking":
                    result = await self._find_booking(**func_args)
                elif func_name == "find_booking_by_phone":
                    result = await self._find_booking_by_phone(**func_args)
                elif func_name == "cancel_booking":
                    result = await self._cancel_booking(**func_args)
                else:
                    result = {"error": f"Unknown function: {func_name}"}

                # Add function result to history
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })

            # Get final response after function execution
            final_response = await self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt_with_date},
                    *self.conversation_history,
                ],
            )

            assistant_message = final_response.choices[0].message.content
        else:
            assistant_message = message.content

        # Add assistant response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message,
        })

        return assistant_message

    async def _create_pickup_order(
        self,
        items: list,
        pickup_time: str,
        customer_name: str,
        customer_phone: str,
        notes: Optional[str] = None,
    ) -> dict:
        """Create a pickup order (stored in memory for demo)."""
        import uuid
        from datetime import datetime

        # Generate order ID
        order_id = str(uuid.uuid4())[:8].upper()

        # Calculate estimated total (rough estimate for demo)
        total_items = sum(item.get("quantity", 1) for item in items)

        # Store order
        order = {
            "order_id": order_id,
            "items": items,
            "pickup_time": pickup_time,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "notes": notes or "",
            "created_at": datetime.now().isoformat(),
            "status": "confirmed"
        }
        self.pickup_orders.append(order)

        # Format items for confirmation
        items_summary = []
        for item in items:
            item_str = f"{item['quantity']}x {item['name']}"
            if item.get('size'):
                item_str += f" ({item['size']})"
            if item.get('sauce'):
                item_str += f" - {item['sauce']}"
            items_summary.append(item_str)

        return {
            "success": True,
            "order_id": order_id,
            "items": items_summary,
            "pickup_time": pickup_time,
            "customer_name": customer_name,
            "message": f"Pickup order {order_id} confirmed for {customer_name} at {pickup_time}. Total items: {total_items}"
        }

    async def _check_availability(
        self,
        date: str,
        party_size: int,
        time: Optional[str] = None,
    ) -> dict:
        """Check availability via Square API."""
        # Store in booking info
        self.booking_info["date"] = date
        self.booking_info["party_size"] = party_size
        if time:
            self.booking_info["time"] = time

        result = await square_service.check_availability(
            date=date,
            party_size=party_size,
            preferred_time=time,
        )

        return result

    async def _create_booking(
        self,
        date: str,
        time: str,
        party_size: int,
        customer_name: str,
        customer_phone: str,
    ) -> dict:
        """Create booking via Square API."""
        # Update booking info
        self.booking_info.update({
            "date": date,
            "time": time,
            "party_size": party_size,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
        })

        result = await square_service.create_booking(
            date=date,
            time=time,
            party_size=party_size,
            customer_name=customer_name,
            customer_phone=customer_phone,
        )

        return result

    async def _transfer_to_human(self, reason: str) -> dict:
        """Transfer call to human staff."""
        # In production, this would trigger actual call transfer
        # For now, just return a message
        return {
            "success": True,
            "transferred": True,
            "reason": reason,
            "message": f"Call transfer initiated for: {reason}",
        }

    async def _find_booking(
        self,
        customer_name: str,
        date: str,
    ) -> dict:
        """Find customer's booking."""
        result = await square_service.find_booking_by_name_and_date(
            customer_name=customer_name,
            date=date,
        )
        return result

    async def _find_booking_by_phone(self, customer_phone: str) -> dict:
        """Find booking by phone number."""
        result = await square_service.find_booking_by_customer(
            customer_name="",
            customer_phone=customer_phone,
        )
        return result

    async def _cancel_booking(self, booking_id: str) -> dict:
        """Cancel a booking via Square API."""
        result = await square_service.cancel_booking(booking_id)
        return result

    def get_greeting(self) -> str:
        """Return initial greeting."""
        return "Thanks for calling Bonchon! What can I help you with today?"

    def reset(self):
        """Reset conversation state."""
        self.conversation_history = []
        self.booking_info = {
            "date": None,
            "time": None,
            "party_size": None,
            "customer_name": None,
            "customer_phone": None,
        }
