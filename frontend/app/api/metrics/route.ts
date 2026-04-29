export async function GET() {
  const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8000'
  try {
    const upstream = await fetch(`${backendUrl}/dashboard/metrics`)
    const data = await upstream.json()
    return Response.json(data, { status: upstream.status })
  } catch {
    return Response.json({ error: 'Backend unreachable' }, { status: 503 })
  }
}
