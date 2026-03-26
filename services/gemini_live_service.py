"""
Gemini Live API Service

Replaces both Deepgram (STT/TTS) and OpenAI (LLM) with a single
bidirectional audio stream that handles speech recognition,
conversation logic, function calling, and text-to-speech natively.

Key design notes:
  - VAD: Gemini's built-in automatic voice activity detection is used.
    Audio is streamed continuously; Gemini detects speech and manages turn-taking.
    Barge-in is handled by flushing the output queue on server_content.interrupted.
  - User audio is MUTED until Gemini finishes the greeting turn (turn_complete).
  - ratecv state is preserved across chunks for clean resampling.
  - Output audio is forwarded via an asyncio Queue so the receive
    loop is never blocked by the Twilio WebSocket write.
  - Session auto-reconnects if Gemini closes the WebSocket (e.g. 1008 policy
    violation after a long tool-call sequence). Conversation context is lost
    on reconnect but the call continues without going silent.
"""

import asyncio
import audioop
import time
from typing import Callable

from google import genai
from google.genai import types

from utils.config import config

# VAD mode switch
# Set USE_BUILTIN_VAD = True to use Gemini's built-in VAD instead of manual RMS-based VAD.
# Manual VAD (False) is the default — more reliable on 8kHz upsampled phone audio.
USE_BUILTIN_VAD = True

# Manual VAD thresholds (only used when USE_BUILTIN_VAD = False)
_SPEECH_RMS_THRESHOLD = 300   # PCM16 8kHz RMS above this = speech
_SPEECH_END_SILENCE_S = 0.65  # Seconds of silence to end user turn


