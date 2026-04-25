// Proxies the /investigate SSE stream from the FastAPI agent service to the browser.
// POST is never cached by default, so no extra config required for streaming.
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

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
