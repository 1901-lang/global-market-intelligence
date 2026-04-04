import { HTMLAttributes } from 'react'
import clsx from 'clsx'

interface TerminalPanelProps extends HTMLAttributes<HTMLDivElement> {
  title?: string
  status?: 'active' | 'idle' | 'processing'
  statusLabel?: string
}

export function TerminalPanel({
  title = 'SYSTEM TERMINAL',
  status = 'active',
  statusLabel,
  className,
  children,
  ...props
}: TerminalPanelProps) {
  const statusColors = {
    active: 'bg-emerald-500',
    idle: 'bg-slate-500',
    processing: 'bg-amber-500 animate-pulse',
  }

  const defaultLabels = { active: 'ACTIVE', idle: 'IDLE', processing: 'PROCESSING' }

  return (
    <div
      className={clsx(
        'rounded-xl border border-slate-800 overflow-hidden',
        'bg-[#070d1a] shadow-[0_0_40px_rgba(0,0,0,0.6)]',
        className,
      )}
      {...props}
    >
      {/* Terminal top bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#0a1120] border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#30363d]" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#30363d]" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#30363d]" />
          </div>
          <span className="text-xs font-mono text-slate-500 ml-2">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={clsx('w-2 h-2 rounded-full', statusColors[status])} />
          <span className="text-xs font-mono text-slate-500">
            {statusLabel || defaultLabels[status]}
          </span>
        </div>
      </div>

      {/* Content */}
      <div>{children}</div>
    </div>
  )
}
