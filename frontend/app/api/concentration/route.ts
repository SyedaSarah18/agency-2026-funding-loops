import { NextRequest } from 'next/server'

export async function GET(request: NextRequest) {
  const limit = request.nextUrl.searchParams.get('limit') ?? '5'
  const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8000'
  try {
    const upstream = await fetch(`${backendUrl}/dashboard/concentration?limit=${limit}`, {
      cache: 'no-store',
    })
    const text = await upstream.text()
    try {
      const data = JSON.parse(text)
      return Response.json(data, { status: upstream.status })
    } catch {
      console.error('[concentration] non-JSON response from backend:', text.slice(0, 500))
      return Response.json({ error: 'Backend returned non-JSON', detail: text.slice(0, 200) }, { status: 502 })
    }
  } catch (err) {
    console.error('[concentration] fetch failed:', err)
    return Response.json({ error: 'Backend unreachable', detail: String(err) }, { status: 503 })
  }
}
