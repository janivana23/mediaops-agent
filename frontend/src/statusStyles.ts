// Single source of truth for job-status → visual treatment, shared between
// the badge in JobTable and the status-breakdown chart so they can never
// drift out of sync with each other.
export const STATUS_CLASS: Record<string, string> = {
  delivered: 'status-good',
  awaiting_approval: 'status-warning',
  approved: 'status-warning',
  qa_failed: 'status-serious',
  rejected: 'status-critical',
  failed: 'status-critical',
  generating: 'status-muted',
  pending: 'status-muted',
}

// Matches the --status-* CSS custom properties in index.css (the dataviz
// skill's reserved status palette: good/warning/serious/critical) — kept
// as plain hex here because the chart needs to compute against them
// (bar fill), not just apply a class name.
export const STATUS_COLOR: Record<string, string> = {
  delivered: '#0ca30c',
  awaiting_approval: '#fab219',
  approved: '#fab219',
  qa_failed: '#ec835a',
  rejected: '#d03b3b',
  failed: '#d03b3b',
  generating: '#898781',
  pending: '#898781',
}

export const STATUS_LABEL: Record<string, string> = {
  delivered: 'Delivered',
  awaiting_approval: 'Awaiting approval',
  approved: 'Approved',
  qa_failed: 'QA failed',
  rejected: 'Rejected',
  failed: 'Failed',
  generating: 'Generating',
  pending: 'Pending',
}
