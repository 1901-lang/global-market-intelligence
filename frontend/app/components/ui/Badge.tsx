import { HTMLAttributes } from 'react'
import clsx from 'clsx'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'live' | 'system' | 'label' | 'signal'
  pulse?: boolean
}

export function Badge({ variant = 'label', pulse = false, className, children, ...props }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full text-xs font-medium tracking-wide px-2.5 py-1',
        variant === 'live' && 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400',
        variant === 'system' && 'bg-cyan-500/10 border border-cyan-500/30 text-cyan-400',
        variant === 'label' && 'bg-slate-800 border border-slate-700 text-slate-400',
        variant === 'signal' && 'bg-indigo-500/10 border border-indigo-500/30 text-indigo-400',
        className,
      )}
      {...props}
    >
      {pulse && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-60" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-current" />
        </span>
      )}
      {children}
    </span>
  )
}
