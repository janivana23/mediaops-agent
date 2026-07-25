import axios from 'axios'
import type { ApprovalOut, ClientOut, CreateJobIn, JobOut, UsageOut } from './types'

const client = axios.create({ baseURL: '/api' })

export const api = {
  listClients: () => client.get<ClientOut[]>('/clients').then(r => r.data),
  getUsage: (clientId: string) => client.get<UsageOut>(`/clients/${clientId}/usage`).then(r => r.data),
  listJobs: (clientId?: string) =>
    client.get<JobOut[]>('/jobs', { params: clientId ? { client_id: clientId } : {} }).then(r => r.data),
  createJob: (payload: CreateJobIn) => client.post<JobOut>('/jobs', payload).then(r => r.data),
  listApprovals: () => client.get<ApprovalOut[]>('/approvals').then(r => r.data),
  approve: (jobId: string, decidedBy: string) =>
    client.post<JobOut>(`/approvals/${jobId}/approve`, { decided_by: decidedBy }).then(r => r.data),
  reject: (jobId: string, decidedBy: string, reason: string) =>
    client.post<JobOut>(`/approvals/${jobId}/reject`, { decided_by: decidedBy, reason }).then(r => r.data),
}
