import { Reveal } from '../ui/Reveal'
import { INFRASTRUCTURE_ITEMS } from '../../data/landingContent'

export function InfrastructureStrip() {
  return (
    <section
      className="py-12 sm:py-16 bg-[#070d1a] border-y border-slate-800/60"
      aria-label="Research infrastructure capabilities"
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <Reveal>
          <p className="text-center text-xs font-semibold uppercase tracking-[0.15em] text-slate-600 mb-8">
            Underlying Research Infrastructure
          </p>
        </Reveal>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4">
          {INFRASTRUCTURE_ITEMS.map((item, i) => (
            <Reveal key={item.label} delay={i * 80}>
              <div className="flex flex-col items-center text-center p-4 rounded-xl bg-[#0a1220] border border-slate-800 hover:border-slate-700 transition-colors">
                <span className="text-xl text-cyan-500/60 mb-2 font-mono">{item.icon}</span>
                <span className="text-sm font-semibold text-slate-300 mb-1">{item.label}</span>
                <span className="text-xs text-slate-600 leading-relaxed">{item.description}</span>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}
