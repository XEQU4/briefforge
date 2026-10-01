import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { readAdmin, revokeUserSessions, setUserActive } from '../api/admin'
import { buildQueryString } from '../api/client'
import { EmptyState, LoadingState } from '../components/StatePanel'
import useListQuery from '../hooks/useListQuery'
import uiError from '../utils/uiError'

const sections = ['overview', 'users', 'organizations', 'teams', 'tasks', 'proposals', 'sessions']
const title = value => value.replaceAll('_', ' ').replace(/\b\w/g, character => character.toUpperCase())
const date = value => value ? new Date(value.endsWith('Z') ? value : value + 'Z').toLocaleString() : '—'
const selectFilter = (key, label, options) => ({ key, label, options })
const idFilter = (key, label) => ({ key, label, numeric: true })
const search = { key: 'q', label: 'Search' }
const order = selectFilter('sort', 'Sort', ['newest', 'oldest'])
const yesNo = [['', 'All'], ['true', 'Yes'], ['false', 'No']]
const config = {
  users: {
    filters: [search, selectFilter('is_active', 'Active', yesNo), selectFilter('is_admin', 'Admin', yesNo), selectFilter('sort', 'Sort', ['newest', 'oldest', 'email'])],
    columns: ['id', 'display_name', 'email', 'is_active', 'is_admin', 'last_login_at', 'created_at'],
  },
  organizations: { filters: [search, order], columns: ['id', 'name', 'slug', 'member_count', 'task_count', 'created_at'] },
  teams: { filters: [search, order], columns: ['id', 'name', 'interests', 'skills', 'technologies', 'member_count', 'proposal_count'] },
  tasks: {
    filters: [search, selectFilter('status', 'Status', ['', 'draft', 'clarifying', 'card_ready', 'confirmed']), selectFilter('publication_status', 'Publication', ['', 'unpublished', 'published', 'archived']), idFilter('organization_id', 'Organization ID'), selectFilter('sort', 'Sort', ['newest', 'oldest', 'rating'])],
    columns: ['id', 'title', 'organization_id', 'created_by_user_id', 'status', 'publication_status', 'rating_score', 'readiness_level', 'created_at'],
  },
  proposals: {
    filters: [selectFilter('status', 'Status', ['', 'pending', 'accepted', 'rejected']), idFilter('task_id', 'Task ID'), idFilter('team_id', 'Team ID'), idFilter('submitted_by_user_id', 'Submitted by user ID')],
    columns: ['id', 'task_id', 'team_id', 'submitted_by_user_id', 'idea', 'status', 'created_at'],
  },
  sessions: {
    filters: [search, idFilter('user_id', 'User ID'), selectFilter('status', 'Status', ['', 'active', 'revoked', 'expired', 'inactive'])],
    columns: ['id', 'user_id', 'email', 'display_name', 'status', 'created_at', 'expires_at', 'last_seen_at', 'revoked_at'],
  },
}
for (const section of Object.values(config)) {
  section.schema = Object.fromEntries(section.filters.map(filter => [filter.key, {
    ...(filter.options ? { options: filter.options.map(option => Array.isArray(option) ? option[0] : option) } : { maxLength: filter.numeric ? 10 : 200 }),
    ...(filter.key === 'sort' ? { default: 'newest' } : {}),
  }]))
}
const overviewLabels = { users: 'Users', active_users: 'Active users', organizations: 'Organizations', teams: 'Teams', tasks: 'Tasks', published_tasks: 'Published', proposals: 'Proposals', pending_proposals: 'Pending', active_sessions: 'Active sessions' }

function useAdminData(path, revision) {
  const key = path + ':' + revision
  const [state, setState] = useState({ key, loading: true })
  useEffect(() => {
    let active = true
    setState({ key, loading: true })
    readAdmin(path).then(data => { if (active) setState({ key, data, loading: false }) })
      .catch(error => { if (active) setState({ key, error, loading: false }) })
    return () => { active = false }
  }, [path, key])
  return state.key === key ? state : { loading: true }
}

