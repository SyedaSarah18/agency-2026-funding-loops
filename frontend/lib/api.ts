export type ToolResult =
  | {
      kind: 'discovery_plan'
      data: {
        scope?: string
        candidates?: Array<{ category: string; top_vendor: string; cat_total: number; top1_share_pct: number; call_id?: string }>
        next_actions?: string[]
        sub_theme?: string
        honest_caveats?: string[]
      }
      call_id?: string
    }
  | {
      kind: 'findings'
      data: {
        headline?: string
        metrics?: Array<{ name: string; value: number | string; call_id?: string; interpretation?: string }>
        supporting_facts?: Array<{ fact: string; call_id?: string }>
        interesting_moments?: string[]
      }
      call_id?: string
    }
  | {
      kind: 'verdict'
      data: {
        verdict?: 'MATCH' | 'PARTIAL' | 'DIVERGE'
        confidence?: 'high' | 'medium' | 'low'
        checks_run?: Array<{ what: string; value_a: number; value_b: number; verdict: string; call_id?: string }>
        cross_dataset?: { appears_in?: string[]; canonical_name?: string; call_id?: string }
        ruled_out?: string[]
        honest_caveats?: string[]
      }
      call_id?: string
    }
  | {
      kind:
        | 'hhi'
        | 'cr_n'
        | 'gini'
        | 'sole_source_rate'
        | 'incumbency_streak'
        | 'vendor_footprint'
        | 'competition_count'
        | 'cross_dataset_lookup'
        | 'divergence_check'
        | 'top_concentrated_categories'
      data: {
        value: unknown
        inputs?: Record<string, unknown>
        trace_preview?: Array<Record<string, unknown>>
        rows_preview?: Array<Record<string, unknown>>
        references?: string[]
      }
      call_id?: string
    }
  | {
      kind: 'final_brief'
      data: {
        headline?: string
        summary?: string
        metrics_table?: Array<{ metric: string; value: string; interpretation?: string; call_id?: string | null }>
        sub_theme?: 'Efficiency' | 'Integrity' | 'Alignment'
        verdict?: 'MATCH' | 'PARTIAL' | 'DIVERGE'
        confidence?: 'high' | 'medium' | 'low'
        recommendation?: string
        caveats?: string[]
      }
      call_id?: string
    }
  | {
      kind: 'route'
      data: { route: string; reason: string }
      call_id?: string
    }

export type ChatEvent =
  | { type: 'text'; text: string }
  | { type: 'tool'; name: string; label: string; question: string }
  | { type: 'tool_done'; name: string }
  | { type: 'tool_result'; result: ToolResult }

export async function* streamChatEvents(query: string): AsyncGenerator<ChatEvent, void, unknown> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: query }),
  })

  if (!response.ok) {
    const errText = await response.text()
    throw new Error(errText || `HTTP ${response.status}`)
  }

  if (!response.body) throw new Error('No response body from /api/chat')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const json = line.slice(6).trim()
      if (!json) continue
      try {
        const parsed = JSON.parse(json)
        if (parsed.error) throw new Error(parsed.error)
        if (parsed.tool_result) {
          yield { type: 'tool_result', result: { kind: parsed.kind, data: parsed.data, call_id: parsed.call_id } }
        } else if (parsed.text) {
          yield { type: 'text', text: parsed.text }
        } else if (parsed.tool) {
          yield { type: 'tool', name: parsed.tool, label: parsed.label ?? parsed.tool, question: parsed.question ?? '' }
        } else if (parsed.tool_done) {
          yield { type: 'tool_done', name: parsed.tool_done }
        }
      } catch (e) {
        if (e instanceof SyntaxError) continue
        throw e
      }
    }
  }
}

export async function* streamChat(query: string): AsyncGenerator<string, void, unknown> {
  for await (const event of streamChatEvents(query)) {
    if (event.type === 'text') yield event.text
  }
}

export async function collectStream(query: string): Promise<string> {
  let result = ''
  for await (const token of streamChat(query)) {
    result += token
  }
  return result
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

export function fetchMetrics() {
  return getJson<import('./types').DashboardMetrics>('/api/metrics')
}

export function fetchTopVendors(limit = 10) {
  return getJson<Array<{ recipient: string; contract_count: number; total_amount: number }>>(
    `/api/top-vendors?limit=${limit}`
  )
}

export function fetchConcentration(limit = 5) {
  return getJson<import('./types').ConcentrationResult[]>(`/api/concentration?limit=${limit}`)
}

export function fetchSpendByYear() {
  return getJson<import('./types').SpendByYear[]>('/api/spend-by-year')
}

export function fetchConcentrationTrend() {
  return getJson<import('./types').ConcentrationTrendPoint[]>('/api/concentration-trend')
}

export function fetchConcentrationScatter() {
  return getJson<import('./types').ConcentrationScatterPoint[]>('/api/concentration-scatter')
}

export function fetchVendorDominance(limit = 12) {
  return getJson<import('./types').VendorDominancePoint[]>(`/api/vendor-dominance?limit=${limit}`)
}

export function fetchVendorCompetition() {
  return getJson<import('./types').VendorCompetitionPoint[]>('/api/vendor-competition')
}

export function fetchContractDistribution() {
  return getJson<import('./types').ContractDistributionBucket[]>('/api/contract-distribution')
}
