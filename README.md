# Voice Restaurant Booking Agent

AI-powered voice agent for restaurant reservations using Deepgram + Twilio + Square.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Phone Call                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Twilio Voice                                │
│  • Receives incoming calls                                       │
│  • Streams audio via WebSocket (Media Streams)                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │ WebSocket (audio stream)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Your Backend Server                            │
│  (Python FastAPI / Node.js)                                      │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Deepgram   │◄──►│   LLM Agent  │◄──►│ Square API   │       │
│  │  Voice Agent │    │  (Booking    │    │ (Availability│       │
│  │  (STT + TTS) │    │   Logic)     │    │  + Booking)  │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Purpose | API/Service |
|-----------|---------|-------------|
| Phone Interface | Receive/make calls | Twilio Voice + Media Streams |
| Speech-to-Text | Convert voice to text | Deepgram STT (real-time) |
| Text-to-Speech | Convert responses to voice | Deepgram TTS |
| Conversation AI | Handle dialog & intent | Deepgram Agent / OpenAI |
| Booking System | Check availability & book | Square Bookings API |

## User Flow

```
1. User calls Twilio number
2. "Hi, I'd like to book a table for 4 people tomorrow at 7pm"
3. Agent checks Square API for availability
4. "I found availability at 7pm and 7:30pm. Which works for you?"
5. User: "7pm please"
6. Agent: "Great! Can I get your name?"
7. User: "John Smith"
8. Agent: "And your phone number for confirmation?"
9. User: "555-123-4567"
10. Agent creates booking via Square API
11. "Perfect! Your reservation for 4 at 7pm tomorrow is confirmed.
     You'll receive a confirmation text. Anything else?"
```

## Setup

### 1. Get API Keys

- **Twilio**: https://console.twilio.com (Account SID, Auth Token, Phone Number)
- **Deepgram**: https://console.deepgram.com (API Key)
- **Square**: https://developer.squareup.com (Access Token, Location ID)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 4. Run Server

```bash
# Development
python server.py

# Production (use ngrok for Twilio webhook)
ngrok http 8000
# Update Twilio webhook URL to ngrok URL
```

### 5. Configure Twilio

1. Go to Twilio Console > Phone Numbers
2. Select your number
3. Set Voice webhook to: `https://your-ngrok-url/incoming-call`

## Project Structure

```
voice-booking-agent/
├── README.md
├── requirements.txt
├── .env.example
├── server.py              # Main FastAPI server
├── agents/
│   └── booking_agent.py   # Conversation logic
├── services/
│   ├── deepgram_service.py    # Deepgram STT/TTS
│   ├── twilio_service.py      # Twilio handling
│   └── square_service.py      # Square Bookings API
└── utils/
    └── config.py          # Configuration
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/incoming-call` | POST | Twilio webhook for incoming calls |
| `/media-stream` | WebSocket | Audio streaming endpoint |
| `/health` | GET | Health check |

## Next Steps

1. [ ] Set up API accounts (Twilio, Deepgram, Square)
2. [ ] Run locally with ngrok
3. [ ] Test with real phone call
4. [ ] Add error handling & edge cases
5. [ ] Deploy to cloud (Railway, Render, AWS)
