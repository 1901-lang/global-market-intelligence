'use client'

interface MarketContext {
  usd_index?: number
  bond_yield_10y?: number
  vix?: number
  news_sentiment?: number
  on_chain_activity?: number
}

interface Asset {
  symbol: string
  name: string
  price: number
  change_24h?: number
  asset_type: string
}

interface MacroHeatmapProps {
  context: MarketContext | null
  assets: Asset[]
}

interface Tile {
  label: string
  value: string
  sentiment: 'bullish' | 'bearish' | 'neutral'
  sub?: string
}

function getTileColor(s: Tile['sentiment']): string {
  if (s === 'bullish') return 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
  if (s === 'bearish') return 'bg-red-500/15 border-red-500/30 text-red-400'
  return 'bg-[#21262d] border-[#30363d] text-gray-400'
}

export default function MacroHeatmap({ context, assets }: MacroHeatmapProps) {
  const tiles: Tile[] = []

  if (context?.usd_index != null) {
    const v = context.usd_index
    tiles.push({ label: 'DXY', value: v.toFixed(2), sentiment: v > 105 ? 'bearish' : v < 100 ? 'bullish' : 'neutral', sub: v > 105 ? 'Strong USD' : v < 100 ? 'Weak USD' : 'Neutral' })
  }
  if (context?.bond_yield_10y != null) {
    const v = context.bond_yield_10y
    tiles.push({ label: '10Y Yield', value: `${v.toFixed(2)}%`, sentiment: v > 4.5 ? 'bearish' : v < 3.5 ? 'bullish' : 'neutral', sub: v > 4.5 ? 'High rates' : v < 3.5 ? 'Low rates' : 'Moderate' })
  }
  if (context?.vix != null) {
    const v = context.vix
    tiles.push({ label: 'VIX', value: v.toFixed(1), sentiment: v > 25 ? 'bearish' : v < 15 ? 'bullish' : 'neutral', sub: v > 25 ? 'High fear' : v < 15 ? 'Low fear' : 'Moderate' })
  }
  if (context?.news_sentiment != null) {
    const v = context.news_sentiment
    tiles.push({
      label: 'News',
      value: v > 0.1 ? '😊 Positive' : v < -0.1 ? '😟 Negative' : '😐 Neutral',
      sentiment: v > 0.1 ? 'bullish' : v < -0.1 ? 'bearish' : 'neutral',
      sub: v.toFixed(3),
    })
  }
  if (context?.on_chain_activity != null) {
    const v = context.on_chain_activity
    tiles.push({ label: 'On-Chain', value: v > 0.7 ? 'High' : v > 0.3 ? 'Med' : 'Low', sentiment: v > 0.7 ? 'bullish' : v < 0.3 ? 'bearish' : 'neutral', sub: v.toFixed(3) })
  }

  for (const sym of ['BTC', 'ETH', 'GOLD', 'OIL']) {
    const a = assets.find(x => x.symbol === sym)
    if (a?.change_24h != null) {
      const ch = a.change_24h
      tiles.push({ label: sym, value: `${ch >= 0 ? '+' : ''}${ch.toFixed(2)}%`, sentiment: ch > 1 ? 'bullish' : ch < -1 ? 'bearish' : 'neutral', sub: '24h change' })
    }
  }

  if (tiles.length === 0) return null

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <h2 className="font-bold text-white mb-4 flex items-center gap-2">
        <span>🌡️</span> Macro Heatmap
      </h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
        {tiles.map((t, i) => (
          <div key={i} className={`rounded-lg border p-3 flex flex-col gap-1 ${getTileColor(t.sentiment)}`}>
            <span className="text-xs font-semibold uppercase tracking-wider opacity-70">{t.label}</span>
            <span className="text-base font-bold font-mono leading-tight">{t.value}</span>
            {t.sub && <span className="text-xs opacity-60">{t.sub}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
