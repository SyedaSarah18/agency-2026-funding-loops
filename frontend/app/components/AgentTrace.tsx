"use client";

import { useState } from "react";

type AgentEvent = {
  ts: string;
  agent: "discovery" | "investigation" | "validator" | "narrative" | "pipeline";
  kind: "start" | "step" | "tool" | "complete" | "done" | "error";
  message: string;
  payload?: Record<string, unknown>;
};

type Verification = {
  tool: string;
  subject: string;
  verified: boolean;
  details: string;
};

type Brief = {
  loop_id: number;
  lead_number: number;
  lead_unit: string;
  lead_sentence: string;
  named_entities: string[];
  mechanism: string;
  recommendation: string;
  evidence_refs: Record<string, unknown>;
  verdict: string;
  verifications?: Verification[];
  risk_score?: number;
  score_breakdown?: Record<string, number>;
};

const AGENT_COLORS: Record<AgentEvent["agent"], string> = {
  discovery: "bg-blue-50 border-blue-300 text-blue-900",
  investigation: "bg-purple-50 border-purple-300 text-purple-900",
  validator: "bg-amber-50 border-amber-300 text-amber-900",
  narrative: "bg-emerald-50 border-emerald-300 text-emerald-900",
  pipeline: "bg-slate-100 border-slate-400 text-slate-900",
};

const KIND_BADGE: Record<AgentEvent["kind"], string> = {
  start: "START",
  step: "STEP",
  tool: "TOOL",
  complete: "DONE",
  done: "DONE",
  error: "ERROR",
};

export default function AgentTrace() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [briefs, setBriefs] = useState<Brief[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"real" | "fake">("real");

  async function run() {
    setEvents([]);
    setBriefs([]);
    setError(null);
    setRunning(true);

    try {
      const res = await fetch(`/api/investigate?mode=${mode}`, { method: "POST" });
      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE messages are separated by blank lines; each message has "data:" lines.
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const raw = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const dataLine = raw
            .split("\n")
            .find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          try {
            const evt: AgentEvent = JSON.parse(dataLine.slice(5).trim());
            setEvents((prev) => [...prev, evt]);
            if (
              evt.agent === "pipeline" &&
              evt.kind === "done" &&
              Array.isArray(evt.payload?.briefs)
            ) {
              setBriefs(evt.payload!.briefs as Brief[]);
            }
          } catch {
            // skip malformed
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="w-full max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-slate-900">
          Agency 2026 — Funding Loops Investigator
        </h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={mode === "fake"}
              onChange={(e) => setMode(e.target.checked ? "fake" : "real")}
              disabled={running}
            />
            fake-events mode
          </label>
          <button
            onClick={run}
            disabled={running}
            className="px-6 py-3 bg-slate-900 text-white rounded-lg font-semibold hover:bg-slate-700 disabled:bg-slate-400 disabled:cursor-not-allowed transition"
          >
            {running ? "Running…" : "Run Investigation"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-300 rounded-lg text-red-900">
          Error: {error}
        </div>
      )}

      {briefs.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-bold mb-3 text-slate-900">
            Minister Briefs ({briefs.length})
          </h2>
          <div className="grid gap-4">
            {briefs.map((b) => (
              <div
                key={b.loop_id}
                className={`border-l-4 p-4 rounded bg-white ${
                  b.verdict === "high_concern"
                    ? "border-red-500"
                    : b.verdict === "medium_concern"
                    ? "border-amber-500"
                    : "border-slate-300"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="text-xs uppercase font-bold text-slate-500">
                    Loop #{b.loop_id} · {b.verdict.replace("_", " ")}
                  </div>
                  {typeof b.risk_score === "number" && (
                    <div className="text-xs font-mono text-slate-600">
                      risk score: <span className="font-bold">{b.risk_score}</span>/100
                    </div>
                  )}
                </div>
                <p className="text-lg font-semibold text-slate-900 mb-2">
                  {b.lead_sentence}
                </p>
                <p className="text-sm text-slate-700 mb-2">{b.mechanism}</p>
                <p className="text-sm text-slate-900 font-semibold mb-2">
                  Recommendation: {b.recommendation}
                </p>
                <div className="text-xs text-slate-500 mb-3">
                  Entities: {b.named_entities.join(", ")}
                </div>

                {b.verifications && b.verifications.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-200">
                    <div className="text-xs font-bold uppercase text-slate-500 mb-2">
                      Validator self-checks ({b.verifications.length})
                    </div>
                    <div className="space-y-1.5">
                      {b.verifications.map((v, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-2 text-xs"
                        >
                          <span
                            className={`shrink-0 inline-flex items-center justify-center w-5 h-5 rounded-full font-bold ${
                              v.verified
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-red-100 text-red-800"
                            }`}
                            title={v.verified ? "Verified against source rows" : "Verification failed"}
                          >
                            {v.verified ? "✓" : "✗"}
                          </span>
                          <div className="flex-1">
                            <code className="text-[10px] text-slate-500 mr-2">
                              {v.tool}
                            </code>
                            <span className="font-semibold text-slate-800">
                              {v.subject}
                            </span>
                            <div className="text-slate-600 mt-0.5">
                              {v.details}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-2">
        {events.length === 0 && !running && (
          <p className="text-slate-500 italic">
            Click &quot;Run Investigation&quot; to launch the 4-agent pipeline.
          </p>
        )}

        {events.map((evt, i) => (
          <div
            key={i}
            className={`flex items-start gap-3 p-3 border-l-4 rounded ${AGENT_COLORS[evt.agent]}`}
          >
            <span className="text-xs font-mono opacity-60 pt-0.5 w-16 shrink-0">
              {new Date(evt.ts).toLocaleTimeString("en-US", {
                hour12: false,
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
            <span className="text-xs font-mono font-bold uppercase pt-0.5 w-24 shrink-0">
              {evt.agent}
            </span>
            <span className="text-xs font-mono opacity-60 pt-0.5 w-12 shrink-0">
              {KIND_BADGE[evt.kind]}
            </span>
            <span className="flex-1 text-sm">{evt.message}</span>
            {evt.payload && Object.keys(evt.payload).length > 0 && (
              <code className="text-xs opacity-60">
                {JSON.stringify(evt.payload)}
              </code>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
