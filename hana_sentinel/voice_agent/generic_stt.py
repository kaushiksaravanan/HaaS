"""
Generic Speech-to-Text adapter for LiveKit Agents.

Uses Python's `speech_recognition` library with Google's free web API.
No API key required. For streaming, pair with livekit's StreamAdapter + Silero VAD.
"""

from __future__ import annotations

import io
import logging
import wave

from livekit import rtc
from livekit.agents import stt, utils
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
)
from livekit.agents._exceptions import APIConnectionError

import speech_recognition as sr

logger = logging.getLogger("voice-agent.generic-stt")

SAMPLE_RATE = 16000
NUM_CHANNELS = 1

# Common garbage prefixes the free Google STT prepends (echo/artifacts)
_STT_JUNK_PREFIXES = [
    "you", "yeah", "hey", "the", "a", "so",
]


def _clean_stt_text(text: str) -> str:
    """Remove common STT artifacts like 'you' prefix from echo bleed."""
    if not text:
        return text
    cleaned = text.strip()
    # Only strip if the junk word is fused with the next word (no space) 
    # e.g. "youwhat is" → "what is", or is a standalone prefix before a question
    for prefix in _STT_JUNK_PREFIXES:
        lower = cleaned.lower()
        # Fused: "youwhat" → remove "you"
        if lower.startswith(prefix) and len(cleaned) > len(prefix) and cleaned[len(prefix)].isalpha():
            cleaned = cleaned[len(prefix):]
            logger.debug("STT cleaned fused prefix %r → %r", prefix, cleaned)
            break
        # Separated: "you what is the time" where "you" is just echo
        if lower.startswith(prefix + " ") and len(cleaned) > len(prefix) + 1:
            rest = cleaned[len(prefix) + 1:]
            # Only strip if what follows looks like a real query
            rest_lower = rest.lower()
            if any(rest_lower.startswith(w) for w in [
                "what", "how", "show", "check", "run", "get", "is", "are",
                "tell", "list", "sapcontrol", "uptime", "df", "free", "top",
                "ps", "cat", "ls", "service", "status", "restart", "stop",
            ]):
                cleaned = rest
                logger.debug("STT cleaned separated prefix %r → %r", prefix, cleaned)
                break
    return cleaned.strip()


class GenericSTT(stt.STT):
    """Speech-to-Text using Python's SpeechRecognition library (Google free web API).

    This is a batch-only STT (no streaming). Wrap with
    ``livekit.agents.stt.StreamAdapter`` + Silero VAD for real-time use.
    """

    def __init__(
        self,
        *,
        language: str = "en-US",
        sample_rate: int = SAMPLE_RATE,
    ) -> None:
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=False,
                interim_results=False,
            ),
        )
        self._language = language
        self._sample_rate = sample_rate
        self._recognizer = sr.Recognizer()

    @property
    def model(self) -> str:
        return "google-free-web"

    @property
    def provider(self) -> str:
        return "speech_recognition"

    async def _recognize_impl(
        self,
        buffer: utils.AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> stt.SpeechEvent:
        import asyncio
        import time

        lang = language if isinstance(language, str) else self._language

        # Combine all audio frames into a single frame
        combined = rtc.combine_audio_frames(buffer)
        duration_ms = len(combined.data) * 1000 // combined.sample_rate
        logger.info(
            "STT _recognize_impl called: %d samples, ~%dms, sr=%d",
            len(combined.data), duration_ms, combined.sample_rate,
        )

        # Feed into speech_recognition
        audio_data = sr.AudioData(
            combined.data.tobytes(),
            sample_rate=combined.sample_rate,
            sample_width=2,
        )

        text = ""
        start = time.time()
        try:
            text = await asyncio.wait_for(
                asyncio.to_thread(
                    self._recognizer.recognize_google,
                    audio_data,
                    language=lang,
                ),
                timeout=15.0,
            )
            logger.info("STT result: %r (%.1fs)", text, time.time() - start)
        except asyncio.TimeoutError:
            logger.warning("STT timed out after 15s")
            text = ""
        except sr.UnknownValueError:
            logger.info("STT: no speech detected (%.1fs)", time.time() - start)
            text = ""
        except sr.RequestError as exc:
            logger.error("Google STT request failed: %s (%.1fs)", exc, time.time() - start)
            text = ""
        except Exception as exc:
            logger.error("STT unexpected error: %s (%.1fs)", exc, time.time() - start)
            text = ""

        # Clean up common STT artifacts
        text = _clean_stt_text(text)

        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[
                stt.SpeechData(
                    language=lang,
                    text=text,
                    confidence=0.9 if text else 0.0,
                ),
            ],
        )

    async def aclose(self) -> None:
        pass


def _pcm_to_wav(
    pcm_data: bytes,
    *,
    sample_rate: int,
    num_channels: int,
    sample_width: int,
) -> bytes:
    """Convert raw PCM bytes to WAV format in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()
