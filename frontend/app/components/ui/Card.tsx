import { HTMLAttributes } from 'react'
import clsx from 'clsx'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'terminal' | 'elevated'
}

export function Card({ variant = 'default', className, children, ...props }: CardProps) {
  return (
    <div
      className={clsx(
        'rounded-xl border transition-colors duration-200',
        variant === 'default' && 'bg-[#0f1623] border-slate-800 hover:border-slate-700',
        variant === 'terminal' && [
          'bg-[#080e1a] border-slate-800',
          'shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]',
        ],
        variant === 'elevated' && [
          'bg-gradient-to-b from-[#131d30] to-[#0a1220] border-slate-700/60',
          'hover:border-cyan-500/30 hover:shadow-[0_4px_24px_rgba(0,212,255,0.08)]',
        ],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
