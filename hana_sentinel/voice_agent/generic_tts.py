"""
Generic Text-to-Speech adapter for LiveKit Agents.

Uses `edge-tts` (Microsoft Edge's free TTS service).
No API key required. High-quality neural voices.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import edge_tts

from livekit.agents import tts
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions
from livekit.agents._exceptions import APIConnectionError
from livekit.agents.utils import shortuuid

logger = logging.getLogger("voice-agent.generic-tts")

# edge-tts default output is MP3 at 24kHz mono
SAMPLE_RATE = 24000
NUM_CHANNELS = 1


class GenericTTS(tts.TTS):
    """Text-to-Speech using Microsoft Edge's free TTS service via `edge-tts`.

    No API key needed. Uses high-quality neural voices.
    """

    def __init__(
        self,
        *,
        voice: str = "en-US-AriaNeural",
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
        )
        self._voice = voice
        self._rate = rate
        self._volume = volume
        self._pitch = pitch

    @property
    def model(self) -> str:
        return self._voice

    @property
    def provider(self) -> str:
        return "edge-tts"

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> "GenericChunkedStream":
        return GenericChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
        )

    async def aclose(self) -> None:
        pass


class GenericChunkedStream(tts.ChunkedStream):
    """ChunkedStream that uses edge-tts to synthesize audio."""

    def __init__(
        self,
        *,
        tts: GenericTTS,
        input_text: str,
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._generic_tts = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        import time

        logger.info("TTS _run called: text=%r", self.input_text[:80])
        start = time.time()

        output_emitter.initialize(
            request_id=shortuuid(),
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
            mime_type="audio/mpeg",  # edge-tts outputs MP3
        )

        communicate = edge_tts.Communicate(
            text=self.input_text,
            voice=self._generic_tts._voice,
            rate=self._generic_tts._rate,
            volume=self._generic_tts._volume,
            pitch=self._generic_tts._pitch,
        )

        try:
            total_bytes = 0
            async for chunk in communicate.stream():
                if chunk["type"] == "audio" and "data" in chunk:
                    total_bytes += len(chunk["data"])
                    output_emitter.push(chunk["data"])

            output_emitter.flush()
            logger.info(
                "TTS done: %d bytes, %.1fs", total_bytes, time.time() - start
            )
        except Exception as exc:
            logger.error("edge-tts synthesis failed: %s (%.1fs)", exc, time.time() - start)
            raise APIConnectionError(
                f"Edge TTS synthesis error: {exc}"
            ) from exc
