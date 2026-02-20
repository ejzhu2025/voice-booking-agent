"""
Voice Restaurant Booking Agent Server

Main server that connects:
- Twilio (phone calls)
- Deepgram (STT/TTS)
- OpenAI (conversation logic)
- Square (bookings)
"""

import asyncio
import base64
import json
from fastapi import FastAPI, WebSocket, Request, Response
from fastapi.responses import PlainTextResponse
import uvicorn

from agents.booking_agent import BookingAgent
from services.deepgram_service import DeepgramVoiceService
from utils.config import config

app = FastAPI(title="Voice Booking Agent")

# Store active sessions
sessions: dict[str, dict] = {}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/incoming-call")
async def incoming_call(request: Request):
    """
    Twilio webhook for incoming calls.
    Returns TwiML to connect call to WebSocket.
    """
    # Get the host from request for WebSocket URL
    host = request.headers.get("host", "localhost:8000")
    # Use wss for Railway deployments, ws for localhost
    protocol = "wss" if "railway.app" in host or "localhost" not in host else "ws"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{protocol}://{host}/media-stream">
            <Parameter name="caller" value="{{{{From}}}}" />
        </Stream>
    </Connect>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.
    Handles bidirectional audio streaming.
    """
    await websocket.accept()

    session_id = None
    agent = None
    deepgram = None
    stream_sid = None

    # Mute flag: ignore transcripts while agent is speaking
    agent_speaking_until = 0.0

    async def on_transcript(text: str, is_final: bool):
        """Handle incoming transcripts from Deepgram."""
        nonlocal agent_speaking_until

        if not is_final or not text.strip():
            return

        # Ignore transcript if agent is still speaking (echo suppression)
        now = asyncio.get_event_loop().time()
        if now < agent_speaking_until:
            print(f"[Suppressed echo]: {text.strip()}")
            return

        print(f"User said: {text.strip()}")

        # Process with booking agent
        response_text = await agent.process_message(text.strip())
        print(f"Agent response: {response_text}")

        # Convert to speech and send back
        await send_audio_response(response_text)

    async def send_audio_response(text: str):
        """Convert text to speech and send to Twilio."""
        nonlocal agent_speaking_until

        if not stream_sid:
            return

        # Get TTS audio from Deepgram
        audio_bytes = await deepgram.text_to_speech(text)

        if audio_bytes:
            import base64
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

            # Calculate speech duration: mulaw 8kHz = 8000 bytes/sec
            speech_duration = len(audio_bytes) / 8000.0
            # Suppress transcription for speech duration + 0.5s buffer (reduced from 1.5s)
            agent_speaking_until = asyncio.get_event_loop().time() + speech_duration + 0.5

            media_message = {
                "event": "media",
                "streamSid": stream_sid,
                "media": {
                    "payload": audio_base64,
                }
            }
            await websocket.send_json(media_message)

    try:
        # Initialize services
        agent = BookingAgent()
        deepgram = DeepgramVoiceService()

        # Start Deepgram transcription
        await deepgram.start_live_transcription(on_transcript)

        # Send initial greeting after connection
        greeting_sent = False

        async for message in websocket.iter_text():
            data = json.loads(message)
            event = data.get("event")

            if event == "connected":
                print("Twilio connected")

            elif event == "start":
                # Call started
                start_data = data.get("start", {})
                stream_sid = start_data.get("streamSid")
                session_id = stream_sid
                print(f"Call started - Stream SID: {stream_sid}")

                # Store session
                sessions[session_id] = {
                    "agent": agent,
                    "deepgram": deepgram,
                }

                # Send greeting after short delay
                if not greeting_sent:
                    await asyncio.sleep(0.5)
                    greeting = agent.get_greeting()
                    await send_audio_response(greeting)
                    greeting_sent = True

            elif event == "media":
                # Incoming audio from caller
                media = data.get("media", {})
                payload = media.get("payload", "")

                if payload:
                    # Decode base64 audio and send to Deepgram
                    audio_bytes = base64.b64decode(payload)
                    await deepgram.send_audio(audio_bytes)

            elif event == "stop":
                print("Call ended")
                break

    except Exception as e:
        print(f"WebSocket error: {e}")

    finally:
        # Cleanup
        if deepgram:
            await deepgram.stop_transcription()
        if session_id and session_id in sessions:
            del sessions[session_id]
        print("Session cleaned up")


@app.post("/outbound-call")
async def make_outbound_call(request: Request):
    """
    Make an outbound call to a customer.
    POST body: {"to": "+1234567890"}
    """
    from twilio.rest import Client

    body = await request.json()
    to_number = body.get("to")

    if not to_number:
        return {"error": "Missing 'to' phone number"}

    client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)

    # Get webhook URL
    host = request.headers.get("host", "localhost:8000")
    webhook_url = f"https://{host}/incoming-call"

    call = client.calls.create(
        to=to_number,
        from_=config.TWILIO_PHONE_NUMBER,
        url=webhook_url,
    )

    return {"call_sid": call.sid, "status": "initiated"}


# ==================== Demo Mode (Text-based) ====================

@app.post("/demo/chat")
async def demo_chat(request: Request):
    """
    Text-based demo endpoint for testing without phone.
    POST body: {"message": "I want to book a table", "session_id": "optional"}
    """
    body = await request.json()
    message = body.get("message", "")
    session_id = body.get("session_id", "demo")

    # Get or create session
    if session_id not in sessions:
        sessions[session_id] = {"agent": BookingAgent()}

    agent = sessions[session_id]["agent"]

    # Process message
    response = await agent.process_message(message)

    return {
        "response": response,
        "session_id": session_id,
        "booking_info": agent.booking_info,
    }


@app.post("/demo/reset")
async def demo_reset(request: Request):
    """Reset demo session."""
    body = await request.json()
    session_id = body.get("session_id", "demo")

    if session_id in sessions:
        sessions[session_id]["agent"].reset()

    return {"status": "reset", "session_id": session_id}


# ==================== Main ====================

if __name__ == "__main__":
    print("=" * 50)
    print("Voice Restaurant Booking Agent")
    print("=" * 50)
    print(f"\nServer starting on http://{config.HOST}:{config.PORT}")
    print("\nEndpoints:")
    print("  POST /incoming-call  - Twilio webhook")
    print("  WS   /media-stream   - Audio streaming")
    print("  POST /demo/chat      - Text demo mode")
    print("  GET  /health         - Health check")
    print("\nTo test with phone:")
    print("  1. Run: ngrok http 8000")
    print("  2. Set Twilio webhook to ngrok URL + /incoming-call")
    print("  3. Call your Twilio number")
    print("\nTo test text mode:")
    print('  curl -X POST http://localhost:8000/demo/chat \\')
    print('       -H "Content-Type: application/json" \\')
    print('       -d \'{"message": "I want to book a table for 4 tomorrow at 7pm"}\'')
    print("=" * 50)

    uvicorn.run(
        "server:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
    )
