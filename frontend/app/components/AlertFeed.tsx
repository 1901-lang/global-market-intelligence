'use client'

import { useEffect, useState, useRef } from 'react'
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

type SeverityFilter = 'all' | 'critical' | 'warning' | 'info'

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

function authHeader(): Record<string, string> {
  if (typeof window === 'undefined') return {}
  const token = localStorage.getItem('aip_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export default function AlertFeed({ apiUrl }: AlertFeedProps) {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all')
  const [assetFilter, setAssetFilter] = useState<string>('all')
  const seenIds = useRef<Set<number>>(new Set())

  useEffect(() => {
    if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
      void Notification.requestPermission()
    }
  }, [])

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/alerts?limit=30`)
        if (res.ok) {
          const data: Alert[] = await res.json()
          setAlerts(data)
          data.forEach(a => {
            if (a.severity === 'critical' && !seenIds.current.has(a.id)) {
              if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
                // Truncate message to avoid overly long notification bodies; strip any HTML-like content
                const safeBody = a.message.replace(/[<>]/g, '').slice(0, 200)
                new Notification(`🚨 Critical: ${a.asset}`, { body: safeBody })
              }
            }
          })
          seenIds.current = new Set(data.map(a => a.id))
        }
      } catch {}
    }
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [apiUrl])

  const markRead = async (id: number) => {
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, is_read: true } : a))
    try {
      await fetch(`${apiUrl}/api/alerts/${id}/read`, {
        method: 'POST',
        headers: authHeader(),
      })
    } catch {}
  }

  const unreadCount = alerts.filter(a => !a.is_read).length
  const uniqueAssets = Array.from(new Set(alerts.map(a => a.asset)))

  const filtered = alerts.filter(a => {
    if (severityFilter !== 'all' && a.severity !== severityFilter) return false
    if (assetFilter !== 'all' && a.asset !== assetFilter) return false
    return true
  })

  const counts: Record<string, number> = {
    all: alerts.length,
    critical: alerts.filter(a => a.severity === 'critical').length,
    warning: alerts.filter(a => a.severity === 'warning').length,
    info: alerts.filter(a => !['critical', 'warning'].includes(a.severity)).length,
  }

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-bold text-white flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse inline-block" />
          Live Alerts
          {unreadCount > 0 && (
            <span className="bg-red-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5 ml-1">{unreadCount}</span>
          )}
        </h2>
        <span className="text-xs text-gray-500">{filtered.length} events</span>
      </div>

      {/* Severity filter pills */}
      <div className="flex gap-1 mb-2 flex-wrap">
        {(['all', 'critical', 'warning', 'info'] as SeverityFilter[]).map(f => (
          <button
            key={f}
            onClick={() => setSeverityFilter(f)}
            className={`px-2 py-0.5 text-xs rounded border transition-colors capitalize ${
              severityFilter === f
                ? f === 'critical' ? 'border-red-500/50 bg-red-500/10 text-red-400'
                  : f === 'warning' ? 'border-amber-500/50 bg-amber-500/10 text-amber-400'
                  : 'border-[#58a6ff]/50 bg-[#58a6ff]/10 text-[#58a6ff]'
                : 'border-[#30363d] text-gray-500 hover:border-gray-400'
            }`}
          >
            {f} {counts[f] > 0 ? `(${counts[f]})` : ''}
          </button>
        ))}
      </div>

      {/* Asset filter */}
      {uniqueAssets.length > 1 && (
        <select
          value={assetFilter}
          onChange={e => setAssetFilter(e.target.value)}
          className="bg-[#0d1117] border border-[#30363d] rounded-lg px-2 py-1 text-xs text-gray-400 mb-2 focus:outline-none focus:border-[#58a6ff] w-full"
        >
          <option value="all">All Assets</option>
          {uniqueAssets.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
      )}

      <div className="flex-1 overflow-y-auto space-y-2 scrollbar-thin">
        {filtered.length === 0 && (
          <div className="text-center text-gray-500 text-sm py-8">
            Monitoring markets…<br />
            <span className="text-xs">Alerts will appear here</span>
          </div>
        )}
        {filtered.map((alert) => (
          <div
            key={alert.id}
            onClick={() => !alert.is_read && markRead(alert.id)}
            className={`border-l-2 pl-3 py-2 rounded-r text-sm ${severityColor(alert.severity)} ${alert.is_read ? 'opacity-60' : 'cursor-pointer hover:opacity-90'}`}
          >
            <div className="flex items-center gap-2 mb-0.5">
              <span className="font-semibold text-white text-xs">{alert.asset}</span>
              <SignalBadge signal={alert.signal} size="sm" />
              {!alert.is_read && <span className="w-1.5 h-1.5 rounded-full bg-[#58a6ff] ml-auto flex-shrink-0" />}
              <span className={`${alert.is_read ? 'ml-auto' : ''} text-gray-500 text-xs`}>{formatTime(alert.timestamp)}</span>
            </div>
            <p className="text-gray-300 text-xs leading-snug">{alert.message}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
