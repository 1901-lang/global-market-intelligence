'use client'

import { HTMLAttributes } from 'react'
import clsx from 'clsx'
import { useScrollReveal } from '../../hooks/useScrollReveal'

interface RevealProps extends HTMLAttributes<HTMLDivElement> {
  delay?: number
  threshold?: number
}

export function Reveal({ delay = 0, threshold = 0.1, className, children, ...props }: RevealProps) {
  const { ref, visible } = useScrollReveal(threshold)

  return (
    <div
      ref={ref as React.RefObject<HTMLDivElement>}
      style={{ transitionDelay: `${delay}ms` }}
      className={clsx(
        'transition-all duration-700 ease-out',
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
