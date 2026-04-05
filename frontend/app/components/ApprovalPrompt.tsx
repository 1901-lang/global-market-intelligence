'use client'

import { useState } from 'react'

interface ApprovalPromptProps {
  taskId: string
  reason?: string
  stepDescription?: string
  onApprove: (taskId: string) => Promise<void>
  onReject: (taskId: string) => Promise<void>
  isLoading?: boolean
}

export function ApprovalPrompt({
  taskId,
  reason,
  stepDescription,
  onApprove,
  onReject,
  isLoading = false,
}: ApprovalPromptProps) {
  const [approving, setApproving] = useState(false)
  const [rejecting, setRejecting] = useState(false)

  const handleApprove = async () => {
    setApproving(true)
    try {
      await onApprove(taskId)
    } finally {
      setApproving(false)
    }
  }

  const handleReject = async () => {
    setRejecting(true)
    try {
      await onReject(taskId)
    } finally {
      setRejecting(false)
    }
  }

  return (
    <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4 my-4">
      <div className="flex items-start gap-3">
        {/* Warning icon */}
        <div className="flex-shrink-0">
          <svg 
            className="w-6 h-6 text-yellow-400" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" 
            />
          </svg>
        </div>

        {/* Content */}
        <div className="flex-1">
          <h3 className="text-yellow-400 font-semibold text-sm mb-1">
            Approval Required
          </h3>
          
          {stepDescription && (
            <p className="text-gray-300 text-sm mb-2">
              {stepDescription}
            </p>
          )}
          
          {reason && (
            <p className="text-gray-400 text-xs mb-3">
              {reason}
            </p>
          )}

          <p className="text-gray-500 text-xs mb-4">
            Task ID: {taskId}
          </p>

          {/* Action buttons */}
          <div className="flex gap-3">
            <button
              onClick={handleApprove}
              disabled={isLoading || approving || rejecting}
              className={`
                px-4 py-2 text-sm font-medium rounded-lg
                bg-emerald-600 hover:bg-emerald-500 text-white
                disabled:opacity-50 disabled:cursor-not-allowed
                transition-colors flex items-center gap-2
              `}
            >
              {approving ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Approving...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Approve
                </>
              )}
            </button>

            <button
              onClick={handleReject}
              disabled={isLoading || approving || rejecting}
              className={`
                px-4 py-2 text-sm font-medium rounded-lg
                bg-gray-700 hover:bg-gray-600 text-gray-200
                disabled:opacity-50 disabled:cursor-not-allowed
                transition-colors flex items-center gap-2
              `}
            >
              {rejecting ? (
                <>
                  <div className="w-4 h-4 border-2 border-gray-400/30 border-t-gray-400 rounded-full animate-spin" />
                  Rejecting...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  Reject
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ApprovalPrompt
