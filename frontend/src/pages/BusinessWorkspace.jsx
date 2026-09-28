import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { listOrganizationTasks } from '../api/organizations'
import OrganizationPicker from '../components/OrganizationPicker'
import { EmptyState, LoadingState } from '../components/StatePanel'

const PAGE_SIZE = 10
const contentLabels = { draft: 'Draft', clarifying: 'Clarifying', card_ready: 'Ready to review', confirmed: 'Confirmed' }
const publicationLabels = { unpublished: 'Unpublished', published: 'Published', archived: 'Archived' }
const readinessLabels = { draft: 'Draft', working: 'Working', ready: 'Ready', priority: 'Priority' }

export default function BusinessWorkspace() {
  const [searchParams] = useSearchParams()
  const [organizationId, setOrganizationId] = useState(null)
  const [organizationCount, setOrganizationCount] = useState(null)
  const [result, setResult] = useState(null)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [publicationStatus, setPublicationStatus] = useState('')
  const [page, setPage] = useState(1)
  const [reload, setReload] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const onSelectionChange = useCallback((id, count) => {
    setOrganizationId(id)
    setOrganizationCount(count)
    setPage(1)
    setResult(null)
  }, [])
  // Hide previous results immediately when the URL changes, before the picker resolves it.
  const selectedOrganizationId = organizationId && String(organizationId) === searchParams.get('org') ? organizationId : null

  useEffect(() => {
    let active = true
    if (!selectedOrganizationId) {
      setLoading(false)
      setResult(null)
      setError(null)
      return undefined
    }
    setLoading(true)
    setError(null)
    setResult(null)
    listOrganizationTasks(selectedOrganizationId, {
      q: query,
      status,
      publication_status: publicationStatus,
      page,
      page_size: PAGE_SIZE,
      sort: 'newest',
    }).then((value) => { if (active) setResult({ organizationId: selectedOrganizationId, data: value }) })
      .catch((reason) => { if (active) setError(reason) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [selectedOrganizationId, query, status, publicationStatus, page, reload])

  const tasks = result?.organizationId === selectedOrganizationId ? result.data : null
  const hasFilters = Boolean(query.trim() || status || publicationStatus)
  const createTask = selectedOrganizationId && <Link className="small-primary-link" to={`/business/tasks/new?org=${selectedOrganizationId}`}>Create task</Link>

  function clearFilters() {
    setQuery('')
    setStatus('')
    setPublicationStatus('')
    setPage(1)
  }

  return (
    <section className="page business-dashboard">
      <header className="business-page-header">
        <div><span className="eyebrow">Business workspace</span><h1>Manage your challenges</h1><p>{organizationCount === 0 ? 'Create an organization to start publishing challenges.' : 'Create, publish, and manage tasks for your organization.'}</p></div>
        {createTask}
      </header>
      <OrganizationPicker onSelectionChange={onSelectionChange} />

      {selectedOrganizationId && <section className="business-task-list-section" aria-labelledby="business-tasks-heading">
        <div className="business-list-heading"><h2 id="business-tasks-heading">Tasks</h2><span role="status">{!loading && !error && tasks ? `${tasks.total} ${tasks.total === 1 ? 'task' : 'tasks'}` : ''}</span></div>
        <div className="business-filter-bar" role="group" aria-label="Task filters">
          <label className="business-task-search">Search tasks<input maxLength={200} value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Title, context, need, or topic" /></label>
          <label>Content status<select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}><option value="">All content states</option>{Object.entries(contentLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>Publication<select value={publicationStatus} onChange={(event) => { setPublicationStatus(event.target.value); setPage(1) }}><option value="">All publication states</option><option value="unpublished">Unpublished</option><option value="published">Published</option><option value="archived">Archived</option></select></label>
          {hasFilters && <button className="text-button" type="button" onClick={clearFilters}>Clear filters</button>}
        </div>
        {error && <div className="feedback feedback-error" role="alert"><strong>Unable to load this organization’s tasks.</strong><span>Please retry. If your access has changed, select another organization.</span><button className="secondary" onClick={() => setReload((value) => value + 1)}>Retry</button></div>}
        {loading && <LoadingState compact title="Loading organization tasks" />}
        {!loading && !error && tasks?.items.length === 0 && hasFilters && <EmptyState title="No tasks match these filters" description="Adjust your search or clear the filters to see more tasks." />}
        {!loading && !error && tasks?.items.length === 0 && !hasFilters && <EmptyState title="No challenges yet" description="Create your first business challenge for student teams." action={createTask} />}
        {!loading && !error && Boolean(tasks?.items.length) && <>
          <ul className="card-list business-task-list">{tasks.items.map((task) => <li className="business-task-row" key={task.id}>
            <div className="business-task-summary">
              <h3>{task.title || `Task #${task.id}`}</h3>
              {(task.need || task.context) && <p className="business-task-excerpt">{task.need || task.context}</p>}
              <div className="business-task-meta">
                <span className={`status-badge status-${task.status}`}><span className="sr-only">Content status: </span>{contentLabels[task.status] || task.status}</span>
                <span className={`status-badge status-${task.publication_status}`}><span className="sr-only">Publication: </span>{publicationLabels[task.publication_status] || task.publication_status}</span>
                <span>Readiness <strong>{task.rating_score ?? '—'}/100</strong>{task.readiness_level && ` · ${readinessLabels[task.readiness_level] || task.readiness_level}`}</span>
                {task.created_at && <span>Created <time dateTime={task.created_at}>{new Date(task.created_at).toLocaleDateString()}</time></span>}
              </div>
            </div>
            <Link className="business-task-link" to={`/business/tasks/${task.id}`} aria-label={`Open task: ${task.title || `Task #${task.id}`}`}>Open task <span aria-hidden="true">→</span></Link>
          </li>)}</ul>
          <div className="pagination-controls"><span>Page {tasks.page} of {Math.max(tasks.pages, 1)} · {tasks.total} tasks</span><div className="button-row"><button className="secondary" disabled={tasks.page <= 1 || loading} onClick={() => setPage((current) => current - 1)}>Previous</button><button className="secondary" disabled={tasks.page >= tasks.pages || loading} onClick={() => setPage((current) => current + 1)}>Next</button></div></div>
        </>}
      </section>}
    </section>
  )
}
