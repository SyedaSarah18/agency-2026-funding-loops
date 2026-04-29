import { NextRequest } from 'next/server'

export async function POST(request: NextRequest) {
  const body = await request.json()
  const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8000'

  const upstream = await fetch(`${backendUrl}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: body.message }),
  })

  if (!upstream.ok) {
    const errorText = await upstream.text()
    return Response.json(
      { error: 'Backend error', details: errorText },
      { status: upstream.status }
    )
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    },
  })
}
