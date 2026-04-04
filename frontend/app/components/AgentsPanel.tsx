'use client'

import { useEffect, useState, useCallback, useRef } from 'react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface AgentStatus {
  agent: string
  status: string
  last_run?: string
  notes?: string
}

interface ActivityEntry {
  id: number
  agent_name: string
  action_type: string
  summary?: string
  timestamp: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  message: string
  timestamp?: string
}

// ── Constants ────────────────────────────────────────────────────────────────

const AGENT_META: Record<string, { emoji: string; title: string; color: string }> = {
  orchestrator:        { emoji: '🎯', title: 'Orchestrator (COO)',        color: 'text-violet-400 border-violet-500/30 bg-violet-500/5' },
  marketing:           { emoji: '📣', title: 'Marketing Director',        color: 'text-pink-400 border-pink-500/30 bg-pink-500/5' },
  market_intelligence: { emoji: '🔍', title: 'Chief Analyst',             color: 'text-blue-400 border-blue-500/30 bg-blue-500/5' },
  customer_success:    { emoji: '💬', title: 'Customer Success',          color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/5' },
  analytics:           { emoji: '📊', title: 'Analytics (Data Analyst)',  color: 'text-amber-400 border-amber-500/30 bg-amber-500/5' },
}

// ── Sub-components ────────────────────────────────────────────────────────────

function AgentStatusCard({ agent, apiUrl }: { agent: AgentStatus; apiUrl: string }) {
  const meta = AGENT_META[agent.agent] ?? { emoji: '🤖', title: agent.agent, color: 'text-gray-400 border-gray-500/30 bg-gray-500/5' }
  return (
    <div className={`rounded-xl border p-4 flex flex-col gap-1 ${meta.color}`}>
      <div className="flex items-center gap-2">
        <span className="text-xl">{meta.emoji}</span>
        <span className="font-semibold text-white text-sm">{meta.title}</span>
        <span className="ml-auto flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${agent.status === 'active' ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500'}`} />
          <span className="text-xs text-gray-400 capitalize">{agent.status}</span>
        </span>
      </div>
      {agent.notes && <p className="text-xs text-gray-400 mt-1">{agent.notes}</p>}
    </div>
  )
}

function SupportChat({ apiUrl }: { apiUrl: string }) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = useCallback(async () => {
    const msg = input.trim()
    if (!msg || loading) return
    setInput('')
    setLoading(true)
    setMessages(prev => [...prev, { role: 'user', message: msg }])

    // Try SSE streaming endpoint first, fall back to regular POST
    const streamUrl = `${apiUrl}/api/agents/support/chat/stream`
    try {
      const res = await fetch(streamUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(typeof window !== 'undefined' && localStorage.getItem('aip_token')
            ? { Authorization: `Bearer ${localStorage.getItem('aip_token')}` }
            : {}),
        },
        body: JSON.stringify({ session_id: sessionId, message: msg }),
      })

      if (!res.ok || !res.body) throw new Error('stream unavailable')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let assistantMsg = ''
      let streamingIdx = -1

      setMessages(prev => {
        streamingIdx = prev.length
        return [...prev, { role: 'assistant', message: '' }]
      })

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const evt = JSON.parse(line.slice(6))
            if (evt.type === 'session' && evt.session_id) {
              setSessionId(evt.session_id)
            } else if (evt.type === 'token' && evt.content) {
              assistantMsg += evt.content
              const captured = assistantMsg
              setMessages(prev => {
                const updated = [...prev]
                if (streamingIdx >= 0 && updated[streamingIdx]) {
                  updated[streamingIdx] = { role: 'assistant', message: captured }
                }
                return updated
              })
            }
          } catch {}
        }
      }
    } catch {
      // Fallback to regular POST
      try {
        const res = await fetch(`${apiUrl}/api/agents/support/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(typeof window !== 'undefined' && localStorage.getItem('aip_token')
              ? { Authorization: `Bearer ${localStorage.getItem('aip_token')}` }
              : {}),
          },
          body: JSON.stringify({ session_id: sessionId, message: msg }),
        })
        if (res.ok) {
          const data = await res.json()
          setSessionId(data.session_id)
          setMessages(prev => [...prev, { role: 'assistant', message: data.reply }])
        }
      } catch {}
    }
    setLoading(false)
  }, [input, loading, sessionId, apiUrl])

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-3 mb-3 pr-1 max-h-64">
        {messages.length === 0 && (
          <p className="text-xs text-gray-500 italic">Ask anything about AIP — features, signals, getting started…</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`rounded-xl px-3 py-2 text-sm max-w-[85%] ${
              m.role === 'user'
                ? 'bg-[#58a6ff]/20 text-white'
                : 'bg-[#21262d] text-gray-200'
            }`}>
              {m.message}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-xl px-3 py-2 text-sm bg-[#21262d] text-gray-400 animate-pulse">
              Thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask a question…"
          className="flex-1 bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#58a6ff]"
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          className="px-3 py-2 rounded-lg bg-[#58a6ff]/10 border border-[#58a6ff]/30 text-[#58a6ff] text-sm hover:bg-[#58a6ff]/20 transition-colors disabled:opacity-50"
        >
          ↑
        </button>
      </div>
    </div>
  )
}

function AgentQueryPanel({
  title,
  endpoint,
  method = 'GET',
  placeholder,
  buttonLabel,
  apiUrl,
  fieldName,
}: {
  title: string
  endpoint: string
  method?: string
  placeholder?: string
  buttonLabel: string
  apiUrl: string
  fieldName?: string
}) {
  const [result, setResult] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  const run = useCallback(async () => {
    setLoading(true)
    setResult(null)
    try {
      const url = method === 'GET' ? `${apiUrl}${endpoint}` : `${apiUrl}${endpoint}`
      const opts: RequestInit = { method }
      if (method === 'POST' && fieldName) {
        opts.headers = { 'Content-Type': 'application/json' }
        opts.body = JSON.stringify({ [fieldName]: input })
      }
      const res = await fetch(url, opts)
      if (res.ok) {
        const data = await res.json()
        const text =
          data.reply ?? data.insight ?? data.analysis ?? data.content ?? data.guide ??
          (typeof data === 'string' ? data : JSON.stringify(data, null, 2))
        setResult(text)
      } else {
        setResult(`Error ${res.status}`)
      }
    } catch (e: unknown) {
      setResult(`Error: ${e instanceof Error ? e.message : 'Unknown error'}`)
    }
    setLoading(false)
  }, [apiUrl, endpoint, method, fieldName, input])

  return (
    <div>
      <p className="text-xs font-semibold text-gray-400 mb-2">{title}</p>
      {fieldName && (
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={placeholder}
          className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 mb-2 focus:outline-none focus:border-[#58a6ff]"
        />
      )}
      <button
        onClick={run}
        disabled={loading || (!!fieldName && !input.trim())}
        className="px-3 py-1.5 text-xs rounded-lg bg-[#58a6ff]/10 border border-[#58a6ff]/30 text-[#58a6ff] hover:bg-[#58a6ff]/20 transition-colors disabled:opacity-50 mb-3"
      >
        {loading ? '⟳ Loading…' : buttonLabel}
      </button>
      {result && (
        <div className="bg-[#0d1117] border border-[#30363d] rounded-lg p-3 text-xs text-gray-300 whitespace-pre-wrap max-h-48 overflow-y-auto">
          {result}
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AgentsPanel({ apiUrl }: { apiUrl: string }) {
  const [statuses, setStatuses] = useState<AgentStatus[]>([])
  const [activity, setActivity] = useState<ActivityEntry[]>([])
  const [activeTab, setActiveTab] = useState<'overview' | 'orchestrator' | 'marketing' | 'intel' | 'support' | 'analytics'>('overview')

  const loadStatus = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/api/agents/status`)
      if (res.ok) setStatuses(await res.json())
    } catch {}
  }, [apiUrl])

  const loadActivity = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/api/agents/activity?limit=20`)
      if (res.ok) setActivity(await res.json())
    } catch {}
  }, [apiUrl])

  useEffect(() => {
    loadStatus()
    loadActivity()
    const interval = setInterval(() => { loadStatus(); loadActivity() }, 30000)
    return () => clearInterval(interval)
  }, [loadStatus, loadActivity])

  const tabs = [
    { id: 'overview',      label: '🗂 Overview' },
    { id: 'orchestrator',  label: '🎯 COO' },
    { id: 'marketing',     label: '📣 Marketing' },
    { id: 'intel',         label: '🔍 Analyst' },
    { id: 'support',       label: '💬 Support' },
    { id: 'analytics',     label: '📊 Analytics' },
  ] as const

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <h2 className="font-bold text-white mb-4 flex items-center gap-2">
        <span>🤖</span> AI Agent Team
        <span className="ml-auto text-xs text-gray-500">{statuses.length}/5 active</span>
      </h2>

      {/* Tab bar */}
      <div className="flex gap-1 mb-4 overflow-x-auto pb-1">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 text-xs rounded-lg border whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? 'border-[#58a6ff] bg-[#58a6ff]/10 text-[#58a6ff]'
                : 'border-[#30363d] text-gray-400 hover:border-[#58a6ff]/50 hover:text-gray-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Overview */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {statuses.map(s => (
              <AgentStatusCard key={s.agent} agent={s} apiUrl={apiUrl} />
            ))}
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Recent Activity
            </p>
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {activity.length === 0 && (
                <p className="text-xs text-gray-600 italic">No activity yet — agents run on schedule.</p>
              )}
              {activity.map(a => (
                <div key={a.id} className="flex items-start gap-2 text-xs text-gray-400 py-1 border-b border-[#21262d]">
                  <span>{AGENT_META[a.agent_name]?.emoji ?? '🤖'}</span>
                  <span className="font-medium text-gray-300 capitalize">{a.agent_name.replace('_', ' ')}</span>
                  <span className="text-gray-600">·</span>
                  <span>{a.action_type}</span>
                  {a.summary && <span className="text-gray-500 truncate flex-1">{a.summary}</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Orchestrator */}
      {activeTab === 'orchestrator' && (
        <div className="space-y-4">
          <AgentQueryPanel
            title="Daily Admin Briefing"
            endpoint="/api/agents/orchestrator/briefing/generate"
            method="POST"
            buttonLabel="Generate Briefing"
            apiUrl={apiUrl}
          />
          <AgentQueryPanel
            title="Ask the COO"
            endpoint="/api/agents/orchestrator/query"
            method="POST"
            placeholder="e.g. What's the platform's current risk level?"
            buttonLabel="Ask"
            apiUrl={apiUrl}
            fieldName="query"
          />
        </div>
      )}

      {/* Marketing */}
      {activeTab === 'marketing' && (
        <div className="space-y-4">
          <AgentQueryPanel
            title="Generate Content (Teaser + Lead Nurture)"
            endpoint="/api/agents/marketing/generate"
            method="POST"
            buttonLabel="Generate Content"
            apiUrl={apiUrl}
          />
          <AgentQueryPanel
            title="Lead Insight"
            endpoint="/api/agents/marketing/lead-insight"
            method="POST"
            placeholder="e.g. Crypto day trader, saw our ad on LinkedIn"
            buttonLabel="Generate Insight"
            apiUrl={apiUrl}
            fieldName="lead_context"
          />
        </div>
      )}

      {/* Market Intelligence */}
      {activeTab === 'intel' && (
        <div className="space-y-4">
          <AgentQueryPanel
            title="Generate Narrative Report"
            endpoint="/api/agents/market-intel/narrative/generate"
            method="POST"
            buttonLabel="Generate Narrative"
            apiUrl={apiUrl}
          />
          <AgentQueryPanel
            title="Asset Deep-Dive"
            endpoint="/api/agents/market-intel/deep-dive"
            method="POST"
            placeholder="e.g. BTC, Gold, ETH"
            buttonLabel="Deep Dive"
            apiUrl={apiUrl}
            fieldName="symbol"
          />
        </div>
      )}

      {/* Customer Success */}
      {activeTab === 'support' && (
        <div className="h-80">
          <SupportChat apiUrl={apiUrl} />
        </div>
      )}

      {/* Analytics */}
      {activeTab === 'analytics' && (
        <div className="space-y-4">
          <AgentQueryPanel
            title="Generate KPI Report"
            endpoint="/api/agents/analytics/kpi/generate"
            method="POST"
            buttonLabel="Generate KPI Report"
            apiUrl={apiUrl}
          />
          <AgentQueryPanel
            title="Latest KPI Report"
            endpoint="/api/agents/analytics/kpi"
            method="GET"
            buttonLabel="Load KPI Report"
            apiUrl={apiUrl}
          />
        </div>
      )}
    </div>
  )
}
