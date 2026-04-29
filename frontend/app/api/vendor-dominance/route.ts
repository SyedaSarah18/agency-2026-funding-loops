export async function GET(req: Request) {
  const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8000'
  const { searchParams } = new URL(req.url)
  const limit = searchParams.get('limit') ?? '12'
  try {
    const upstream = await fetch(`${backendUrl}/dashboard/vendor-dominance?limit=${limit}`, { cache: 'no-store' })
    const text = await upstream.text()
    try {
      return Response.json(JSON.parse(text), { status: upstream.status })
    } catch {
      return Response.json({ error: 'Backend returned non-JSON', detail: text.slice(0, 200) }, { status: 502 })
    }
  } catch (err) {
    return Response.json({ error: 'Backend unreachable', detail: String(err) }, { status: 503 })
  }
}
