import { NextRequest } from 'next/server'

export async function GET(_request: NextRequest) {
  const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8000'

  try {
    const upstream = await fetch(`${backendUrl}/health`)
    if (!upstream.ok) {
      return Response.json(
        { status: 'unhealthy', code: upstream.status },
        { status: upstream.status }
      )
    }
    const data = await upstream.json()
    return Response.json(data, { status: 200 })
  } catch (error) {
    console.error('[health] Backend unreachable:', error)
    return Response.json({ status: 'unreachable', error: String(error) }, { status: 503 })
  }
}
