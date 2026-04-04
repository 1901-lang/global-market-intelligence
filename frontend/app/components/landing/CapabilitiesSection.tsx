import { Reveal } from '../ui/Reveal'
import { SectionHeading } from '../ui/SectionHeading'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { CAPABILITY_CARDS } from '../../data/landingContent'

export function CapabilitiesSection() {
  return (
    <section
      id="capabilities"
      className="py-20 sm:py-28 bg-[#0d1117]"
      aria-label="Core platform capabilities"
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <Reveal className="mb-14">
          <SectionHeading
            eyebrow="Intelligence System Modules"
            title="Core Capabilities"
            subtitle="Six specialised intelligence modules working in coordination to produce structured, explainable market intelligence."
          />
        </Reveal>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {CAPABILITY_CARDS.map((card, i) => (
            <Reveal key={card.title} delay={i * 70}>
              <Card
                variant="elevated"
                className="p-6 h-full flex flex-col gap-4"
              >
                <div className="flex items-start justify-between">
                  <div className="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center flex-shrink-0">
                    <span className="text-cyan-400 text-lg font-mono">{card.icon}</span>
                  </div>
                  <Badge variant="label">{card.tag}</Badge>
                </div>
                <div className="space-y-2">
                  <h3 className="text-sm font-bold text-white leading-snug">{card.title}</h3>
                  <p className="text-xs text-slate-500 leading-relaxed">{card.description}</p>
                </div>
              </Card>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}
