import { ApprovalQueue } from './ApprovalQueue'
import { BudgetCard } from './BudgetCard'
import { JobTable } from './JobTable'
import { NewClientForm } from './NewClientForm'
import { NewJobForm } from './NewJobForm'
import { StatusBreakdownChart } from './StatusBreakdownChart'
import type { ApprovalOut, ClientOut, CreateClientIn, CreateJobIn, JobOut, UsageOut } from '../types'

export function Dashboard({
  clients,
  selectedClient,
  setSelectedClient,
  usage,
  jobs,
  approvals,
  onDecide,
  onCreateJob,
  onCreateClient,
}: {
  clients: ClientOut[]
  selectedClient: string
  setSelectedClient: (id: string) => void
  usage: UsageOut | null
  jobs: JobOut[]
  approvals: ApprovalOut[]
  onDecide: (jobId: string, decision: 'approve' | 'reject') => Promise<void>
  onCreateJob: (payload: CreateJobIn) => Promise<void>
  onCreateClient: (payload: CreateClientIn) => Promise<void>
}) {
  const deliveredCosts = jobs.filter(j => j.status === 'delivered' && j.actual_cost_cents != null)
  const costPerDeliverable = deliveredCosts.length
    ? Math.round(deliveredCosts.reduce((sum, j) => sum + (j.actual_cost_cents ?? 0), 0) / deliveredCosts.length)
    : null

  return (
    <>
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
            <div style={{ marginTop: 10 }}>
              <NewClientForm onSubmit={onCreateClient} />
            </div>
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
        <h2>Jobs by status</h2>
        <div className="card">
          <StatusBreakdownChart jobs={jobs} />
        </div>
      </section>

      <section>
        <h2>Pending approvals</h2>
        <ApprovalQueue approvals={approvals} onDecide={onDecide} />
      </section>

      <section>
        <h2>New job</h2>
        <NewJobForm clientId={selectedClient} onSubmit={onCreateJob} />
      </section>

      <section>
        <h2>Jobs</h2>
        <JobTable jobs={jobs} />
      </section>
    </>
  )
}
