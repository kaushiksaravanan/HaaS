import { NextResponse } from "next/server";
import { AccessToken, RoomAgentDispatch, RoomConfiguration } from "livekit-server-sdk";

export async function POST() {
  // Hardcoded for temp deployment — move to env vars for production
  const apiKey = process.env.LIVEKIT_API_KEY || "APIeZq6oRUsszkJ";
  const apiSecret = process.env.LIVEKIT_API_SECRET || "LIVEKIT_SECRET_REVOKED_PLACEHOLDER_0000000000000000";
  const livekitUrl = process.env.LIVEKIT_URL || "wss://blazer-eokti6f6.livekit.cloud";

  // Each connection gets a unique room so the agent is dispatched fresh
  const roomName = `hana-sentinel-voice-${Date.now()}`;
  const participantIdentity = `web-user-${Date.now()}`;

  const at = new AccessToken(apiKey, apiSecret, {
    identity: participantIdentity,
    ttl: "10m",
  });
  at.addGrant({
    roomJoin: true,
    room: roomName,
    canPublish: true,
    canSubscribe: true,
  });

  // Request agent dispatch — tells LiveKit Cloud to assign an agent worker
  at.roomConfig = new RoomConfiguration({
    agents: [new RoomAgentDispatch({ agentName: "hana-sentinel-voice" })],
  });

  const token = await at.toJwt();

  return NextResponse.json({
    token,
    url: livekitUrl,
    room: roomName,
  });
}
