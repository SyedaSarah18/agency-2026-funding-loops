// Proxies the /ask-cloud SSE stream from the FastAPI agent service.
// /ask-cloud routes the question through AWS Bedrock AgentCore Runtime
// (deployed in deployment/conductor-agentcore/), as opposed to /ask which
// runs the Conductor in-process locally.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  const body = await req.text();
  const upstream = await fetch(`${AGENT_SERVICE_URL}/ask-cloud`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body,
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(`AgentCore proxy error: ${upstream.status}`, {
      status: 502,
    });
  }

  const { readable, writable } = new TransformStream();
  upstream.body.pipeTo(writable).catch(() => {});

  return new Response(readable, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