function AdminError({ error, retry }) {
  return <div className="feedback feedback-error" role="alert">
    <span>{error.status === 403 ? 'Admin access required. Your administrator access may have changed.' : uiError(error, 'Unable to load admin data. Please try again.')}</span>
    <button className="secondary" onClick={retry}>Retry</button>
  </div>
}

export default function Admin() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const section = sections.includes(params.get('section')) ? params.get('section') : 'overview'
  if (!user.is_admin) return <section className="page product-page"><header className="product-page-header"><div><h1>Admin access required</h1><p>Your account does not have administrator access.</p></div></header><Link to="/tasks">Return to challenges</Link></section>
  return <section className="page product-page admin-page">
    <header className="product-page-header"><div><span className="eyebrow">Installation</span><h1>Admin</h1><p>Inspect records and manage account access.</p></div></header>
    <nav className="admin-nav" aria-label="Admin sections">{sections.map(item => <Link key={item} to={item === 'overview' ? '/admin' : `/admin?section=${item}`} aria-current={section === item ? 'page' : undefined} className={`nav-button${section === item ? ' is-active' : ''}`}>{title(item)}</Link>)}</nav>
    {section === 'overview' ? <Overview /> : <AdminList key={section} section={section} currentUser={user} />}
  </section>
}

function Overview() {
  const [revision, setRevision] = useState(0)
  const { data, loading, error } = useAdminData('summary', revision)
  return <section aria-labelledby="admin-overview-heading">
    <div className="admin-section-heading"><h2 id="admin-overview-heading">System overview</h2><button className="secondary" disabled={loading} onClick={() => setRevision(value => value + 1)}>Refresh</button></div>
    {loading && <LoadingState title="Loading system overview" />}
    {error && <AdminError error={error} retry={() => setRevision(value => value + 1)} />}
    {data && <dl className="admin-counts">{Object.entries(overviewLabels).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{data[key]}</dd></div>)}</dl>}
  </section>
}

function Filters({ filters, values, apply }) {
  const [draft, setDraft] = useState(values)
  return <form className="admin-filters" onSubmit={event => { event.preventDefault(); apply(draft) }}>
    {filters.map(filter => <label key={filter.key}>{filter.label}
      {filter.options ? <select value={draft[filter.key]} onChange={event => setDraft({ ...draft, [filter.key]: event.target.value })}>
        {filter.options.map(option => { const [value, label] = Array.isArray(option) ? option : [option, option ? title(option) : 'All']; return <option key={value} value={value}>{label}</option> })}
      </select> : <input type={filter.numeric ? 'number' : 'search'} min={filter.numeric ? 1 : undefined} step={filter.numeric ? 1 : undefined} max={filter.numeric ? 2147483647 : undefined} maxLength={filter.numeric ? undefined : 200} value={draft[filter.key]} onChange={event => setDraft({ ...draft, [filter.key]: event.target.value })} />}
    </label>)}
    <button type="submit">Apply filters</button>
  </form>
}

