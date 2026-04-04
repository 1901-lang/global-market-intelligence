import { Reveal } from '../ui/Reveal'
import { SectionHeading } from '../ui/SectionHeading'
import { Card } from '../ui/Card'
import { TARGET_USERS } from '../../data/landingContent'

export function TargetUsersSection() {
  return (
    <section
      id="users"
      className="py-20 sm:py-28 bg-[#070d1a]"
      aria-label="Target users and use cases"
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <Reveal className="mb-14">
          <SectionHeading
            eyebrow="Who It's For"
            title="Built for institutional users."
            subtitle="Decision support for professionals who require structured, auditable intelligence — not autonomous execution or consumer alerts."
          />
        </Reveal>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {TARGET_USERS.map((user, i) => (
            <Reveal key={user.role} delay={i * 70}>
              <Card variant="default" className="p-5 h-full flex flex-col gap-3">
                <div className="w-9 h-9 rounded-lg bg-slate-900 border border-slate-700 flex items-center justify-center flex-shrink-0">
                  <span className="text-slate-400 font-mono">{user.icon}</span>
                </div>
                <div className="space-y-1.5 flex-1">
                  <h3 className="text-sm font-bold text-white leading-snug">{user.role}</h3>
                  <p className="text-xs text-slate-500 leading-relaxed">{user.description}</p>
                </div>
                <div className="pt-2 border-t border-slate-800">
                  <span className="text-xs text-cyan-500/70 font-mono">{user.useCase}</span>
                </div>
              </Card>
            </Reveal>
          ))}
        </div>

        {/* Not for section */}
        <Reveal className="mt-10">
          <div className="bg-[#0a1220] border border-slate-800 rounded-xl p-5 flex flex-wrap gap-x-8 gap-y-2 items-center">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-600">
              Not for:
            </span>
            {[
              'Retail trading apps',
              'Autonomous execution',
              'Consumer finance',
              'Crypto exchanges',
              'Generic chat assistants',
            ].map(item => (
              <span key={item} className="text-xs text-slate-600 flex items-center gap-1.5">
                <span className="text-slate-700">—</span>
                {item}
              </span>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  )
}
