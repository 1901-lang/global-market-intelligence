'use client'

import { useState } from 'react'
import SignalBadge from './SignalBadge'

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

interface AssetCardProps {
  asset: Asset
  consensus?: Consensus
  priceHistory?: number[]
  onClick?: () => void
}

function formatPrice(price: number, symbol: string): string {
  if (price >= 1000) return `$${price.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
  if (price >= 1) return `$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  return `$${price.toFixed(4)}`
}

function formatChange(change?: number): string {
  if (change == null) return '—'
  return `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`
}

function formatVolume(v: number): string {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`
  return `$${(v / 1e3).toFixed(0)}k`
}

function ChangeIndicator({ value }: { value?: number }) {
  const isPositive = (value ?? 0) >= 0
  return (
    <span className={isPositive ? 'text-emerald-400' : 'text-red-400'}>
      {isPositive ? '▲' : '▼'} {formatChange(value)}
    </span>
  )
}

function Sparkline({ prices }: { prices: number[] }) {
  if (prices.length < 2) return null
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min || 1
  const w = 60, h = 28
  const pts = prices.map((p, i) => `${(i / (prices.length - 1)) * w},${h - ((p - min) / range) * h}`).join(' ')
  const color = prices[prices.length - 1] >= prices[0] ? '#10b981' : '#ef4444'
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

export default function AssetCard({ asset, consensus, priceHistory, onClick }: AssetCardProps) {
  const [showTooltip, setShowTooltip] = useState(false)
  const signal = consensus?.final_signal || 'HOLD'
  const confidence = consensus?.confidence || 0
  const agreementLevel = consensus?.agreement_level || 'low'

  const agreementColors: Record<string, string> = {
    high: 'text-emerald-400',
    medium: 'text-amber-400',
    low: 'text-red-400',
  }

  const emoji = asset.asset_type === 'crypto'
    ? (asset.symbol === 'BTC' ? '₿' : 'Ξ')
    : (asset.symbol === 'GOLD' ? '🥇' : '🛢')

  return (
    <div
      className={`bg-[#161b22] border border-[#30363d] rounded-xl p-5 hover:border-[#58a6ff]/40 transition-colors ${onClick ? 'cursor-pointer' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl">{emoji}</span>
            <div>
              <h3 className="font-bold text-white text-lg">{asset.symbol}</h3>
              <p className="text-gray-500 text-xs">{asset.name}</p>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <SignalBadge signal={signal} size="md" />
          {priceHistory && priceHistory.length >= 2 && <Sparkline prices={priceHistory} />}
        </div>
      </div>

      <div className="mb-3">
        <div className="text-2xl font-mono font-bold text-white">
          {formatPrice(asset.price, asset.symbol)}
        </div>
        <div className="flex gap-3 text-sm mt-1">
          <span className="text-gray-500">1h: <ChangeIndicator value={asset.change_1h} /></span>
          <span className="text-gray-500">24h: <ChangeIndicator value={asset.change_24h} /></span>
        </div>
        {asset.volume_24h != null && (
          <div className="text-xs text-gray-500 mt-0.5">
            Vol: <span className="text-gray-400">{formatVolume(asset.volume_24h)}</span>
          </div>
        )}
      </div>

      {consensus && (
        <div
          className="border-t border-[#30363d] pt-3 mt-3 relative"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
        >
          {showTooltip && consensus?.models && Object.keys(consensus.models).length > 0 && (
            <div className="absolute bottom-full left-0 mb-1 z-20 bg-[#0d1117] border border-[#30363d] rounded-lg p-2 text-xs shadow-xl min-w-[160px]">
              {Object.entries(consensus.models).map(([name, m]) => (
                <div key={name} className="flex justify-between gap-3 py-0.5">
                  <span className="text-gray-400 capitalize">{name}</span>
                  <span className="text-white">{m.signal} {(m.confidence * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          )}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">AI Confidence</span>
            <span className="font-semibold text-white">{(confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="w-full bg-[#21262d] rounded-full h-1.5 mt-1.5">
            <div
              className={`h-1.5 rounded-full transition-all ${
                signal === 'BUY' ? 'bg-emerald-500' :
                signal === 'SELL' ? 'bg-red-500' : 'bg-amber-500'
              }`}
              style={{ width: `${confidence * 100}%` }}
            />
          </div>
          <div className="flex justify-between text-xs mt-1.5">
            <span className="text-gray-500">Agreement:</span>
            <span className={agreementColors[agreementLevel] || 'text-gray-400'}>
              {agreementLevel.charAt(0).toUpperCase() + agreementLevel.slice(1)}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
