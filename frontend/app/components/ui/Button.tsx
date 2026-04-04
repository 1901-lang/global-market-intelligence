import { ButtonHTMLAttributes } from 'react'
import clsx from 'clsx'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  asChild?: boolean
}

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center gap-2 font-medium transition-all duration-200 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed',
        // Sizes
        size === 'sm' && 'px-3 py-1.5 text-xs',
        size === 'md' && 'px-5 py-2.5 text-sm',
        size === 'lg' && 'px-7 py-3.5 text-base',
        // Variants
        variant === 'primary' && [
          'bg-cyan-500 text-navy-950 font-semibold',
          'hover:bg-cyan-400 hover:shadow-[0_0_20px_rgba(0,212,255,0.4)]',
          'active:bg-cyan-600',
        ],
        variant === 'secondary' && [
          'bg-transparent border border-slate-700 text-gray-200',
          'hover:border-cyan-500/60 hover:text-cyan-400',
          'active:bg-slate-800',
        ],
        variant === 'ghost' && [
          'bg-transparent text-gray-400',
          'hover:text-cyan-400 hover:bg-white/5',
        ],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}
