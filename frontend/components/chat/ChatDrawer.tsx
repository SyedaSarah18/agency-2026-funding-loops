'use client'

import { useRef, useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import ReactMarkdown from 'react-markdown'
import { Skeleton } from '@/components/ui/skeleton'
import { streamChatEvents } from '@/lib/api'
import { cn } from '@/lib/utils'
import {
  ArrowUp, Sparkles, Compass, Calculator, ShieldCheck,
  CheckCircle2, Loader2, RotateCcw, X, Zap,
} from 'lucide-react'

interface ToolCall {
  id: string
  name: string
  label: string
  question: string
  done: boolean
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  toolCalls?: ToolCall[]
}

interface ChatDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

// ── Pipeline architecture — routed by the Router agent ───────────────────────
//
// The top "Router" card (rendered separately as the coordinator) always runs
// first. Based on the route it picks (pipeline / discovery / investigation /
// validation / narration / out_of_scope), one or more of these specialist
// cards light up in sequence.

const PIPELINE_NODES = [
  {
    name: 'discovery',
    label: 'Discovery',
    sublabel: 'Reframe question · pick scope · choose tools',
    icon: <Compass className="h-3.5 w-3.5" />,
    color: 'hsl(var(--chart-2))',
  },
  {
    name: 'investigation',
    label: 'Investigation',
    sublabel: 'Run deterministic math · gather findings',
    icon: <Calculator className="h-3.5 w-3.5" />,
    color: 'hsl(var(--chart-4))',
  },
  {
    name: 'validator',
    label: 'Validator',
    sublabel: 'Cross-check via second source · enforce gates',
    icon: <ShieldCheck className="h-3.5 w-3.5" />,
    color: 'hsl(var(--chart-1))',
  },
  {
    name: 'narrative',
    label: 'Narrative',
    sublabel: 'Plain-English brief for non-technical decision maker',
    icon: <Sparkles className="h-3.5 w-3.5" />,
    color: 'hsl(var(--chart-5))',
  },
] as const

const SUGGESTIONS = [
  'Find the worst vendor lock-in in Alberta IT spending',
  'Which categories have the highest HHI?',
  'Is the IBM mainframe contract really 100% sole-source?',
  'Show me vendors locked in across both Alberta and federal',
]

// ── Sub-components ────────────────────────────────────────────────────────────

function QuickStart({ onSuggest }: { onSuggest: (s: string) => void }) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
        Quick Start
      </p>
      <div className="flex flex-col gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onSuggest(s)}
            className="text-left text-[11px] text-muted-foreground hover:text-foreground leading-snug px-3 py-2.5 rounded-lg bg-muted/40 hover:bg-muted border border-border/50 hover:border-border transition-all duration-150"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}

type NodeState = 'idle' | 'active' | 'done'

function useElapsedTime(active: boolean): number {
  const [elapsed, setElapsed] = useState(0)
  const startRef = useRef<number | null>(null)
  useEffect(() => {
    if (active) {
      startRef.current = Date.now()
      setElapsed(0)
      const id = setInterval(() => {
        if (startRef.current !== null)
          setElapsed(Math.floor((Date.now() - startRef.current) / 1000))
      }, 1000)
      return () => clearInterval(id)
    }
    startRef.current = null
    return undefined
  }, [active])
  return elapsed
}

