"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Stable placeholder so SSR + first client render match. The real id is
// generated in useEffect after mount so Date.now() doesn't cause hydration drift.
const PLACEHOLDER_SESSION = "init";

type ConductorEvent = {
  ts: string;
  agent: "conductor";
  kind: "start" | "tool" | "data" | "complete" | "error";
  message: string;
  payload?: Record<string, unknown>;
};

type ChatTurn = {
  role: "user" | "assistant";
  text: string;
  toolCalls: { name: string; preview: string }[];
  isStreaming?: boolean;
  errored?: boolean;
};

const SAMPLE_PROMPTS = [
  "Show me IBM Canada's full Alberta footprint",
  "What categories has Microsoft monopolised?",
  "Why did the pipeline flag Hull Services?",
  "Is McKinsey in this data?",
  "What's the median Herfindahl in IT services?",
];

export default function Chat() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [sessionId, setSessionId] = useState<string>(PLACEHOLDER_SESSION);
  // "local" = in-process Conductor on the FastAPI service.
  // "cloud" = AWS Bedrock AgentCore Runtime (Phase F deployment).
  const [backend, setBackend] = useState<"local" | "cloud">("local");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Generate the session id only on the client to avoid hydration mismatch.
  useEffect(() => {
    setSessionId(`s-${Date.now().toString(36)}`);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [turns]);

  async function ask(question: string) {
    if (!question.trim() || running) return;
    const userTurn: ChatTurn = { role: "user", text: question, toolCalls: [] };
    const assistantTurn: ChatTurn = {
      role: "assistant",
      text: "",
      toolCalls: [],
      isStreaming: true,
    };
    setTurns((prev) => [...prev, userTurn, assistantTurn]);
    setInput("");
    setRunning(true);

    try {
      const endpoint = backend === "cloud" ? "/api/ask-cloud" : "/api/ask";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          question,
        }),
      });
      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const SEP_RE = /\r?\n\r?\n/;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        while (true) {
          const m = SEP_RE.exec(buffer);
          if (!m) break;
          const raw = buffer.slice(0, m.index);
          buffer = buffer.slice(m.index + m[0].length);
          const dataLine = raw
            .split(/\r?\n/)
            .find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          try {
            const evt: ConductorEvent = JSON.parse(dataLine.slice(5).trim());
            setTurns((prev) => {
              const next = [...prev];
              const last = { ...next[next.length - 1] };
              if (evt.kind === "data") {
                last.text += evt.message;
              } else if (evt.kind === "tool") {
                last.toolCalls = [
                  ...last.toolCalls,
                  {
                    name: evt.message.replace(/^calling tool:\s*/, ""),
                    preview: String(evt.payload?.input_preview ?? ""),
                  },
                ];
              } else if (evt.kind === "complete") {
                last.isStreaming = false;
                const fa = String(evt.payload?.final_answer ?? "");
                if (fa && !last.text) last.text = fa;
              } else if (evt.kind === "error") {
                last.isStreaming = false;
                last.errored = true;
                last.text = (last.text ? last.text + "\n\n" : "") + `[error] ${evt.message}`;
              }
              next[next.length - 1] = last;
              return next;
            });
          } catch {
            // skip malformed
          }
        }
      }
    } catch (e) {
      setTurns((prev) => {
        const next = [...prev];
        const last = { ...next[next.length - 1] };
        last.isStreaming = false;
        last.errored = true;
        last.text = (last.text ? last.text + "\n\n" : "") + `[error] ${e instanceof Error ? e.message : String(e)}`;
        next[next.length - 1] = last;
        return next;
      });
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="bg-white border border-slate-200 rounded-lg flex flex-col h-[600px]">
      <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between gap-3">
        <div>
          <div className="font-semibold text-slate-900">Conductor chat</div>
          <div className="text-xs text-slate-500">
            Ask anything about Alberta procurement. The Conductor reasons about
            which tools to use per question.
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 text-xs">
            <span className="text-slate-500">backend:</span>
            <button
              type="button"
              onClick={() => setBackend("local")}
              disabled={running}
              className={`px-2 py-1 rounded font-mono ${
                backend === "local"
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              } disabled:opacity-50`}
              title="In-process Conductor (FastAPI)"
            >
              local
            </button>
            <button
              type="button"
              onClick={() => setBackend("cloud")}
              disabled={running}
              className={`px-2 py-1 rounded font-mono ${
                backend === "cloud"
                  ? "bg-orange-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              } disabled:opacity-50`}
              title="AWS Bedrock AgentCore Runtime"
            >
              cloud (AgentCore)
            </button>
          </div>
          <div className="text-xs text-slate-400 font-mono">
            session: {sessionId.slice(-6)}
          </div>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {turns.length === 0 && (
          <div className="text-sm text-slate-500">
            <p className="mb-2">Try one of these:</p>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => ask(p)}
                  disabled={running}
                  className="text-xs px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 rounded-md border border-slate-200 text-left transition disabled:opacity-50"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((t, i) => (
          <div
            key={i}
            className={`flex ${t.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 ${
                t.role === "user"
                  ? "bg-slate-900 text-white"
                  : t.errored
                  ? "bg-red-50 border border-red-200 text-red-900"
                  : "bg-slate-50 border border-slate-200 text-slate-900"
              }`}
            >
              {t.role === "assistant" && t.toolCalls.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1">
                  {t.toolCalls.map((tc, j) => (
                    <span
                      key={j}
                      className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 bg-amber-100 text-amber-900 rounded"
                      title={tc.preview}
                    >
                      ⚙ {tc.name}
                    </span>
                  ))}
                </div>
              )}
              {t.role === "user" ? (
                <div className="whitespace-pre-wrap text-sm leading-snug">
                  {t.text}
                </div>
              ) : (
                <div className="text-sm leading-snug chat-md">
                  {t.text ? (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        // Excel-like table: bordered cells, monospaced numbers,
                        // horizontal scroll on overflow so wide tables don't
                        // break the chat layout.
                        table: ({ children }) => (
                          <div className="my-2 overflow-x-auto">
                            <table className="border-collapse border border-slate-300 text-xs">
                              {children}
                            </table>
                          </div>
                        ),
                        thead: ({ children }) => (
                          <thead className="bg-slate-100">{children}</thead>
                        ),
                        th: ({ children }) => (
                          <th className="border border-slate-300 px-2 py-1 text-left font-semibold text-slate-900">
                            {children}
                          </th>
                        ),
                        td: ({ children }) => (
                          <td className="border border-slate-300 px-2 py-1 align-top tabular-nums">
                            {children}
                          </td>
                        ),
                        code: ({ children, ...props }) => {
                          const inline = !(
                            (props as { node?: { tagName?: string } }).node
                              ?.tagName === "pre"
                          );
                          return inline ? (
                            <code className="bg-slate-200 text-slate-900 px-1 rounded text-[11px]">
                              {children}
                            </code>
                          ) : (
                            <code className="block bg-slate-100 text-slate-900 p-2 rounded text-[11px] overflow-x-auto">
                              {children}
                            </code>
                          );
                        },
                        ul: ({ children }) => (
                          <ul className="list-disc list-inside space-y-0.5 my-2">
                            {children}
                          </ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal list-inside space-y-0.5 my-2">
                            {children}
                          </ol>
                        ),
                        p: ({ children }) => <p className="my-1.5">{children}</p>,
                        strong: ({ children }) => (
                          <strong className="font-semibold text-slate-900">
                            {children}
                          </strong>
                        ),
                        a: ({ children, href }) => (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-700 underline"
                          >
                            {children}
                          </a>
                        ),
                      }}
                    >
                      {t.text}
                    </ReactMarkdown>
                  ) : t.isStreaming ? (
                    "…"
                  ) : (
                    ""
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
        className="px-4 py-3 border-t border-slate-200 flex gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the Conductor anything about the data..."
          disabled={running}
          className="flex-1 text-sm px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:border-slate-900 disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={running || !input.trim()}
          className="px-4 py-2 bg-slate-900 text-white text-sm font-semibold rounded-md hover:bg-slate-700 disabled:bg-slate-400 disabled:cursor-not-allowed"
        >
          {running ? "…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
