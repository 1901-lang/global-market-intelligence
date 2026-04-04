'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type SystemStatus = 'active' | 'degraded' | 'unknown'

export function HeroSection() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus>('unknown')

  // Fetch /health to drive the live system badge
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await fetch(`${API_URL}/health`)
        if (res.ok) {
          const data = await res.json()
          setSystemStatus(data.status === 'ok' ? 'active' : 'degraded')
        } else {
          setSystemStatus('degraded')
        }
      } catch {
        setSystemStatus('unknown')
      }
    }
    fetchHealth()
  }, [])

  const badgeVariant = systemStatus === 'active' ? 'live' : 'label'
  const badgeLabel =
    systemStatus === 'active'
      ? 'Intelligence engine active'
      : systemStatus === 'degraded'
      ? 'System degraded'
      : 'Institutional-grade quantitative intelligence'

  return (
    <section
      className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden bg-[#050c1a] pt-16"
      aria-label="Hero section"
    >
      {/* Background elements */}
      <div className="absolute inset-0 bg-grid-pattern opacity-60 pointer-events-none" aria-hidden="true" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-10%,rgba(0,212,255,0.12),transparent)] pointer-events-none" aria-hidden="true" />
      <div className="absolute bottom-0 left-0 right-0 h-40 bg-gradient-to-t from-[#0d1117] to-transparent pointer-events-none" aria-hidden="true" />

      {/* Content */}
      <div className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 text-center space-y-8">
        {/* Live badge */}
        <div className="flex justify-center">
          <Badge variant={badgeVariant} pulse={systemStatus === 'active'}>
            {badgeLabel}
          </Badge>
        </div>

        {/* Headline */}
        <h1 className="text-4xl sm:text-5xl lg:text-7xl font-bold text-white leading-[1.05] tracking-tight">
          Structured market
          <br />
          <span className="text-cyan-400">intelligence.</span>
        </h1>

        {/* Sub-copy */}
        <p className="text-base sm:text-lg lg:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
          A decision-support platform generating explainable, thesis-driven,
          regime-aware research for discretionary macro traders, family offices,
          and research desks.
        </p>

        {/* Supporting feature tags */}
        <div className="flex flex-wrap justify-center gap-2 text-xs">
          {[
            'Multi-model consensus',
            'Explainable outputs',
            'Thesis-driven research',
            'Regime-aware analysis',
          ].map(tag => (
            <span
              key={tag}
              className="px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-slate-500"
            >
              {tag}
            </span>
          ))}
        </div>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link href="/login?mode=register" aria-label="Request platform access">
            <Button variant="primary" size="lg" className="min-w-[180px]">
              Request Access
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Button>
          </Link>
          <Link href="/dashboard" aria-label="View the live platform dashboard">
            <Button variant="secondary" size="lg" className="min-w-[180px]">
              View Platform Demo
            </Button>
          </Link>
        </div>

        {/* Trust footnote */}
        <p className="text-xs text-slate-600">
          For institutional users · Decision support only · Not financial advice
        </p>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1 text-slate-700" aria-hidden="true">
        <span className="text-xs tracking-widest uppercase font-mono">Scroll</span>
        <svg className="w-4 h-4 animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </section>
  )
}
