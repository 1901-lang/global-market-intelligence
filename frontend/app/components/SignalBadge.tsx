'use client'

import clsx from 'clsx'

interface SignalBadgeProps {
  signal: string
  size?: 'sm' | 'md' | 'lg'
}

export default function SignalBadge({ signal, size = 'md' }: SignalBadgeProps) {
  const colors: Record<string, string> = {
    BUY: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40',
    SELL: 'bg-red-500/20 text-red-400 border border-red-500/40',
    HOLD: 'bg-amber-500/20 text-amber-400 border border-amber-500/40',
  }

  const sizes: Record<string, string> = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-1.5',
  }

  const sig = signal?.toUpperCase() || 'HOLD'
  const colorClass = colors[sig] || colors.HOLD

  return (
    <span
      className={clsx(
        'inline-block font-bold rounded-full tracking-wider',
        colorClass,
        sizes[size]
      )}
    >
      {sig}
    </span>
  )
}
