import axios from 'axios'
import type { ApprovalOut, ClientOut, CreateClientIn, CreateJobIn, JobOut, UsageOut } from './types'

const apiKey = import.meta.env.VITE_API_KEY as string | undefined
// Local dev leans on Vite's /api proxy (vite.config.ts) to the backend on
// :8000. Once frontend and backend are separate deployed services (e.g.
// two Cloud Run services with different URLs), there's no proxy — this
// needs to be baked in as an absolute URL at build time instead.
const baseURL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '/api'

const client = axios.create({
  baseURL,
  headers: apiKey ? { 'X-API-Key': apiKey } : {},
})

// The backend serves /outputs at its own root (not under /api). In dev,
// a relative path works because vite.config.ts proxies /outputs directly;
// once deployed as a separate service, it needs the same absolute origin
// as the API calls above.
export const outputsBaseURL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || ''

export const api = {
  listClients: () => client.get<ClientOut[]>('/clients').then(r => r.data),
  createClient: (payload: CreateClientIn) => client.post<ClientOut>('/clients', payload).then(r => r.data),
  getUsage: (clientId: string) => client.get<UsageOut>(`/clients/${clientId}/usage`).then(r => r.data),
  listJobs: (clientId?: string, limit = 50) =>
    client
      .get<JobOut[]>('/jobs', { params: { ...(clientId ? { client_id: clientId } : {}), limit } })
      .then(r => r.data),
  createJob: (payload: CreateJobIn) => client.post<JobOut>('/jobs', payload).then(r => r.data),
  listApprovals: () => client.get<ApprovalOut[]>('/approvals').then(r => r.data),
  approve: (jobId: string, decidedBy: string) =>
    client.post<JobOut>(`/approvals/${jobId}/approve`, { decided_by: decidedBy }).then(r => r.data),
  reject: (jobId: string, decidedBy: string, reason: string) =>
    client.post<JobOut>(`/approvals/${jobId}/reject`, { decided_by: decidedBy, reason }).then(r => r.data),
}
