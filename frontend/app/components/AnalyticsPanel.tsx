'use client'

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, BarChart, Bar
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

const COLORS: Record<string, string> = {
  BTC: '#f7931a',
  ETH: '#627eea',
  GOLD: '#ffd700',
  OIL: '#8b4513',
}

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ts
  }
}

export default function AnalyticsPanel({ apiUrl, symbols = ['BTC', 'ETH', 'GOLD', 'OIL'] }: AnalyticsPanelProps) {
  const [priceHistory, setPriceHistory] = useState<Record<string, PricePoint[]>>({})
  const [activeSymbol, setActiveSymbol] = useState('BTC')

  useEffect(() => {
    const loadHistory = async (symbol: string) => {
      try {
        const res = await fetch(`${apiUrl}/api/history/${symbol}?limit=50`)
        if (res.ok) {
          const data = await res.json()
          setPriceHistory(prev => ({ ...prev, [symbol]: data.reverse() }))
        }
      } catch {}
    }
    symbols.forEach(loadHistory)
    const interval = setInterval(() => symbols.forEach(loadHistory), 30000)
    return () => clearInterval(interval)
  }, [apiUrl, symbols])

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

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <h2 className="font-bold text-white mb-4 flex items-center gap-2">
        <span>📊</span> Analytics
      </h2>

      {/* Symbol selector */}
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

      {/* Price chart */}
      <div className="mb-6">
        <p className="text-xs text-gray-500 mb-2">Price History — {activeSymbol}</p>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
              <XAxis dataKey="time" tick={{ fill: '#6e7681', fontSize: 10 }} />
              <YAxis
                tick={{ fill: '#6e7681', fontSize: 10 }}
                tickFormatter={v => `$${v.toLocaleString()}`}
                width={70}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#21262d', border: '1px solid #30363d', borderRadius: 8 }}
                labelStyle={{ color: '#e6edf3' }}
                formatter={(v: number) => [`$${v.toLocaleString()}`, 'Price']}
              />
              <Line
                type="monotone"
                dataKey="price"
                stroke={COLORS[activeSymbol] || '#58a6ff'}
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-40 flex items-center justify-center text-gray-500 text-sm">
            Collecting price data…
          </div>
        )}
      </div>

      {/* 24h change bar chart */}
      <div>
        <p className="text-xs text-gray-500 mb-2">24h Change (%)</p>
        <ResponsiveContainer width="100%" height={100}>
          <BarChart data={changeBarData} barSize={24}>
            <XAxis dataKey="symbol" tick={{ fill: '#6e7681', fontSize: 11 }} />
            <YAxis tick={{ fill: '#6e7681', fontSize: 10 }} unit="%" />
            <Tooltip
              contentStyle={{ backgroundColor: '#21262d', border: '1px solid #30363d', borderRadius: 8 }}
              formatter={(v: number) => [`${v.toFixed(2)}%`, '24h Change']}
            />
            <Bar
              dataKey="change"
              fill="#58a6ff"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
