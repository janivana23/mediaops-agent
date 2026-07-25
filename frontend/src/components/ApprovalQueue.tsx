import { useState } from 'react'
import type { ApprovalOut } from '../types'

export function ApprovalQueue({
  approvals,
  onDecide,
}: {
  approvals: ApprovalOut[]
  onDecide: (jobId: string, decision: 'approve' | 'reject') => Promise<void>
}) {
  const [busy, setBusy] = useState<string | null>(null)

  if (approvals.length === 0) {
    return <p className="empty">Nothing waiting on a human right now.</p>
  }

  const decide = async (jobId: string, decision: 'approve' | 'reject') => {
    setBusy(jobId)
    try {
      await onDecide(jobId, decision)
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
