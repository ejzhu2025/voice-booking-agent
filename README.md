# Ringo — AI Phone Agent for Restaurants

![unnamed](https://github.com/user-attachments/assets/016103c9-21e5-4d4e-a3ff-918bb98777c8)

![Deploy](https://github.com/ejzhu2025/voice-booking-agent/actions/workflows/deploy.yml/badge.svg)

> **Every call answered. Every order taken. No staff required.**

**Try it now:** Call **669-201-5051** — place an order, book a table, or ask about the menu. No app, no typing.

**Demo video:** https://www.youtube.com/shorts/BQhC79C_ZXg

**Website:** https://get-ringo.com

---

## The Problem

Restaurant phones ring constantly — during lunch rush, after hours, when staff are occupied. Missed calls mean missed revenue. Hiring someone to answer phones costs $15–25/hour and still produces errors: wrong orders, missed allergy notes, double-booked tables.

The fix isn't a chatbot. It's a voice agent that sounds natural, handles interruptions, and writes the order correctly every time.

---

## Design Philosophy

Four principles shaped every decision in this system:

**1. Latency is the product.**
In a phone conversation, a 2-second pause feels like a disconnect. The architecture is built around minimizing end-to-end audio latency — from the caller's voice to the agent's spoken response. Everything else is secondary.

**2. One agent, structured actions — not free-form generation.**
A single orchestrator agent maps caller intent to a small set of explicit tool calls: `check_availability`, `create_booking`, `create_pickup_order`, `cancel_booking`, `transfer_to_human`. The agent never generates freeform actions. This makes the system easier to debug, cheaper to run, and more reliable in production than a multi-agent pipeline.

**3. Every write action requires confirmation.**
Before placing an order or booking a table, the agent reads back the full details and waits for an explicit yes. The biggest operational risk isn't an unnatural conversation — it's a wrong order or a missed allergy. Confirmation before commit prevents that.

**4. Structured state, not raw conversation history.**
Session memory is a structured state object tracking items ordered, party size, pickup time, and unresolved questions — not a raw transcript fed back to the model. Restaurant context (menu, hours, policies, escalation rules) is injected as a separate system prompt, not mixed into conversation history.

---

## Architecture

```
Caller
  │  phone call
  ▼
Twilio                          ← telephony layer: PSTN → WebSocket
  │  mulaw 8kHz audio stream
  ▼
FastAPI Server (Cloud Run)      ← voice bridge + VAD + session management
  │  PCM 16kHz + ActivityStart/End signals
  ▼
Gemini 2.5 Flash Live API       ← orchestration layer: STT + LLM + TTS + function calling
  │  function calls
  ▼
Tool Execution Layer            ← integration layer
  ├── Square API (bookings + orders)
  ├── SMS confirmations (Twilio)
  └── Merchant email alerts (Resend)
```

### Voice Layer

The caller enters through Twilio, which streams raw mulaw 8kHz audio over a WebSocket. The server resamples to PCM 16kHz and forwards it to Gemini Live API — a single bidirectional stream that handles speech recognition, conversation, and speech synthesis in one round trip.

Model choice is secondary. The goal is the fastest model that produces acceptable conversational quality. Gemini 2.5 Flash Native Audio was chosen because it handles STT, reasoning, and TTS natively without separate pipeline hops — each hop adds latency.

### Orchestration Layer

Gemini runs as a single agent with six tool declarations. When the caller's intent is clear (order, reservation, cancellation, question), the agent maps it directly to a tool call. When it's ambiguous, the agent asks one clarifying question — never a menu of options.

A single orchestrator was chosen over intent routing + sub-agents because: sub-agents add handoff latency, split context causes repetition, and debugging failures across agent boundaries is significantly harder.

### Integration Layer

Tool calls execute against Square (bookings and orders), send SMS confirmations to the customer, and trigger email alerts to the restaurant owner when no POS/reservation system is connected. All write operations return a result that the agent reads back to the caller before the call ends.

### Reliability Layer

- **Human fallback:** `transfer_to_human` is always available — triggered for angry callers, allergy emergencies, or repeated tool failures
- **Ring timeout:** the caller first rings the restaurant's real number for N seconds; AI only picks up if no one answers
- **Caller ID reuse:** the caller's phone number is injected at session start; the agent never asks them to repeat it
- **Barge-in:** the output audio queue is flushed the moment the caller speaks, preventing overlapping audio
- **Audit trail:** every tool call and its result is logged with the call session ID

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Voice AI | Gemini 2.5 Flash Native Audio — Live API | Native STT+LLM+TTS in one stream, lowest latency |
| Telephony | Twilio Media Streams | Industry standard, reliable WebSocket audio delivery |
| Bookings + Orders | Square Bookings API + Orders API | Real POS integration, customer SMS confirmations included |
| Merchant alerts | Resend (email) | Instant notification when no POS connected |
| Backend | FastAPI + Python | Async WebSocket handling, minimal overhead |
| Database | PostgreSQL (Cloud SQL) | Multi-tenant restaurant records, call session state |
| Cloud | Google Cloud Run | Auto-scales to zero, per-request billing |
| Onboarding | Claude claude-sonnet-4-6 Vision | Extracts structured menu from PDF/image/website |

---

## Key Engineering Decisions

**Single orchestrator over intent router + sub-agents**
The natural instinct for a multi-intent system is to build a router that classifies the call (order / reservation / cancellation / question) and dispatches to specialized sub-agents. We chose not to do this. Sub-agents add handoff latency, split session context causes the caller to repeat themselves, and failures across agent boundaries are significantly harder to debug. A single agent with six structured tool declarations handles all intents cleanly within one context window.

**Caller ID reuse — never ask what you already know**
When a call arrives, Twilio provides the caller's phone number. This number is injected into the Gemini session at the start of every call. The agent uses it as the default contact number and confirms rather than asks: "I'll use the number you're calling from — does that work?" This removes one of the most friction-heavy moments in phone ordering.

**Ring timeout — human-first, AI as fallback**
When a call comes in, the system first rings the restaurant's real phone number for a configurable timeout (default 15 seconds). Only if no one answers does Ringo take over. Staff can always intercept — the AI handles overflow, not replacement. This design decision made the product acceptable to restaurant owners who were skeptical about handing off calls entirely to AI.

**Output queue flush on barge-in**
When a caller interrupts while the agent is speaking, Gemini stops generating — but audio chunks already queued for playback keep streaming out. The result: the agent keeps talking over the caller for several seconds after being interrupted. We flush the entire `_output_queue` the moment `ActivityStart` is detected, so the agent stops instantly. VAD controls when we listen; queue flush controls when we stop talking. Both are required for natural turn-taking.

**Confirmation before every write — operational safety over conversational flow**
The agent never executes a write action (place order, create booking) without first reading back the complete details and receiving an explicit yes. This adds one turn to every transaction. It's intentional. The biggest operational risk in a restaurant voice agent isn't an unnatural conversation — it's a wrong order, a missed allergy, or a double-booked table. Confirmation before commit eliminates the most costly class of errors.

---

## Demo

Call **+1 669-201-5051** (Bonchon San Jose) and try:
- "I'd like to order medium wings, soy garlic"
- "Can I book a table for 4 this Saturday at 7?"
- "What are your hours?"
- Speak in Mandarin, Cantonese, or Spanish — it mirrors your language automatically

---

## Setup

### Prerequisites

- Python 3.11+
- Twilio account with a phone number
- Google AI API key (Gemini)
- Square developer account

### Local Development

```bash
git clone https://github.com/ejzhu2025/voice-booking-agent
cd voice-booking-agent
pip install -r requirements.txt

cp .env.example .env
# Fill in your API keys

python server.py
# Runs on http://localhost:8000

# In another terminal:
ngrok http 8000
# Set Twilio webhook → https://<ngrok-url>/incoming-call
```

### Environment Variables

```env
GOOGLE_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
SQUARE_ACCESS_TOKEN=
SQUARE_LOCATION_ID=
RESEND_API_KEY=
DATABASE_URL=
```

### Deployment

```bash
gcloud run deploy voice-booking-agent \
  --source . \
  --region us-central1
```

Pushes to `main` automatically deploy via GitHub Actions.

---

Built for the [Gemini Live Agent Challenge](https://geminiagentchallenge.devpost.com/) — March 2026

MIT License
