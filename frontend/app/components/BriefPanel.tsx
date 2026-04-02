'use client'

import SignalBadge from './SignalBadge'

interface KeySignal {
  asset: string
  signal: string
  confidence: number
}

interface Brief {
  id?: number
  content: string
  key_signals?: KeySignal[]
  risks?: string[]
  date?: string
  timestamp?: string
}

interface BriefPanelProps {
  brief: Brief | null
  loading?: boolean
}

export default function BriefPanel({ brief, loading }: BriefPanelProps) {
  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-bold text-white flex items-center gap-2">
          <span>📰</span> Daily Intelligence Brief
        </h2>
        {brief?.date && (
          <span className="text-xs text-gray-500 bg-[#21262d] px-2 py-1 rounded">
            {brief.date}
          </span>
        )}
      </div>

      {loading ? (
        <div className="text-center text-gray-500 text-sm py-8">
          <div className="animate-spin w-6 h-6 border-2 border-[#58a6ff] border-t-transparent rounded-full mx-auto mb-2" />
          Generating brief…
        </div>
      ) : brief ? (
        <div>
          <div className="prose prose-sm max-w-none">
            <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
              {brief.content}
            </p>
          </div>

          {brief.key_signals && brief.key_signals.length > 0 && (
            <div className="mt-4 border-t border-[#30363d] pt-4">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Key Signals
              </h3>
              <div className="flex flex-wrap gap-2">
                {brief.key_signals.map((s, i) => (
                  <div key={i} className="flex items-center gap-1.5 bg-[#21262d] rounded-lg px-2 py-1">
                    <span className="text-xs font-semibold text-white">{s.asset}</span>
                    <SignalBadge signal={s.signal} size="sm" />
                    <span className="text-xs text-gray-500">{(s.confidence * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {brief.risks && brief.risks.length > 0 && (
            <div className="mt-4 border-t border-[#30363d] pt-4">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                ⚠️ Risk Factors
              </h3>
              <ul className="space-y-1">
                {brief.risks.map((risk, i) => (
                  <li key={i} className="text-xs text-amber-400/80 flex items-start gap-1.5">
                    <span className="mt-0.5">•</span>
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center text-gray-500 text-sm py-8">
          No brief available yet.<br />
          <span className="text-xs">Brief generates daily or on demand.</span>
        </div>
      )}
    </div>
  )
}
