'use client'

import { useState, useCallback, useEffect, useRef } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Types
export interface TaskEvent {
  event: string
  task_id: string
  payload: Record<string, unknown> | null
  timestamp: string
}

export interface TaskStep {
  step_id: string
  description: string
  tool: string | null
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  input?: unknown
  output?: unknown
  error?: string | null
  started_at?: string
  completed_at?: string
}

export interface TaskArtifact {
  artifact_id: string
  artifact_type: string
  name: string
  url?: string
  metadata?: Record<string, unknown>
}

export interface CoordinatorResponse {
  answer: string
  task_id: string
  artifacts: TaskArtifact[]
  evidence: string[]
  step_summary: Array<{
    step_id: string
    description: string
    tool: string | null
    status: string
    duration_seconds?: number
  }>
}

export interface CoordinatorState {
  sessionId: string | null
  taskId: string | null
  status: 'idle' | 'loading' | 'streaming' | 'awaiting_approval' | 'completed' | 'error'
  events: TaskEvent[]
  steps: TaskStep[]
  artifacts: TaskArtifact[]
  answer: string | null
  error: string | null
}

function authHeaders(): HeadersInit {
  if (typeof window === 'undefined') return {}
  const token = localStorage.getItem('aip_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * React hook for coordinator chat with SSE streaming
 */
export function useCoordinator() {
  const [state, setState] = useState<CoordinatorState>({
    sessionId: null,
    taskId: null,
    status: 'idle',
    events: [],
    steps: [],
    artifacts: [],
    answer: null,
    error: null,
  })

  const abortControllerRef = useRef<AbortController | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  // Initialize session on mount
  useEffect(() => {
    const storedSessionId = sessionStorage.getItem('coordinator_session_id')
    if (storedSessionId) {
      setState(prev => ({ ...prev, sessionId: storedSessionId }))
    }
  }, [])

  // Save session ID when it changes
  useEffect(() => {
    if (state.sessionId) {
      sessionStorage.setItem('coordinator_session_id', state.sessionId)
    }
  }, [state.sessionId])

  /**
   * Process incoming SSE events
   */
  const processEvent = useCallback((eventType: string, data: Record<string, unknown>) => {
    const event: TaskEvent = {
      event: eventType,
      task_id: data.task_id as string,
      payload: data.payload as Record<string, unknown>,
      timestamp: data.timestamp as string || new Date().toISOString(),
    }

    setState(prev => {
      const newState = { ...prev, events: [...prev.events, event] }

      // Update state based on event type
      switch (eventType) {
        case 'task.created':
          newState.taskId = data.task_id as string
          newState.sessionId = newState.sessionId || (data.session_id as string)
          break

        case 'task.classified':
          // Classification info in payload
          break

        case 'task.planned': {
          const planPayload = data.payload as Record<string, unknown>
          if (planPayload?.steps) {
            newState.steps = (planPayload.steps as Array<Record<string, unknown>>).map(s => ({
              step_id: s.step_id as string,
              description: s.description as string,
              tool: s.tool as string | null,
              status: (s.status as TaskStep['status']) || 'pending',
            }))
          }
          break
        }

        case 'step.started': {
          const startPayload = data.payload as Record<string, unknown>
          newState.steps = prev.steps.map(s =>
            s.step_id === startPayload?.step_id
              ? { ...s, status: 'running' as const }
              : s
          )
          break
        }

        case 'step.completed': {
          const completePayload = data.payload as Record<string, unknown>
          newState.steps = prev.steps.map(s =>
            s.step_id === completePayload?.step_id
              ? { ...s, status: 'completed' as const, output: completePayload?.output }
              : s
          )
          break
        }

        case 'step.failed': {
          const failPayload = data.payload as Record<string, unknown>
          newState.steps = prev.steps.map(s =>
            s.step_id === failPayload?.step_id
              ? { ...s, status: 'failed' as const, error: failPayload?.error as string }
              : s
          )
          break
        }

        case 'task.awaiting_approval':
          newState.status = 'awaiting_approval'
          break

        case 'task.completed':
        case 'task.failed':
          newState.status = eventType === 'task.completed' ? 'completed' : 'error'
          break

        case 'response': {
          const respPayload = data as Record<string, unknown>
          newState.answer = respPayload.answer as string
          newState.artifacts = (respPayload.artifacts as TaskArtifact[]) || []
          newState.taskId = respPayload.task_id as string
          break
        }

        case 'error':
          newState.status = 'error'
          newState.error = (data.payload as Record<string, unknown>)?.error as string || 'Unknown error'
          break
      }

      return newState
    })
  }, [])

  /**
   * Send a chat message with streaming response
   */
  const sendMessage = useCallback(async (
    message: string,
    options?: { priorTaskId?: string }
  ) => {
    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setState(prev => ({
      ...prev,
      status: 'loading',
      events: [],
      steps: [],
      artifacts: [],
      answer: null,
      error: null,
    }))

    try {
      // Use fetch for SSE (EventSource doesn't support POST)
      const response = await fetch(`${API_URL}/api/coordinator/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          ...authHeaders(),
        },
        body: JSON.stringify({
          message,
          session_id: state.sessionId,
          prior_task_id: options?.priorTaskId,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`)
      }

      if (!response.body) {
        throw new Error('No response body')
      }

      setState(prev => ({ ...prev, status: 'streaming' }))

      // Process SSE stream
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let currentEvent = ''
        let currentData = ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7)
          } else if (line.startsWith('data: ')) {
            currentData = line.slice(6)
          } else if (line === '' && currentEvent && currentData) {
            // Process complete event
            try {
              const eventData = JSON.parse(currentData)
              processEvent(currentEvent, eventData)
            } catch {
              console.warn('Failed to parse event data:', currentData)
            }
            currentEvent = ''
            currentData = ''
          } else if (line.startsWith(':')) {
            // Comment/heartbeat, ignore
          }
        }
      }

      setState(prev => ({
        ...prev,
        status: prev.status === 'awaiting_approval' ? 'awaiting_approval' : 'completed',
      }))

    } catch (error) {
      console.error('Coordinator error:', error)
      setState(prev => ({
        ...prev,
        status: 'error',
        error: error instanceof Error ? error.message : 'Unknown error',
      }))
    }
  }, [state.sessionId, processEvent])

  /**
   * Send a non-streaming chat message
   */
  const sendMessageSync = useCallback(async (
    message: string,
    options?: { priorTaskId?: string }
  ): Promise<CoordinatorResponse | null> => {
    setState(prev => ({ ...prev, status: 'loading', error: null }))

    try {
      const response = await fetch(`${API_URL}/api/coordinator/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({
          message,
          session_id: state.sessionId,
          prior_task_id: options?.priorTaskId,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`)
      }

      const data = await response.json()

      setState(prev => ({
        ...prev,
        status: 'completed',
        taskId: data.task_id,
        answer: data.answer,
        artifacts: data.artifacts || [],
      }))

      return data
    } catch (error) {
      console.error('Coordinator error:', error)
      setState(prev => ({
        ...prev,
        status: 'error',
        error: error instanceof Error ? error.message : 'Unknown error',
      }))
      return null
    }
  }, [state.sessionId])

  /**
   * Approve or reject a pending task
   */
  const approveTask = useCallback(async (taskId: string, approved: boolean): Promise<boolean> => {
    try {
      const response = await fetch(`${API_URL}/api/coordinator/tasks/${taskId}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({ approved }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`)
      }

      setState(prev => ({
        ...prev,
        status: approved ? 'loading' : 'completed',
      }))

      return true
    } catch (error) {
      console.error('Approval error:', error)
      return false
    }
  }, [])

  /**
   * Cancel a running task
   */
  const cancelTask = useCallback(async (taskId: string): Promise<boolean> => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    try {
      const response = await fetch(`${API_URL}/api/coordinator/tasks/${taskId}/cancel`, {
        method: 'POST',
        headers: {
          ...authHeaders(),
        },
      })

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`)
      }

      setState(prev => ({ ...prev, status: 'completed' }))
      return true
    } catch (error) {
      console.error('Cancel error:', error)
      return false
    }
  }, [])

  /**
   * Create a new session
   */
  const createSession = useCallback(async (): Promise<string | null> => {
    try {
      const response = await fetch(`${API_URL}/api/coordinator/sessions`, {
        method: 'POST',
        headers: authHeaders(),
      })

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`)
      }

      const data = await response.json()
      setState(prev => ({ ...prev, sessionId: data.session_id }))
      return data.session_id
    } catch (error) {
      console.error('Create session error:', error)
      return null
    }
  }, [])

  /**
   * Get available tools
   */
  const getTools = useCallback(async (): Promise<Array<Record<string, unknown>>> => {
    try {
      const response = await fetch(`${API_URL}/api/coordinator/tools`, {
        headers: authHeaders(),
      })

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`)
      }

      const data = await response.json()
      return data.tools
    } catch (error) {
      console.error('Get tools error:', error)
      return []
    }
  }, [])

  /**
   * Reset state
   */
  const reset = useCallback(() => {
    setState(prev => ({
      ...prev,
      taskId: null,
      status: 'idle',
      events: [],
      steps: [],
      artifacts: [],
      answer: null,
      error: null,
    }))
  }, [])

  return {
    ...state,
    sendMessage,
    sendMessageSync,
    approveTask,
    cancelTask,
    createSession,
    getTools,
    reset,
  }
}

export default useCoordinator