class GeminiLiveService:
    """
    Bridges Twilio audio (mulaw 8kHz) ↔ Gemini Live API (PCM 16kHz in / 24kHz out).
    One session = STT + Gemini LLM + TTS + function calling + barge-in.
    """

    MODEL = "gemini-2.5-flash-native-audio-latest"

    def __init__(
        self,
        on_audio: Callable,
        system_prompt: str,
        tools: list,
        tool_handler: Callable,
    ):
        self.client = genai.Client(api_key=config.GOOGLE_API_KEY)
        self.on_audio = on_audio
        self.system_prompt = system_prompt
        self.tools = tools
        self.tool_handler = tool_handler

        self.session = None
        self._context = None
        self._receive_task = None
        self._sender_task = None
        self._live_config = None  # saved for reconnects

        self._output_queue: asyncio.Queue = asyncio.Queue()

        # Mute user audio until greeting turn completes
        self._mute_user_audio = True

        # Manual VAD state
        self._in_activity = False          # Currently inside an activity window
        self._last_speech_t: float = 0.0   # Last time RMS was above threshold
        self._ratecv_state = None          # Preserved between ratecv calls

        # Latency tracking
        self._last_user_audio_t: float = 0.0
        self._first_response_logged: bool = False

        # Reconnect state
        self._session_alive = True
        self._reconnecting = False

    def _build_live_config(self) -> types.LiveConnectConfig:
        if USE_BUILTIN_VAD:
            realtime_input_config = types.RealtimeInputConfig(
                # Let Gemini detect speech automatically.
                # TURN_INCLUDES_ALL_INPUT: all audio (not just activity windows) feeds the turn.
                turn_coverage=types.TurnCoverage.TURN_INCLUDES_ALL_INPUT,
            )
        else:
            realtime_input_config = types.RealtimeInputConfig(
                # Disable Gemini's built-in VAD — we send activity signals manually.
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=True
                ),
                # Only audio between ActivityStart and ActivityEnd counts as the turn.
                turn_coverage=types.TurnCoverage.TURN_INCLUDES_ONLY_ACTIVITY,
            )

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=self.system_prompt,
            tools=self.tools,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Aoede"
                    )
                )
            ),
            realtime_input_config=realtime_input_config,
        )

    async def start(self):
        """Open Gemini Live session and start background tasks."""
        self._live_config = self._build_live_config()
        self._context = self.client.aio.live.connect(
            model=self.MODEL,
            config=self._live_config,
        )
        self.session = await self._context.__aenter__()
        self._session_alive = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        if not self._sender_task or self._sender_task.done():
            self._sender_task = asyncio.create_task(self._output_sender())
        print("[Gemini Live] Session started")

    async def _reconnect_session(self):
        """
        Reconnect after session dies (e.g. 1008 policy violation).
        The call keeps going; new session picks up where the old one left off
        with a brief context hint.
        """
        if self._reconnecting:
            return
        self._reconnecting = True
        print("[Gemini Live] Session dead — reconnecting...")

        # Cancel the dead receive task
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        # Close the dead context
        if self._context:
            try:
                await self._context.__aexit__(None, None, None)
            except Exception:
                pass

        # Reset connection state (keep VAD reset clean)
        self._in_activity = False
        self._ratecv_state = None

        try:
            # Open fresh session
            self._live_config = self._build_live_config()
            self._context = self.client.aio.live.connect(
                model=self.MODEL,
                config=self._live_config,
            )
            self.session = await self._context.__aenter__()
            self._session_alive = True

            # Don't mute — greeting already happened before disconnect
            self._mute_user_audio = False

            # Restart receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Tell Gemini the context (it starts fresh each session)
            await self.session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text=(
                        "[The connection was briefly interrupted. "
                        "You are still on a call with a Bonchon customer. "
                        "Apologize briefly for the interruption and ask how you can continue helping them.]"
                    ))],
                ),
                turn_complete=True,
            )
            print("[Gemini Live] Reconnected successfully")
        except Exception as e:
            print(f"[Gemini Live] Reconnect failed: {e}")
            self._session_alive = False
        finally:
            self._reconnecting = False

    async def send_greeting_kickstart(self, caller_phone: str = ""):
        """Send text turn to make Gemini say the greeting. Called from server on stream start."""
        phone_context = ""
        if caller_phone:
            # Strip country code (+1) to get 10-digit US number
            digits = "".join(c for c in caller_phone if c.isdigit())
            if digits.startswith("1") and len(digits) == 11:
                digits = digits[1:]
            if len(digits) == 10:
                phone_context = (
                    f" The caller's phone number is {digits} — "
                    "use this as their contact number by default (confirm it with them rather than asking them to say it)."
                )
            print(f"[Gemini Live] Caller phone parsed: raw={caller_phone!r} → digits={digits!r} → context={'set' if phone_context else 'none'}")

        text = f"[The caller just connected. Greet them warmly, mention this is Bonchon, and ask how you can help.{phone_context}]"
        await self.session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part(text=text)],
            ),
            turn_complete=True,
        )
        print(f"[Gemini Live] Greeting kick-start sent (caller_phone={caller_phone!r})")

    def _is_session_error(self, e: Exception) -> bool:
        """Return True if the exception indicates the session WebSocket is dead."""
        msg = str(e).lower()
        return "1008" in msg or "policy violation" in msg or "session" in msg

    async def send_audio(self, mulaw_bytes: bytes):
        """
        Process mulaw 8kHz audio from Twilio and forward to Gemini.
        In builtin-VAD mode: stream all audio continuously, let Gemini detect speech.
        In manual-VAD mode: run RMS-based VAD and send ActivityStart/ActivityEnd signals.
        """
        if not self.session or self._mute_user_audio:
            return

        if not self._session_alive and not self._reconnecting:
            asyncio.create_task(self._reconnect_session())
            return

        # Convert mulaw 8kHz → PCM16 8kHz, then upsample → PCM16 16kHz for Gemini
        pcm8k = audioop.ulaw2lin(mulaw_bytes, 2)
        pcm16k, self._ratecv_state = audioop.ratecv(
            pcm8k, 2, 1, 8000, 16000, self._ratecv_state
        )

        if USE_BUILTIN_VAD:
            # ── Built-in VAD mode: stream everything, Gemini handles detection ──
            self._last_user_audio_t = time.monotonic()
            self._first_response_logged = False
            try:
                await self.session.send_realtime_input(
                    audio=types.Blob(data=pcm16k, mime_type="audio/pcm;rate=16000")
                )
            except Exception as e:
                print(f"[Audio] send error: {e}")
                if self._is_session_error(e):
                    self._session_alive = False
                    asyncio.create_task(self._reconnect_session())
            return

        # ── Manual VAD mode ────────────────────────────────────────────────────
        rms = audioop.rms(pcm8k, 2)
        now = time.monotonic()

        if rms > _SPEECH_RMS_THRESHOLD:
            # Speech detected
            self._last_speech_t = now
            self._last_user_audio_t = now
            self._first_response_logged = False

            if not self._in_activity:
                # Start of a new utterance — flush any queued output first (barge-in)
                self._in_activity = True
                flushed = 0
                while not self._output_queue.empty():
                    try:
                        self._output_queue.get_nowait()
                        self._output_queue.task_done()
                        flushed += 1
                    except asyncio.QueueEmpty:
                        break
                if flushed:
                    print(f"[VAD] Flushed {flushed} audio chunks on barge-in")
                print(f"[VAD] Speech start (RMS={rms})")
                try:
                    await self.session.send_realtime_input(
                        activity_start=types.ActivityStart()
                    )
                except Exception as e:
                    print(f"[VAD] activity_start error: {e}")
                    if self._is_session_error(e):
                        self._session_alive = False
                        self._in_activity = False
                        asyncio.create_task(self._reconnect_session())
                    return

            try:
                await self.session.send_realtime_input(
                    audio=types.Blob(data=pcm16k, mime_type="audio/pcm;rate=16000")
                )
            except Exception as e:
                print(f"[Audio] send error: {e}")
                if self._is_session_error(e):
                    self._session_alive = False
                    self._in_activity = False
                    asyncio.create_task(self._reconnect_session())

        elif self._in_activity:
            # In activity but current chunk is silence — keep sending (natural pauses)
            try:
                await self.session.send_realtime_input(
                    audio=types.Blob(data=pcm16k, mime_type="audio/pcm;rate=16000")
                )
            except Exception as e:
                print(f"[Audio] send error: {e}")
                if self._is_session_error(e):
                    self._session_alive = False
                    self._in_activity = False
                    asyncio.create_task(self._reconnect_session())
                return

            silence_s = now - self._last_speech_t
            if silence_s >= _SPEECH_END_SILENCE_S:
                self._in_activity = False
                print(f"[VAD] Speech end (silence={silence_s:.2f}s) → activity_end")
                try:
                    await self.session.send_realtime_input(
                        activity_end=types.ActivityEnd()
                    )
                except Exception as e:
                    print(f"[VAD] activity_end error: {e}")
                    if self._is_session_error(e):
                        self._session_alive = False
                        asyncio.create_task(self._reconnect_session())
        # else: silence and not in activity — don't send anything

    async def _receive_loop(self):
        """
        Receive Gemini responses: audio → output queue, tool calls → execute.

        session.receive() is a single-turn generator — it terminates after each
        turn_complete. We wrap it in while True so it restarts for every new turn.
        """
        try:
            while True:
                async for response in self.session.receive():

                    if response.server_content:
                        # Barge-in (builtin VAD): Gemini signals it was interrupted
                        if USE_BUILTIN_VAD and getattr(response.server_content, "interrupted", False):
                            flushed = 0
                            while not self._output_queue.empty():
                                try:
                                    self._output_queue.get_nowait()
                                    self._output_queue.task_done()
                                    flushed += 1
                                except asyncio.QueueEmpty:
                                    break
                            if flushed:
                                print(f"[Builtin VAD] Barge-in detected — flushed {flushed} audio chunks")

                        # Audio chunks → queue for forwarding to Twilio
                        if response.server_content.model_turn:
                            for part in response.server_content.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    audio_bytes = part.inline_data.data
                                    if not self._first_response_logged:
                                        elapsed = time.monotonic() - self._last_user_audio_t
                                        print(f"[Latency] First audio: {elapsed:.3f}s")
                                        self._first_response_logged = True
                                    mulaw = self._pcm24k_to_mulaw8k(audio_bytes)
                                    await self._output_queue.put(mulaw)

                        # Gemini finished its turn
                        if response.server_content.turn_complete:
                            if self._mute_user_audio:
                                # First turn = greeting done → start listening
                                print("[Gemini Live] Greeting done — manual VAD now active")
                                self._mute_user_audio = False
                            else:
                                print("[Gemini Live] Turn complete — ready for next input")

                    # Function call → execute and return result
                    if response.tool_call:
                        for fc in response.tool_call.function_calls:
                            t0 = time.monotonic()
                            print(f"[Gemini] Tool call: {fc.name}({dict(fc.args)})")
                            result = await self.tool_handler(fc.name, dict(fc.args))
                            print(f"[Latency] Tool {fc.name}: {time.monotonic()-t0:.3f}s")
                            await self.session.send_tool_response(
                                function_responses=[
                                    types.FunctionResponse(
                                        name=fc.name,
                                        id=fc.id,
                                        response=result,
                                    )
                                ]
                            )

        except asyncio.CancelledError:
            print("[Gemini Live] receive loop cancelled")
        except Exception as e:
            print(f"[Gemini Live] receive loop error: {e}")
            # Mark session dead so send_audio triggers reconnect
            self._session_alive = False
        finally:
            print("[Gemini Live] receive loop exited")

    async def _output_sender(self):
        """Drain the output queue and send audio to Twilio without blocking the receive loop."""
        try:
            while True:
                mulaw = await self._output_queue.get()
                await self.on_audio(mulaw)
                self._output_queue.task_done()
        except asyncio.CancelledError:
            pass

    # ── Audio format conversion ──────────────────────────────────────────────

    def _pcm24k_to_mulaw8k(self, pcm24k: bytes) -> bytes:
        """Gemini Live output PCM16 24kHz → mulaw 8kHz (Twilio format)."""
        pcm8k, _ = audioop.ratecv(pcm24k, 2, 1, 24000, 8000, None)
        return audioop.lin2ulaw(pcm8k, 2)

    # ────────────────────────────────────────────────────────────────────────

    async def stop(self):
        """Close the Gemini Live session."""
        for task in (self._receive_task, self._sender_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if self._context:
            try:
                await self._context.__aexit__(None, None, None)
            except Exception:
                pass
        self.session = None
        print("[Gemini Live] Session closed")
