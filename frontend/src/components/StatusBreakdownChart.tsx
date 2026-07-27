import { STATUS_COLOR, STATUS_LABEL } from '../statusStyles'
import type { JobOut } from '../types'

export function StatusBreakdownChart({ jobs }: { jobs: JobOut[] }) {
  if (jobs.length === 0) {
    return <p className="empty">No jobs yet — nothing to chart.</p>
  }

  const counts = new Map<string, number>()
  for (const job of jobs) {
    counts.set(job.status, (counts.get(job.status) ?? 0) + 1)
  }
  const rows = [...counts.entries()].sort((a, b) => b[1] - a[1])
  const max = Math.max(...rows.map(([, n]) => n))
  const total = jobs.length

  return (
    <div className="chart-root" role="img" aria-label="Jobs by status">
      {rows.map(([status, count]) => {
        const pct = Math.round((count / total) * 100)
        const widthPct = (count / max) * 100
        const color = STATUS_COLOR[status] ?? '#898781'
        return (
          <div className="chart-row" key={status} title={`${STATUS_LABEL[status] ?? status}: ${count} of ${total} jobs (${pct}%)`}>
            <span className="chart-row-label">{STATUS_LABEL[status] ?? status}</span>
            <div className="chart-row-track">
              <div className="chart-row-fill" style={{ width: `${widthPct}%`, background: color }} />
            </div>
            <span className="chart-row-value">{count}</span>
          </div>
        )
      })}
    </div>
  )
}
