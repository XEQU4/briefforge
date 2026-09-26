import { useEffect, useState } from 'react'
import { createOrganization, listMyOrganizations } from '../api/organizations'
import { EmptyState, LoadingState } from './StatePanel'

function slugFor(name) {
  return name.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

export default function OrganizationPicker({ initialSelectedId, onSelectionChange }) {
  const [organizations, setOrganizations] = useState([])
  const [selectedId, setSelectedId] = useState(initialSelectedId ? String(initialSelectedId) : '')
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', slug: '' })
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    listMyOrganizations().then((items) => {
      if (!active) return
      setOrganizations(items)
      const preferred = items.find((item) => String(item.id) === String(initialSelectedId))
      setSelectedId(String(preferred?.id ?? items[0]?.id ?? ''))
      setShowCreate(items.length === 0)
    }).catch((reason) => { if (active) setError(reason.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [initialSelectedId])

  useEffect(() => { onSelectionChange?.(selectedId ? Number(selectedId) : null) }, [selectedId, onSelectionChange])

  function updateName(name) {
    setForm((current) => ({ ...current, name, slug: slugFor(name) }))
  }

  async function submit(event) {
    event.preventDefault()
    setCreating(true)
    setError('')
    try {
      const created = await createOrganization(form)
      setOrganizations((current) => [...current, created])
      setSelectedId(String(created.id))
      setShowCreate(false)
      setForm({ name: '', slug: '' })
    } catch (reason) {
      setError(reason.status === 409 ? 'That organization slug is already in use. Change the slug and try again.' : reason.message)
    } finally { setCreating(false) }
  }

  if (loading) return <LoadingState compact title="Loading organizations" lines={2} />
  if (error && organizations.length === 0 && !showCreate) return <div className="feedback feedback-error" role="alert">Unable to load organizations: {error}</div>

  return (
    <div className="organization-picker">
      {error && <div className="feedback feedback-error" role="alert">{error}</div>}
      {organizations.length > 0 && <label>Organization
        <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
          {organizations.map((organization) => <option key={organization.id} value={organization.id}>{organization.name}</option>)}
        </select>
      </label>}
      {showCreate ? <form className="form-panel compact-form" onSubmit={submit}>
        <div className="panel-heading"><span className="eyebrow">Business workspace</span><h2>{organizations.length ? 'Add an organization' : 'Create your organization'}</h2><p>Task drafts need an organization workspace.</p></div>
        <label>Name<input required maxLength={200} value={form.name} onChange={(event) => updateName(event.target.value)} /></label>
        <label>Slug<input required maxLength={120} value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} /></label>
        <button disabled={creating || !form.slug.trim()}>{creating ? 'Creating…' : 'Create organization'}</button>
      </form> : organizations.length > 0 && <button className="text-button" type="button" onClick={() => { setShowCreate(true); setError('') }}>Create another organization</button>}
      {!organizations.length && !showCreate && <EmptyState title="No organizations available" description="Create an organization to start a business task." />}
    </div>
  )
}
