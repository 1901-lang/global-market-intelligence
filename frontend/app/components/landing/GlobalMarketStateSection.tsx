'use client'

import { useState } from 'react'
import { Reveal } from '../ui/Reveal'
import { SectionHeading } from '../ui/SectionHeading'
import { Badge } from '../ui/Badge'
import { MARKET_NODES, type MarketNode } from '../../data/landingContent'

// Regime color mapping
const regimeColor: Record<string, string> = {
  'Risk-On': 'text-emerald-400',
  'Risk-Off': 'text-red-400',
  'Transitional': 'text-amber-400',
  'Reflationary': 'text-cyan-400',
}

function NodeMarker({
  node,
  selected,
  onSelect,
}: {
  node: MarketNode
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      onClick={onSelect}
      style={{ top: node.position.top, left: node.position.left }}
      className="absolute -translate-x-1/2 -translate-y-1/2 group"
      aria-label={`View ${node.city} market data`}
      aria-pressed={selected}
    >
      <div
        className={`relative flex items-center justify-center transition-all duration-200 ${
          selected ? 'scale-125' : 'hover:scale-110'
        }`}
      >
        {/* Pulse ring */}
        <span
          className={`absolute inline-flex rounded-full opacity-40 ${
            node.positive ? 'bg-emerald-500' : 'bg-red-500'
          } ${selected ? 'h-8 w-8 animate-ping' : 'h-6 w-6'}`}
        />
        {/* Core dot */}
        <span
          className={`relative inline-flex rounded-full h-3 w-3 border-2 ${
            node.positive
              ? 'bg-emerald-500 border-emerald-400'
              : 'bg-red-500 border-red-400'
          }`}
        />
        {/* Label */}
        <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[10px] font-mono text-slate-400 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity">
          {node.city}
        </span>
      </div>
    </button>
  )
}

function DetailsPanel({ node }: { node: MarketNode | null }) {
  if (!node) {
    return (
      <div className="flex items-center justify-center h-full text-center p-6">
        <p className="text-sm text-slate-600">Select a market node to view details</p>
      </div>
    )
  }

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-bold text-white text-base">{node.city}</h3>
          <p className="text-xs text-slate-500 mt-0.5">{node.market}</p>
        </div>
        <Badge variant={node.positive ? 'live' : 'label'}>
          {node.positive ? 'Active' : 'Closed'}
        </Badge>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {[
          { label: 'Index', value: node.index },
          { label: '24H Change', value: node.change },
          { label: '24H Volume', value: node.volume },
          { label: 'Active Models', value: `${node.models} running` },
        ].map(item => (
          <div key={item.label} className="bg-[#070d1a] rounded-lg p-2.5 border border-slate-800">
            <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">{item.label}</p>
            <p className="text-sm font-mono font-semibold text-white">{item.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-[#070d1a] rounded-lg p-3 border border-slate-800">
        <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Detected Regime</p>
        <p className={`text-sm font-semibold font-mono ${regimeColor[node.regime] || 'text-slate-300'}`}>
          {node.regime}
        </p>
      </div>

      <div className="bg-[#070d1a] rounded-lg p-3 border border-slate-800">
        <p className="text-xs text-slate-600 uppercase tracking-wider mb-1">Intelligence Stream</p>
        <div className="space-y-1.5 font-mono text-xs">
          <p className="text-cyan-500">→ Regime change: {node.regime}</p>
          <p className="text-slate-500">→ {node.models} models running consensus loop</p>
          <p className="text-slate-600">→ Next update in 45s</p>
        </div>
      </div>
    </div>
  )
}

export function GlobalMarketStateSection() {
  const [selected, setSelected] = useState<MarketNode | null>(null)

  return (
    <section
      id="global-market"
      className="py-20 sm:py-28 bg-[#070d1a]"
      aria-label="Global market state interface"
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <Reveal className="text-center mb-12">
          <SectionHeading
            eyebrow="Global Command Layer"
            title="Global Market State Interface"
            subtitle="Visibility into liquidity hubs, regime deployments, and active model states across global markets."
          />
        </Reveal>

        <Reveal>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Map panel */}
            <div className="lg:col-span-2 bg-[#0a1220] border border-slate-800 rounded-xl overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800 bg-[#070d1a]">
                <span className="text-xs font-mono text-slate-500">GLOBAL MARKET STATE — LIVE VIEW</span>
                <Badge variant="live" pulse>Live</Badge>
              </div>

              {/* SVG world map placeholder with positioned nodes */}
              <div className="relative h-64 sm:h-80 bg-[#0a1220] overflow-hidden">
                {/* Simplified continents outline using SVG */}
                <svg
                  viewBox="0 0 800 400"
                  className="absolute inset-0 w-full h-full opacity-10"
                  aria-hidden="true"
                >
                  {/* Simplified continent outlines */}
                  {[
                    'M80,60 L200,50 L220,80 L210,140 L180,160 L160,150 L130,170 L100,160 L80,120 Z',
                    'M160,180 L220,170 L240,220 L230,290 L200,310 L170,300 L155,250 Z',
                    'M340,40 L420,35 L440,70 L410,100 L370,110 L340,90 Z',
                    'M360,120 L440,110 L460,180 L450,260 L400,280 L350,260 L340,200 Z',
                    'M440,30 L660,25 L680,80 L650,130 L560,150 L460,130 L440,90 Z',
                    'M600,220 L700,210 L720,270 L680,300 L610,290 Z',
                  ].map((d, i) => (
                    <path key={i} d={d} fill="#22d3ee" />
                  ))}
                </svg>

                {/* Grid overlay */}
                <div className="absolute inset-0 bg-grid-pattern opacity-30" aria-hidden="true" />

                {/* Market node markers */}
                {MARKET_NODES.map(node => (
                  <NodeMarker
                    key={node.city}
                    node={node}
                    selected={selected?.city === node.city}
                    onSelect={() => setSelected(prev => prev?.city === node.city ? null : node)}
                  />
                ))}

                {/* Legend */}
                <div className="absolute bottom-3 left-3 flex items-center gap-4 text-xs" aria-label="Map legend">
                  <span className="flex items-center gap-1.5 text-slate-600">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    Active session
                  </span>
                  <span className="flex items-center gap-1.5 text-slate-600">
                    <span className="w-2 h-2 rounded-full bg-red-500" />
                    Closed / risk-off
                  </span>
                </div>
              </div>

              {/* Market node list */}
              <div className="p-3 flex flex-wrap gap-2 border-t border-slate-800">
                {MARKET_NODES.map(node => (
                  <button
                    key={node.city}
                    onClick={() => setSelected(prev => prev?.city === node.city ? null : node)}
                    className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                      selected?.city === node.city
                        ? 'border-cyan-500/60 bg-cyan-500/10 text-cyan-400'
                        : 'border-slate-800 bg-slate-900 text-slate-500 hover:border-slate-700 hover:text-slate-300'
                    }`}
                    aria-pressed={selected?.city === node.city}
                  >
                    {node.city}
                  </button>
                ))}
              </div>
            </div>

            {/* Details panel */}
            <div className="lg:col-span-1 bg-[#0a1220] border border-slate-800 rounded-xl min-h-[200px]">
              <div className="px-4 py-2.5 border-b border-slate-800 bg-[#070d1a]">
                <span className="text-xs font-mono text-slate-500">MARKET NODE DETAIL</span>
              </div>
              <DetailsPanel node={selected} />
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
