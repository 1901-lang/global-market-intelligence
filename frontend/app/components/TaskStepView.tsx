'use client'

import { useMemo } from 'react'

interface TaskStep {
  step_id: string
  description: string
  tool: string | null
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  duration_seconds?: number
  error?: string | null
}

interface TaskStepViewProps {
  steps: TaskStep[]
  compact?: boolean
}

function getStatusIcon(status: TaskStep['status']) {
  switch (status) {
    case 'pending':
      return (
        <div className="w-4 h-4 rounded-full border-2 border-gray-500 bg-transparent" />
      )
    case 'running':
      return (
        <div className="w-4 h-4 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
      )
    case 'completed':
      return (
        <div className="w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center">
          <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      )
    case 'failed':
      return (
        <div className="w-4 h-4 rounded-full bg-red-500 flex items-center justify-center">
          <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
      )
    case 'skipped':
      return (
        <div className="w-4 h-4 rounded-full bg-gray-400 flex items-center justify-center">
          <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M9 5l7 7-7 7" />
          </svg>
        </div>
      )
    default:
      return null
  }
}

function getStatusColor(status: TaskStep['status']) {
  switch (status) {
    case 'pending':
      return 'text-gray-400'
    case 'running':
      return 'text-blue-400'
    case 'completed':
      return 'text-emerald-400'
    case 'failed':
      return 'text-red-400'
    case 'skipped':
      return 'text-gray-500'
    default:
      return 'text-gray-400'
  }
}

function getLineColor(status: TaskStep['status']) {
  switch (status) {
    case 'completed':
      return 'bg-emerald-500'
    case 'failed':
      return 'bg-red-500'
    case 'running':
      return 'bg-blue-400'
    default:
      return 'bg-gray-600'
  }
}

export function TaskStepView({ steps, compact = false }: TaskStepViewProps) {
  const completedCount = useMemo(
    () => steps.filter(s => s.status === 'completed').length,
    [steps]
  )

  const failedCount = useMemo(
    () => steps.filter(s => s.status === 'failed').length,
    [steps]
  )

  if (steps.length === 0) {
    return null
  }

  if (compact) {
    // Compact view: just show progress bar
    const progress = steps.length > 0 
      ? ((completedCount + failedCount) / steps.length) * 100 
      : 0

    return (
      <div className="w-full">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-400">
            {completedCount}/{steps.length} steps
          </span>
          {failedCount > 0 && (
            <span className="text-xs text-red-400">
              {failedCount} failed
            </span>
          )}
        </div>
        <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div 
            className={`h-full transition-all duration-300 ${
              failedCount > 0 ? 'bg-yellow-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    )
  }

  // Full view: show all steps
  return (
    <div className="space-y-0">
      {steps.map((step, index) => (
        <div key={step.step_id} className="relative">
          {/* Connector line */}
          {index < steps.length - 1 && (
            <div 
              className={`absolute left-[7px] top-6 w-0.5 h-full ${getLineColor(step.status)}`}
            />
          )}
          
          <div className="flex items-start gap-3 py-2">
            {/* Status icon */}
            <div className="flex-shrink-0 mt-0.5">
              {getStatusIcon(step.status)}
            </div>
            
            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className={`text-sm font-medium ${getStatusColor(step.status)}`}>
                {step.description}
              </div>
              
              {step.tool && (
                <div className="text-xs text-gray-500 mt-0.5">
                  Tool: {step.tool}
                </div>
              )}
              
              {step.status === 'failed' && step.error && (
                <div className="text-xs text-red-400 mt-1 bg-red-500/10 rounded px-2 py-1">
                  {step.error}
                </div>
              )}
              
              {step.duration_seconds !== undefined && step.status === 'completed' && (
                <div className="text-xs text-gray-500 mt-0.5">
                  Completed in {step.duration_seconds.toFixed(1)}s
                </div>
              )}
            </div>
            
            {/* Status badge */}
            <div className={`flex-shrink-0 text-xs px-2 py-0.5 rounded ${
              step.status === 'running' 
                ? 'bg-blue-500/20 text-blue-400' 
                : step.status === 'completed'
                  ? 'bg-emerald-500/20 text-emerald-400'
                  : step.status === 'failed'
                    ? 'bg-red-500/20 text-red-400'
                    : 'bg-gray-700 text-gray-400'
            }`}>
              {step.status}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default TaskStepView
