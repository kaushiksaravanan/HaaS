# HANA Sentinel Voice Agent

Voice-powered interface for HANA Sentinel using **LiveKit**. Operators can talk to the system hands-free — ask about health, run diagnostics, check backups, and execute commands via natural speech.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Vercel (voice_frontend/)             │
│  Next.js app  ──►  /api/token  ──►  LiveKit token    │
│  Browser mic  ◄──────────────────►  LiveKit Cloud     │
└──────────────────────────────┬───────────────────────┘
                               │ WebRTC audio
                               ▼
┌──────────────────────────────────────────────────────┐
│               LiveKit Cloud / Server                  │
│  Routes audio between browser ◄──► voice agent        │
└──────────────────────────────┬───────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────┐
│            Voice Agent (voice_agent/agent.py)          │
│                                                        │
│  Deepgram STT  ──►  HANA Sentinel API  ──►  OpenAI TTS│
│  (speech→text)      /api/v1/agent/chat      (text→speech)│
│                     (full tool pipeline)                │
└──────────────────────────────┬───────────────────────┘
                               │ HTTP
                               ▼
┌──────────────────────────────────────────────────────┐
│           HANA Sentinel FastAPI (main.py api)         │
│  Agent chat  │  HANA tools  │  Remote exec  │  RAG    │
└──────────────────────────────────────────────────────┘
```

## Prerequisites

1. **LiveKit Cloud account** — Sign up at [livekit.io](https://livekit.io) (free tier available)
2. **Deepgram API key** — For speech-to-text ([deepgram.com](https://deepgram.com))
3. **OpenAI API key** — For text-to-speech (TTS)
4. **HANA Sentinel API** running (the existing FastAPI server)

## Setup

### 1. LiveKit Cloud

1. Create a project at [cloud.livekit.io](https://cloud.livekit.io)
2. Copy the **WebSocket URL**, **API Key**, and **API Secret**

### 2. Voice Agent (Backend)

```bash
cd voice_agent
pip install -r requirements.txt

# Copy and fill in credentials
cp .env.example .env
# Edit .env with your LiveKit, Deepgram, and OpenAI keys

# Make sure HANA Sentinel API is running
# (in another terminal: python main.py api)

# Start the voice agent worker
python agent.py dev
```

The agent connects to LiveKit Cloud and waits for participants to join the room.

### 3. Voice Frontend (Vercel)

```bash
cd voice_frontend
npm install

# For local development
cp .env.example .env.local
# Edit .env.local with your LiveKit credentials
npm run dev
# Open http://localhost:3000
```

#### Deploy to Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
cd voice_frontend
vercel

# Set environment variables in Vercel dashboard:
#   LIVEKIT_URL       = wss://your-project.livekit.cloud
#   LIVEKIT_API_KEY   = your_api_key
#   LIVEKIT_API_SECRET = your_api_secret
```

Or connect the repo to Vercel with these settings:
- **Root Directory:** `voice_frontend`
- **Framework Preset:** Next.js
- **Build Command:** `npm run build`
- **Output Directory:** `.next`

## How It Works

1. User clicks **"Start Voice Session"** on the web page
2. Frontend calls `/api/token` (Next.js serverless function) to get a LiveKit room token
3. Browser connects to LiveKit Cloud via WebRTC (mic audio streams in real-time)
4. The **voice agent worker** (`voice_agent/agent.py`) picks up the session:
   - **Silero VAD** detects when the user is speaking
   - **Deepgram STT** converts speech to text
   - Text is sent to **HANA Sentinel API** (`/api/v1/agent/chat`) which runs the full agent pipeline
   - Response text is cleaned of markdown formatting
   - **OpenAI TTS** converts the response to speech
   - Audio streams back to the browser
5. User hears the response and can continue the conversation

## Configuration

| Variable | Where | Description |
|----------|-------|-------------|
| `LIVEKIT_URL` | Agent + Frontend | LiveKit server WebSocket URL |
| `LIVEKIT_API_KEY` | Agent + Frontend | LiveKit API key |
| `LIVEKIT_API_SECRET` | Agent + Frontend | LiveKit API secret |
| `DEEPGRAM_API_KEY` | Agent only | Deepgram STT API key |
| `OPENAI_API_KEY` | Agent only | OpenAI TTS (and fallback LLM) key |
| `SENTINEL_API_URL` | Agent only | HANA Sentinel FastAPI URL (default: `http://localhost:8000`) |
| `VOICE_USE_SENTINEL_PROXY` | Agent only | `true` = route through Sentinel API, `false` = direct OpenAI |

## Troubleshooting

- **"LiveKit credentials not configured"** — Set env vars in Vercel dashboard or `.env.local`
- **Agent not responding** — Ensure `python agent.py dev` is running and connected to LiveKit
- **No audio** — Check browser microphone permissions; ensure HTTPS (Vercel provides this)
- **Slow responses** — HANA queries can take time; the agent buffers and streams when ready
