import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { Dashboard } from './components/Dashboard'
import { HowItWorks } from './components/HowItWorks'
import { IconLogoMark } from './components/icons'
import type { ApprovalOut, ClientOut, CreateClientIn, CreateJobIn, JobOut, UsageOut } from './types'

const POLL_MS = 4000
type Tab = 'dashboard' | 'how-it-works'

export default function App() {
  const [tab, setTab] = useState<Tab>('dashboard')
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

  const handleDecide = async (jobId: string, decision: 'approve' | 'reject') => {
    if (decision === 'approve') await api.approve(jobId, 'demo@3echo.sg')
    else await api.reject(jobId, 'demo@3echo.sg', 'rejected from dashboard')
    await refresh()
  }

  const handleCreate = async (payload: CreateJobIn) => {
    await api.createJob(payload)
    await refresh()
  }

  const handleCreateClient = async (payload: CreateClientIn) => {
    const created = await api.createClient(payload)
    setClients(await api.listClients())
    setSelectedClient(created.id)
  }

  return (
    <>
      <header className="app-header">
        <div className="app-header-top">
          <div className="app-brand">
            <span className="app-logo" aria-hidden="true">
              <IconLogoMark width={20} height={20} />
            </span>
            <div>
              <span className="app-eyebrow">3echo · generative media ops</span>
              <h1>MediaOps Agent</h1>
              <p>Budget limits, approval checkpoints, and QA enforced server-side — not by the model.</p>
            </div>
          </div>
          <nav className="tab-nav">
            <button
              className={tab === 'dashboard' ? 'tab-active' : ''}
              onClick={() => setTab('dashboard')}
            >
              Dashboard
            </button>
            <button
              className={tab === 'how-it-works' ? 'tab-active' : ''}
              onClick={() => setTab('how-it-works')}
            >
              How it works
            </button>
          </nav>
        </div>
      </header>

      {loadError && <p className="error-text">{loadError}</p>}

      {tab === 'dashboard' ? (
        <Dashboard
          clients={clients}
          selectedClient={selectedClient}
          setSelectedClient={setSelectedClient}
          usage={usage}
          jobs={jobs}
          approvals={approvals}
          onDecide={handleDecide}
          onCreateJob={handleCreate}
          onCreateClient={handleCreateClient}
        />
      ) : (
        <HowItWorks />
      )}
    </>
  )
}
