export async function GET() {
  const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8000'
  try {
    const upstream = await fetch(`${backendUrl}/dashboard/spend-by-year`, {
      cache: 'no-store',
    })
    const text = await upstream.text()
    try {
      const data = JSON.parse(text)
      return Response.json(data, { status: upstream.status })
    } catch {
      console.error('[spend-by-year] non-JSON from backend:', text.slice(0, 500))
      return Response.json(
        { error: 'Backend returned non-JSON', detail: text.slice(0, 200) },
        { status: 502 }
      )
    }
  } catch (err) {
    console.error('[spend-by-year] fetch failed:', err)
    return Response.json({ error: 'Backend unreachable', detail: String(err) }, { status: 503 })
  }
}
