'use client'

import { Reveal } from '../ui/Reveal'
import { TerminalPanel } from '../ui/TerminalPanel'
import { MetricPill } from '../ui/MetricPill'
import { Badge } from '../ui/Badge'
import { TICKER_ITEMS } from '../../data/landingContent'

// Signal colour mapping matches the real ConsensusResult.final_signal values: BUY, SELL, HOLD
function SignalChip({ signal }: { signal: 'BUY' | 'SELL' | 'HOLD' }) {
  const styles = {
    BUY: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    SELL: 'text-red-400 bg-red-500/10 border-red-500/30',
    HOLD: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  }
  return (
    <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${styles[signal]}`}>
      {signal}
    </span>
  )
}

function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-cyan-500/70 rounded-full"
          style={{ width: `${value * 100}%` }}
        />
      </div>
      <span className="text-xs font-mono text-slate-500 w-8">{Math.round(value * 100)}%</span>
    </div>
  )
}

// Static mock consensus data — matches ConsensusResult schema shape
const MOCK_CONSENSUS = [
  { asset: 'BTC', final_signal: 'BUY' as const, confidence: 0.84, agreement_level: 'high', regime: 'Risk-On' },
  { asset: 'ETH', final_signal: 'HOLD' as const, confidence: 0.61, agreement_level: 'medium', regime: 'Neutral' },
  { asset: 'GOLD', final_signal: 'BUY' as const, confidence: 0.77, agreement_level: 'high', regime: 'Risk-Off Hedge' },
  { asset: 'OIL', final_signal: 'SELL' as const, confidence: 0.69, agreement_level: 'medium', regime: 'Demand Slowdown' },
]

// Static mock macro context — matches MarketContext schema shape
const MOCK_CONTEXT = {
  usd_index: 104.5,
  bond_yield_10y: 4.82,
  vix: 14.32,
  news_sentiment: 0.14,
}

export function DashboardMockup() {
  return (
    <section
      className="relative bg-[#0d1117] py-4 px-4 sm:px-6"
      aria-label="Platform dashboard mockup"
    >
      <Reveal className="max-w-6xl mx-auto">
        <TerminalPanel
          title="WORKSPACE: MACRO ALPHA"
          status="active"
          statusLabel="DATA PIPELINE & ANALYST TOOLS ACTIVE"
        >
          {/* Ticker strip — doubles the items for seamless loop */}
          <div className="overflow-hidden border-b border-slate-800/60 bg-[#070d1a]" aria-label="Asset ticker">
            <div className="flex ticker-animate whitespace-nowrap py-2.5 px-2 gap-6">
              {[...TICKER_ITEMS, ...TICKER_ITEMS].map((item, i) => (
                <span key={i} className="inline-flex items-center gap-2 text-xs flex-shrink-0">
                  <span className="font-mono text-slate-500 text-[10px]">{item.symbol}</span>
                  <span className="font-mono font-semibold text-white">{item.price}</span>
                  <span className={`font-mono text-[11px] ${item.positive ? 'text-emerald-400' : 'text-red-400'}`}>
                    {item.change}
                  </span>
                </span>
              ))}
            </div>
          </div>

          {/* Main dashboard grid */}
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-12 gap-3">

            {/* Signal + consensus card — lg:col-span-5 */}
            <div className="lg:col-span-5 bg-[#0a1220] border border-slate-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Consensus Signals
                </span>
                <Badge variant="system" pulse>Live</Badge>
              </div>

              <div className="space-y-3">
                {MOCK_CONSENSUS.map(c => (
                  <div key={c.asset} className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <span className="font-mono font-bold text-white text-sm w-10">{c.asset}</span>
                        <SignalChip signal={c.final_signal} />
                        <span className="text-xs text-slate-600 hidden sm:block">{c.regime}</span>
                      </div>
                      <span className={`text-xs font-medium ${c.agreement_level === 'high' ? 'text-cyan-500' : 'text-slate-500'}`}>
                        {c.agreement_level}
                      </span>
                    </div>
                    <ConfidenceBar value={c.confidence} />
                  </div>
                ))}
              </div>
            </div>

            {/* Macro context card — lg:col-span-3 */}
            <div className="lg:col-span-3 bg-[#0a1220] border border-slate-800 rounded-xl p-4 space-y-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block">
                Macro Context
              </span>
              <div className="space-y-2.5">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-500">DXY</span>
                  <span className="font-mono text-sm text-white">{MOCK_CONTEXT.usd_index.toFixed(1)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-500">10Y Yield</span>
                  <span className="font-mono text-sm text-red-400">{MOCK_CONTEXT.bond_yield_10y}%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-500">VIX</span>
                  <span className="font-mono text-sm text-white">{MOCK_CONTEXT.vix.toFixed(1)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-500">Sentiment</span>
                  <span className="font-mono text-sm text-emerald-400">
                    {MOCK_CONTEXT.news_sentiment > 0 ? 'Positive' : MOCK_CONTEXT.news_sentiment < 0 ? 'Negative' : 'Neutral'}
                  </span>
                </div>
              </div>
              <div className="pt-2 border-t border-slate-800">
                <span className="text-xs text-slate-600">Regime Detection</span>
                <p className="text-xs text-cyan-400 font-medium mt-1">Risk-On / Reflationary</p>
              </div>
            </div>

            {/* Live event stream — lg:col-span-4 */}
            <div className="lg:col-span-4 bg-[#0a1220] border border-slate-800 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Intelligence Stream
                </span>
                <span className="text-[10px] font-mono text-slate-600">LIVE</span>
              </div>
              <div className="space-y-2.5 font-mono text-xs">
                {[
                  { time: '09:02', msg: 'BTC consensus updated → BUY (84%)', color: 'text-emerald-400' },
                  { time: '09:00', msg: 'Pre-market narrative generated', color: 'text-cyan-400' },
                  { time: '08:58', msg: 'GOLD signal confirmed: BUY / high agreement', color: 'text-emerald-400' },
                  { time: '08:55', msg: 'OIL model debate: dissent from gemini', color: 'text-amber-400' },
                  { time: '08:50', msg: 'DXY spike detected — regime check triggered', color: 'text-red-400' },
                  { time: '08:45', msg: 'Update cycle complete. Assets: 8, Signals: 8', color: 'text-slate-500' },
                ].map((evt, i) => (
                  <div key={i} className="flex gap-2 items-start">
                    <span className="text-slate-700 flex-shrink-0">{evt.time}</span>
                    <span className={evt.color}>{evt.msg}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Correlation strip — lg:col-span-12 */}
            <div className="lg:col-span-12 bg-[#0a1220] border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Cross-Asset Correlation
                </span>
                <span className="text-xs text-slate-600 font-mono">60-period Pearson</span>
              </div>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { pair: 'BTC / ETH', value: 0.94, label: 'Very High' },
                  { pair: 'BTC / GOLD', value: 0.31, label: 'Low' },
                  { pair: 'GOLD / DXY', value: -0.72, label: 'Inverse' },
                  { pair: 'OIL / SPX', value: 0.48, label: 'Moderate' },
                ].map(c => (
                  <div key={c.pair} className="text-center">
                    <div className="text-xs text-slate-600 mb-1">{c.pair}</div>
                    <div className={`text-base font-mono font-bold ${c.value >= 0.7 ? 'text-cyan-400' : c.value < 0 ? 'text-red-400' : 'text-slate-300'}`}>
                      {c.value > 0 ? '+' : ''}{c.value.toFixed(2)}
                    </div>
                    <div className="text-xs text-slate-600">{c.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Mock metric pills strip */}
          <div className="px-4 pb-4 flex flex-wrap gap-2" aria-label="Platform metrics">
            <MetricPill label="Models" value="3 active" />
            <MetricPill label="Assets" value="8 tracked" />
            <MetricPill label="Cycle" value="60s" />
            <MetricPill label="Consensus" value="4 signals" trend="up" />
          </div>
        </TerminalPanel>
      </Reveal>
    </section>
  )
}
