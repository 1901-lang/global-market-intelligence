import { Reveal } from '../ui/Reveal'
import { SectionHeading } from '../ui/SectionHeading'
import { METHODOLOGY_STEPS } from '../../data/landingContent'

export function MethodologySection() {
  return (
    <section
      id="methodology"
      className="py-20 sm:py-28 bg-[#070d1a]"
      aria-label="Platform methodology and pipeline"
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <Reveal className="mb-14">
          <SectionHeading
            eyebrow="System Architecture"
            title="Intelligence Pipeline"
            subtitle="Five operational stages transform raw market context into structured, explainable intelligence outputs."
          />
        </Reveal>

        {/* Desktop: horizontal connector strip */}
        <div className="hidden lg:block">
          <Reveal>
            <div className="relative flex items-start gap-0">
              {/* Connector line */}
              <div
                className="absolute top-7 left-[10%] right-[10%] h-px bg-gradient-to-r from-transparent via-cyan-500/30 to-transparent"
                aria-hidden="true"
              />

              {METHODOLOGY_STEPS.map((step) => (
                <div key={step.label} className="flex-1 flex flex-col items-center text-center px-3">
                  {/* Step circle */}
                  <div className="relative z-10 w-14 h-14 rounded-full bg-[#0a1220] border-2 border-cyan-500/40 flex flex-col items-center justify-center mb-4 shadow-[0_0_16px_rgba(0,212,255,0.15)]">
                    <span className="text-[10px] font-mono font-bold text-cyan-400 leading-none">{step.label}</span>
                    <span className="text-[9px] text-slate-600 font-mono">{`0${step.step}`}</span>
                  </div>
                  <h3 className="text-sm font-bold text-white mb-1.5">{step.title}</h3>
                  <p className="text-xs text-slate-500 leading-relaxed mb-2">{step.description}</p>
                  <span className="text-[10px] font-mono text-cyan-500/60 bg-cyan-500/5 border border-cyan-500/10 px-2 py-0.5 rounded-full">
                    {step.detail}
                  </span>
                </div>
              ))}
            </div>
          </Reveal>
        </div>

        {/* Mobile: vertical stack */}
        <div className="lg:hidden space-y-4">
          {METHODOLOGY_STEPS.map((step, i) => (
            <Reveal key={step.label} delay={i * 80}>
              <div className="flex gap-4 p-4 rounded-xl bg-[#0a1220] border border-slate-800">
                <div className="w-12 h-12 rounded-full bg-[#070d1a] border-2 border-cyan-500/40 flex flex-col items-center justify-center flex-shrink-0 shadow-[0_0_12px_rgba(0,212,255,0.1)]">
                  <span className="text-[10px] font-mono font-bold text-cyan-400">{step.label}</span>
                </div>
                <div className="space-y-1 min-w-0">
                  <h3 className="text-sm font-bold text-white">{step.title}</h3>
                  <p className="text-xs text-slate-500 leading-relaxed">{step.description}</p>
                  <span className="text-[10px] font-mono text-cyan-500/60">{step.detail}</span>
                </div>
              </div>
            </Reveal>
          ))}
        </div>

        {/* Backend pipeline note */}
        <Reveal className="mt-12">
          <div className="bg-[#0a1220] border border-slate-800 rounded-xl p-5 text-center">
            <p className="text-xs text-slate-600 font-mono">
              UPDATE CYCLE · 60s interval · Background scheduler ·
              <span className="text-slate-500"> OpenAI · Anthropic · Gemini</span> ·
              <span className="text-cyan-500/60"> Adaptive model weighting</span>
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
