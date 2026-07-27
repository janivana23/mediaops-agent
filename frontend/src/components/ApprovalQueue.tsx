import { useState } from 'react'
import { IconCheckCircle } from './icons'
import type { ApprovalOut } from '../types'

export function ApprovalQueue({
  approvals,
  onDecide,
}: {
  approvals: ApprovalOut[]
  onDecide: (jobId: string, decision: 'approve' | 'reject') => Promise<void>
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})

  if (approvals.length === 0) {
    return (
      <div className="card empty">
        <span className="empty-icon"><IconCheckCircle /></span>
        Nothing waiting on a human right now.
      </div>
    )
  }

  const decide = async (jobId: string, decision: 'approve' | 'reject') => {
    setBusy(jobId)
    setErrors(prev => ({ ...prev, [jobId]: '' }))
    try {
      await onDecide(jobId, decision)
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setErrors(prev => ({ ...prev, [jobId]: msg ?? `Failed to ${decision} job` }))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="card">
      {approvals.map(a => (
        <div className="approval-row" key={a.id}>
          <div className="approval-meta">
            <div>Job {a.job_id}</div>
            <div className="reason">{a.reason}</div>
            {errors[a.job_id] && <div className="error-text">{errors[a.job_id]}</div>}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="primary"
              disabled={busy === a.job_id}
              onClick={() => decide(a.job_id, 'approve')}
            >
              Approve
            </button>
            <button
              className="danger"
              disabled={busy === a.job_id}
              onClick={() => decide(a.job_id, 'reject')}
            >
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
