# HANA Sentinel — Voice Frontend

Voice-powered SAP HANA operations assistant. Browser-based WebRTC interface using LiveKit.

## Stack

- **Next.js 15** (App Router)
- **LiveKit** (WebRTC voice, agent dispatch)
- **Tailwind CSS** (dark theme)
- **edge-tts** + **SpeechRecognition** (free STT/TTS via the Python voice agent)

## Environment Variables

Set these in your deployment platform (never commit real values):

| Variable | Description | Example |
|---|---|---|
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL | `wss://your-project.livekit.cloud` |
| `LIVEKIT_API_KEY` | LiveKit API key | `APIxxxxx` |
| `LIVEKIT_API_SECRET` | LiveKit API secret | `your_secret_here` |

All variables are **server-side only** (no `NEXT_PUBLIC_` prefix) — they're used in the `/api/token` route.

## Deploy to Vercel

1. Push this folder to a Git repo (or use Vercel CLI)
2. Import the project in [vercel.com/new](https://vercel.com/new)
3. Set **Root Directory** to `voice_frontend` (if in a monorepo)
4. Add the 3 environment variables above in **Settings → Environment Variables**
5. Deploy — Vercel auto-detects Next.js

The included `vercel.json` handles framework detection.

## Deploy to Render

1. Push to a Git repo
2. Create a **New Web Service** at [dashboard.render.com](https://dashboard.render.com)
3. Set **Root Directory** to `voice_frontend`
4. Build command: `npm install && npm run build`
5. Start command: `npm run start`
6. Add the 3 environment variables in the service's Environment tab

The included `render.yaml` can also be used with Render Blueprints for one-click deploy.

## Local Development

```bash
cp .env.example .env
# Fill in your LiveKit credentials in .env
npm install
npm run dev
```

Opens on [http://localhost:3000](http://localhost:3000).

## Architecture

```
voice_frontend/
├── app/
│   ├── api/token/route.ts   # Server-side token generation + agent dispatch
│   ├── page.tsx              # Main UI (connect/disconnect state machine)
│   ├── layout.tsx            # Root layout + metadata
│   └── globals.css           # Dark theme + LiveKit overrides
├── components/
│   └── VoiceRoom.tsx         # LiveKit room, visualizer, merged transcript
├── next.config.js
├── vercel.json               # Vercel deployment config
├── render.yaml               # Render deployment config
└── .env.example              # Template for environment variables
```

## SIP / Phone Access

A US phone number **+1 (484) 270-7074** is configured via LiveKit Cloud SIP:
- Inbound trunk: `ST_aXZPuTr7QoAS`
- Dispatch rule: `SDR_KLJGEH6HuDsZ` (routes to `sip-call-*` rooms)
- Callers are greeted with a phone-optimized shorter greeting

## Notes

- `iceTransportPolicy: "relay"` is set in `VoiceRoom.tsx` for corporate firewall compatibility. For public deployments you can remove this for lower latency.
- The voice agent (`voice_agent/agent.py`) must be running and registered with LiveKit Cloud for the frontend to work.
