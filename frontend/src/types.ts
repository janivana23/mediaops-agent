export interface ClientOut {
  id: string
  name: string
  monthly_budget_cents: number
}

export interface JobOut {
  id: string
  client_id: string
  campaign: string
  prompt: string
  kind: string
  requested_resolution: string
  resolution_used: string | null
  status: string
  status_reason: string | null
  estimated_cost_cents: number
  actual_cost_cents: number | null
  provider_used: string | null
  output_path: string | null
  qa_identity_score: number | null
  qa_brand_score: number | null
  created_at: string
}

export interface ApprovalOut {
  id: string
  job_id: string
  reason: string
  status: string
}

export interface UsageOut {
  client_id: string
  client_name: string
  monthly_budget_cents: number
  used_cents: number
  remaining_cents: number
}

export interface CreateJobIn {
  client_id: string
  campaign: string
  prompt: string
  kind: string
  resolution: string
  reference_image_path?: string | null
}

export interface CreateClientIn {
  name: string
  monthly_budget_cents: number
}
