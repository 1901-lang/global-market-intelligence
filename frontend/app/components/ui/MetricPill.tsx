import { HTMLAttributes } from 'react'
import clsx from 'clsx'

interface MetricPillProps extends HTMLAttributes<HTMLSpanElement> {
  label: string
  value: string
  trend?: 'up' | 'down' | 'neutral'
}

export function MetricPill({ label, value, trend = 'neutral', className, ...props }: MetricPillProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-2 rounded-lg px-3 py-1.5',
        'bg-slate-900 border border-slate-800 text-xs',
        className,
      )}
      {...props}
    >
      <span className="text-slate-500 font-medium uppercase tracking-wider">{label}</span>
      <span
        className={clsx(
          'font-mono font-semibold',
          trend === 'up' && 'text-emerald-400',
          trend === 'down' && 'text-red-400',
          trend === 'neutral' && 'text-slate-300',
        )}
      >
        {value}
      </span>
    </span>
  )
}
