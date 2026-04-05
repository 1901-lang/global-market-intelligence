'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import useCoordinator from '../hooks/useCoordinator'
import TaskStepView from './TaskStepView'
import ApprovalPrompt from './ApprovalPrompt'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  taskId?: string
}

interface CoordinatorChatProps {
  className?: string
  onArtifact?: (artifact: { type: string; name: string; data: unknown }) => void
}

export function CoordinatorChat({ className = '', onArtifact }: CoordinatorChatProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const {
    status,
    steps,
    artifacts,
    answer,
    taskId,
    error,
    sendMessage,
    approveTask,
    cancelTask,
    reset,
  } = useCoordinator()

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, steps, answer])

  // Add assistant response when answer is ready
  useEffect(() => {
    if (answer && status === 'completed') {
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: answer,
        timestamp: new Date(),
        taskId: taskId || undefined,
      }
      setMessages(prev => [...prev, assistantMessage])

      // Notify parent about artifacts
      if (onArtifact && artifacts.length > 0) {
        artifacts.forEach(artifact => {
          onArtifact({
            type: artifact.artifact_type,
            name: artifact.name,
            data: artifact.metadata,
          })
        })
      }

      reset()
    }
  }, [answer, status, taskId, artifacts, onArtifact, reset])

  // Handle submit
  const handleSubmit = useCallback(async (e?: React.FormEvent) => {
    e?.preventDefault()
    
    const message = inputValue.trim()
    if (!message || status === 'loading' || status === 'streaming') return

    // Add user message
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMessage])
    setInputValue('')

    // Send to coordinator
    await sendMessage(message)
  }, [inputValue, status, sendMessage])

  // Handle approval
  const handleApprove = useCallback(async (taskIdToApprove: string) => {
    await approveTask(taskIdToApprove, true)
  }, [approveTask])

  const handleReject = useCallback(async (taskIdToReject: string) => {
    await approveTask(taskIdToReject, false)
    reset()
  }, [approveTask, reset])

  // Handle cancel
  const handleCancel = useCallback(async () => {
    if (taskId) {
      await cancelTask(taskId)
      reset()
    }
  }, [taskId, cancelTask, reset])

  // Handle key press
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className={`flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
          <span className="text-sm font-medium text-gray-200">Coordinator</span>
        </div>
        <div className="text-xs text-gray-500">
          {status === 'idle' && 'Ready'}
          {status === 'loading' && 'Processing...'}
          {status === 'streaming' && 'Executing...'}
          {status === 'awaiting_approval' && 'Awaiting approval'}
          {status === 'completed' && 'Complete'}
          {status === 'error' && 'Error'}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && status === 'idle' && (
          <div className="text-center text-gray-500 py-8">
            <p className="mb-2">Ask me anything about the market</p>
            <p className="text-sm">
              Try: &ldquo;What&apos;s the current consensus on BTC?&rdquo; or &ldquo;Generate a market brief&rdquo;
            </p>
          </div>
        )}

        {messages.map(message => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-200'
              }`}
            >
              {message.role === 'assistant' ? (
                <div className="prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc pl-4 mb-2">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal pl-4 mb-2">{children}</ol>,
                      li: ({ children }) => <li className="mb-1">{children}</li>,
                      code: ({ children }) => (
                        <code className="bg-gray-700 px-1 py-0.5 rounded text-sm">{children}</code>
                      ),
                      pre: ({ children }) => (
                        <pre className="bg-gray-700 p-2 rounded text-sm overflow-x-auto">{children}</pre>
                      ),
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <p>{message.content}</p>
              )}
              <div className="text-xs opacity-50 mt-1">
                {message.timestamp.toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}

        {/* Loading/streaming state */}
        {(status === 'loading' || status === 'streaming') && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg px-4 py-3 bg-gray-800">
              {steps.length > 0 ? (
                <TaskStepView steps={steps} />
              ) : (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                  <span className="text-gray-400 text-sm">Processing...</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Approval prompt */}
        {status === 'awaiting_approval' && taskId && (
          <ApprovalPrompt
            taskId={taskId}
            reason="This operation requires your approval before proceeding."
            onApprove={handleApprove}
            onReject={handleReject}
          />
        )}

        {/* Error state */}
        {status === 'error' && error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
            <p className="text-red-400 text-sm">{error}</p>
            <button
              onClick={reset}
              className="text-red-400 text-xs underline mt-2"
            >
              Dismiss
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-800">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask the coordinator..."
            disabled={status === 'loading' || status === 'streaming'}
            className={`
              flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2
              text-gray-200 placeholder-gray-500 resize-none
              focus:outline-none focus:border-blue-500
              disabled:opacity-50 disabled:cursor-not-allowed
            `}
            rows={1}
          />
          
          {status === 'loading' || status === 'streaming' ? (
            <button
              type="button"
              onClick={handleCancel}
              className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors"
            >
              Cancel
            </button>
          ) : (
            <button
              type="submit"
              disabled={!inputValue.trim()}
              className={`
                px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg
                transition-colors disabled:opacity-50 disabled:cursor-not-allowed
              `}
            >
              Send
            </button>
          )}
        </form>
      </div>
    </div>
  )
}

export default CoordinatorChat