function AdminList({ section, currentUser }) {
  const { filters, schema, columns } = config[section]
  const query = useListQuery(schema)
  const [params, setParams] = useSearchParams()
  const [revision, setRevision] = useState(0)
  const values = Object.fromEntries(filters.map(filter => [filter.key, query[filter.key]]))
  const filterKey = JSON.stringify(values)
  const searchQuery = buildQueryString({ ...values, page: query.page, page_size: 20 })
  const { data, loading, error } = useAdminData(`${section}?${searchQuery}`, revision)
  const record = /^\d+$/.test(params.get('record') || '') && Number(params.get('record')) > 0 ? Number(params.get('record')) : null
  const showDetail = record && section !== 'sessions'
  const listParams = new URLSearchParams(params)
  listParams.delete('record')
  const listUrl = '/admin?' + listParams.toString()

  useEffect(() => { if (data) query.fitPage(data.pages) }, [data, query.fitPage])

  function apply(changes) {
    setParams(current => {
      const next = new URLSearchParams(current)
      next.delete('page')
      next.delete('record')
      for (const filter of filters) {
        const value = changes[filter.key]
        if (value) next.set(filter.key, value)
        else next.delete(filter.key)
      }
      return next
    })
  }

  return <section aria-labelledby="admin-list-heading">
    <div className="admin-section-heading"><h2 id="admin-list-heading">{title(section)}</h2><button className="secondary" disabled={loading} onClick={() => setRevision(value => value + 1)}>Refresh</button></div>
    {showDetail ? <AdminDetail key={section + ':' + record} section={section} id={record} currentUser={currentUser} revision={revision} onChange={() => setRevision(value => value + 1)} back={listUrl} /> : <>
      <Filters key={filterKey} filters={filters} values={values} apply={apply} />
      {loading && <LoadingState title={`Loading ${section}`} />}
      {error && <AdminError error={error} retry={() => setRevision(value => value + 1)} />}
      {data && <><p className="admin-result-count" role="status">{data.total} records</p>
        {data.items.length === 0 ? <EmptyState eyebrow="" title="No matching records" description="Try changing the filters." /> :
          <div className="admin-table-wrap"><table className="admin-table"><caption className="sr-only">{title(section)} records</caption>
            <thead><tr>{columns.map(column => <th key={column} scope="col">{title(column)}</th>)}{section !== 'sessions' && <th scope="col">Details</th>}</tr></thead>
            <tbody>{data.items.map(row => { const detailParams = new URLSearchParams(listParams); detailParams.set('record',row.id); return <tr key={row.id}>
              {columns.map(column => <td key={column} data-label={title(column)}><Value field={column} value={row[column]} compact /></td>)}
              {section !== 'sessions' && <td data-label="Details"><Link to={'/admin?' + detailParams} aria-label={`View ${section} record ${row.id}`}>View</Link></td>}
            </tr> })}</tbody>
          </table></div>}
        {data.pages > 0 && <div className="pagination-controls"><span>Page {data.page} of {data.pages}</span><div className="button-row">
          <button className="secondary" disabled={data.page <= 1 || loading} onClick={() => query.update({ page: query.page - 1 })}>Previous</button>
          <button className="secondary" disabled={data.page >= data.pages || loading} onClick={() => query.update({ page: query.page + 1 })}>Next</button>
        </div></div>}
      </>}
    </>}
  </section>
}

function Value({ field, value, compact = false }) {
  if (typeof value === 'boolean') return <span className="admin-flag">{value ? 'Yes' : 'No'}</span>
  if (value == null || value === '') return <span className="muted">—</span>
  if (field.endsWith('_at')) return <time dateTime={value}>{date(value)}</time>
  if (['status', 'publication_status', 'readiness_level'].includes(field)) return <span className={`status-badge status-${value}`}>{title(value)}</span>
  if (typeof value === 'object') return <span>{Object.entries(value).map(([key, amount]) => `${title(key)}: ${amount}`).join(' · ')}</span>
  return <span className={compact ? 'admin-cell-text' : undefined}>{String(value)}</span>
}

