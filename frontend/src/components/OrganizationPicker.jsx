import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { createOrganization, listMyOrganizations } from '../api/organizations'
import { LoadingState } from './StatePanel'

function slugFor(name) {
  const normalized = name.trim().normalize('NFKC').toLowerCase().replace(/\s+/gu, ' ')
  const withoutMarks = normalized.normalize('NFKD').replace(/\p{M}+/gu, '')
  const base = withoutMarks.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
  const nonAsciiLetters = /[^\x00-\x7f]/u.test(withoutMarks.replace(/[^\p{L}\p{N}]/gu, ''))
  let suffix = ''
  if (!base || nonAsciiLetters) {
    // A stable suffix keeps names in any script usable without transliteration.
    let hash = 2166136261
    for (const character of normalized) hash = Math.imul(hash ^ character.codePointAt(0), 16777619)
    suffix = `-${(hash >>> 0).toString(16).padStart(8, '0')}`
  }
  return `${(base || 'organization').slice(0, 120 - suffix.length).replace(/-+$/g, '')}${suffix}`
}

export default function OrganizationPicker({ initialSelectedId, onSelectionChange }) {
  const [organizations, setOrganizations] = useState([])
  const [searchParams, setSearchParams] = useSearchParams()
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [createError, setCreateError] = useState('')
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const [loaded, setLoaded] = useState(false)
  const [success, setSuccess] = useState('')
  const nameRef = useRef(null)
  const selectRef = useRef(null)
  const moveFocus = useRef(false)
  const requestedId = searchParams.get('org') ?? String(initialSelectedId ?? '')
  const selectedId = String((organizations.find((item) => String(item.id) === requestedId) || organizations[0])?.id ?? '')

  useEffect(() => {
    if (!moveFocus.current || loading || creating) return
    const target = showCreate ? nameRef.current : selectRef.current
    if (target) { target.focus(); moveFocus.current = false }
  }, [showCreate, loading, creating])

  useEffect(() => {
    let active = true
    setLoading(true)
    setLoaded(false)
    setError('')
    listMyOrganizations().then((items) => {
      if (!active) return
      setOrganizations(items)
      setLoaded(true)
      setShowCreate(items.length === 0)
    }).catch((reason) => { if (active) setError(reason.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [reload])

  useEffect(() => {
    // Only membership results may select an organization; URL IDs are preferences.
    onSelectionChange?.(loaded && selectedId ? Number(selectedId) : null, loaded ? organizations.length : null)
  }, [loaded, selectedId, organizations.length, onSelectionChange])

  useEffect(() => {
    if (!loaded || (searchParams.get('org') || '') === selectedId) return
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      if (selectedId) next.set('org', selectedId)
      else next.delete('org')
      return next
    }, { replace: true })
  }, [loaded, selectedId, searchParams, setSearchParams])

  function selectOrganization(id) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      next.set('org', String(id))
      return next
    })
  }

  async function submit(event) {
    event.preventDefault()
    if (creating || !name.trim()) return
    setCreating(true)
    setCreateError('')
    setSuccess('')
    try {
      const created = await createOrganization({ name: name.trim(), slug: slugFor(name) })
      setOrganizations((current) => [...current, created])
      selectOrganization(created.id)
      moveFocus.current = true
      setShowCreate(false)
      setName('')
      setSuccess(`Organization “${created.name}” created and selected.`)
    } catch (reason) {
      setCreateError(reason.status === 409
        ? 'An organization with this identifier already exists. Try a slightly different name.'
        : 'Unable to create your organization. Check your connection and try again.')
    } finally { setCreating(false) }
  }

  if (loading) return <LoadingState compact title="Loading organizations" lines={2} />
  if (error) return <div className="feedback feedback-error" role="alert"><span>Unable to load your organizations. Please retry.</span><button className="secondary" onClick={() => setReload((value) => value + 1)}>Retry</button></div>

  return (
    <div className="organization-picker">
      {organizations.length > 0 && <div className="organization-selector-row">
        <label>Organization
          <select ref={selectRef} value={selectedId} disabled={creating} onChange={(event) => selectOrganization(event.target.value)}>
            {organizations.map((organization) => <option key={organization.id} value={organization.id}>{organization.name}</option>)}
          </select>
        </label>
        {!showCreate && <button className="text-button" type="button" onClick={() => { moveFocus.current = true; setShowCreate(true); setCreateError(''); setSuccess('') }}>Create another organization</button>}
      </div>}
      {success && <div className="feedback feedback-success" role="status">{success}</div>}
      {showCreate && <form className="organization-create-form" onSubmit={submit} aria-busy={creating}>
        <div className="panel-heading"><h2>{organizations.length ? 'Add an organization' : 'Create your organization'}</h2><p>You need an organization workspace before creating business challenges.</p></div>
        {createError && <div className="feedback feedback-error" role="alert">{createError}</div>}
        <label>Organization name<input ref={nameRef} name="organization_name" autoComplete="organization" required maxLength={200} disabled={creating} value={name} onChange={(event) => setName(event.target.value)} /></label>
        <div className="organization-create-actions">
          <button disabled={creating || !name.trim()}>{creating ? 'Creating…' : 'Create organization'}</button>
          {organizations.length > 0 && <button className="text-button" type="button" disabled={creating} onClick={() => { moveFocus.current = true; setShowCreate(false); setCreateError('') }}>Cancel</button>}
        </div>
      </form>}
    </div>
  )
}
