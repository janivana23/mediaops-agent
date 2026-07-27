import { IconWallet } from './icons'
import type { UsageOut } from '../types'

function money(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`
}

export function BudgetCard({ usage }: { usage: UsageOut }) {
  const pct = usage.monthly_budget_cents > 0 ? (usage.used_cents / usage.monthly_budget_cents) * 100 : 0
  const over = usage.remaining_cents < 0

  return (
    <div className="card">
      <div className="client-name">
        <IconWallet /> {usage.client_name}
      </div>
      <div className="meter-track">
        <div
          className={`meter-fill${over ? ' over' : ''}`}
          style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        />
      </div>
      <div className="meter-label">
        <span>{money(usage.used_cents)} used · {Math.round(pct)}%</span>
        <span>{money(usage.monthly_budget_cents)} budget</span>
      </div>
      <div className="kpi-row" style={{ marginTop: 14 }}>
        <div className="stat-tile">
          <div>
            <div className="stat-value" style={{ color: over ? 'var(--status-critical)' : undefined }}>
              {money(usage.remaining_cents)}
            </div>
            <div className="stat-label">Remaining this month</div>
          </div>
        </div>
      </div>
    </div>
  )
}
