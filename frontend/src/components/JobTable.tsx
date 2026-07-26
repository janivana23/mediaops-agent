import { outputsBaseURL } from '../api'
import type { JobOut } from '../types'

const STATUS_CLASS: Record<string, string> = {
  delivered: 'status-good',
  awaiting_approval: 'status-warning',
  approved: 'status-warning',
  qa_failed: 'status-serious',
  rejected: 'status-critical',
  failed: 'status-critical',
  generating: 'status-muted',
  pending: 'status-muted',
}

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_CLASS[status] ?? 'status-muted'
  return <span className={`badge ${cls}`}>{status.replace('_', ' ')}</span>
}

function Thumbnail({ job }: { job: JobOut }) {
  if (!job.output_path) {
    return <div className="thumb-placeholder" aria-hidden="true" />
  }
  const src = `${outputsBaseURL}/outputs/${job.id}/${job.output_path.split('/').pop()}`
  return (
    <a href={src} target="_blank" rel="noreferrer" title={`Open full-size ${job.kind} output`}>
      <img className="thumb-img" src={src} alt={`${job.kind} output for ${job.campaign}`} loading="lazy" />
    </a>
  )
}

export function JobTable({ jobs }: { jobs: JobOut[] }) {
  if (jobs.length === 0) {
    return <p className="empty">No jobs yet — submit one below, or run `python -m app.seed`.</p>
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table>
        <thead>
          <tr>
            <th>Output</th>
            <th>Campaign</th>
            <th>Prompt</th>
            <th>Status</th>
            <th>Provider</th>
            <th>Resolution</th>
            <th className="num">Cost</th>
            <th className="num">Identity QA</th>
            <th className="num">Brand QA</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map(job => (
            <tr key={job.id}>
              <td><Thumbnail job={job} /></td>
              <td>{job.campaign}</td>
              <td>{job.prompt}</td>
              <td>
                <StatusBadge status={job.status} />
                {job.status_reason && (
                  <div className="status-reason" title={job.status_reason}>
                    {job.status_reason}
                  </div>
                )}
              </td>
              <td>{job.provider_used ?? '—'}</td>
              <td>{job.resolution_used ?? job.requested_resolution}</td>
              <td className="num">{job.actual_cost_cents != null ? `${job.actual_cost_cents}c` : '—'}</td>
              <td className="num">{job.qa_identity_score ?? '—'}</td>
              <td className="num">{job.qa_brand_score ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
