import { collectStream } from '@/lib/api'

function sseBody(chunks: Array<{ text?: string; error?: string }>) {
  const lines = chunks
    .map((c) => `data: ${JSON.stringify(c)}\n\n`)
    .join('')
  return new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(lines))
      controller.close()
    },
  })
}

global.fetch = jest.fn()

describe('collectStream', () => {
  it('concatenates text tokens into a single string', async () => {
    ;(fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      body: sseBody([{ text: 'hello ' }, { text: 'world' }]),
    })
    const result = await collectStream('test query')
    expect(result).toBe('hello world')
  })

  it('throws when the stream contains an error payload', async () => {
    ;(fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      body: sseBody([{ error: 'backend exploded' }]),
    })
    await expect(collectStream('bad query')).rejects.toThrow('backend exploded')
  })
})

describe('fetchSpendByYear', () => {
  it('returns parsed spend-by-year array', async () => {
    ;(fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => [
        { year: 2021, total_spend: 1000000 },
        { year: 2022, total_spend: 2000000 },
      ],
    })
    const { fetchSpendByYear } = await import('@/lib/api')
    const result = await fetchSpendByYear()
    expect(result).toEqual([
      { year: 2021, total_spend: 1000000 },
      { year: 2022, total_spend: 2000000 },
    ])
    expect(fetch).toHaveBeenCalledWith('/api/spend-by-year')
  })

  it('throws on non-ok response', async () => {
    ;(fetch as jest.Mock).mockResolvedValueOnce({ ok: false, status: 503 })
    const { fetchSpendByYear } = await import('@/lib/api')
    await expect(fetchSpendByYear()).rejects.toThrow('HTTP 503')
  })
})
