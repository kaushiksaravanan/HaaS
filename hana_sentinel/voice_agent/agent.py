"""
HANA Sentinel Voice Agent — LiveKit Agents 1.4 Pipeline
========================================================

A voice agent that connects callers to the HANA Sentinel system.
Uses LiveKit Agents 1.4+ framework with:
  - Generic STT via SpeechRecognition (free Google web API, no key)
  - Generic TTS via edge-tts (free Microsoft Edge TTS, no key)
  - Custom LLM that proxies to HANA Sentinel API
  - Silero VAD (voice activity detection)

The agent proxies user speech into the /api/v1/agent/chat endpoint
and speaks the response back.

Requires: livekit-agents>=1.4, livekit-plugins-silero,
          SpeechRecognition, edge-tts
"""

import os
import re
import asyncio
import json
import logging
import random
import time
from typing import Any

import requests
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
)
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
)
from livekit.agents.llm import (
    ChatContext,
    ChatChunk,
    ChoiceDelta,
    LLM,
    LLMStream,
    Tool,
    ToolChoice,
)
from livekit.agents.stt import StreamAdapter
from livekit.plugins import silero
from livekit.rtc import RtcConfiguration
from livekit.rtc._proto.room_pb2 import IceTransportType

try:
    from voice_agent.generic_stt import GenericSTT
    from voice_agent.generic_tts import GenericTTS
except ModuleNotFoundError:
    from generic_stt import GenericSTT
    from generic_tts import GenericTTS

# Load env from project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
# Also load local .env if present
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

logger = logging.getLogger("voice-agent")
logger.setLevel(logging.INFO)

# HANA Sentinel API base URL
SENTINEL_API_URL = os.getenv("SENTINEL_API_URL", "http://localhost:8000")


# ── Sentinel API proxy ──────────────────────────────

