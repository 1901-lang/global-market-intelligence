'use client'

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar, Cell
} from 'recharts'
import { useEffect, useState } from 'react'

interface PricePoint {
  id: number
  symbol: string
  price: number
  change_24h: number
  timestamp: string
}

interface AnalyticsPanelProps {
  apiUrl: string
  symbols?: string[]
}

interface CorrelationData {
  symbols: string[]
  matrix: Record<string, Record<string, number | null>>
}

const COLORS: Record<string, string> = {
  BTC: '#f7931a',
  ETH: '#627eea',
  GOLD: '#ffd700',
  OIL: '#8b4513',
}

const TIMEFRAME_LIMITS: Record<string, number> = {
  '1H': 12,
  '6H': 72,
  '1D': 288,
  '7D': 2016,
}

type ChartTab = 'Price' | '24h Change' | 'Correlation' | 'Volatility'

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ts
  }
}

function correlationColor(v: number | null): string {
  if (v == null) return '#21262d'
  if (v >= 0.7) return 'rgba(52, 211, 153, 0.55)'
  if (v >= 0.3) return 'rgba(52, 211, 153, 0.25)'
  if (v > -0.3) return 'rgba(110, 118, 129, 0.20)'
  if (v > -0.7) return 'rgba(248, 113, 113, 0.25)'
  return 'rgba(248, 113, 113, 0.55)'
}