function AgentCard({
  icon,
  color,
  label,
  role,
  sublabel,
  state,
  badge,
}: {
  icon: React.ReactNode
  color: string
  label: string
  role: string
  sublabel?: string
  state: NodeState
  badge?: string
}) {
  const elapsed = useElapsedTime(state === 'active')

  return (
    <div
      className={cn(
        'relative rounded-md border overflow-hidden transition-all duration-500',
        state === 'idle' && 'border-border/15 opacity-40',
        state === 'active' && 'border-border/50',
        state === 'done' && 'border-border/35',
      )}
    >
      {/* Left accent bar */}
      <div
        className="absolute left-0 top-0 bottom-0 w-[3px] transition-all duration-500"
        style={{
          backgroundColor:
            state === 'done' ? 'hsl(var(--chart-3))' :
            state === 'active' ? color :
            'transparent',
        }}
      />

      <div className="pl-3.5 pr-2.5 py-2">
        {/* Row 1: role label + status */}
        <div className="flex items-center justify-between mb-1">
          <span
            className="text-[8px] font-bold uppercase tracking-[0.12em] transition-colors duration-300"
            style={{
              color:
                state === 'active' ? color :
                state === 'done' ? 'hsl(var(--chart-3))' :
                'hsl(var(--muted-foreground) / 0.3)',
            }}
          >
            {role}
          </span>
          <div className="flex items-center gap-1">
            {state === 'active' && elapsed > 0 && (
              <span className="text-[9px] font-mono tabular-nums text-muted-foreground/45">
                {elapsed}s
              </span>
            )}
            {state === 'active' && <Loader2 className="h-2.5 w-2.5 text-primary animate-spin" />}
            {state === 'done' && (
              <CheckCircle2 className="h-2.5 w-2.5" style={{ color: 'hsl(var(--chart-3))' }} />
            )}
            {state === 'idle' && <div className="h-1.5 w-1.5 rounded-full bg-border/25" />}
          </div>
        </div>

        {/* Row 2: icon + label + badge */}
        <div className="flex items-center gap-1.5">
          <span
            className="shrink-0 transition-colors duration-300"
            style={{ color: state === 'idle' ? 'hsl(var(--muted-foreground) / 0.3)' : color }}
          >
            {icon}
          </span>
          <span
            className={cn(
              'text-[12px] font-semibold tracking-tight transition-colors duration-300',
              state === 'idle' && 'text-muted-foreground/30',
              state === 'active' && 'text-foreground',
              state === 'done' && 'text-muted-foreground/70',
            )}
          >
            {label}
          </span>
          {badge && state !== 'idle' && (
            <span className="text-[8px] font-medium text-muted-foreground/50 bg-muted border border-border/40 rounded px-1 py-0.5 leading-none">
              {badge}
            </span>
          )}
        </div>

        {/* Row 3: query / sublabel */}
        {sublabel && state !== 'idle' && (
          <p
            className={cn(
              'text-[10px] mt-1.5 pl-[22px] leading-snug break-words line-clamp-3 transition-colors duration-300',
              state === 'active' ? 'text-muted-foreground' : 'text-muted-foreground/40',
            )}
          >
            {sublabel}
          </p>
        )}
      </div>

      {/* Scan line for active state */}
      {state === 'active' && (
        <div className="absolute bottom-0 left-0 right-0 h-[2px] overflow-hidden">
          <div
            className="absolute top-0 bottom-0 w-2/5 pipeline-scan"
            style={{
              background: `linear-gradient(90deg, transparent 0%, ${color} 50%, transparent 100%)`,
            }}
          />
        </div>
      )}
    </div>
  )
}

// ── Pipeline panel ────────────────────────────────────────────────────────────

