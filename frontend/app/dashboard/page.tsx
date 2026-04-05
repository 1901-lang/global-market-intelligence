'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import AssetCard from '../components/AssetCard'
import AlertFeed from '../components/AlertFeed'
import AnalyticsPanel from '../components/AnalyticsPanel'
import ConsensusView from '../components/ConsensusView'
import BriefPanel from '../components/BriefPanel'
import SignalBadge from '../components/SignalBadge'
import AgentsPanel from '../components/AgentsPanel'
import WatchlistPanel from '../components/WatchlistPanel'
import MacroHeatmap from '../components/MacroHeatmap'
import CoordinatorChat from '../components/CoordinatorChat'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const REFRESH_DELAY_MS = 3000
const BRIEF_GENERATION_DELAY_MS = 5000
const TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000

function authHeaders(): HeadersInit {
  if (typeof window === 'undefined') return {}
  const token = localStorage.getItem('aip_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function getTokenExpiry(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return typeof payload.exp === 'number' ? payload.exp : null
  } catch {
    return null
  }
}

interface Asset {
  symbol: string
  name: string
  price: number
  change_1h?: number
  change_24h?: number
  volume_24h?: number
  asset_type: string
}

interface Consensus {
  asset: string
  final_signal: string
  confidence: number
  agreement_level: string
  models?: Record<string, { signal: string; confidence: number; reasoning: string[] }>
  dissenting_models?: string[]
}

interface MarketContext {
  usd_index?: number
  bond_yield_10y?: number
  vix?: number
  news_sentiment?: number
  on_chain_activity?: number
}

interface Brief {
  content: string
  key_signals?: { asset: string; signal: string; confidence: number }[]
  risks?: string[]
  date?: string
  timestamp?: string
}

interface FullData {
  assets: Asset[]
  context: MarketContext | null
  signals: unknown[]
  consensus: Consensus[]
  alerts: unknown[]
  model_outputs: unknown[]
}

function getMarketSession() {
  const h = new Date().getUTCHours()
  if (h >= 13 && h < 21) return { label: 'NY Open', color: 'text-emerald-400' }
  if (h >= 7 && h < 16) return { label: 'London', color: 'text-amber-400' }
  if (h >= 0 && h < 8) return { label: 'Asia', color: 'text-blue-400' }
  return { label: 'Off-Hours', color: 'text-gray-500' }
}

function DeltaArrow({ curr, prev }: { curr?: number; prev?: number }) {
  if (curr == null || prev == null) return null
  if (curr > prev) return <span className="text-emerald-400 text-xs ml-0.5">▲</span>
  if (curr < prev) return <span className="text-red-400 text-xs ml-0.5">▼</span>
  return null
}

