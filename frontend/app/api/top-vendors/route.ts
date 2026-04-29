import { NextRequest } from 'next/server'

export async function GET(request: NextRequest) {
  const limit = request.nextUrl.searchParams.get('limit') ?? '10'
  const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8000'
  try {
    const upstream = await fetch(`${backendUrl}/dashboard/top-vendors?limit=${limit}`)
    const data = await upstream.json()
    return Response.json(data, { status: upstream.status })
  } catch {
    return Response.json({ error: 'Backend unreachable' }, { status: 503 })
  }
}
