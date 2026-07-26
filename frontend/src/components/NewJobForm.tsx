import { useState } from 'react'
import type { CreateJobIn } from '../types'

export function NewJobForm({
  clientId,
  onSubmit,
}: {
  clientId: string
  onSubmit: (payload: CreateJobIn) => Promise<void>
}) {
  const [campaign, setCampaign] = useState('')
  const [prompt, setPrompt] = useState('')
  const [resolution, setResolution] = useState('1024x1024')
  const [kind, setKind] = useState('image')
  const [referenceImagePath, setReferenceImagePath] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onSubmit({
        client_id: clientId,
        campaign,
        prompt,
        kind,
        resolution,
        reference_image_path: referenceImagePath || null,
      })
      setPrompt('')
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Failed to submit job')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="new-job card" onSubmit={submit}>
      <label>
        Campaign
        <input value={campaign} onChange={e => setCampaign(e.target.value)} required />
      </label>
      <label style={{ gridColumn: 'span 2' }}>
        Prompt
        <input value={prompt} onChange={e => setPrompt(e.target.value)} required />
      </label>
      <label>
        Kind
        <select value={kind} onChange={e => setKind(e.target.value)}>
          <option value="image">image</option>
          <option value="video">video (storyboard)</option>
        </select>
      </label>
      <label>
        Resolution
        <select value={resolution} onChange={e => setResolution(e.target.value)} disabled={kind === 'video'}>
          <option value="512x512">512x512</option>
          <option value="1024x1024">1024x1024</option>
          <option value="2048x2048">2048x2048</option>
        </select>
      </label>
      <label style={{ gridColumn: 'span 2' }}>
        Reference image path (optional, relative to the backend process, e.g. run from backend/)
        <input
          value={referenceImagePath}
          onChange={e => setReferenceImagePath(e.target.value)}
          placeholder="outputs/seed_reference.png"
        />
      </label>
      <button className="primary" type="submit" disabled={busy || !clientId}>
        {busy ? 'Generating…' : 'Generate asset'}
      </button>
      {error && <div className="error-text">{error}</div>}
    </form>
  )
}
