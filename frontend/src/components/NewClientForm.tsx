import { useState } from 'react'
import type { CreateClientIn } from '../types'

export function NewClientForm({ onSubmit }: { onSubmit: (payload: CreateClientIn) => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [budgetDollars, setBudgetDollars] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} style={{ fontSize: 12 }}>
        + New client
      </button>
    )
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const cents = Math.round(parseFloat(budgetDollars) * 100)
      await onSubmit({ name, monthly_budget_cents: cents })
      setName('')
      setBudgetDollars('')
      setOpen(false)
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Failed to create client')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} style={{ display: 'flex', gap: 8, alignItems: 'end', flexWrap: 'wrap' }}>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: 'var(--text-secondary)' }}>
        Client name
        <input value={name} onChange={e => setName(e.target.value)} required autoFocus />
      </label>
      <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: 'var(--text-secondary)' }}>
        Monthly budget (USD)
        <input
          type="number"
          min="0.01"
          step="0.01"
          value={budgetDollars}
          onChange={e => setBudgetDollars(e.target.value)}
          required
        />
      </label>
      <button className="primary" type="submit" disabled={busy}>
        {busy ? 'Creating…' : 'Create'}
      </button>
      <button type="button" onClick={() => setOpen(false)} disabled={busy}>
        Cancel
      </button>
      {error && <div className="error-text">{error}</div>}
    </form>
  )
}
