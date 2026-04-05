'use client'

import { useState } from 'react'
import SignalBadge from './SignalBadge'
import ReactMarkdown from 'react-markdown'

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
  assets?: { symbol: string; price: number; change_24h?: number }[]
}

function formatRelative(ts: string): string {
  const diff = (Date.now() - new Date(ts).getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} hrs ago`
  return `${Math.floor(diff / 86400)} days ago`
}

export default function BriefPanel({ brief, loading, assets }: BriefPanelProps) {
  const [copied, setCopied] = useState(false)

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h2 className="font-bold text-white flex items-center gap-2">
          <span>📰</span> Daily Intelligence Brief
        </h2>
        <div className="flex items-center gap-2 flex-wrap">
          {brief?.date && (
            <span className="text-xs text-gray-500 bg-[#21262d] px-2 py-1 rounded">
              {brief.date}
            </span>
          )}
          {brief && (
            <button
              onClick={() => {
                navigator.clipboard.writeText(brief.content).catch(() => {})
                setCopied(true)
                setTimeout(() => setCopied(false), 2000)
              }}
              className="px-2 py-1 text-xs rounded border border-[#30363d] text-gray-400 hover:text-white transition-colors"
            >
              {copied ? '✓ Copied' : '📋 Copy'}
            </button>
          )}
        </div>
      </div>
      {brief?.timestamp && (
        <span className="text-xs text-gray-600 block mb-3">Generated {formatRelative(brief.timestamp)}</span>
      )}

      {loading ? (
        <div className="text-center text-gray-500 text-sm py-8">
          <div className="animate-spin w-6 h-6 border-2 border-[#58a6ff] border-t-transparent rounded-full mx-auto mb-2" />
          Generating brief…
        </div>
      ) : brief ? (
        <div>
          <div className="prose prose-sm max-w-none text-sm leading-relaxed">
            <ReactMarkdown
              components={{
                h1: ({children}) => <h1 className="text-white font-bold text-base mt-3 mb-1">{children}</h1>,
                h2: ({children}) => <h2 className="text-white font-semibold text-sm mt-2 mb-1">{children}</h2>,
                h3: ({children}) => <h3 className="text-gray-200 font-medium text-sm mt-2 mb-0.5">{children}</h3>,
                p: ({children}) => <p className="text-gray-300 mb-2">{children}</p>,
                strong: ({children}) => <strong className="text-white font-semibold">{children}</strong>,
                ul: ({children}) => <ul className="list-disc list-inside text-gray-300 space-y-0.5 mb-2">{children}</ul>,
                li: ({children}) => <li className="text-gray-300">{children}</li>,
              }}
            >
              {brief.content}
            </ReactMarkdown>
          </div>

          {brief.key_signals && brief.key_signals.length > 0 && (
            <div className="mt-4 border-t border-[#30363d] pt-4">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                Key Signals
              </h3>
              <div className="flex flex-wrap gap-2">
                {brief.key_signals.map((s, i) => {
                  const a = (assets || []).find(x => x.symbol === s.asset)
                  return (
                    <div key={i} className="flex items-center gap-1.5 bg-[#21262d] rounded-lg px-2 py-1">
                      <span className="text-xs font-semibold text-white">{s.asset}</span>
                      <SignalBadge signal={s.signal} size="sm" />
                      <span className="text-xs text-gray-500">{(s.confidence * 100).toFixed(0)}%</span>
                      {a ? (
                        <span className="text-gray-600 ml-1">
                          ${a.price >= 1000 ? a.price.toLocaleString('en-US', { maximumFractionDigits: 0 }) : a.price.toFixed(2)}
                          {a.change_24h != null ? ` ${a.change_24h >= 0 ? '+' : ''}${a.change_24h.toFixed(1)}%` : ''}
                        </span>
                      ) : null}
                    </div>
                  )
                })}
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
