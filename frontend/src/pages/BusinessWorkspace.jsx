import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { listOrganizationTasks } from '../api/organizations'
import { useAuth } from '../auth/AuthContext'
import OrganizationPicker from '../components/OrganizationPicker'
import { EmptyState, LoadingState } from '../components/StatePanel'

const PAGE_SIZE = 10

export default function BusinessWorkspace() {
  const { user } = useAuth()
  const [organizationId, setOrganizationId] = useState(null)
  const [result, setResult] = useState(null)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [publicationStatus, setPublicationStatus] = useState('')
  const [page, setPage] = useState(1)
  const [reload, setReload] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const onSelectionChange = useCallback((id) => {
    setOrganizationId(id)
    setPage(1)
    setResult(null)
  }, [])

  useEffect(() => {
    let active = true
    if (!organizationId) {
      setLoading(false)
      setResult(null)
      setError(null)
      return undefined
    }
    setLoading(true)
    setError(null)
    listOrganizationTasks(organizationId, {
      q: query,
      status,
      publication_status: publicationStatus,
      page,
      page_size: PAGE_SIZE,
      sort: 'newest',
    }).then((value) => { if (active) setResult(value) })
      .catch((reason) => { if (active) setError(reason) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [organizationId, query, status, publicationStatus, page, reload])

  const hasFilters = Boolean(query.trim() || status || publicationStatus)
  const createTask = <Link className="small-primary-link" to="/business/tasks/new" state={{ organizationId }}>Create a task</Link>

  return (
    <section className="page workspace-page">
      <header className="page-header split-header">
        <div><span className="eyebrow">Business workspace</span><h1>Shape a challenge around your organization.</h1><p>Choose an organization to manage its private and published tasks. The server checks your membership for every business action.</p></div>
        <div className="glass-panel account-summary"><span>Signed in as</span><strong>{user.display_name || user.email}</strong></div>
      </header>
      <div className="workspace-grid">
        <section className="feature-panel">
          <div className="panel-heading"><span className="eyebrow">Organizations</span><h2>Your workspaces</h2></div>
          <OrganizationPicker onSelectionChange={onSelectionChange} />
          {organizationId && <div className="form-footer"><span className="form-hint">Tasks and filters below belong to this organization.</span>{createTask}</div>}
        </section>
        <aside className="side-note glass-panel"><span className="eyebrow">Your workflow</span><h2>From need to published challenge.</h2><ul className="feature-list"><li><strong>Describe</strong><span>Start from the business need.</span></li><li><strong>Clarify</strong><span>Answer focused questions and shape the brief.</span></li><li><strong>Publish</strong><span>Manage visibility and review team proposals.</span></li></ul></aside>
      </div>

      {organizationId && <section className="business-task-list-section">
        <div className="section-heading"><div><span className="eyebrow">Selected organization</span><h2>Tasks</h2></div></div>
        <div className="filters-panel glass-panel business-task-filters">
          <label>Search tasks<input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Title, context, need, or topic" /></label>
          <label>Content status<select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}><option value="">All content states</option><option value="draft">Draft</option><option value="clarifying">Clarifying</option><option value="card_ready">Card ready</option><option value="confirmed">Confirmed</option></select></label>
          <label>Publication<select value={publicationStatus} onChange={(event) => { setPublicationStatus(event.target.value); setPage(1) }}><option value="">All publication states</option><option value="unpublished">Unpublished</option><option value="published">Published</option><option value="archived">Archived</option></select></label>
        </div>
        {error && <div className="feedback feedback-error" role="alert"><strong>Unable to load this organization’s tasks.</strong><span>Please retry. Your organization access is checked by the server.</span><button className="secondary" onClick={() => setReload((value) => value + 1)}>Retry</button></div>}
        {loading && <LoadingState title="Loading organization tasks" />}
        {!loading && !error && result?.items.length === 0 && hasFilters && <EmptyState title="No tasks match these filters" description="Adjust your search or status filters to see more tasks." action={<button className="secondary" onClick={() => { setQuery(''); setStatus(''); setPublicationStatus(''); setPage(1) }}>Clear filters</button>} />}
        {!loading && !error && result?.items.length === 0 && !hasFilters && <EmptyState title="No tasks in this organization yet" description="Create a task to turn a business need into a challenge for student teams." action={createTask} />}
        {!loading && !error && Boolean(result?.items.length) && <>
          <ul className="card-list business-task-list">{result.items.map((task) => <li className="task-card" key={task.id}>
            <div className="card-topline"><span className="task-id">TASK {String(task.id).padStart(2, '0')}</span><span className={`status-badge status-${task.publication_status}`}>{task.publication_status}</span></div>
            <h3>{task.title || `Task #${task.id}`}</h3><p className="task-excerpt">{task.need || task.context || 'No task summary yet.'}</p>
            <div className="task-meta"><span>Content: <strong>{task.status}</strong></span><span>Readiness: <strong>{task.readiness_level} · {task.rating_score}</strong></span>{task.created_at && <span>Created {new Date(task.created_at).toLocaleDateString()}</span>}</div>
            <Link className="card-action" to={`/business/tasks/${task.id}`}>Open task <span aria-hidden="true">→</span></Link>
          </li>)}</ul>
          <div className="pagination-controls"><span>Page {result.page} of {Math.max(result.pages, 1)} · {result.total} tasks</span><div className="button-row"><button className="secondary" disabled={result.page <= 1 || loading} onClick={() => setPage((current) => current - 1)}>Previous</button><button className="secondary" disabled={result.page >= result.pages || loading} onClick={() => setPage((current) => current + 1)}>Next</button></div></div>
        </>}
      </section>}
    </section>
  )
}
