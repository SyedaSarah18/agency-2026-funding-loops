// Proxies the /investigate SSE stream from the FastAPI agent service to the browser.
// Force Node runtime + dynamic so Next.js doesn't try to buffer/cache the stream.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  const url = new URL(req.url);
  const mode = url.searchParams.get("mode") ?? "real";
  const upstream = await fetch(
    `${AGENT_SERVICE_URL}/investigate?mode=${encodeURIComponent(mode)}`,
    {
      method: "POST",
      headers: { Accept: "text/event-stream" },
    }
  );

  if (!upstream.ok || !upstream.body) {
    return new Response(`Agent service error: ${upstream.status}`, {
      status: 502,
    });
  }

  // Re-pipe through a TransformStream so Node doesn't buffer-then-flush the
  // upstream chunks. Each chunk arrives at the browser as soon as FastAPI emits it.
  const { readable, writable } = new TransformStream();
  upstream.body.pipeTo(writable).catch(() => {});

  return new Response(readable, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      // Disables nginx/edge proxy buffering. Required for SSE to flow chunk-by-chunk.
      "X-Accel-Buffering": "no",
    },
  });
}
