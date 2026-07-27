import { ApprovalQueue } from './ApprovalQueue'
import { BudgetCard } from './BudgetCard'
import { IconBarChart, IconClock, IconCoins, IconLayers, IconSparkles } from './icons'
import { JobTable } from './JobTable'
import { NewClientForm } from './NewClientForm'
import { NewJobForm } from './NewJobForm'
import { SectionHeading } from './SectionHeading'
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
        <SectionHeading
          icon={<IconSparkles />}
          title="Client"
          subtitle="Who this run is billed to, and what's left in their monthly budget"
        />
        <div className="grid-2">
          <div className="card">
            <label style={{ display: 'flex', flexDirection: 'column', gap: 5, fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
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
            <div className="kpi-row" style={{ marginTop: 16 }}>
              <div className="stat-tile">
                <span className="stat-icon"><IconLayers /></span>
                <div>
                  <div className="stat-value">{jobs.length}</div>
                  <div className="stat-label">Jobs (this client)</div>
                </div>
              </div>
              <div className="stat-tile">
                <span className="stat-icon"><IconClock /></span>
                <div>
                  <div className="stat-value">{approvals.length}</div>
                  <div className="stat-label">Awaiting approval</div>
                </div>
              </div>
              <div className="stat-tile">
                <span className="stat-icon"><IconCoins /></span>
                <div>
                  <div className="stat-value">{costPerDeliverable != null ? `${costPerDeliverable}c` : '—'}</div>
                  <div className="stat-label">Avg cost / asset</div>
                </div>
              </div>
            </div>
          </div>
          {usage && <BudgetCard usage={usage} />}
        </div>
      </section>

      <section>
        <SectionHeading icon={<IconBarChart />} title="Jobs by status" />
        <div className="card">
          <StatusBreakdownChart jobs={jobs} />
        </div>
      </section>

      <section>
        <SectionHeading
          icon={<IconClock />}
          title="Pending approvals"
          subtitle="Nothing here auto-generates until a human signs off"
        />
        <ApprovalQueue approvals={approvals} onDecide={onDecide} />
      </section>

      <section>
        <SectionHeading icon={<IconSparkles />} title="New job" />
        <NewJobForm clientId={selectedClient} onSubmit={onCreateJob} />
      </section>

      <section>
        <SectionHeading icon={<IconLayers />} title="Jobs" />
        <JobTable jobs={jobs} />
      </section>
    </>
  )
}
