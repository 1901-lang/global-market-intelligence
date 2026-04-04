'use client'

import { useEffect, useRef, useState } from 'react'
/**
 * useScrollReveal — triggers a CSS reveal class when the element enters
 * the viewport. Returns a ref to attach to the target element and a boolean
 * indicating whether the element is currently visible.
 */
export function useScrollReveal(threshold = 0.15) {
  const ref = useRef<HTMLElement | null>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.unobserve(el)
        }
      },
      { threshold },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [threshold])

  return { ref, visible }
}
