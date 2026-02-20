"""Deepgram Voice Service - STT and TTS (deepgram-sdk v5)."""

import asyncio
import base64
import inspect
from typing import Callable, Optional

from deepgram import AsyncDeepgramClient
from deepgram.listen.v1.socket_client import AsyncV1SocketClient, EventType, ListenV1ResultsEvent
from utils.config import config


class DeepgramVoiceService:
    """Handle real-time speech-to-text and text-to-speech."""

    def __init__(self):
        self.client = AsyncDeepgramClient(api_key=config.DEEPGRAM_API_KEY)
        self.live_connection: Optional[AsyncV1SocketClient] = None
        self._connection_cm = None
        self._listen_task = None
        self.on_transcript: Optional[Callable] = None

    async def start_live_transcription(
        self,
        on_transcript: Callable[[str, bool], None],
    ):
        """Start real-time transcription."""
        self.on_transcript = on_transcript

        try:
            self._connection_cm = self.client.listen.v1.connect(
                model="nova-2",
                language="en-US",
                encoding="mulaw",
                sample_rate="8000",
                punctuate="true",
                endpointing="500",
            )
            self.live_connection = await self._connection_cm.__aenter__()

            def handle_message(event):
                try:
                    # Only process Results events with a valid channel object
                    if not hasattr(event, "is_final"):
                        return
                    channel = event.channel
                    # channel must be an object with alternatives, not an int/list
                    if isinstance(channel, (int, list)) or not hasattr(channel, "alternatives"):
                        return
                    transcript = channel.alternatives[0].transcript
                    is_final = event.is_final
                    if transcript and self.on_transcript:
                        cb = self.on_transcript(transcript, is_final)
                        if inspect.isawaitable(cb):
                            asyncio.create_task(cb)
                except Exception:
                    pass

            self.live_connection.on(EventType.MESSAGE, handle_message)

            # Start listening in background
            self._listen_task = asyncio.create_task(
                self.live_connection.start_listening()
            )
            return True

        except Exception as e:
            print(f"Error starting transcription: {e}")
            return False

    async def send_audio(self, audio_data: bytes):
        """Send audio chunk to Deepgram for transcription."""
        if self.live_connection:
            try:
                await self.live_connection.send_media(audio_data)
            except Exception as e:
                print(f"Error sending audio: {e}")

    async def stop_transcription(self):
        """Stop live transcription."""
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self._connection_cm and self.live_connection:
            try:
                await self._connection_cm.__aexit__(None, None, None)
            except Exception:
                pass
            self.live_connection = None
            self._connection_cm = None

    async def text_to_speech(self, text: str) -> bytes:
        """Convert text to speech audio (mulaw 8kHz for Twilio) - returns all at once."""
        try:
            audio_data = b""
            async for chunk in self.client.speak.v1.audio.generate(
                text=text,
                model="aura-asteria-en",
                encoding="mulaw",
                sample_rate=8000,
            ):
                audio_data += chunk
            return audio_data

        except Exception as e:
            print(f"TTS error: {e}")
            return b""

    async def text_to_speech_stream(self, text: str):
        """Stream TTS audio in chunks (async generator)."""
        try:
            async for chunk in self.client.speak.v1.audio.generate(
                text=text,
                model="aura-asteria-en",
                encoding="mulaw",
                sample_rate=8000,
            ):
                yield chunk
        except Exception as e:
            print(f"TTS streaming error: {e}")

    async def text_to_speech_base64(self, text: str) -> str:
        """Convert text to base64-encoded mulaw audio for Twilio."""
        audio_bytes = await self.text_to_speech(text)
        return base64.b64encode(audio_bytes).decode("utf-8")


# Singleton
deepgram_service = DeepgramVoiceService()