function TopBar({ context, prevContext, lastUpdated, onRefresh, refreshing, username, onSignOut }: {
  context: MarketContext | null
  prevContext: MarketContext | null
  lastUpdated: Date | null
  onRefresh: () => void
  refreshing: boolean
  username: string | null
  onSignOut: () => void
}) {
  const [showMobileMetrics, setShowMobileMetrics] = useState(false)
  const session = getMarketSession()

  const sentimentLabel = (s?: number) => {
    if (s == null) return '—'
    if (s > 0.1) return '😊 Positive'
    if (s < -0.1) return '😟 Negative'
    return '😐 Neutral'
  }

  return (
    <div className="sticky top-0 z-50 bg-[#161b22] border-b border-[#30363d] px-6 py-3">
      <div className="max-w-screen-2xl mx-auto">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-bold text-white text-lg tracking-tight">AIP</span>
            <span className="text-gray-500 text-sm">Market Intelligence Platform</span>
          </div>

          {/* Desktop metrics */}
          <div className="hidden sm:flex items-center gap-4 text-sm flex-wrap">
            {context?.usd_index != null && (
              <span className="text-gray-400">
                DXY: <span className="text-white font-mono">{context.usd_index.toFixed(2)}</span>
                <DeltaArrow curr={context.usd_index} prev={prevContext?.usd_index} />
              </span>
            )}
            {context?.bond_yield_10y != null && (
              <span className="text-gray-400">
                10Y: <span className="text-white font-mono">{context.bond_yield_10y.toFixed(2)}%</span>
                <DeltaArrow curr={context.bond_yield_10y} prev={prevContext?.bond_yield_10y} />
              </span>
            )}
            {context?.vix != null && (
              <span className="text-gray-400">
                VIX: <span className="text-white font-mono">{context.vix.toFixed(1)}</span>
                <DeltaArrow curr={context.vix} prev={prevContext?.vix} />
              </span>
            )}
            {context?.news_sentiment != null && (
              <span className="text-gray-400">
                News: <span className="text-white">{sentimentLabel(context.news_sentiment)}</span>
              </span>
            )}
            {context?.on_chain_activity != null && (
              <span className="text-gray-400">
                On-chain: <span className="text-white">{context.on_chain_activity > 0.7 ? 'High' : context.on_chain_activity > 0.3 ? 'Med' : 'Low'}</span>
              </span>
            )}
            <span className={`text-xs font-medium ${session.color}`}>● {session.label}</span>
          </div>

          {/* Mobile toggle */}
          <button
            className="sm:hidden text-xs text-gray-400 border border-[#30363d] rounded px-2 py-1"
            onClick={() => setShowMobileMetrics(v => !v)}
          >
            Markets ▾
          </button>

          <div className="flex items-center gap-3">
            {lastUpdated && (
              <span className="text-xs text-gray-500">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            {username ? (
              <>
                <span className="text-xs text-gray-400 border border-[#30363d] rounded-lg px-3 py-1.5">
                  👤 {username}
                </span>
                <button
                  onClick={onSignOut}
                  className="px-3 py-1.5 text-xs rounded-lg border border-[#30363d] text-gray-400 hover:border-red-500/50 hover:text-red-400 transition-colors"
                >
                  Sign out
                </button>
              </>
            ) : (
              <a
                href="/login"
                className="px-3 py-1.5 text-xs rounded-lg border border-[#30363d] text-gray-400 hover:border-[#58a6ff] hover:text-[#58a6ff] transition-colors"
              >
                Sign in
              </a>
            )}
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className="px-3 py-1.5 text-xs rounded-lg border border-[#30363d] text-gray-300 hover:border-[#58a6ff] hover:text-[#58a6ff] transition-colors disabled:opacity-50"
            >
              {refreshing ? '⟳ Refreshing…' : '⟳ Refresh'}
            </button>
          </div>
        </div>

        {/* Mobile metrics dropdown */}
        {showMobileMetrics && (
          <div className="sm:hidden mt-2 pt-2 border-t border-[#30363d] flex flex-col gap-1.5 text-xs text-gray-400">
            {context?.usd_index != null && <span>DXY: <span className="text-white font-mono">{context.usd_index.toFixed(2)}</span></span>}
            {context?.bond_yield_10y != null && <span>10Y: <span className="text-white font-mono">{context.bond_yield_10y.toFixed(2)}%</span></span>}
            {context?.vix != null && <span>VIX: <span className="text-white font-mono">{context.vix.toFixed(1)}</span></span>}
            {context?.news_sentiment != null && <span>News: <span className="text-white">{sentimentLabel(context?.news_sentiment)}</span></span>}
            <span className={session.color}>● {session.label}</span>
          </div>
        )}
      </div>
    </div>
  )
}

function SignalHistoryPanel({ apiUrl, symbols }: { apiUrl: string; symbols: string[] }) {
  const [selectedSymbol, setSelectedSymbol] = useState(symbols[0] || 'BTC')
  const [history, setHistory] = useState<{ model: string; signal: string; confidence: number; timestamp: string }[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!selectedSymbol) return
    setLoading(true)
    fetch(`${apiUrl}/api/signals/history?asset=${selectedSymbol}`)
      .then(r => r.ok ? r.json() : [])
      .then((d: unknown) => setHistory(Array.isArray(d) ? d as { model: string; signal: string; confidence: number; timestamp: string }[] : []))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false))
  }, [apiUrl, selectedSymbol])

  if (symbols.length === 0) return null

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="font-bold text-white flex items-center gap-2"><span>📜</span> Signal History</h2>
        <div className="flex gap-1 flex-wrap">
          {symbols.map(sym => (
            <button key={sym} onClick={() => setSelectedSymbol(sym)}
              className={`px-2 py-1 text-xs rounded border transition-colors ${selectedSymbol === sym ? 'border-[#58a6ff] bg-[#58a6ff]/10 text-[#58a6ff]' : 'border-[#30363d] text-gray-400 hover:border-[#58a6ff]/50'}`}>
              {sym}
            </button>
          ))}
        </div>
      </div>
      {loading ? (
        <div className="flex justify-center py-6"><div className="animate-spin w-5 h-5 border-2 border-[#58a6ff] border-t-transparent rounded-full" /></div>
      ) : history.length === 0 ? (
        <p className="text-xs text-gray-500 italic text-center py-4">No signal history for {selectedSymbol}.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-[#30363d]">
              <th className="text-left py-2 pr-4">Model</th>
              <th className="text-left py-2 pr-4">Signal</th>
              <th className="text-right py-2 pr-4">Confidence</th>
              <th className="text-right py-2">Date</th>
            </tr></thead>
            <tbody>
              {history.map((row, i) => (
                <tr key={i} className="border-b border-[#21262d] text-gray-300">
                  <td className="py-2 pr-4 font-medium capitalize">{row.model}</td>
                  <td className="py-2 pr-4"><SignalBadge signal={row.signal} size="sm" /></td>
                  <td className="py-2 pr-4 text-right font-mono">{(row.confidence * 100).toFixed(0)}%</td>
                  <td className="py-2 text-right text-gray-500 text-xs">{row.timestamp ? new Date(row.timestamp).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function MultiAssetComparison({ apiUrl, assets, consensus }: { apiUrl: string; assets: Asset[]; consensus: Consensus[] }) {
  const symbols = assets.map(a => a.symbol)
  const [symA, setSymA] = useState(symbols[0] || '')
  const [symB, setSymB] = useState(symbols[1] || '')
  const [histA, setHistA] = useState<number[]>([])
  const [histB, setHistB] = useState<number[]>([])
  const [loadingA, setLoadingA] = useState(false)
  const [loadingB, setLoadingB] = useState(false)

  const fetchHist = useCallback(async (sym: string, set: (v: number[]) => void, setLoad: (v: boolean) => void) => {
    if (!sym) return
    setLoad(true)
    try {
      const r = await fetch(`${apiUrl}/api/history/${sym}?limit=50`)
      if (r.ok) {
        const rows: { price?: number; close?: number }[] = await r.json()
        set(rows.map(x => x.price ?? x.close ?? 0).filter(p => p > 0).reverse())
      }
    } catch {}
    setLoad(false)
  }, [apiUrl])

  useEffect(() => { void fetchHist(symA, setHistA, setLoadingA) }, [symA, fetchHist])
  useEffect(() => { void fetchHist(symB, setHistB, setLoadingB) }, [symB, fetchHist])

  const assetA = assets.find(a => a.symbol === symA)
  const assetB = assets.find(a => a.symbol === symB)
  const consA = consensus.find(c => c.asset === symA)
  const consB = consensus.find(c => c.asset === symB)

  const norm = (prices: number[]) => {
    if (!prices.length) return []
    const base = prices[0]
    return base ? prices.map(p => +((p - base) / base * 100).toFixed(3)) : prices.map(() => 0)
  }
  const normA = norm(histA)
  const normB = norm(histB)
  const chartData = Array.from({ length: Math.max(normA.length, normB.length) }, (_, i) => ({
    i,
    [symA]: normA[i],
    [symB]: normB[i],
  }))

  if (assets.length < 2) return null

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <h2 className="font-bold text-white mb-4 flex items-center gap-2"><span>⚖️</span> Multi-Asset Comparison</h2>
      <div className="flex gap-3 mb-4">
        <div className="flex-1">
          <label className="text-xs text-gray-500 mb-1 block">Asset A</label>
          <select value={symA} onChange={e => setSymA(e.target.value)} className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#58a6ff]">
            {symbols.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="flex-1">
          <label className="text-xs text-gray-500 mb-1 block">Asset B</label>
          <select value={symB} onChange={e => setSymB(e.target.value)} className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#58a6ff]">
            {symbols.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>
      <div className="flex gap-3 mb-4">
        {[{ asset: assetA, cons: consA }, { asset: assetB, cons: consB }].map(({ asset, cons }, idx) => (
          <div key={idx} className="flex-1 bg-[#0d1117] rounded-lg p-3 space-y-1.5 text-sm">
            {asset ? (
              <>
                <div className="text-xs font-bold text-white mb-2">{asset.symbol} — {asset.name}</div>
                <div className="flex justify-between"><span className="text-gray-500">Price</span><span className="text-white font-mono">${asset.price >= 1000 ? asset.price.toLocaleString('en-US', { maximumFractionDigits: 0 }) : asset.price.toFixed(2)}</span></div>
                {asset.change_24h != null && <div className="flex justify-between"><span className="text-gray-500">24h</span><span className={asset.change_24h >= 0 ? 'text-emerald-400' : 'text-red-400'}>{asset.change_24h >= 0 ? '+' : ''}{asset.change_24h.toFixed(2)}%</span></div>}
                {cons && (
                  <>
                    <div className="flex justify-between items-center"><span className="text-gray-500">Signal</span><SignalBadge signal={cons.final_signal} size="sm" /></div>
                    <div className="flex justify-between"><span className="text-gray-500">Confidence</span><span className="text-white">{(cons.confidence * 100).toFixed(0)}%</span></div>
                  </>
                )}
              </>
            ) : <p className="text-gray-600 text-xs italic">Select asset</p>}
          </div>
        ))}
      </div>
      {(loadingA || loadingB) ? (
        <div className="flex justify-center py-4"><div className="animate-spin w-5 h-5 border-2 border-[#58a6ff] border-t-transparent rounded-full" /></div>
      ) : chartData.length > 1 ? (
        <div>
          <p className="text-xs text-gray-500 mb-2">% change from start (last 50 points)</p>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={chartData}>
              <XAxis dataKey="i" hide />
              <YAxis tickFormatter={(v: number) => `${v.toFixed(1)}%`} tick={{ fontSize: 10, fill: '#6e7681' }} width={55} />
              <Tooltip formatter={(v: number) => [`${v.toFixed(2)}%`]} contentStyle={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 11, color: '#8b949e' }} />
              <Line type="monotone" dataKey={symA} stroke="#58a6ff" dot={false} strokeWidth={1.5} connectNulls />
              <Line type="monotone" dataKey={symB} stroke="#f78166" dot={false} strokeWidth={1.5} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : null}
    </div>
  )
}

function ModelPerformancePanel({ apiUrl }: { apiUrl: string }) {
  const [perf, setPerf] = useState<{
    model_name: string; asset: string; total_predictions: number;
    accuracy: number; weight: number
  }[]>([])
  const [sortKey, setSortKey] = useState<'model_name' | 'asset' | 'total_predictions' | 'accuracy' | 'weight'>('accuracy')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/performance`)
        if (res.ok) setPerf(await res.json())
      } catch {}
    }
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [apiUrl])

  if (perf.length === 0) return null

  const handleSort = (key: typeof sortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const sorted = [...perf].sort((a, b) => {
    const va = a[sortKey]
    const vb = b[sortKey]
    if (typeof va === 'string' && typeof vb === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
    return sortDir === 'asc' ? (va as number) - (vb as number) : (vb as number) - (va as number)
  })

  const SortHeader = ({ label, k }: { label: string; k: typeof sortKey }) => (
    <th
      onClick={() => handleSort(k)}
      className="text-left py-2 pr-4 cursor-pointer hover:text-gray-300 select-none"
    >
      {label} {sortKey === k ? (sortDir === 'asc' ? '▲' : '▼') : <span className="opacity-30">▼</span>}
    </th>
  )

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <h2 className="font-bold text-white mb-4 flex items-center gap-2">
        <span>📈</span> Model Performance & Weights
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-[#30363d]">
              <SortHeader label="Model" k="model_name" />
              <SortHeader label="Asset" k="asset" />
              <th onClick={() => handleSort('total_predictions')} className="text-right py-2 pr-4 cursor-pointer hover:text-gray-300 select-none">
                Predictions {sortKey === 'total_predictions' ? (sortDir === 'asc' ? '▲' : '▼') : <span className="opacity-30">▼</span>}
              </th>
              <th onClick={() => handleSort('accuracy')} className="text-right py-2 pr-4 cursor-pointer hover:text-gray-300 select-none">
                Accuracy {sortKey === 'accuracy' ? (sortDir === 'asc' ? '▲' : '▼') : <span className="opacity-30">▼</span>}
              </th>
              <th onClick={() => handleSort('weight')} className="text-right py-2 cursor-pointer hover:text-gray-300 select-none">
                Weight {sortKey === 'weight' ? (sortDir === 'asc' ? '▲' : '▼') : <span className="opacity-30">▼</span>}
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p, i) => (
              <tr key={i} className="border-b border-[#21262d] text-gray-300">
                <td className="py-2 pr-4 font-medium capitalize">{p.model_name}</td>
                <td className="py-2 pr-4">{p.asset}</td>
                <td className="py-2 pr-4 text-right font-mono">{p.total_predictions}</td>
                <td className="py-2 pr-4 text-right">
                  <span className="font-mono">{(p.accuracy * 100).toFixed(1)}%</span>
                  <div className="w-full bg-[#21262d] rounded-full h-1 mt-1">
                    <div
                      className={`h-1 rounded-full ${p.accuracy > 0.65 ? 'bg-emerald-500' : p.accuracy > 0.5 ? 'bg-amber-500' : 'bg-red-500'}`}
                      style={{ width: `${Math.min(Math.max((p.accuracy - 0.5) * 2 * 100, 0), 100)}%` }}
                    />
                  </div>
                </td>
                <td className="py-2 text-right font-mono">
                  <span className={p.weight > 1 ? 'text-emerald-400' : p.weight < 1 ? 'text-red-400' : 'text-gray-400'}>
                    {p.weight.toFixed(2)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function Home() {
  const [data, setData] = useState<FullData | null>(null)
  const [brief, setBrief] = useState<Brief | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [briefLoading, setBriefLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [username, setUsername] = useState<string | null>(null)
  const [priceHistories, setPriceHistories] = useState<Record<string, number[]>>({})
  const prevContextRef = useRef<MarketContext | null>(null)
  const analyticsPanelRef = useRef<HTMLDivElement>(null)
  const tokenRefreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const scheduleTokenRefreshRef = useRef<() => void>(() => {})

  const doTokenRefresh = useCallback(async () => {
    const refreshToken = localStorage.getItem('aip_refresh_token')
    if (!refreshToken) return
    try {
      const res = await fetch(`${API_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (res.ok) {
        const { access_token, refresh_token } = await res.json()
        localStorage.setItem('aip_token', access_token)
        localStorage.setItem('aip_refresh_token', refresh_token)
        scheduleTokenRefreshRef.current()
      }
    } catch {}
  }, [])

  const scheduleTokenRefresh = useCallback(() => {
    if (typeof window === 'undefined') return
    const token = localStorage.getItem('aip_token')
    if (!token) return
    const exp = getTokenExpiry(token)
    if (!exp) return
    const msUntilExpiry = exp * 1000 - Date.now()
    const msUntilRefresh = msUntilExpiry - TOKEN_REFRESH_BUFFER_MS
    if (tokenRefreshTimer.current) clearTimeout(tokenRefreshTimer.current)
    if (msUntilRefresh <= 0) {
      void doTokenRefresh()
      return
    }
    tokenRefreshTimer.current = setTimeout(() => {
      void doTokenRefresh()
    }, msUntilRefresh)
  }, [doTokenRefresh])

  useEffect(() => {
    scheduleTokenRefreshRef.current = scheduleTokenRefresh
  }, [scheduleTokenRefresh])

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/full`, { headers: authHeaders() })
      if (res.status === 401) {
        localStorage.removeItem('aip_token')
        localStorage.removeItem('aip_refresh_token')
        window.location.href = '/login'
        return
      }
      if (!res.ok) throw new Error(`API error ${res.status}`)
      const json = await res.json()
      setData(prev => {
        prevContextRef.current = prev?.context ?? null
        return json
      })
      setLastUpdated(new Date())
      setError(null)
    } catch {
      setError('Cannot connect to backend API. Make sure it is running.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  const fetchBrief = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/brief`, { headers: authHeaders() })
      if (res.ok) {
        const json = await res.json()
        setBrief(json)
      }
    } catch {}
  }, [])

  const handleSignOut = useCallback(() => {
    localStorage.removeItem('aip_token')
    localStorage.removeItem('aip_refresh_token')
    setUsername(null)
    if (tokenRefreshTimer.current) clearTimeout(tokenRefreshTimer.current)
    window.location.href = '/login'
  }, [])

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    const res = await fetch(`${API_URL}/api/refresh`, {
      method: 'POST',
      headers: authHeaders(),
    }).catch(() => null)
    if (res && res.status === 401) {
      localStorage.removeItem('aip_token')
      localStorage.removeItem('aip_refresh_token')
      window.location.href = '/login'
      return
    }
    setTimeout(fetchData, REFRESH_DELAY_MS)
  }, [fetchData])

  const handleGenerateBrief = useCallback(async () => {
    setBriefLoading(true)
    await fetch(`${API_URL}/api/brief/generate`, {
      method: 'POST',
      headers: authHeaders(),
    }).catch(() => {})
    setTimeout(async () => {
      await fetchBrief()
      setBriefLoading(false)
    }, BRIEF_GENERATION_DELAY_MS)
  }, [fetchBrief])

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('aip_token')
      if (token) {
        const exp = getTokenExpiry(token)
        if (exp && exp * 1000 > Date.now()) {
          try {
            const payload = JSON.parse(atob(token.split('.')[1]))
            if (payload.sub) setUsername(payload.sub as string)
          } catch {}
        }
      }
    }
    fetchData()
    fetchBrief()
    scheduleTokenRefresh()
    const interval = setInterval(fetchData, 60000)
    return () => {
      clearInterval(interval)
      if (tokenRefreshTimer.current) clearTimeout(tokenRefreshTimer.current)
    }
  }, [fetchData, fetchBrief, scheduleTokenRefresh])

  useEffect(() => {
    if (!data?.assets) return
    const assets = data.assets
    const fetchHistories = async () => {
      const results = await Promise.all(
        assets.map(async asset => {
          try {
            const res = await fetch(`${API_URL}/api/history/${asset.symbol}?limit=7`)
            if (res.ok) {
              const rows: { price?: number; close?: number }[] = await res.json()
              return { symbol: asset.symbol, prices: rows.map(r => r.price ?? r.close ?? 0).filter(p => p > 0).reverse() }
            }
          } catch {}
          return { symbol: asset.symbol, prices: [] }
        })
      )
      setPriceHistories(Object.fromEntries(results.map(r => [r.symbol, r.prices])))
    }
    void fetchHistories()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  const consensus = data?.consensus || []

  return (
    <div className="min-h-screen bg-[#0d1117]">
      <TopBar
        context={data?.context || null}
        prevContext={prevContextRef.current}
        lastUpdated={lastUpdated}
        onRefresh={handleRefresh}
        refreshing={refreshing}
        username={username}
        onSignOut={handleSignOut}
      />

      <main className="max-w-screen-2xl mx-auto px-4 py-5 space-y-5">
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm">
            ⚠️ {error}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center h-64 text-gray-500">
            <div className="text-center">
              <div className="animate-spin w-8 h-8 border-2 border-[#58a6ff] border-t-transparent rounded-full mx-auto mb-3" />
              <p>Loading market data…</p>
            </div>
          </div>
        ) : (
          <>
            {/* Asset Grid + Alert Feed */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
              <div className="lg:col-span-3">
                <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                  Assets
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
                  {(data?.assets || []).map(asset => (
                    <AssetCard
                      key={asset.symbol}
                      asset={asset}
                      consensus={consensus.find(c => c.asset === asset.symbol)}
                      priceHistory={priceHistories[asset.symbol] || []}
                      onClick={() => analyticsPanelRef.current?.scrollIntoView({ behavior: 'smooth' })}
                    />
                  ))}
                </div>
              </div>

              <div className="lg:col-span-1">
                <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
                  Alerts
                </h2>
                <div className="h-80 lg:h-[320px]">
                  <AlertFeed apiUrl={API_URL} />
                </div>
              </div>
            </div>

            {/* Macro Heatmap */}
            <MacroHeatmap context={data?.context || null} assets={data?.assets || []} />

            {/* Analytics + Consensus */}
            <div ref={analyticsPanelRef} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <AnalyticsPanel
                apiUrl={API_URL}
                symbols={(data?.assets || []).map(a => a.symbol)}
              />
              <ConsensusView consensus={consensus} />
            </div>

            {/* Watchlist + Daily Brief */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-1">
                <WatchlistPanel
                  apiUrl={API_URL}
                  assets={data?.assets || []}
                  consensus={consensus}
                />
              </div>
              <div className="lg:col-span-2">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">
                    Daily Brief
                  </h2>
                  <button
                    onClick={handleGenerateBrief}
                    disabled={briefLoading}
                    className="px-3 py-1.5 text-xs rounded-lg bg-[#58a6ff]/10 border border-[#58a6ff]/30 text-[#58a6ff] hover:bg-[#58a6ff]/20 transition-colors disabled:opacity-50"
                  >
                    {briefLoading ? '⟳ Generating…' : '✦ Generate Brief'}
                  </button>
                </div>
                <BriefPanel brief={brief} loading={briefLoading} assets={data?.assets || []} />
              </div>
            </div>

            {/* Model Performance */}
            <ModelPerformancePanel apiUrl={API_URL} />

            {/* Signal History */}
            <SignalHistoryPanel apiUrl={API_URL} symbols={(data?.assets || []).map(a => a.symbol)} />

            {/* Multi-Asset Comparison */}
            <MultiAssetComparison apiUrl={API_URL} assets={data?.assets || []} consensus={consensus} />

            {/* AI Agent Team */}
            <AgentsPanel apiUrl={API_URL} />

            {/* Coordinator Chat */}
            <div className="fixed bottom-4 right-4 z-50">
              <CoordinatorChatWidget />
            </div>
          </>
        )}
      </main>
    </div>
  )
}

// Floating chat widget with expand/collapse
function CoordinatorChatWidget() {
  const [isExpanded, setIsExpanded] = useState(false)

  if (!isExpanded) {
    return (
      <button
        onClick={() => setIsExpanded(true)}
        className="w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-500 shadow-lg flex items-center justify-center transition-all hover:scale-105"
        title="Open Coordinator Chat"
      >
        <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" 
          />
        </svg>
      </button>
    )
  }

  return (
    <div className="w-[400px] h-[500px] shadow-2xl rounded-lg overflow-hidden">
      <div className="bg-gray-800 px-3 py-2 flex items-center justify-between border-b border-gray-700">
        <span className="text-sm font-medium text-white">AI Coordinator</span>
        <button
          onClick={() => setIsExpanded(false)}
          className="text-gray-400 hover:text-white transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>
      <CoordinatorChat className="h-[calc(100%-40px)]" />
    </div>
  )
}
