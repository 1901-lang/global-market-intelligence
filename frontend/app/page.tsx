'use client'

import { useEffect, useState, useCallback } from 'react'
import AssetCard from './components/AssetCard'
import AlertFeed from './components/AlertFeed'
import AnalyticsPanel from './components/AnalyticsPanel'
import ConsensusView from './components/ConsensusView'
import BriefPanel from './components/BriefPanel'
import SignalBadge from './components/SignalBadge'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Delay (ms) after triggering a backend refresh before re-fetching data,
// allowing the update cycle to complete before the frontend polls again.
const REFRESH_DELAY_MS = 3000
// Delay (ms) after requesting brief generation before polling for the result,
// allowing the AI generation to complete.
const BRIEF_GENERATION_DELAY_MS = 5000

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
}

interface FullData {
  assets: Asset[]
  context: MarketContext | null
  signals: unknown[]
  consensus: Consensus[]
  alerts: unknown[]
  model_outputs: unknown[]
}

function formatNumber(n?: number, decimals = 2): string {
  if (n == null) return '—'
  return n.toFixed(decimals)
}

function TopBar({ context, lastUpdated, onRefresh, refreshing }: {
  context: MarketContext | null
  lastUpdated: Date | null
  onRefresh: () => void
  refreshing: boolean
}) {
  const sentimentLabel = (s?: number) => {
    if (s == null) return '—'
    if (s > 0.1) return '😊 Positive'
    if (s < -0.1) return '😟 Negative'
    return '😐 Neutral'
  }

  return (
    <div className="bg-[#161b22] border-b border-[#30363d] px-6 py-3">
      <div className="max-w-screen-2xl mx-auto flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-bold text-white text-lg tracking-tight">AIP</span>
          <span className="text-gray-500 text-sm">Market Intelligence Platform</span>
        </div>

        <div className="flex items-center gap-4 text-sm flex-wrap">
          {context?.usd_index != null && (
            <span className="text-gray-400">
              DXY: <span className="text-white font-mono">{formatNumber(context.usd_index)}</span>
            </span>
          )}
          {context?.bond_yield_10y != null && (
            <span className="text-gray-400">
              10Y: <span className="text-white font-mono">{formatNumber(context.bond_yield_10y)}%</span>
            </span>
          )}
          {context?.vix != null && (
            <span className="text-gray-400">
              VIX: <span className="text-white font-mono">{formatNumber(context.vix, 1)}</span>
            </span>
          )}
          {context?.news_sentiment != null && (
            <span className="text-gray-400">
              News: <span className="text-white">{sentimentLabel(context.news_sentiment)}</span>
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-gray-500">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
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

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/full`)
      if (!res.ok) throw new Error(`API error ${res.status}`)
      const json = await res.json()
      setData(json)
      setLastUpdated(new Date())
      setError(null)
    } catch (e) {
      setError('Cannot connect to backend API. Make sure it is running.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  const fetchBrief = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/brief`)
      if (res.ok) {
        const json = await res.json()
        setBrief(json)
      }
    } catch {}
  }, [])

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    await fetch(`${API_URL}/api/refresh`, { method: 'POST' }).catch(() => {})
    setTimeout(fetchData, REFRESH_DELAY_MS)
  }, [fetchData])

  const handleGenerateBrief = useCallback(async () => {
    setBriefLoading(true)
    await fetch(`${API_URL}/api/brief/generate`, { method: 'POST' }).catch(() => {})
    setTimeout(async () => {
      await fetchBrief()
      setBriefLoading(false)
    }, BRIEF_GENERATION_DELAY_MS)
  }, [fetchBrief])

  useEffect(() => {
    fetchData()
    fetchBrief()
    const interval = setInterval(fetchData, 60000)
    return () => clearInterval(interval)
  }, [fetchData, fetchBrief])

  const consensus = data?.consensus || []

  return (
    <div className="min-h-screen bg-[#0d1117]">
      <TopBar
        context={data?.context || null}
        lastUpdated={lastUpdated}
        onRefresh={handleRefresh}
        refreshing={refreshing}
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

            {/* Analytics + Consensus */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <AnalyticsPanel
                apiUrl={API_URL}
                symbols={(data?.assets || []).map(a => a.symbol)}
              />
              <ConsensusView consensus={consensus} />
            </div>

            {/* Daily Brief */}
            <div className="grid grid-cols-1 gap-4">
              <div>
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
                <BriefPanel brief={brief} loading={briefLoading} />
              </div>
            </div>

            {/* Model Performance */}
            <ModelPerformancePanel apiUrl={API_URL} />
          </>
        )}
      </main>
    </div>
  )
}

function ModelPerformancePanel({ apiUrl }: { apiUrl: string }) {
  const [perf, setPerf] = useState<{
    model_name: string; asset: string; total_predictions: number;
    accuracy: number; weight: number
  }[]>([])

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

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <h2 className="font-bold text-white mb-4 flex items-center gap-2">
        <span>📈</span> Model Performance & Weights
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-[#30363d]">
              <th className="text-left py-2 pr-4">Model</th>
              <th className="text-left py-2 pr-4">Asset</th>
              <th className="text-right py-2 pr-4">Predictions</th>
              <th className="text-right py-2 pr-4">Accuracy</th>
              <th className="text-right py-2">Weight</th>
            </tr>
          </thead>
          <tbody>
            {perf.map((p, i) => (
              <tr key={i} className="border-b border-[#21262d] text-gray-300">
                <td className="py-2 pr-4 font-medium capitalize">{p.model_name}</td>
                <td className="py-2 pr-4">{p.asset}</td>
                <td className="py-2 pr-4 text-right font-mono">{p.total_predictions}</td>
                <td className="py-2 pr-4 text-right font-mono">
                  {(p.accuracy * 100).toFixed(1)}%
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
