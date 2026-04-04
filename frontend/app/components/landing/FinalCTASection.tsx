'use client'

import { useState, useCallback } from 'react'
import Link from 'next/link'
import { Reveal } from '../ui/Reveal'
import { Button } from '../ui/Button'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type Step = 'idle' | 'loading' | 'success' | 'error'

export function FinalCTASection() {
  const [step, setStep] = useState<Step>('idle')
  const [name, setName] = useState('')
  const [interest, setInterest] = useState('')
  const [experience, setExperience] = useState('')
  const [guide, setGuide] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  /**
   * POST /api/agents/support/onboard — no auth required
   * Body: { name?: string, interest?: string, experience?: string }
   * Response: { guide: string }
   */
  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault()
      if (!name.trim()) return
      setStep('loading')
      setErrorMsg('')
      try {
        const trimOrUndefined = (v: string) => v.trim() || undefined
        const res = await fetch(`${API_URL}/api/agents/support/onboard`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: trimOrUndefined(name),
            interest: trimOrUndefined(interest),
            experience: trimOrUndefined(experience),
          }),
        })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          setErrorMsg(data.detail || 'Submission failed. Please try again.')
          setStep('error')
          return
        }
        const data = await res.json()
        setGuide(data.guide || '')
        setStep('success')
      } catch {
        setErrorMsg('Unable to connect to the platform. Please try again shortly.')
        setStep('error')
      }
    },
    [name, interest, experience],
  )

  return (
    <section
      id="access"
      className="relative py-24 sm:py-32 bg-[#050c1a] overflow-hidden"
      aria-label="Request platform access"
    >
      {/* Background */}
      <div className="absolute inset-0 bg-grid-pattern opacity-40 pointer-events-none" aria-hidden="true" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_60%_at_50%_100%,rgba(0,212,255,0.08),transparent)] pointer-events-none" aria-hidden="true" />

      <div className="relative z-10 max-w-2xl mx-auto px-4 sm:px-6 text-center">
        <Reveal>
          <div className="space-y-6 mb-12">
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-cyan-500">
              Request Access
            </p>
            <h2 className="text-3xl sm:text-5xl font-bold text-white leading-tight">
              Institutional intelligence,
              <br />
              <span className="text-slate-500">ready to deploy.</span>
            </h2>
            <p className="text-slate-400 text-base sm:text-lg leading-relaxed">
              Join research desks, macro teams, and institutional strategy groups
              using structured market intelligence to support investment decision-making.
            </p>
          </div>
        </Reveal>

        {step === 'success' ? (
          <Reveal>
            <div className="bg-[#0a1628] border border-cyan-500/30 rounded-2xl p-8 text-left space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
                  <span className="text-emerald-400 text-sm">✓</span>
                </div>
                <h3 className="text-base font-semibold text-white">Welcome to the platform, {name}.</h3>
              </div>
              {guide && (
                <p className="text-sm text-slate-400 leading-relaxed">{guide}</p>
              )}
              <div className="flex flex-col sm:flex-row gap-3 pt-2">
                <Link href="/login?mode=register" className="flex-1">
                  <Button variant="primary" className="w-full">
                    Create Your Account
                  </Button>
                </Link>
                <Link href="/dashboard" className="flex-1">
                  <Button variant="secondary" className="w-full">
                    View Dashboard
                  </Button>
                </Link>
              </div>
            </div>
          </Reveal>
        ) : (
          <Reveal>
            <form
              onSubmit={handleSubmit}
              className="bg-[#0a1220] border border-slate-800 rounded-2xl p-6 sm:p-8 text-left space-y-5"
            >
              <div>
                <label htmlFor="cta-name" className="block text-xs text-slate-400 mb-1.5 font-medium">
                  Name <span className="text-red-500" aria-hidden="true">*</span>
                </label>
                <input
                  id="cta-name"
                  type="text"
                  required
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Your name or organisation"
                  autoComplete="name"
                  className="w-full bg-[#070d1a] border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-slate-700 focus:outline-none focus:border-cyan-500/60 transition-colors"
                />
              </div>

              <div>
                <label htmlFor="cta-interest" className="block text-xs text-slate-400 mb-1.5 font-medium">
                  Primary interest
                </label>
                <input
                  id="cta-interest"
                  type="text"
                  value={interest}
                  onChange={e => setInterest(e.target.value)}
                  placeholder="e.g. Macro research, crypto signals, portfolio intelligence"
                  className="w-full bg-[#070d1a] border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-slate-700 focus:outline-none focus:border-cyan-500/60 transition-colors"
                />
              </div>

              <div>
                <label htmlFor="cta-experience" className="block text-xs text-slate-400 mb-1.5 font-medium">
                  Background
                </label>
                <input
                  id="cta-experience"
                  type="text"
                  value={experience}
                  onChange={e => setExperience(e.target.value)}
                  placeholder="e.g. Institutional PM, prop desk, family office analyst"
                  className="w-full bg-[#070d1a] border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-white placeholder-slate-700 focus:outline-none focus:border-cyan-500/60 transition-colors"
                />
              </div>

              {step === 'error' && errorMsg && (
                <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2" role="alert">
                  {errorMsg}
                </p>
              )}

              <div className="flex flex-col sm:flex-row gap-3 pt-1">
                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  disabled={step === 'loading' || !name.trim()}
                  className="flex-1"
                >
                  {step === 'loading' ? 'Submitting…' : 'Request Access'}
                </Button>
                <Link href="/dashboard" className="flex-1">
                  <Button variant="secondary" size="lg" type="button" className="w-full">
                    View Demo
                  </Button>
                </Link>
              </div>

              <p className="text-xs text-slate-700 text-center">
                By submitting you agree to be contacted regarding platform access.
                Decision-support only · Not financial advice.
              </p>
            </form>
          </Reveal>
        )}
      </div>
    </section>
  )
}
