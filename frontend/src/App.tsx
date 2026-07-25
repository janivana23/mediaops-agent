import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { ApprovalQueue } from './components/ApprovalQueue'
import { BudgetCard } from './components/BudgetCard'
import { JobTable } from './components/JobTable'
import { NewJobForm } from './components/NewJobForm'
import type { ApprovalOut, ClientOut, CreateJobIn, JobOut, UsageOut } from './types'

const POLL_MS = 4000

export default function App() {
  const [clients, setClients] = useState<ClientOut[]>([])
  const [selectedClient, setSelectedClient] = useState<string>('')
  const [usage, setUsage] = useState<UsageOut | null>(null)
  const [jobs, setJobs] = useState<JobOut[]>([])
  const [approvals, setApprovals] = useState<ApprovalOut[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [jobList, approvalList] = await Promise.all([
        api.listJobs(selectedClient || undefined),
        api.listApprovals(),
      ])
      setJobs(jobList)
      setApprovals(approvalList)
      if (selectedClient) {
        setUsage(await api.getUsage(selectedClient))
      }
      setLoadError(null)
    } catch {
      setLoadError('Could not reach the MediaOps API — is the backend running on :8000?')
    }
  }, [selectedClient])

  useEffect(() => {
    api.listClients().then(list => {
      setClients(list)
      if (list.length > 0) setSelectedClient(list[0].id)
    }).catch(() => setLoadError('Could not reach the MediaOps API — is the backend running on :8000?'))
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, POLL_MS)
    return () => clearInterval(id)
  }, [refresh])

  const deliveredCosts = jobs.filter(j => j.status === 'delivered' && j.actual_cost_cents != null)
  const costPerDeliverable = deliveredCosts.length
    ? Math.round(deliveredCosts.reduce((sum, j) => sum + (j.actual_cost_cents ?? 0), 0) / deliveredCosts.length)
    : null

  const handleDecide = async (jobId: string, decision: 'approve' | 'reject') => {
    if (decision === 'approve') await api.approve(jobId, 'demo@3echo.sg')
    else await api.reject(jobId, 'demo@3echo.sg', 'rejected from dashboard')
    await refresh()
  }

  const handleCreate = async (payload: CreateJobIn) => {
    await api.createJob(payload)
    await refresh()
  }

  return (
    <>
      <header className="app-header">
        <h1>MediaOps Agent</h1>
        <p>Generative media pipeline — budget limits, approval checkpoints, and QA enforced server-side.</p>
      </header>

      {loadError && <p className="error-text">{loadError}</p>}

      <section>
        <h2>Client</h2>
        <div className="grid-2">
          <div className="card">
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: 'var(--text-secondary)' }}>
              Active client
              <select value={selectedClient} onChange={e => setSelectedClient(e.target.value)}>
                {clients.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </label>
            <div className="kpi-row" style={{ marginTop: 14 }}>
              <div className="stat-tile">
                <div className="stat-value">{jobs.length}</div>
                <div className="stat-label">Jobs (this client)</div>
              </div>
              <div className="stat-tile">
                <div className="stat-value">{approvals.length}</div>
                <div className="stat-label">Awaiting approval (all clients)</div>
              </div>
              <div className="stat-tile">
                <div className="stat-value">{costPerDeliverable != null ? `${costPerDeliverable}c` : '—'}</div>
                <div className="stat-label">Avg cost / delivered asset</div>
              </div>
            </div>
          </div>
          {usage && <BudgetCard usage={usage} />}
        </div>
      </section>

      <section>
        <h2>Pending approvals</h2>
        <ApprovalQueue approvals={approvals} onDecide={handleDecide} />
      </section>

      <section>
        <h2>New job</h2>
        <NewJobForm clientId={selectedClient} onSubmit={handleCreate} />
      </section>

      <section>
        <h2>Jobs</h2>
        <JobTable jobs={jobs} />
      </section>
    </>
  )
}