function AdminDetail({ section, id, currentUser, revision, onChange, back }) {
  const [notice, setNotice] = useState('')
  const { data, loading, error } = useAdminData(`${section}/${id}`, revision)
  return <div className="admin-detail">
    <Link className="back-link" to={back}>Back to {section}</Link>
    {notice && <p className="feedback feedback-success" role="status">{notice}</p>}
    {loading && <LoadingState title="Loading record details" />}
    {error && <AdminError error={error} retry={onChange} />}
    {data && <div className="feature-panel">
      <h3>{section === 'users' ? data.display_name || data.email : data.name || data.title || `${title(section)} #${id}`}</h3>
      <dl className="admin-record-fields">{Object.entries(data).map(([key, value]) => <div key={key}><dt>{title(key)}</dt><dd><Value field={key} value={value} /></dd></div>)}</dl>
      <div className="admin-related-links">
        {section === 'users' && <><Link to={`/admin?section=sessions&user_id=${id}`}>User sessions</Link><Link to={`/admin?section=proposals&submitted_by_user_id=${id}`}>Submitted proposals</Link></>}
        {section === 'organizations' && <Link to={`/admin?section=tasks&organization_id=${id}`}>Organization tasks</Link>}
        {section === 'teams' && <Link to={`/admin?section=proposals&team_id=${id}`}>Team proposals</Link>}
        {section === 'tasks' && <Link to={`/admin?section=proposals&task_id=${id}`}>Task proposals</Link>}
        {section === 'proposals' && <><Link to={`/admin?section=tasks&record=${data.task_id}`}>Task details</Link><Link to={`/admin?section=teams&record=${data.team_id}`}>Team details</Link></>}
      </div>
      {section === 'users' && <UserActions user={data} self={id === currentUser.id} onChange={message => { setNotice(message); onChange() }} />}
    </div>}
  </div>
}

function UserActions({ user, self, onChange }) {
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const mounted = useRef(false)
  const pending = useRef(false)
  const confirmationRef = useRef(null)
  const triggerRef = useRef(null)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => { if (confirmation) confirmationRef.current?.focus() }, [confirmation])

  async function perform(action) {
    if (pending.current || self) return
    pending.current = true
    setBusy(true)
    setError('')
    try {
      const result = action === 'revoke' ? await revokeUserSessions(user.id) : await setUserActive(user.id, action === 'activate')
      if (!mounted.current) return
      setConfirmation('')
      onChange(action === 'revoke' ? `${result.revoked_count} active sessions revoked.` : action === 'activate' ? 'Account reactivated. The user can log in again.' : 'Account deactivated and active sessions revoked.')
    } catch (reason) {
      if (mounted.current) setError(reason.status === 409 ? 'This action is not allowed for your own account.' : uiError(reason, 'Unable to update account access. Please try again.'))
    } finally {
      pending.current = false
      if (mounted.current) setBusy(false)
    }
  }

  function confirm(action, event) {
    triggerRef.current = event.currentTarget
    setConfirmation(action)
    setError('')
  }

  return <div className="admin-user-actions">
    <h3>Account access</h3>
    {self && <p>Your current account is protected from these actions.</p>}
    {error && <p className="feedback feedback-error" role="alert">{error}</p>}
    <div className="button-row">
      <button className="secondary" disabled={self || busy || Boolean(confirmation)} onClick={event => user.is_active ? confirm('deactivate', event) : perform('activate')}>{user.is_active ? 'Deactivate user' : 'Reactivate user'}</button>
      <button className="secondary" disabled={self || busy || Boolean(confirmation)} onClick={event => confirm('revoke', event)}>Revoke sessions</button>
    </div>
    {confirmation && <div className="admin-confirmation" role="group" aria-label="Confirm account action" aria-busy={busy}>
      <p ref={confirmationRef} tabIndex={-1}>{confirmation === 'deactivate' ? `Deactivate ${user.email}? Their active sessions will end and login will be blocked until reactivation.` : `Revoke all active sessions for ${user.email}? They will need to log in again.`}</p>
      <div className="button-row"><button disabled={busy} onClick={() => perform(confirmation)}>{busy ? 'Please wait…' : confirmation === 'deactivate' ? 'Confirm deactivation' : 'Confirm session revocation'}</button>
        <button className="secondary" disabled={busy} onClick={() => { setConfirmation(''); requestAnimationFrame(() => triggerRef.current?.focus()) }}>Cancel</button></div>
    </div>}
  </div>
}
