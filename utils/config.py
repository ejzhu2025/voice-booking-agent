"""Configuration management."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

    # Deepgram
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

    # Square
    SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN")
    SQUARE_LOCATION_ID = os.getenv("SQUARE_LOCATION_ID")
    SQUARE_ENVIRONMENT = os.getenv("SQUARE_ENVIRONMENT", "sandbox")

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    @classmethod
    def validate(cls):
        """Validate required config values."""
        required = [
            ("TWILIO_ACCOUNT_SID", cls.TWILIO_ACCOUNT_SID),
            ("TWILIO_AUTH_TOKEN", cls.TWILIO_AUTH_TOKEN),
            ("DEEPGRAM_API_KEY", cls.DEEPGRAM_API_KEY),
            ("SQUARE_ACCESS_TOKEN", cls.SQUARE_ACCESS_TOKEN),
        ]
        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")


config = Config()
