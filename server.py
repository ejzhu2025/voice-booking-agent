"""
Voice Restaurant Booking Agent — Server

Architecture:
  Twilio (phone) ↔ WebSocket ↔ Gemini Live API (STT + Gemini LLM + TTS)
                                        ↕ function calls
                                   Square API (bookings)

Gemini Live API handles:
  - Speech-to-text (any language, auto-detect)
  - Conversation & reasoning (Gemini 2.0 Flash Live)
  - Text-to-speech (audio response)
  - Barge-in / interruption natively
  - Function calling for bookings
"""

import asyncio
import base64
import json

import uvicorn
from fastapi import FastAPI, WebSocket, Request, Response

from agents.booking_agent import BookingTools, get_greeting, get_system_prompt, get_tools
from services.gemini_live_service import GeminiLiveService
from utils.config import config

app = FastAPI(title="Voice Booking Agent — Powered by Gemini Live")

# Active sessions (session_id → metadata)
sessions: dict[str, dict] = {}


@app.get("/", response_class=Response)
async def root():
    html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Bonchon Voice Booking Agent</title>
<style>
  body { font-family: sans-serif; max-width: 700px; margin: 60px auto; padding: 0 20px; color: #333; }
  h1 { color: #e8341c; }
  .badge { display: inline-block; background: #34a853; color: white; padding: 4px 10px; border-radius: 12px; font-size: 13px; }
  pre { background: #f5f5f5; padding: 16px; border-radius: 8px; overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; }
  td, th { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
  th { background: #f9f9f9; }
</style>
</head>
<body>
  <h1>🍗 Bonchon Voice Booking Agent</h1>
  <p><span class="badge">● LIVE</span> &nbsp; Powered by <strong>Gemini 2.5 Flash Native Audio</strong> on Google Cloud Run</p>
  <p>A real-time AI voice agent that handles restaurant reservations and pickup orders via phone call.
     Automatically responds in the caller's language (English, Chinese, Spanish, and more).</p>

  <h2>API Endpoints</h2>
  <table>
    <tr><th>Method</th><th>Path</th><th>Description</th></tr>
    <tr><td>POST</td><td>/incoming-call</td><td>Twilio webhook — starts a phone call session</td></tr>
    <tr><td>WS</td><td>/media-stream</td><td>Bidirectional audio bridge (Twilio ↔ Gemini Live)</td></tr>
    <tr><td>POST</td><td>/demo/chat</td><td>Text-based demo (no phone needed)</td></tr>
    <tr><td>GET</td><td>/health</td><td>Health check</td></tr>
  </table>

  <h2>Try the Text Demo</h2>
  <pre>curl -X POST {url}/demo/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "I want to book a table for 2 tonight at 7pm"}}'</pre>

  <h2>Tech Stack</h2>
  <ul>
    <li><strong>LLM + STT + TTS:</strong> Gemini 2.5 Flash Native Audio (Live API)</li>
    <li><strong>Phone:</strong> Twilio Media Streams</li>
    <li><strong>Bookings:</strong> Square API</li>
    <li><strong>Hosting:</strong> Google Cloud Run</li>
  </ul>
</body>
</html>""".replace("{url}", "https://voice-booking-agent-983680558370.us-central1.run.app")
    return Response(content=html, media_type="text/html")


@app.get("/health")
async def health():
    return {"status": "ok", "model": "gemini-2.5-flash-native-audio-latest"}


@app.post("/incoming-call")
async def incoming_call(request: Request):
    """Twilio webhook — returns TwiML to stream audio to this server."""
    host = request.headers.get("host", "localhost:8000")
    protocol = "wss" if "localhost" not in host else "ws"

    # Extract caller phone from Twilio POST form data.
    # NOTE: {{From}} template syntax only works in Twilio TwiML Bins, NOT in
    # webhook responses. We must read it from the request and inject it directly.
    form = await request.form()
    caller = form.get("From", "")
    print(f"[Twilio] Incoming call from: {caller!r}")

    # No <Say> — Gemini handles the greeting for a consistent voice.
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{protocol}://{host}/media-stream">
            <Parameter name="caller" value="{caller}" />
        </Stream>
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    """
    WebSocket bridge: Twilio Media Streams ↔ Gemini Live API.

    Audio flow:
      Twilio → mulaw 8kHz → GeminiLiveService → PCM 16kHz → Gemini Live
      Gemini Live → PCM 24kHz → GeminiLiveService → mulaw 8kHz → Twilio
    """
    await websocket.accept()

    stream_sid = None
    gemini: GeminiLiveService | None = None
    tools = BookingTools()

    async def send_audio_to_twilio(audio_bytes: bytes):
        """Forward Gemini's audio response back to Twilio."""
        if not stream_sid:
            return
        await websocket.send_json({
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": base64.b64encode(audio_bytes).decode()},
        })

    try:
        # Start Gemini Live session for this call
        gemini = GeminiLiveService(
            on_audio=send_audio_to_twilio,
            system_prompt=get_system_prompt(),
            tools=get_tools(),
            tool_handler=tools.handle,
        )
        await gemini.start()

        async for message in websocket.iter_text():
            data = json.loads(message)
            event = data.get("event")

            if event == "connected":
                print("[Twilio] WebSocket connected")

            elif event == "start":
                start_data = data.get("start", {})
                stream_sid = start_data.get("streamSid")
                sessions[stream_sid] = {"tools": tools}
                # Extract caller phone number from Twilio stream parameters
                caller_phone = start_data.get("customParameters", {}).get("caller", "")
                print(f"[Twilio] Call started — stream SID: {stream_sid}, caller: {caller_phone}")
                # Trigger Gemini to say the greeting via text kick-start.
                # User audio stays MUTED until receive loop sees turn_complete.
                await gemini.send_greeting_kickstart(caller_phone=caller_phone)

            elif event == "media":
                payload = data.get("media", {}).get("payload", "")
                if payload:
                    audio_bytes = base64.b64decode(payload)
                    await gemini.send_audio(audio_bytes)

            elif event == "stop":
                print("[Twilio] Call ended")
                break

    except Exception as e:
        print(f"[Server] WebSocket error: {e}")

    finally:
        if gemini:
            await gemini.stop()
        if stream_sid and stream_sid in sessions:
            del sessions[stream_sid]
        print("[Server] Session cleaned up")


@app.post("/outbound-call")
async def make_outbound_call(request: Request):
    """Initiate an outbound call via Twilio."""
    from twilio.rest import Client

    body = await request.json()
    to_number = body.get("to")
    if not to_number:
        return {"error": "Missing 'to' phone number"}

    client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    host = request.headers.get("host", "localhost:8000")
    call = client.calls.create(
        to=to_number,
        from_=config.TWILIO_PHONE_NUMBER,
        url=f"https://{host}/incoming-call",
    )
    return {"call_sid": call.sid, "status": "initiated"}


# ── Demo Mode (text-based, uses regular Gemini Flash) ───────────────────────

@app.post("/demo/chat")
async def demo_chat(request: Request):
    """
    Text-based demo for testing without a phone.
    Uses Gemini 2.0 Flash (non-live) with function calling.
    POST body: {"message": "...", "session_id": "optional"}
    """
    from google import genai
    from google.genai import types as gtypes

    body = await request.json()
    message = body.get("message", "")
    session_id = body.get("session_id", "demo")

    # Per-session conversation history
    if session_id not in sessions:
        sessions[session_id] = {
            "history": [],
            "tools": BookingTools(),
        }

    sess = sessions[session_id]
    history: list = sess["history"]
    booking_tools: BookingTools = sess["tools"]

    history.append(gtypes.Content(role="user", parts=[gtypes.Part(text=message)]))

    client = genai.Client(api_key=config.GOOGLE_API_KEY)

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=history,
        config=gtypes.GenerateContentConfig(
            system_instruction=get_system_prompt(),
            tools=get_tools(),
        ),
    )

    candidate = response.candidates[0]
    history.append(candidate.content)

    # Handle function calls
    while candidate.content.parts and any(p.function_call for p in candidate.content.parts):
        tool_results = []
        for part in candidate.content.parts:
            if part.function_call:
                fc = part.function_call
                result = await booking_tools.handle(fc.name, dict(fc.args))
                tool_results.append(
                    gtypes.Part(
                        function_response=gtypes.FunctionResponse(
                            name=fc.name,
                            response=result,
                        )
                    )
                )

        history.append(gtypes.Content(role="user", parts=tool_results))

        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=history,
            config=gtypes.GenerateContentConfig(
                system_instruction=get_system_prompt(),
                tools=get_tools(),
            ),
        )
        candidate = response.candidates[0]
        history.append(candidate.content)

    reply = response.text or ""
    return {"response": reply, "session_id": session_id}


@app.post("/demo/reset")
async def demo_reset(request: Request):
    body = await request.json()
    session_id = body.get("session_id", "demo")
    if session_id in sessions:
        del sessions[session_id]
    return {"status": "reset", "session_id": session_id}


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  Voice Booking Agent — Gemini Live API")
    print("=" * 55)
    print(f"\n  Server: http://{config.HOST}:{config.PORT}")
    print("\n  Endpoints:")
    print("    POST /incoming-call   — Twilio webhook")
    print("    WS   /media-stream    — Audio bridge")
    print("    POST /demo/chat       — Text demo (no phone needed)")
    print("    GET  /health          — Health check")
    print("\n  To test locally:")
    print("    1. python server.py")
    print("    2. ngrok http 8000")
    print("    3. Set Twilio webhook → <ngrok-url>/incoming-call")
    print("    4. Call your Twilio number")
    print("=" * 55)

    uvicorn.run("server:app", host=config.HOST, port=config.PORT, reload=True)