function CorrelationMatrix({ correlations }: { correlations: CorrelationData }) {
  const { symbols, matrix } = correlations
  return (
    <div>
      <p className="text-xs text-gray-500 mb-2">Cross-Asset Correlation (Pearson, recent data points)</p>
      <div className="overflow-x-auto">
        <table className="text-xs w-full">
          <thead>
            <tr>
              <th className="text-gray-500 font-normal pb-1 pr-2 text-right w-12" />
              {symbols.map(s => (
                <th key={s} className="text-gray-400 font-semibold pb-1 px-1 text-center min-w-[52px]">{s}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {symbols.map(row => (
              <tr key={row}>
                <td className="text-gray-400 font-semibold pr-2 py-0.5 text-right">{row}</td>
                {symbols.map(col => {
                  const v = matrix[row]?.[col]
                  return (
                    <td
                      key={col}
                      className="text-center py-0.5 px-1 rounded font-mono"
                      style={{ backgroundColor: correlationColor(v) }}
                      title={v != null ? `${row} / ${col}: ${v.toFixed(3)}` : 'insufficient data'}
                    >
                      <span className={row === col ? 'text-gray-500' : 'text-gray-200'}>
                        {v != null ? v.toFixed(2) : '—'}
                      </span>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-3">
          <p className="text-[10px] text-gray-600 mb-1">Correlation scale</p>
          <div className="h-2 rounded" style={{ background: 'linear-gradient(to right, rgba(248,113,113,0.6), rgba(110,118,129,0.3), rgba(52,211,153,0.6))' }} />
          <div className="flex justify-between text-[10px] text-gray-600 mt-0.5"><span>-1.0</span><span>0</span><span>+1.0</span></div>
        </div>
      </div>
    </div>
  )
}

function computeVolatility(prices: number[]): { time: string; vol: number }[] {
  if (prices.length < 7) return []
  const returns = prices.map((p, i) => i === 0 ? 0 : (p - prices[i - 1]) / prices[i - 1])
  const result: { time: string; vol: number }[] = []
  for (let i = 6; i < prices.length; i++) {
    const window = returns.slice(i - 6, i + 1)
    const mean = window.reduce((a, b) => a + b, 0) / window.length
    const variance = window.reduce((a, b) => a + (b - mean) ** 2, 0) / window.length
    result.push({ time: String(i), vol: parseFloat((Math.sqrt(variance) * 100).toFixed(4)) })
  }
  return result
}

export default function AnalyticsPanel({ apiUrl, symbols = ['BTC', 'ETH', 'GOLD', 'OIL'] }: AnalyticsPanelProps) {
  const [priceHistory, setPriceHistory] = useState<Record<string, PricePoint[]>>({})
  const [activeSymbol, setActiveSymbol] = useState('BTC')
  const [correlations, setCorrelations] = useState<CorrelationData | null>(null)
  const [timeframe, setTimeframe] = useState<string>('1D')
  const [compareMode, setCompareMode] = useState(false)
  const [chartTab, setChartTab] = useState<ChartTab>('Price')

  useEffect(() => {
    const limit = TIMEFRAME_LIMITS[timeframe] ?? 288
    const loadHistory = async (symbol: string) => {
      try {
        const res = await fetch(`${apiUrl}/api/history/${symbol}?limit=${limit}`)
        if (res.ok) {
          const data = await res.json()
          setPriceHistory(prev => ({ ...prev, [symbol]: data.reverse() }))
        }
      } catch {}
    }
    symbols.forEach(loadHistory)
    const interval = setInterval(() => symbols.forEach(loadHistory), 30000)
    return () => clearInterval(interval)
  }, [apiUrl, symbols, timeframe])

  useEffect(() => {
    const limit = TIMEFRAME_LIMITS[timeframe] ?? 288
    const loadCorrelation = async () => {
      try {
        const symsParam = symbols.join(',')
        const res = await fetch(`${apiUrl}/api/correlation?symbols=${symsParam}&limit=${limit}`)
        if (res.ok) setCorrelations(await res.json())
      } catch {}
    }
    loadCorrelation()
    const interval = setInterval(loadCorrelation, 60000)
    return () => clearInterval(interval)
  }, [apiUrl, symbols, timeframe])

  const chartData = (priceHistory[activeSymbol] || []).map(p => ({
    time: formatTimestamp(p.timestamp),
    price: p.price,
    change: p.change_24h,
  }))

  const changeBarData = symbols.map(sym => {
    const latest = priceHistory[sym]?.[priceHistory[sym].length - 1]
    return {
      symbol: sym,
      change: latest?.change_24h ?? 0,
    }
  })

  const compareChartData = (() => {
    const maxLen = Math.max(...symbols.map(s => priceHistory[s]?.length ?? 0))
    return Array.from({ length: maxLen }, (_, i) => {
      const point: Record<string, number | string> = { i }
      symbols.forEach(s => {
        const p = priceHistory[s]?.[i]
        if (p) point[s] = p.price
      })
      return point
    })
  })()

  const volData = computeVolatility((priceHistory[activeSymbol] || []).map(p => p.price))

  const tabs: ChartTab[] = ['Price', '24h Change', 'Correlation', 'Volatility']

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <h2 className="font-bold text-white mb-4 flex items-center gap-2">
        <span>📊</span> Analytics
      </h2>

      {/* Timeframe + Compare */}
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex gap-1">
          {Object.keys(TIMEFRAME_LIMITS).map(tf => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-2 py-1 text-xs rounded border transition-colors ${
                timeframe === tf
                  ? 'border-[#58a6ff] bg-[#58a6ff]/10 text-[#58a6ff]'
                  : 'border-[#30363d] text-gray-500 hover:border-gray-400'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
        <button
          onClick={() => setCompareMode(v => !v)}
          className={`px-3 py-1 text-xs rounded border transition-colors ${
            compareMode
              ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-400'
              : 'border-[#30363d] text-gray-500 hover:border-gray-400'
          }`}
        >
          {compareMode ? '✓ Compare' : 'Compare'}
        </button>
      </div>

      {/* Chart tabs */}
      <div className="flex gap-1 mb-4 border-b border-[#30363d] pb-2">
        {tabs.map(tab => (
          <button
            key={tab}
            onClick={() => setChartTab(tab)}
            className={`px-3 py-1 text-xs rounded-t transition-colors ${
              chartTab === tab
                ? 'text-white border-b-2 border-[#58a6ff]'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Symbol selector (not shown in compare mode for Price tab) */}
      {chartTab === 'Price' && !compareMode && (
        <div className="flex gap-2 mb-4">
          {symbols.map(sym => (
            <button
              key={sym}
              onClick={() => setActiveSymbol(sym)}
              className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                activeSymbol === sym
                  ? 'border-[#58a6ff] bg-[#58a6ff]/10 text-[#58a6ff]'
                  : 'border-[#30363d] text-gray-400 hover:border-gray-400'
              }`}
            >
              {sym}
            </button>
          ))}
        </div>
      )}

      {/* Price tab */}
      {chartTab === 'Price' && (
        <div className="mb-2">
          {compareMode ? (
            <div>
              <p className="text-xs text-gray-500 mb-2">Price History — All Assets</p>
              {compareChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={compareChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                    <XAxis dataKey="i" hide />
                    <YAxis tick={{ fill: '#6e7681', fontSize: 10 }} tickFormatter={v => `$${(v as number).toLocaleString()}`} width={70} />
                    <Tooltip contentStyle={{ backgroundColor: '#21262d', border: '1px solid #30363d', borderRadius: 8 }} labelStyle={{ color: '#e6edf3' }} formatter={(v: number) => [`$${v.toLocaleString()}`, '']} />
                    <Legend wrapperStyle={{ fontSize: 11, color: '#8b949e' }} />
                    {symbols.map(sym => (
                      <Line key={sym} type="monotone" dataKey={sym} stroke={COLORS[sym] || '#58a6ff'} dot={false} strokeWidth={1.5} connectNulls />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[280px] flex items-center justify-center text-gray-500 text-sm">Collecting data…</div>
              )}
            </div>
          ) : (
            <div>
              <p className="text-xs text-gray-500 mb-2">Price History — {activeSymbol}</p>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                    <XAxis dataKey="time" tick={{ fill: '#6e7681', fontSize: 10 }} />
                    <YAxis tick={{ fill: '#6e7681', fontSize: 10 }} tickFormatter={v => `$${(v as number).toLocaleString()}`} width={70} />
                    <Tooltip contentStyle={{ backgroundColor: '#21262d', border: '1px solid #30363d', borderRadius: 8 }} labelStyle={{ color: '#e6edf3' }} formatter={(v: number) => [`$${v.toLocaleString()}`, 'Price']} />
                    <Line type="monotone" dataKey="price" stroke={COLORS[activeSymbol] || '#58a6ff'} dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[280px] flex items-center justify-center text-gray-500 text-sm">Collecting price data…</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 24h Change tab */}
      {chartTab === '24h Change' && (
        <div className="mb-2">
          <p className="text-xs text-gray-500 mb-2">24h Change (%)</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={changeBarData} barSize={32}>
              <XAxis dataKey="symbol" tick={{ fill: '#6e7681', fontSize: 11 }} />
              <YAxis tick={{ fill: '#6e7681', fontSize: 10 }} unit="%" />
              <Tooltip contentStyle={{ backgroundColor: '#21262d', border: '1px solid #30363d', borderRadius: 8 }} formatter={(v: number) => [`${v.toFixed(2)}%`, '24h Change']} />
              <Bar dataKey="change" radius={[4, 4, 0, 0]}>
                {changeBarData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.change >= 0 ? '#10b981' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Correlation tab */}
      {chartTab === 'Correlation' && (
        <div className="mb-2">
          {correlations && correlations.symbols.length >= 2 ? (
            <CorrelationMatrix correlations={correlations} />
          ) : (
            <div className="h-32 flex items-center justify-center text-gray-500 text-sm">Collecting correlation data…</div>
          )}
        </div>
      )}

      {/* Volatility tab */}
      {chartTab === 'Volatility' && (
        <div className="mb-2">
          <div className="flex gap-2 mb-3">
            {symbols.map(sym => (
              <button key={sym} onClick={() => setActiveSymbol(sym)}
                className={`px-3 py-1 text-xs rounded-full border transition-colors ${activeSymbol === sym ? 'border-[#58a6ff] bg-[#58a6ff]/10 text-[#58a6ff]' : 'border-[#30363d] text-gray-400 hover:border-gray-400'}`}>
                {sym}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-500 mb-2">Rolling 7-period Volatility (%) — {activeSymbol}</p>
          {volData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={volData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
                <XAxis dataKey="time" hide />
                <YAxis tick={{ fill: '#6e7681', fontSize: 10 }} unit="%" width={45} />
                <Tooltip contentStyle={{ backgroundColor: '#21262d', border: '1px solid #30363d', borderRadius: 8 }} formatter={(v: number) => [`${v.toFixed(3)}%`, 'Volatility']} />
                <Line type="monotone" dataKey="vol" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-gray-500 text-sm">Need more data points…</div>
          )}
        </div>
      )}
    </div>
  )
}