def _call_sentinel_chat(message: str, conversation_id: str | None = None) -> dict:
    """Call the HANA Sentinel /api/v1/agent/chat endpoint."""
    try:
        resp = requests.post(
            f"{SENTINEL_API_URL}/api/v1/agent/chat",
            json={
                "message": message,
                "conversation_id": conversation_id,
                "admin_mode": True,
                "voice_mode": True,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("Sentinel API call failed: %s", exc)
        return {
            "response": (
                "I'm sorry, I couldn't reach the HANA Sentinel backend. "
                f"Error: {exc}"
            )
        }


def _strip_markdown_for_speech(text: str) -> str:
    """Remove markdown formatting to make text more natural for TTS."""
    # Remove code blocks entirely — they're unreadable in speech
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code backticks
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove bold/italic markers
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    # Remove headings
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove markdown links — keep the text, drop the URL
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove label prefixes like "Admin Command:" or "Output:"
    text = re.sub(r"\*?\*?Admin Command:\*?\*?\s*", "", text)
    text = re.sub(r"\*?\*?Command:\*?\*?\s*", "", text)
    text = re.sub(r"\*?\*?Output:\*?\*?\s*", "", text)
    text = re.sub(r"\*?\*?Error:\*?\*?\s*", "", text)
    # Collapse whitespace
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\n", " ", text)
    text = re.sub(r" {2,}", " ", text)
    # Remove orphaned punctuation from stripping
    text = re.sub(r"\. *\. *\.", ".", text)
    text = re.sub(r"  +", " ", text)
    return text.strip().strip('.').strip()


def _normalize_for_speech(text: str) -> str:
    """Convert numbers, units, and abbreviations to spoken-word forms."""
    # Percentages: "66%" → "66 percent"
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1 percent', text)
    # Bytes: "7G" / "7GB" → "7 gigs", "512M" / "512MB" → "512 megs"
    text = re.sub(r'(\d+(?:\.\d+)?)\s*(?:GB|G\b)', r'\1 gigs', text)
    text = re.sub(r'(\d+(?:\.\d+)?)\s*(?:MB|M\b)', r'\1 megs', text)
    text = re.sub(r'(\d+(?:\.\d+)?)\s*(?:KB|K\b)', r'\1 K B', text)
    text = re.sub(r'(\d+(?:\.\d+)?)\s*(?:TB|T\b)', r'\1 terabytes', text)
    # Time: "5s" → "5 seconds", "120ms" → "120 milliseconds"
    text = re.sub(r'(\d+(?:\.\d+)?)\s*ms\b', r'\1 milliseconds', text)
    text = re.sub(r'(\d+(?:\.\d+)?)\s*s\b', r'\1 seconds', text)
    # Common abbreviations
    text = re.sub(r'\bCPU\b', 'C P U', text)
    text = re.sub(r'\bI/O\b', 'I O', text)
    text = re.sub(r'\bSQL\b', 'S Q L', text)
    text = re.sub(r'\bSSH\b', 'S S H', text)
    text = re.sub(r'\bHTTP\b', 'H T T P', text)
    text = re.sub(r'\bAPI\b', 'A P I', text)
    text = re.sub(r'\bURL\b', 'U R L', text)
    # Filesystem paths: "/dev/sda1" reads oddly, simplify
    text = re.sub(r'/dev/\w+', 'the disk', text)
    # IP-like patterns: make them pronounceable
    text = re.sub(r'(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})', r'\1 dot \2 dot \3 dot \4', text)
    return text


# Filler phrases to bridge the gap while the API processes
_THINKING_FILLERS = [
    "Let me check on that.",
    "One moment.",
    "Looking into it.",
    "Checking now.",
    "Let me see.",
    "On it.",
]

# Greeting variety
_GREETINGS = [
    "Hey there! I'm HANA Ops Agent. What can I help you with?",
    "Hello! HANA Ops Agent here. How can I help?",
    "Hi! I'm HANA Ops Agent, your SAP HANA assistant. What do you need?",
    "Hey! HANA Ops Agent ready. What's up?",
    "Hello! I'm HANA Ops Agent. Ask me anything about your HANA system.",
]


# ── Custom LLM that routes through Sentinel API ─────

class SentinelLLM(LLM):
    """LLM adapter that routes requests through HANA Sentinel
    /api/v1/agent/chat so the full tool pipeline is used."""

    def __init__(self) -> None:
        super().__init__()
        self._conversation_id: str | None = None
        self._room = None  # Set by entrypoint so streams can publish data logs

    @property
    def model(self) -> str:
        return "sentinel-proxy"

    @property
    def provider(self) -> str:
        return "hana-sentinel"

    def chat(
        self,
        *,
        chat_ctx: ChatContext,
        tools: list[Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> "SentinelLLMStream":
        # Extract the latest user message from chat context
        user_msg = ""
        for msg in reversed(chat_ctx.messages()):
            if msg.role == "user":
                user_msg = msg.text_content or ""
                break

        return SentinelLLMStream(
            llm=self,
            user_msg=user_msg,
            conversation_id=self._conversation_id,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
        )

    async def aclose(self) -> None:
        pass


class SentinelLLMStream(LLMStream):
    """Streams the HANA Sentinel response back as an LLM chunk."""

    def __init__(
        self,
        llm: SentinelLLM,
        user_msg: str,
        conversation_id: str | None,
        chat_ctx: ChatContext,
        tools: list[Tool],
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(
            llm,
            chat_ctx=chat_ctx,
            tools=tools,
            conn_options=conn_options,
        )
        self._user_msg = user_msg
        self._conversation_id = conversation_id
        self._sentinel_llm = llm

    async def _run(self) -> None:
        # Helper to send a log event to the frontend via data channel
        async def _publish_log(event: str, detail: str = ""):
            room = self._sentinel_llm._room
            if room and room.local_participant:
                try:
                    payload = json.dumps({
                        "type": "sentinel_log",
                        "event": event,
                        "detail": detail,
                        "ts": time.time(),
                    }).encode("utf-8")
                    await room.local_participant.publish_data(payload, reliable=True)
                except Exception:
                    pass  # Don't break speech pipeline for log failures

        # Emit a quick filler phrase so the user doesn't hear dead silence
        filler = random.choice(_THINKING_FILLERS)
        self._event_ch.send_nowait(
            ChatChunk(
                id="sentinel-filler",
                delta=ChoiceDelta(role="assistant", content=filler + " "),
            )
        )

        await _publish_log("stt_received", self._user_msg)
        await _publish_log("api_call", f"POST {SENTINEL_API_URL}/api/v1/agent/chat")

        # Call Sentinel API in a thread (synchronous HTTP)
        t0 = time.time()
        result = await asyncio.to_thread(
            _call_sentinel_chat, self._user_msg, self._conversation_id
        )
        elapsed = time.time() - t0

        # Persist conversation ID for multi-turn
        conv_id = result.get("conversation_id")
        if conv_id:
            self._sentinel_llm._conversation_id = conv_id

        response_text = result.get("response", "I didn't get a response.")
        await _publish_log("api_response", f"{len(response_text)} chars in {elapsed:.1f}s")

        clean_text = _strip_markdown_for_speech(response_text)
        clean_text = _normalize_for_speech(clean_text)
        await _publish_log("tts_start", clean_text[:120])

        # Stream in sentence-sized chunks for faster first-byte TTS
        sentences = re.split(r'(?<=[.!?])\s+', clean_text)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            self._event_ch.send_nowait(
                ChatChunk(
                    id=conv_id or "sentinel-chunk",
                    delta=ChoiceDelta(
                        role="assistant",
                        content=sentence + " ",
                    ),
                )
            )


# ── Agent entrypoint ────────────────────────────────

def prewarm(proc: JobProcess) -> None:
    """Pre-load the Silero VAD model once per worker process."""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext) -> None:
    """Main entrypoint for each voice session."""
    await ctx.connect(
        auto_subscribe=AutoSubscribe.AUDIO_ONLY,
        rtc_config=RtcConfiguration(
            ice_transport_type=IceTransportType.TRANSPORT_RELAY,
        ),
    )

    # Detect if this is a phone call (SIP) vs browser WebRTC
    is_sip = ctx.room.name.startswith("sip-call-")
    if is_sip:
        logger.info("SIP phone call detected (room=%s)", ctx.room.name)
    else:
        logger.info("WebRTC browser session (room=%s)", ctx.room.name)

    # LLM proxy
    agent_llm = SentinelLLM()
    agent_llm._room = ctx.room  # Give LLM stream access to room for data-channel logs
    logger.info("Using HANA Sentinel API proxy for LLM")

    # Free STT: SpeechRecognition (Google web API) + StreamAdapter with Silero VAD
    batch_stt = GenericSTT(language="en-US")
    streaming_stt = StreamAdapter(
        stt=batch_stt,
        vad=ctx.proc.userdata["vad"],
    )

    # Free TTS: edge-tts (Microsoft Edge neural voices)
    # JennyNeural = warm & conversational, +15% rate for snappier delivery
    edge_voice = os.getenv("EDGE_TTS_VOICE", "en-US-JennyNeural")
    generic_tts = GenericTTS(voice=edge_voice, rate="+15%", pitch="+2Hz")

    # Phone callers get slightly different instructions
    if is_sip:
        instructions = (
            "You are HANA Ops Agent, a voice-first AI ops assistant for SAP HANA. "
            "The user is calling from a phone. "
            "RULES FOR PHONE: "
            "1) Keep answers to 1-2 sentences — phone audio quality is lower. "
            "2) Spell out numbers clearly. Say 'percent' not the symbol. "
            "3) Never mention URLs, links, or visual elements. "
            "4) If a command fails, briefly say what went wrong. "
            "5) For long outputs, give only the single most important finding. "
            "6) Be direct and efficient — phone callers are often on the go. "
            "\n\n"
            "COMMON COMMANDS YOU CAN RUN — use these proactively:\n"
            "OS: uptime, df -h, free -h, top -bn1 | head -20, ps aux --sort=-%mem | head -20, "
            "cat /etc/hosts, cat /var/log/messages | tail -50, cat /etc/os-release, "
            "ls -ltr /hana/data, ls -ltr /hana/log, ls -ltr /hana/backup, "
            "du -sh /hana/data/* /hana/log/* /hana/shared/*, "
            "cat /proc/sys/vm/swappiness, cat /sys/kernel/mm/transparent_hugepage/enabled, "
            "ss -tlnp, mount | grep hana\n"
            "HANA: sapcontrol -nr 02 -function GetProcessList, "
            "sapcontrol -nr 02 -function GetSystemInstanceList, HDB info, HDB version, "
            "hdbuserstore list, "
            "hdbsql -U DEFAULT \"SELECT SERVICE_NAME, ACTIVE_STATUS FROM M_SERVICES\", "
            "hdbsql -U DEFAULT \"SELECT HOST, ROUND(CPU_USER_PCT,1) AS CPU, ROUND(MEMORY_USED_PCT,1) AS MEM FROM M_HOST_RESOURCE_UTILIZATION\", "
            "hdbsql -U DEFAULT \"SELECT TOP 5 BACKUP_ID, STATE_NAME, SYS_START_TIME, SYS_END_TIME FROM M_BACKUP_CATALOG ORDER BY SYS_END_TIME DESC\", "
            "hdbsql -U DEFAULT \"SELECT USAGE_TYPE, ROUND(USED_SIZE/1024/1024/1024,1) AS USED_GB, ROUND(TOTAL_SIZE/1024/1024/1024,1) AS TOTAL_GB FROM M_DISK_USAGE\", "
            "hdbsql -U DEFAULT \"SELECT ALERT_ID, ALERT_RATING, ALERT_DETAILS FROM STATISTICS_CURRENT_ALERTS WHERE ALERT_RATING >= 3\", "
            "hdbsql -U DEFAULT \"SELECT * FROM M_SYSTEM_OVERVIEW\"\n"
            "When the user asks about disk, memory, processes, backups, services, etc., "
            "run the matching command and report the real numbers."
        )
    else:
        instructions = (
            "You are HANA Ops Agent, a voice-first AI ops assistant for SAP HANA. "
            "You are connected to a LIVE server and can run real commands. "
            "RULES FOR VOICE: "
            "1) Keep every answer under 2-3 sentences unless the user asks for detail. "
            "2) Never read out raw command output, tables, or code — summarize the key finding. "
            "3) Use natural spoken English: contractions, filler words are OK. "
            "4) For command results, say the important number or status, not the whole output. "
            "   Example: instead of reading df -h output, say 'Root partition is 66 percent used with about 7 gigs free.' "
            "5) If something failed, say what went wrong in plain language. "
            "6) When asked to run something, just do it and report back — no need to confirm first for read-only commands. "
            "7) NEVER give textbook definitions. If the user asks about uptime, disk, memory, etc., "
            "   check the actual LIVE system and report real numbers. "
            "\n\n"
            "COMMON COMMANDS YOU CAN RUN — use these proactively:\n"
            "OS: uptime, df -h, free -h, top -bn1 | head -20, ps aux --sort=-%mem | head -20, "
            "cat /etc/hosts, cat /var/log/messages | tail -50, cat /etc/os-release, "
            "ls -ltr /hana/data, ls -ltr /hana/log, ls -ltr /hana/backup, "
            "du -sh /hana/data/* /hana/log/* /hana/shared/*, "
            "cat /proc/sys/vm/swappiness, cat /sys/kernel/mm/transparent_hugepage/enabled, "
            "ss -tlnp, mount | grep hana\n"
            "HANA: sapcontrol -nr 02 -function GetProcessList, "
            "sapcontrol -nr 02 -function GetSystemInstanceList, HDB info, HDB version, "
            "hdbuserstore list, "
            "hdbsql -U DEFAULT \"SELECT SERVICE_NAME, ACTIVE_STATUS FROM M_SERVICES\", "
            "hdbsql -U DEFAULT \"SELECT HOST, ROUND(CPU_USER_PCT,1) AS CPU, ROUND(MEMORY_USED_PCT,1) AS MEM FROM M_HOST_RESOURCE_UTILIZATION\", "
            "hdbsql -U DEFAULT \"SELECT TOP 5 BACKUP_ID, STATE_NAME, SYS_START_TIME, SYS_END_TIME FROM M_BACKUP_CATALOG ORDER BY SYS_END_TIME DESC\", "
            "hdbsql -U DEFAULT \"SELECT USAGE_TYPE, ROUND(USED_SIZE/1024/1024/1024,1) AS USED_GB, ROUND(TOTAL_SIZE/1024/1024/1024,1) AS TOTAL_GB FROM M_DISK_USAGE\", "
            "hdbsql -U DEFAULT \"SELECT ALERT_ID, ALERT_RATING, ALERT_DETAILS FROM STATISTICS_CURRENT_ALERTS WHERE ALERT_RATING >= 3\", "
            "hdbsql -U DEFAULT \"SELECT * FROM M_SYSTEM_OVERVIEW\"\n"
            "When the user asks about disk, memory, processes, backups, services, etc., "
            "run the matching command and report the real numbers."
        )

    agent = Agent(
        instructions=instructions,
        stt=streaming_stt,
        llm=agent_llm,
        tts=generic_tts,
    )

    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        allow_interruptions=True,
        min_endpointing_delay=0.35,
    )

    logger.info("Starting agent session...")
    await session.start(agent, room=ctx.room)
    logger.info("Agent session started, generating greeting...")

    # Phone gets a shorter greeting; browser gets variety
    if is_sip:
        greeting = "HANA Sentinel. How can I help?"
    else:
        greeting = random.choice(_GREETINGS)

    await session.say(greeting, allow_interruptions=False)
    logger.info("Greeting sent, now listening for user speech.")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name="hana-sentinel-voice",
        )
    )
