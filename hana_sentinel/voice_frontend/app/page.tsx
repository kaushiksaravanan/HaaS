"use client";

import { useState, useCallback } from "react";
import VoiceRoom from "@/components/VoiceRoom";

type ConnectionState = "idle" | "connecting" | "connected" | "error";

export default function Home() {
  const [state, setState] = useState<ConnectionState>("idle");
  const [token, setToken] = useState<string>("");
  const [wsUrl, setWsUrl] = useState<string>("");
  const [error, setError] = useState<string>("");

  const connect = useCallback(async () => {
    setState("connecting");
    setError("");

    try {
      const res = await fetch("/api/token", { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `Token request failed (${res.status})`);
      }
      const data = await res.json();
      setToken(data.token);
      setWsUrl(data.url);
      setState("connected");
    } catch (err: any) {
      setError(err.message || "Failed to connect");
      setState("error");
    }
  }, []);

  const disconnect = useCallback(() => {
    setState("idle");
    setToken("");
    setWsUrl("");
  }, []);

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-4">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="flex items-center justify-center gap-3 mb-2">
          <div className="w-3 h-3 rounded-full bg-violet-500 shadow-lg shadow-violet-500/50" />
          <h1 className="text-3xl font-bold tracking-tight">HANA Ops agent</h1>
        </div>
        <p className="text-neutral-400 text-sm">
          Voice-powered SAP HANA operations assistant
        </p>
      </div>

      {/* Main content area */}
      <div className="w-full max-w-lg">
        {state === "idle" && (
          <div className="flex flex-col items-center gap-6">
            <div className="w-32 h-32 rounded-full bg-[#16131F] border-2 border-violet-900/50 flex items-center justify-center">
              <MicIcon className="w-12 h-12 text-violet-400/50" />
            </div>
            <button
              onClick={connect}
              className="px-8 py-3 bg-violet-600 hover:bg-violet-500 text-white font-medium rounded-full
                         transition-all duration-200 shadow-lg shadow-violet-600/25 hover:shadow-violet-500/40"
            >
              Start Voice Session
            </button>
            <p className="text-neutral-500 text-xs text-center max-w-sm">
              Microphone access required. You&apos;ll be connected to HANA Ops agent
              for hands-free SAP HANA management.
            </p>
            <div className="flex items-center gap-2 px-4 py-2 bg-[#16131F]/60 border border-violet-900/30 rounded-lg">
              <PhoneIcon className="w-4 h-4 text-violet-400 shrink-0" />
              <p className="text-neutral-400 text-xs">
                Prefer a phone call? Dial{" "}
                <span className="text-violet-400 font-mono font-medium">+1 (484) 270-7074</span>
              </p>
            </div>
          </div>
        )}

        {state === "connecting" && (
          <div className="flex flex-col items-center gap-6">
            <div className="w-32 h-32 rounded-full bg-[#16131F] border-2 border-violet-700 flex items-center justify-center animate-pulse">
              <MicIcon className="w-12 h-12 text-violet-500" />
            </div>
            <p className="text-neutral-400">Connecting...</p>
          </div>
        )}

        {state === "connected" && token && wsUrl && (
          <VoiceRoom token={token} wsUrl={wsUrl} onDisconnect={disconnect} />
        )}

        {state === "error" && (
          <div className="flex flex-col items-center gap-6">
            <div className="w-32 h-32 rounded-full bg-neutral-900 border-2 border-red-800 flex items-center justify-center">
              <MicIcon className="w-12 h-12 text-red-500" />
            </div>
            <p className="text-red-400 text-sm text-center">{error}</p>
            <button
              onClick={connect}
              className="px-6 py-2 bg-neutral-800 hover:bg-neutral-700 text-white rounded-full transition-colors"
            >
              Retry
            </button>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="mt-16 text-neutral-600 text-xs">
        Powered by DLM &middot; HANA Ops agent v2
      </footer>
    </main>
  );
}

function PhoneIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z"
      />
    </svg>
  );
}

function MicIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"
      />
    </svg>
  );
}
