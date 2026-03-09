"""
HANA Sentinel — Configuration loader.
Loads settings from .env file using python-dotenv.
"""

import os
from dotenv import load_dotenv


# Load .env from the project root (override=True ensures .env values win)
_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(_env_path, override=True)


class Config:
    """Centralized configuration from environment variables."""

    # HANA Database
    HANA_HOST = os.getenv("HANA_HOST", "localhost")
    HANA_PORT = int(os.getenv("HANA_PORT", "39013"))
    HANA_USER = os.getenv("HANA_USER", "SYSTEM")
    HANA_PASSWORD = os.getenv("HANA_PASSWORD", "")

    # Remote Execution Server
    REMOTE_EXEC_URL = os.getenv("REMOTE_EXEC_URL", "http://10.238.36.146:9999")

    # Google Cloud / Vertex AI
    GOOGLE_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    GOOGLE_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    # ADK model
    MODEL = os.getenv("ADK_MODEL", "gemini-2.0-flash")

    @classmethod
    def summary(cls) -> dict:
        return {
            "hana_host": cls.HANA_HOST,
            "hana_port": cls.HANA_PORT,
            "hana_user": cls.HANA_USER,
            "remote_exec_url": cls.REMOTE_EXEC_URL,
            "google_project": cls.GOOGLE_PROJECT_ID,
            "google_location": cls.GOOGLE_LOCATION,
            "model": cls.MODEL,
        }
