'use client'

import { useEffect, useState, useCallback } from 'react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface ScenarioCase {
  label: string
  probability?: number
  thesis: string
  price_target?: string
  catalysts: string[]
  risks: string[]
}

interface ResearchNote {
  id?: number
  asset: string
  note_type: string
  time_horizon?: string
  market_regime?: string
  thesis: string
  confidence: number
  key_drivers: string[]
  confirming_evidence: string[]
  contradictory_evidence: string[]
  key_risks: string[]
  catalysts: string[]
  invalidation_conditions: string[]
  scenario_analysis: ScenarioCase[]
  summary: string
  timestamp?: string
}

interface MarketRegime {
  id?: number
  label: string
  rationale: string
  contributing_factors: string[]
  confidence: number
  timestamp?: string
}

interface CatalystEvent {
  id?: number
  title: string
  event_type: string
  asset_scope: string[]
  importance: string
  expected_impact?: string
  status: string
  notes?: string
  timestamp?: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function authHeaders(): HeadersInit {
  if (typeof window === 'undefined') return {}
  const token = localStorage.getItem('aip_token')
  return token
    ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' }
}

const REGIME_META: Record<string, { color: string; badge: string }> = {
  risk_on:             { color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10', badge: '🟢' },
  risk_off:            { color: 'text-red-400 border-red-500/30 bg-red-500/10',             badge: '🔴' },
  inflationary:        { color: 'text-orange-400 border-orange-500/30 bg-orange-500/10',    badge: '🔥' },
  disinflationary:     { color: 'text-sky-400 border-sky-500/30 bg-sky-500/10',             badge: '❄️' },
  dollar_strength:     { color: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10',    badge: '💵' },
  dollar_weakness:     { color: 'text-purple-400 border-purple-500/30 bg-purple-500/10',    badge: '📉' },
  volatility_stress:   { color: 'text-red-400 border-red-500/30 bg-red-500/10',             badge: '⚡' },
  liquidity_supportive:{ color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10', badge: '💧' },
  mixed_transition:    { color: 'text-gray-400 border-gray-500/30 bg-gray-500/10',          badge: '〰️' },
}

const IMPORTANCE_COLOR: Record<string, string> = {
  high:   'text-red-400 bg-red-500/10 border-red-500/30',
  medium: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  low:    'text-gray-400 bg-gray-500/10 border-gray-500/30',
}

const SCENARIO_COLOR: Record<string, string> = {
  bull: 'border-emerald-500/40 bg-emerald-500/5',
  base: 'border-blue-500/40 bg-blue-500/5',
  bear: 'border-red-500/40 bg-red-500/5',
}

function confidenceColor(c: number): string {
  if (c >= 0.7) return 'text-emerald-400'
  if (c >= 0.5) return 'text-yellow-400'
  return 'text-red-400'
}

function RegimeBadge({ regime }: { regime: MarketRegime | null }) {
  if (!regime) return null
  const meta = REGIME_META[regime.label] ?? REGIME_META.mixed_transition
  return (
    <div className={`rounded-lg border px-3 py-2 ${meta.color} text-sm`}>
      <div className="flex items-center gap-2 mb-1">
        <span>{meta.badge}</span>
        <span className="font-semibold uppercase tracking-wide text-xs">{regime.label.replace(/_/g, ' ')}</span>
        <span className="ml-auto text-xs opacity-70">{(regime.confidence * 100).toFixed(0)}% confidence</span>
      </div>
      <p className="text-xs opacity-80 leading-relaxed">{regime.rationale}</p>
      {regime.contributing_factors.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {regime.contributing_factors.map((f, i) => (
            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-black/20 opacity-70">{f}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function NoteDisplay({ note }: { note: ResearchNote }) {
  return (
    <div className="space-y-3">
      {/* Thesis */}
      <div className="bg-[#0d1117] border border-[#30363d] rounded-lg p-3">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Thesis</span>
          <span className={`ml-auto text-xs font-mono font-bold ${confidenceColor(note.confidence)}`}>
            {(note.confidence * 100).toFixed(0)}% confidence
          </span>
          {note.time_horizon && (
            <span className="text-xs text-gray-600 border border-[#30363d] px-1.5 py-0.5 rounded">{note.time_horizon}</span>
          )}
        </div>
        <p className="text-sm text-white leading-relaxed">{note.thesis}</p>
      </div>

      {/* Key Drivers + Risks */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {note.key_drivers.length > 0 && (
          <div className="bg-[#0d1117] border border-[#30363d] rounded-lg p-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Key Drivers</p>
            <ul className="space-y-1">
              {note.key_drivers.map((d, i) => (
                <li key={i} className="text-xs text-gray-300 flex gap-2">
                  <span className="text-blue-400 flex-shrink-0">→</span>
                  <span>{d}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {note.key_risks.length > 0 && (
          <div className="bg-[#0d1117] border border-red-500/20 rounded-lg p-3">
            <p className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-2">Key Risks</p>
            <ul className="space-y-1">
              {note.key_risks.map((r, i) => (
                <li key={i} className="text-xs text-gray-300 flex gap-2">
                  <span className="text-red-400 flex-shrink-0">⚠</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Confirming / Contradicting evidence */}
      {(note.confirming_evidence.length > 0 || note.contradictory_evidence.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {note.confirming_evidence.length > 0 && (
            <div className="bg-[#0d1117] border border-emerald-500/20 rounded-lg p-3">
              <p className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-2">Confirming Evidence</p>
              <ul className="space-y-1">
                {note.confirming_evidence.map((e, i) => (
                  <li key={i} className="text-xs text-gray-300 flex gap-2">
                    <span className="text-emerald-400">✓</span><span>{e}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {note.contradictory_evidence.length > 0 && (
            <div className="bg-[#0d1117] border border-orange-500/20 rounded-lg p-3">
              <p className="text-xs font-semibold text-orange-400 uppercase tracking-wider mb-2">Contradictory Evidence</p>
              <ul className="space-y-1">
                {note.contradictory_evidence.map((e, i) => (
                  <li key={i} className="text-xs text-gray-300 flex gap-2">
                    <span className="text-orange-400">✗</span><span>{e}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Invalidation conditions */}
      {note.invalidation_conditions.length > 0 && (
        <div className="bg-[#0d1117] border border-yellow-500/20 rounded-lg p-3">
          <p className="text-xs font-semibold text-yellow-400 uppercase tracking-wider mb-2">Invalidation Conditions</p>
          <div className="flex flex-wrap gap-2">
            {note.invalidation_conditions.map((c, i) => (
              <span key={i} className="text-xs text-yellow-300 bg-yellow-500/10 border border-yellow-500/20 px-2 py-0.5 rounded">{c}</span>
            ))}
          </div>
        </div>
      )}

      {/* Scenario Analysis */}
      {note.scenario_analysis.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Scenario Analysis</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {note.scenario_analysis.map((s, i) => (
              <div key={i} className={`rounded-lg border p-3 ${SCENARIO_COLOR[s.label] ?? 'border-[#30363d]'}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold uppercase tracking-wide text-gray-300">{s.label}</span>
                  {s.probability != null && (
                    <span className="text-xs text-gray-500">{(s.probability * 100).toFixed(0)}%</span>
                  )}
                </div>
                <p className="text-xs text-gray-300 leading-relaxed">{s.thesis}</p>
                {s.price_target && (
                  <p className="text-xs text-gray-500 mt-1">Target: {s.price_target}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Summary */}
      {note.summary && (
        <div className="bg-[#0d1117] border border-[#58a6ff]/20 rounded-lg p-3">
          <p className="text-xs font-semibold text-[#58a6ff] uppercase tracking-wider mb-1">Summary</p>
          <p className="text-xs text-gray-300 leading-relaxed">{note.summary}</p>
        </div>
      )}
    </div>
  )
}

function CatalystList({ catalysts }: { catalysts: CatalystEvent[] }) {
  if (catalysts.length === 0) return (
    <p className="text-xs text-gray-600 italic">No catalysts on record. Generate a catalyst memo to populate.</p>
  )
  return (
    <div className="space-y-2">
      {catalysts.map((c, i) => (
        <div key={c.id ?? i} className="flex items-start gap-3 bg-[#0d1117] border border-[#30363d] rounded-lg p-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <span className="text-xs font-semibold text-white truncate">{c.title}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded border flex-shrink-0 ${IMPORTANCE_COLOR[c.importance] ?? IMPORTANCE_COLOR.low}`}>
                {c.importance.toUpperCase()}
              </span>
              <span className="text-[10px] text-gray-600 flex-shrink-0 border border-[#30363d] px-1.5 py-0.5 rounded">{c.event_type.replace(/_/g, ' ')}</span>
            </div>
            {c.expected_impact && (
              <p className="text-xs text-gray-400 leading-relaxed">{c.expected_impact}</p>
            )}
            {c.asset_scope.length > 0 && (
              <div className="flex gap-1 mt-1">
                {c.asset_scope.map((a, j) => (
                  <span key={j} className="text-[10px] text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded">{a}</span>
                ))}
              </div>
            )}
          </div>
          <span className={`text-[10px] flex-shrink-0 px-1.5 py-0.5 rounded border ${c.status === 'active' ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' : 'text-gray-500 border-gray-700'}`}>
            {c.status}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

const GENERATE_DELAY_MS = 4000

export default function ResearchPanel({ apiUrl }: { apiUrl: string }) {
  const [note, setNote] = useState<ResearchNote | null>(null)
  const [regime, setRegime] = useState<MarketRegime | null>(null)
  const [catalysts, setCatalysts] = useState<CatalystEvent[]>([])
  const [activeTab, setActiveTab] = useState<'note' | 'regime' | 'catalysts'>('note')
  const [generating, setGenerating] = useState(false)
  const [deepDiveSymbol, setDeepDiveSymbol] = useState('')
  const [deepDiveResult, setDeepDiveResult] = useState<ResearchNote | null>(null)
  const [deepDiveLoading, setDeepDiveLoading] = useState(false)
  const [loading, setLoading] = useState(true)

  const loadNote = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/api/agents/research/latest`)
      if (res.ok) {
        const data = await res.json()
        if (data) setNote(data)
      }
    } catch {}
  }, [apiUrl])

  const loadRegime = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/api/agents/research/regime`)
      if (res.ok) setRegime(await res.json())
    } catch {}
  }, [apiUrl])

  const loadCatalysts = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/api/agents/research/catalysts?limit=10`)
      if (res.ok) setCatalysts(await res.json())
    } catch {}
  }, [apiUrl])

  useEffect(() => {
    Promise.all([loadNote(), loadRegime(), loadCatalysts()]).finally(() => setLoading(false))
    const interval = setInterval(() => { loadNote(); loadRegime(); loadCatalysts() }, 60000)
    return () => clearInterval(interval)
  }, [loadNote, loadRegime, loadCatalysts])

  const handleGenerate = useCallback(async () => {
    setGenerating(true)
    try {
      await fetch(`${apiUrl}/api/agents/research/generate`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ note_type: 'daily_note' }),
      })
      setTimeout(async () => {
        await Promise.all([loadNote(), loadRegime()])
        setGenerating(false)
      }, GENERATE_DELAY_MS)
    } catch {
      setGenerating(false)
    }
  }, [apiUrl, loadNote, loadRegime])

  const handleGenerateCatalysts = useCallback(async () => {
    setGenerating(true)
    try {
      await fetch(`${apiUrl}/api/agents/research/catalysts/generate`, {
        method: 'POST',
        headers: authHeaders(),
      })
      setTimeout(async () => {
        await loadCatalysts()
        setGenerating(false)
      }, GENERATE_DELAY_MS)
    } catch {
      setGenerating(false)
    }
  }, [apiUrl, loadCatalysts])

  const handleDeepDive = useCallback(async () => {
    if (!deepDiveSymbol.trim()) return
    setDeepDiveLoading(true)
    setDeepDiveResult(null)
    try {
      const res = await fetch(`${apiUrl}/api/agents/research/deep-dive`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ symbol: deepDiveSymbol.trim().toUpperCase() }),
      })
      if (res.ok) setDeepDiveResult(await res.json())
    } catch {}
    setDeepDiveLoading(false)
  }, [apiUrl, deepDiveSymbol])

  const tabs = [
    { id: 'note' as const,      label: '📋 Research Note' },
    { id: 'regime' as const,    label: '🌐 Regime' },
    { id: 'catalysts' as const, label: '⚡ Catalysts' },
  ]

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="font-bold text-white flex items-center gap-2">
          <span>🔬</span> Research Analyst
          {regime && (
            <span className={`text-xs px-2 py-0.5 rounded border ml-1 ${REGIME_META[regime.label]?.color ?? 'text-gray-400 border-gray-700'}`}>
              {regime.label.replace(/_/g, ' ')}
            </span>
          )}
        </h2>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-3 py-1.5 text-xs rounded-lg bg-[#58a6ff]/10 border border-[#58a6ff]/30 text-[#58a6ff] hover:bg-[#58a6ff]/20 transition-colors disabled:opacity-50"
        >
          {generating ? '⟳ Generating…' : '✦ Generate Note'}
        </button>
      </div>

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

      {loading ? (
        <div className="flex items-center justify-center h-32 text-gray-500 text-sm">
          <div className="animate-spin w-5 h-5 border-2 border-[#58a6ff] border-t-transparent rounded-full mr-2" />
          Loading research data…
        </div>
      ) : (
        <>
          {/* Research Note tab */}
          {activeTab === 'note' && (
            <div className="space-y-4">
              {note ? (
                <>
                  <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
                    <span className="uppercase tracking-wider">{note.note_type.replace(/_/g, ' ')}</span>
                    <span>·</span>
                    <span>{note.asset}</span>
                    {note.timestamp && (
                      <>
                        <span>·</span>
                        <span>{new Date(note.timestamp).toLocaleString()}</span>
                      </>
                    )}
                  </div>
                  <NoteDisplay note={note} />
                </>
              ) : (
                <div className="text-center py-8 text-gray-500 text-sm">
                  <p>No research note generated yet.</p>
                  <p className="text-xs mt-1 text-gray-600">Click &quot;Generate Note&quot; to produce the first institutional research note.</p>
                </div>
              )}

              {/* Deep dive section */}
              <div className="border-t border-[#30363d] pt-4">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Asset Deep Dive</p>
                <div className="flex gap-2 mb-3">
                  <input
                    value={deepDiveSymbol}
                    onChange={e => setDeepDiveSymbol(e.target.value.toUpperCase())}
                    placeholder="e.g. BTC, Gold, ETH"
                    className="flex-1 bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#58a6ff]"
                    onKeyDown={e => e.key === 'Enter' && handleDeepDive()}
                  />
                  <button
                    onClick={handleDeepDive}
                    disabled={deepDiveLoading || !deepDiveSymbol.trim()}
                    className="px-3 py-2 text-xs rounded-lg bg-[#58a6ff]/10 border border-[#58a6ff]/30 text-[#58a6ff] hover:bg-[#58a6ff]/20 disabled:opacity-50 transition-colors"
                  >
                    {deepDiveLoading ? '⟳' : 'Dive'}
                  </button>
                </div>
                {deepDiveResult && (
                  <div>
                    <p className="text-xs text-gray-500 mb-2">
                      Deep Research: <span className="text-white font-semibold">{deepDiveResult.asset}</span>
                    </p>
                    <NoteDisplay note={deepDiveResult} />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Regime tab */}
          {activeTab === 'regime' && (
            <div className="space-y-3">
              <RegimeBadge regime={regime} />
              {!regime && (
                <div className="text-center py-8 text-gray-500 text-sm">
                  No regime data. Generate a research note to classify the current regime.
                </div>
              )}
            </div>
          )}

          {/* Catalysts tab */}
          {activeTab === 'catalysts' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-500">{catalysts.length} catalyst{catalysts.length !== 1 ? 's' : ''} on watch</span>
                <button
                  onClick={handleGenerateCatalysts}
                  disabled={generating}
                  className="px-3 py-1.5 text-xs rounded-lg bg-[#58a6ff]/10 border border-[#58a6ff]/30 text-[#58a6ff] hover:bg-[#58a6ff]/20 transition-colors disabled:opacity-50"
                >
                  {generating ? '⟳ Generating…' : '⚡ Generate Catalysts'}
                </button>
              </div>
              <CatalystList catalysts={catalysts} />
            </div>
          )}
        </>
      )}

      <p className="text-[10px] text-gray-600 mt-4 border-t border-[#21262d] pt-3">
        For informational and decision-support purposes only. Not financial advice.
      </p>
    </div>
  )
}
