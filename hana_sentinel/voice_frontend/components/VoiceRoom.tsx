"use client";

import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  useLocalParticipant,
  useTrackTranscription,
  BarVisualizer,
  DisconnectButton,
  useRoomContext,
} from "@livekit/components-react";
import "@livekit/components-styles";
import { Track, RoomEvent } from "livekit-client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

interface VoiceRoomProps {
  token: string;
  wsUrl: string;
  onDisconnect: () => void;
}

// Log event from agent's data channel
interface LogEntry {
  id: number;
  event: string;
  detail: string;
  ts: number;
}

const EVENT_LABELS: Record<string, { label: string; color: string }> = {
  stt_received: { label: "STT", color: "text-blue-400" },
  api_call: { label: "API", color: "text-yellow-400" },
  api_response: { label: "RES", color: "text-green-400" },
  tts_start: { label: "TTS", color: "text-purple-400" },
  command_blocked: { label: "BLK", color: "text-red-400" },
};

export default function VoiceRoom({ token, wsUrl, onDisconnect }: VoiceRoomProps) {
  return (
    <LiveKitRoom
      token={token}
      serverUrl={wsUrl}
      connect={true}
      audio={true}
      video={false}
      onDisconnected={onDisconnect}
      connectOptions={{
        rtcConfig: {
          iceTransportPolicy: "relay",
        },
      }}
      className="flex flex-col items-center gap-6"
    >
      <ActiveRoom onDisconnect={onDisconnect} />
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

function ActiveRoom({ onDisconnect }: { onDisconnect: () => void }) {
  const { state, audioTrack, agentTranscriptions } = useVoiceAssistant();
  const room = useRoomContext();

  // ── Log panel state ──
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logsOpen, setLogsOpen] = useState(true);
  const logIdRef = useRef(0);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  // Listen for data-channel messages from the agent
  useEffect(() => {
    if (!room) return;
    const handler = (payload: Uint8Array) => {
      try {
        const text = new TextDecoder().decode(payload);
        const data = JSON.parse(text);
        if (data.type === "sentinel_log") {
          logIdRef.current += 1;
          setLogs((prev) => [
            ...prev.slice(-100), // keep last 100
            {
              id: logIdRef.current,
              event: data.event || "info",
              detail: data.detail || "",
              ts: data.ts || Date.now() / 1000,
            },
          ]);
        }
      } catch {
        // ignore non-JSON data
      }
    };
    room.on(RoomEvent.DataReceived, handler);
    return () => {
      room.off(RoomEvent.DataReceived, handler);
    };
  }, [room]);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Get user's own speech transcription (STT results sent back by the agent)
  const { localParticipant, microphoneTrack } = useLocalParticipant();
  const micTrackRef = useMemo(
    () =>
      microphoneTrack
        ? {
            participant: localParticipant,
            publication: microphoneTrack,
            source: Track.Source.Microphone as Track.Source,
          }
        : undefined,
    [localParticipant, microphoneTrack]
  );
  const { segments: userSegments } = useTrackTranscription(micTrackRef);

  const lastTranscriptRef = useCallback(
    (node: HTMLDivElement | null) => {
      node?.scrollIntoView({ behavior: "smooth" });
    },
    []
  );

  // Track transcripts in arrival order (no timestamp sorting)
  const [mergedTranscripts, setMergedTranscripts] = useState<
    { role: "user" | "agent"; text: string; id: string }[]
  >([]);
  const seenIdsRef = useRef(new Set<string>());

  useEffect(() => {
    const newItems: { role: "user" | "agent"; text: string; id: string }[] = [];
    for (const s of userSegments) {
      if (s.final && s.text.trim()) {
        const id = `u-${s.id}`;
        if (!seenIdsRef.current.has(id)) {
          seenIdsRef.current.add(id);
          newItems.push({ role: "user", text: s.text, id });
        }
      }
    }
    if (newItems.length > 0) {
      setMergedTranscripts((prev) => [...prev, ...newItems]);
    }
  }, [userSegments]);

  useEffect(() => {
    const newItems: { role: "user" | "agent"; text: string; id: string }[] = [];
    for (const t of agentTranscriptions) {
      if (t.final && t.text.trim()) {
        const id = `a-${t.id}`;
        if (!seenIdsRef.current.has(id)) {
          seenIdsRef.current.add(id);
          newItems.push({ role: "agent", text: t.text, id });
        }
      }
    }
    if (newItems.length > 0) {
      setMergedTranscripts((prev) => [...prev, ...newItems]);
    }
  }, [agentTranscriptions]);

  return (
    <div className="flex flex-col items-center gap-6 w-full">
      {/* Voice visualizer */}
      <div className="relative w-40 h-40 flex items-center justify-center">
        {state === "speaking" && (
          <div className="absolute inset-0 rounded-full bg-violet-500/10 animate-pulse-ring" />
        )}
        <div className="w-32 h-32 rounded-full bg-[#16131F] border-2 border-violet-500 flex items-center justify-center overflow-hidden">
          {audioTrack ? (
            <BarVisualizer
              state={state}
              trackRef={audioTrack}
              barCount={5}
              className="w-20 h-20"
              options={{ minHeight: 4 }}
            />
          ) : (
            <div className="flex gap-1 items-end h-10">
              {[...Array(5)].map((_, i) => (
                <div
                  key={i}
                  className="w-2 bg-violet-500/50 rounded-full"
                  style={{ height: `${12 + Math.random() * 20}px` }}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Status */}
      <div className="text-center">
        <p className="text-sm font-medium text-neutral-300">
          {state === "listening"
            ? "Listening..."
            : state === "thinking"
            ? "Processing..."
            : state === "speaking"
            ? "HANA Ops agent is speaking"
            : state === "connecting"
            ? "Connecting to agent..."
            : "Connected"}
        </p>
        <p className="text-xs text-neutral-500 mt-1">
          {state === "listening" && "Speak to ask about your HANA system"}
        </p>
      </div>

      {/* Transcript area — shows both user and agent messages */}
      <div className="w-full max-h-60 overflow-y-auto bg-[#16131F]/50 rounded-xl border border-violet-900/30 p-4 space-y-3">
        {mergedTranscripts.length === 0 && (
          <p className="text-neutral-600 text-sm text-center">
            Conversation will appear here...
          </p>
        )}
        {mergedTranscripts.map((t, i, arr) => (
          <div
            key={t.id}
            ref={i === arr.length - 1 ? lastTranscriptRef : null}
            className={`text-sm ${
              t.role === "user" ? "text-blue-400" : "text-violet-400"
            }`}
          >
            <span className="font-medium text-xs uppercase tracking-wide mr-2 opacity-60">
              {t.role === "user" ? "you" : "sentinel"}
            </span>
            {t.text}
          </div>
        ))}
      </div>

      {/* ── Agent logs panel ── */}
      <div className="w-full">
        <button
          onClick={() => setLogsOpen((v) => !v)}
          className="flex items-center gap-2 text-xs text-neutral-500 hover:text-neutral-300 transition-colors mb-1"
        >
          <span className="font-mono">{logsOpen ? "▾" : "▸"}</span>
          <span>Agent Logs</span>
          {logs.length > 0 && (
            <span className="bg-neutral-800 text-neutral-400 px-1.5 py-0.5 rounded text-[10px]">
              {logs.length}
            </span>
          )}
        </button>
        {logsOpen && (
          <div className="w-full max-h-44 overflow-y-auto bg-[#0c0a14]/80 rounded-lg border border-violet-900/30 p-3 font-mono text-[11px] space-y-1">
            {logs.length === 0 && (
              <p className="text-neutral-700 text-center">
                Waiting for agent events...
              </p>
            )}
            {logs.map((log) => {
              const meta = EVENT_LABELS[log.event] || { label: log.event.toUpperCase(), color: "text-neutral-400" };
              const timeStr = new Date(log.ts * 1000).toLocaleTimeString("en-US", {
                hour12: false,
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              });
              return (
                <div key={log.id} className="flex gap-2 leading-tight">
                  <span className="text-neutral-600 shrink-0">{timeStr}</span>
                  <span className={`font-bold shrink-0 w-8 ${meta.color}`}>{meta.label}</span>
                  <span className="text-neutral-400 break-all">{log.detail}</span>
                </div>
              );
            })}
            <div ref={logEndRef} />
          </div>
        )}
      </div>

      {/* Disconnect */}
      <DisconnectButton
        className="px-6 py-2 bg-red-600/10 hover:bg-red-600/25 text-red-400 border border-red-900/50
                   rounded-full text-sm transition-colors"
      >
        End Session
      </DisconnectButton>
    </div>
  );
}
