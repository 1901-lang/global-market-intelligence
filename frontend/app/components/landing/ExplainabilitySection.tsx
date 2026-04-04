'use client'

import { useState } from 'react'
import { Reveal } from '../ui/Reveal'
import { SectionHeading } from '../ui/SectionHeading'
import { TerminalPanel } from '../ui/TerminalPanel'
import { EXPLAINABILITY_TABS } from '../../data/landingContent'

export function ExplainabilitySection() {
  const [activeTab, setActiveTab] = useState(EXPLAINABILITY_TABS[0].id)

  const current = EXPLAINABILITY_TABS.find(t => t.id === activeTab) ?? EXPLAINABILITY_TABS[0]

  return (
    <section
      id="explainability"
      className="py-20 sm:py-28 bg-[#0d1117]"
      aria-label="Explainability and auditability"
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <Reveal className="mb-14">
          <SectionHeading
            eyebrow="Explainability & Provenance"
            title="Every output is auditable."
            subtitle="Confidence levels, evidence chains, contradictions, invalidation conditions, and full data provenance on every signal."
          />
        </Reveal>

        <Reveal>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Tabs */}
            <div className="lg:col-span-1 space-y-2">
              {EXPLAINABILITY_TABS.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full text-left px-4 py-3.5 rounded-xl border transition-all duration-200 ${
                    activeTab === tab.id
                      ? 'bg-[#0a1628] border-cyan-500/40 text-white shadow-[0_0_20px_rgba(0,212,255,0.06)]'
                      : 'bg-[#0a1220] border-slate-800 text-slate-500 hover:border-slate-700 hover:text-slate-300'
                  }`}
                  aria-pressed={activeTab === tab.id}
                >
                  <span className="text-sm font-semibold block">{tab.label}</span>
                </button>
              ))}
            </div>

            {/* Detail panel */}
            <div className="lg:col-span-2">
              <TerminalPanel
                title={`SYSTEM › ${current.label.toUpperCase()}`}
                status="active"
              >
                <div className="p-5 space-y-5">
                  <div>
                    <h3 className="text-base font-bold text-white mb-1.5">{current.heading}</h3>
                    <p className="text-sm text-slate-400 leading-relaxed">{current.description}</p>
                  </div>

                  <div className="space-y-2">
                    {current.features.map((f, i) => (
                      <div key={i} className="flex items-start gap-2.5">
                        <span className="text-cyan-500 mt-0.5 flex-shrink-0 font-mono text-xs">›</span>
                        <span className="text-sm text-slate-300 leading-snug">{f}</span>
                      </div>
                    ))}
                  </div>

                  {/* Mock output sample */}
                  <div className="bg-[#070d1a] rounded-lg p-4 border border-slate-800 font-mono text-xs space-y-1.5">
                    <div className="flex items-center gap-2 mb-2.5">
                      <span className="text-cyan-500/60 text-[10px] uppercase tracking-wider">Sample output</span>
                    </div>
                    <p className="text-slate-500">
                      <span className="text-slate-600">asset:</span>{' '}
                      <span className="text-white">BTC/USD</span>
                    </p>
                    <p className="text-slate-500">
                      <span className="text-slate-600">final_signal:</span>{' '}
                      <span className="text-emerald-400">BUY</span>
                    </p>
                    <p className="text-slate-500">
                      <span className="text-slate-600">confidence:</span>{' '}
                      <span className="text-cyan-400">0.84</span>
                    </p>
                    <p className="text-slate-500">
                      <span className="text-slate-600">agreement_level:</span>{' '}
                      <span className="text-white">high</span>
                    </p>
                    <p className="text-slate-500">
                      <span className="text-slate-600">dissenting_models:</span>{' '}
                      <span className="text-amber-400">[]</span>
                    </p>
                    <p className="text-slate-500">
                      <span className="text-slate-600">regime:</span>{' '}
                      <span className="text-cyan-400">Risk-On / Reflationary</span>
                    </p>
                    <p className="text-slate-500">
                      <span className="text-slate-600">reasoning:</span>{' '}
                      <span className="text-slate-400">[&quot;Strong on-chain inflow&quot;, &quot;DXY weakness&quot;, &quot;Positive sentiment&quot;]</span>
                    </p>
                  </div>
                </div>
              </TerminalPanel>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
