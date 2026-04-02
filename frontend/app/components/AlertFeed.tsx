'use client'

import { useEffect, useState } from 'react'
import SignalBadge from './SignalBadge'

interface Alert {
  id: number
  asset: string
  alert_type: string
  message: string
  signal: string
  confidence: number
  severity: string
  is_read: boolean
  timestamp: string
}

interface AlertFeedProps {
  apiUrl: string
}

function severityColor(severity: string): string {
  switch (severity) {
    case 'critical': return 'border-l-red-500 bg-red-500/5'
    case 'warning': return 'border-l-amber-500 bg-amber-500/5'
    default: return 'border-l-blue-500 bg-blue-500/5'
  }
}

function formatTime(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export default function AlertFeed({ apiUrl }: AlertFeedProps) {
  const [alerts, setAlerts] = useState<Alert[]>([])

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/alerts?limit=30`)
        if (res.ok) {
          const data = await res.json()
          setAlerts(data)
        }
      } catch {}
    }
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [apiUrl])

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-bold text-white flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse inline-block" />
          Live Alerts
        </h2>
        <span className="text-xs text-gray-500">{alerts.length} events</span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 scrollbar-thin">
        {alerts.length === 0 && (
          <div className="text-center text-gray-500 text-sm py-8">
            Monitoring markets…<br />
            <span className="text-xs">Alerts will appear here</span>
          </div>
        )}
        {alerts.map((alert) => (
          <div
            key={alert.id}
            className={`border-l-2 pl-3 py-2 rounded-r text-sm ${severityColor(alert.severity)} ${alert.is_read ? 'opacity-60' : ''}`}
          >
            <div className="flex items-center gap-2 mb-0.5">
              <span className="font-semibold text-white text-xs">{alert.asset}</span>
              <SignalBadge signal={alert.signal} size="sm" />
              <span className="ml-auto text-gray-500 text-xs">{formatTime(alert.timestamp)}</span>
            </div>
            <p className="text-gray-300 text-xs leading-snug">{alert.message}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