function PipelinePanel({
  toolCalls,
  streaming,
  empty,
  onSuggest,
}: {
  toolCalls: ToolCall[]
  streaming: boolean
  empty: boolean
  onSuggest: (s: string) => void
}) {
  const hasCalls   = toolCalls.length > 0
  const allDone    = hasCalls && toolCalls.every((t) => t.done)
  const isPlanning = streaming && !hasCalls
  const isWriting  = streaming && hasCalls && allDone

  if (empty || (!streaming && !hasCalls)) {
    return <QuickStart onSuggest={onSuggest} />
  }

  const routerState: NodeState =
    !streaming && allDone ? 'done' : streaming ? 'active' : 'done'

  const doneCount = toolCalls.filter((t) => t.done).length

  return (
    <div className="flex flex-col gap-1.5">
      <style>{`
        @keyframes pipeline-scan {
          from { transform: translateX(-200%); }
          to   { transform: translateX(500%); }
        }
        .pipeline-scan { animation: pipeline-scan 2s linear infinite; }
      `}</style>

      {/* Header */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
            Agents
          </p>
          {hasCalls && (
            <span className="text-[9px] font-mono tabular-nums text-muted-foreground/35">
              {doneCount}/{toolCalls.length}
            </span>
          )}
        </div>
        {streaming && (
          <span className="flex items-center gap-1 text-[9px] font-bold text-primary uppercase tracking-wider">
            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
            Live
          </span>
        )}
        {!streaming && hasCalls && allDone && (
          <span
            className="text-[9px] font-bold uppercase tracking-wider"
            style={{ color: 'hsl(var(--chart-3))' }}
          >
            Complete
          </span>
        )}
      </div>

      {/* Router — classifies the question and routes to specialist(s) */}
      <AgentCard
        icon={<Zap className="h-3.5 w-3.5" />}
        color={routerState === 'done' ? 'hsl(var(--chart-3))' : 'hsl(var(--primary))'}
        label="Router"
        role="coordinator"
        sublabel={
          isPlanning ? 'Classifying question…' :
          isWriting  ? 'Composing response…' :
          undefined
        }
        state={routerState}
      />

      {/* Sub-agent tree */}
      {(hasCalls || isPlanning) && (
        <div className="ml-3 border-l-2 border-border/20 pl-3 flex flex-col gap-1.5 pt-0.5">
          {PIPELINE_NODES.map((node) => {
            const calls = toolCalls.filter((t) => t.name === node.name)
            const isActive = calls.some((t) => !t.done)
            const isDone   = calls.length > 0 && calls.every((t) => t.done)
            const nodeState: NodeState = isActive ? 'active' : isDone ? 'done' : 'idle'

            const activeQuestion = calls.find((t) => !t.done)?.question
            const lastQuestion   = calls[calls.length - 1]?.question
            const questionDisplay = activeQuestion || (isDone ? lastQuestion : undefined)

            return (
              <AgentCard
                key={node.name}
                icon={node.icon}
                color={node.color}
                label={node.label}
                role={'parallel' in node && node.parallel ? 'parallel agent' : 'agent'}
                sublabel={questionDisplay ?? (nodeState !== 'idle' ? node.sublabel : undefined)}
                state={nodeState}
                badge={
                  'parallel' in node && node.parallel && nodeState !== 'idle'
                    ? 'parallel'
                    : calls.length > 1
                      ? `×${calls.length}`
                      : undefined
                }
              />
            )
          })}
        </div>
      )}

      {/* Synthesizing */}
      {isWriting && (
        <AgentCard
          icon={<Sparkles className="h-3.5 w-3.5" />}
          color="hsl(var(--primary))"
          label="Synthesizing"
          role="writer"
          sublabel="Composing response…"
          state="active"
        />
      )}
    </div>
  )
}

// ── Message rendering ─────────────────────────────────────────────────────────

function AssistantMessage({ content, streaming }: { content: string; streaming?: boolean }) {
  if (!content && streaming) {
    return (
      <div className="flex flex-col gap-2">
        <Skeleton className="h-3.5 w-4/5" />
        <Skeleton className="h-3.5 w-3/5" />
        <Skeleton className="h-3.5 w-2/3" />
      </div>
    )
  }
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none text-foreground [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_p]:leading-relaxed [&_ul]:my-1.5 [&_ol]:my-1.5 [&_li]:my-0.5 [&_strong]:font-semibold [&_strong]:text-foreground [&_code]:bg-muted [&_code]:rounded [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-[11px] [&_code]:font-mono [&_pre]:bg-muted [&_pre]:rounded-lg [&_pre]:p-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_h1]:text-sm [&_h2]:text-sm [&_h3]:text-[13px] [&_h1]:font-bold [&_h2]:font-bold [&_h3]:font-semibold [&_blockquote]:border-l-2 [&_blockquote]:border-primary/40 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground [&_hr]:border-border">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function ChatDrawer({ open, onOpenChange }: ChatDrawerProps) {
  const [mounted, setMounted]   = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const bottomRef               = useRef<HTMLDivElement>(null)
  const inputRef                = useRef<HTMLInputElement>(null)

  useEffect(() => setMounted(true), [])

  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50)
  }, [open])

  useEffect(() => {
    if (!open) return
    const handle = (e: KeyboardEvent) => { if (e.key === 'Escape') onOpenChange(false) }
    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [open, onOpenChange])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const query = input.trim()
    if (!query || loading) return

    setInput('')
    setLoading(true)
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: query },
      { role: 'assistant', content: '', streaming: true, toolCalls: [] },
    ])

    try {
      let assembled = ''
      for await (const event of streamChatEvents(query)) {
        if (event.type === 'text') {
          assembled += event.text
          setMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: assembled,
              streaming: true,
            }
            return updated
          })
        } else if (event.type === 'tool') {
          setMessages((prev) => {
            const updated = [...prev]
            const last = { ...updated[updated.length - 1] }
            last.toolCalls = [
              ...(last.toolCalls ?? []),
              {
                id: `${event.name}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                name: event.name,
                label: event.label,
                question: event.question,
                done: false,
              },
            ]
            updated[updated.length - 1] = last
            return updated
          })
        } else if (event.type === 'tool_done') {
          setMessages((prev) => {
            const updated = [...prev]
            const last = { ...updated[updated.length - 1] }
            // FIFO: mark only the first undone entry with this name
            let marked = false
            last.toolCalls = (last.toolCalls ?? []).map((t) => {
              if (!marked && t.name === event.name && !t.done) {
                marked = true
                return { ...t, done: true }
              }
              return t
            })
            updated[updated.length - 1] = last
            return updated
          })
        }
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
      }
      setMessages((prev) => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        updated[updated.length - 1] = {
          ...last,
          content: assembled,
          streaming: false,
          // Flush any tool calls that never received a tool_done event
          toolCalls: (last.toolCalls ?? []).map((t) => ({ ...t, done: true })),
        }
        return updated
      })
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Something went wrong'
      setMessages((prev) => {
        const updated = [...prev]
        const last = updated[updated.length - 1]
        updated[updated.length - 1] = {
          ...last,
          content: `**Error:** ${msg}`,
          streaming: false,
          toolCalls: (last.toolCalls ?? []).map((t) => ({ ...t, done: true })),
        }
        return updated
      })
    } finally {
      setLoading(false)
    }
  }

  if (!mounted || !open) return null

  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')
  const pipelineTools = lastAssistant?.toolCalls ?? []
  const isStreaming   = lastAssistant?.streaming ?? false

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-8"
      role="dialog"
      aria-modal="true"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/75 backdrop-blur-md"
        onClick={() => onOpenChange(false)}
      />

      {/* Modal */}
      <div
        className="relative z-10 w-full max-w-3xl flex flex-col bg-card border border-border rounded-2xl shadow-2xl overflow-hidden"
        style={{ height: 'min(640px, 90vh)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border shrink-0">
          <div className="flex items-center gap-3">
            <div className="h-7 w-7 rounded-lg bg-primary/15 flex items-center justify-center shrink-0">
              <Sparkles className="h-4 w-4 text-primary" />
            </div>
            <div className="leading-tight">
              <h2
                className="text-[13px] font-bold tracking-tight text-foreground leading-none"
                style={{ fontFamily: 'var(--font-syne)' }}
              >
                Ask AI
              </h2>
              <p className="text-[10px] text-muted-foreground uppercase tracking-widest mt-0.5">
                Vendor concentration analysis
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {messages.length > 0 && (
              <button
                onClick={() => { setMessages([]); setInput('') }}
                disabled={loading}
                title="Clear conversation"
                className="h-7 w-7 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              onClick={() => onOpenChange(false)}
              className="h-7 w-7 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* ── Body ── */}
        <div className="flex flex-1 min-h-0">

          {/* Left: conversation */}
          <div className="flex-1 min-w-0 overflow-y-auto px-5 py-5 space-y-5">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
                <div className="h-12 w-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                  <Sparkles className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <p
                    className="text-sm font-semibold text-foreground"
                    style={{ fontFamily: 'var(--font-syne)' }}
                  >
                    Ask about Alberta government contracts
                  </p>
                  <p className="text-xs text-muted-foreground mt-1 max-w-[280px]">
                    Vendor concentration, HHI trends,
                    <br />
                    supplier dominance, and procurement patterns.
                  </p>
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}
              >
                {msg.role === 'user' ? (
                  <div className="max-w-[80%] rounded-2xl rounded-br-sm px-4 py-2.5 text-sm leading-relaxed bg-primary text-primary-foreground">
                    {msg.content}
                  </div>
                ) : (
                  <div className="max-w-[92%] min-w-[200px] rounded-2xl rounded-bl-sm px-4 py-3 bg-muted text-foreground">
                    <AssistantMessage content={msg.content} streaming={msg.streaming} />
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Right: pipeline panel */}
          <div className="w-[250px] shrink-0 border-l border-border bg-card/50 overflow-y-auto px-4 py-5">
            <PipelinePanel
              toolCalls={pipelineTools}
              streaming={isStreaming}
              empty={messages.length === 0}
              onSuggest={(s) => { setInput(s); inputRef.current?.focus() }}
            />
          </div>
        </div>

        {/* ── Input ── */}
        <form
          onSubmit={handleSubmit}
          className="px-4 py-3.5 border-t border-border shrink-0 bg-card"
        >
          <div className="flex items-center gap-2 bg-muted rounded-xl px-3.5 py-2.5 focus-within:ring-2 focus-within:ring-primary/30 transition-all">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about vendor concentration…"
              disabled={loading}
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="h-7 w-7 rounded-lg bg-primary flex items-center justify-center shrink-0 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary/90 transition-colors"
            >
              <ArrowUp className="h-3.5 w-3.5 text-primary-foreground" />
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  )
}
