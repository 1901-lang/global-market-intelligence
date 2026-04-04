import { Reveal } from '../ui/Reveal'

const COMPARISON_CARDS = [
  {
    label: 'Raw Terminal',
    description: 'Price feeds and order book data. No context, no narrative, no continuity.',
    highlight: false,
    items: ['Raw price data', 'No thesis tracking', 'No regime context', 'No explainability'],
  },
  {
    label: 'Analyst Agent Workflow',
    description: 'Structured intelligence with explainable signals, thesis continuity, and auditable outputs.',
    highlight: true,
    items: ['Regime-aware signals', 'Thesis state tracking', 'Multi-model consensus', 'Full provenance'],
  },
  {
    label: 'Generic AI Chat',
    description: 'Conversational responses with no persistent state, no source attribution, no auditability.',
    highlight: false,
    items: ['No persistent state', 'No source attribution', 'No signal confidence', 'Not auditable'],
  },
]

export function ProblemSolutionSection() {
  return (
    <section
      id="problem"
      className="py-20 sm:py-28 bg-[#0d1117]"
      aria-label="Problem and solution overview"
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16 items-center">

          {/* Left — positioning text */}
          <Reveal>
            <div className="space-y-6">
              <p className="text-xs font-semibold uppercase tracking-[0.15em] text-cyan-500">
                The Problem
              </p>
              <h2 className="text-3xl sm:text-4xl font-bold text-white leading-tight">
                Professionals need thesis tracking,
                <span className="text-slate-500"> not just commentary.</span>
              </h2>
              <div className="space-y-4 text-slate-400 text-sm leading-relaxed">
                <p>
                  Raw data terminals provide price feeds without analytical structure.
                  Generic AI assistants generate plausible-sounding responses without
                  source attribution or auditable reasoning chains.
                </p>
                <p>
                  Black-box signals offer no explainability. One-shot analysis has no
                  continuity. Institutional users require structured, auditable research
                  outputs they can defend and build upon.
                </p>
              </div>
              <ul className="space-y-2">
                {[
                  'Structured, thesis-driven research workflows',
                  'Explainable signals with evidence chains',
                  'Multi-model consensus with dissent visibility',
                  'Regime-aware analysis and alerts',
                  'Full provenance and audit trail per output',
                ].map(item => (
                  <li key={item} className="flex items-start gap-2.5 text-sm text-slate-300">
                    <span className="text-cyan-500 mt-0.5 flex-shrink-0">◈</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>

          {/* Right — comparison cards */}
          <div className="space-y-3">
            {COMPARISON_CARDS.map((card, i) => (
              <Reveal key={card.label} delay={i * 100}>
                <div
                  className={`rounded-xl p-5 border transition-colors ${
                    card.highlight
                      ? 'bg-gradient-to-br from-[#0a1628] to-[#0d1e34] border-cyan-500/40 shadow-[0_0_30px_rgba(0,212,255,0.08)]'
                      : 'bg-[#0a1220] border-slate-800'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={`text-sm font-semibold ${
                        card.highlight ? 'text-cyan-400' : 'text-slate-500'
                      }`}
                    >
                      {card.label}
                    </span>
                    {card.highlight && (
                      <span className="text-xs bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 px-2 py-0.5 rounded-full">
                        Preferred
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mb-3 leading-relaxed">{card.description}</p>
                  <div className="flex flex-wrap gap-2">
                    {card.items.map(item => (
                      <span
                        key={item}
                        className={`text-xs px-2 py-0.5 rounded-full border ${
                          card.highlight
                            ? 'bg-cyan-500/5 border-cyan-500/20 text-cyan-500/80'
                            : 'bg-slate-900 border-slate-700 text-slate-600'
                        }`}
                      >
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
