export async function GET() {
  const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8000'
  try {
    const upstream = await fetch(`${backendUrl}/dashboard/concentration-scatter`, { cache: 'no-store' })
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
