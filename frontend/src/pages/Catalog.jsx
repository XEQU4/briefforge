import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { listTasks } from '../api/tasks'
import ReadinessScore from '../components/ReadinessScore'
import { EmptyState, LoadingState } from '../components/StatePanel'
import Select from '../components/Select'

const PAGE_SIZE = 12
const readinessOptions = [
  { value: '', label: 'All levels' },
  { value: 'draft', label: 'Draft' },
  { value: 'working', label: 'Working' },
  { value: 'ready', label: 'Ready' },
  { value: 'priority', label: 'Priority' },
]
const sortOptions = [{ value: 'newest', label: 'Newest first' }, { value: 'rating', label: 'Highest rating' }]

export default function Catalog() {
  const [tasks, setTasks] = useState(null)
  const [topic, setTopic] = useState('')
  const [readiness, setReadiness] = useState('')
  const [sort, setSort] = useState('newest')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    listTasks({ topic, readiness_level: readiness, sort, q, page, page_size: PAGE_SIZE })
      .then((value) => { if (active) setTasks(value) })
      .catch((reason) => { if (active) setError(reason.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [topic, readiness, sort, q, page])

  function resetPage(setter) {
    return (value) => { setter(value); setPage(1) }
  }

  return (
    <section className="page catalog-page">
      <header className="hero bento-hero">
        <div className="hero-copy"><span className="eyebrow">Open opportunity board</span><h1>Turn real business needs into student-ready challenges.</h1><p>Explore published tasks, understand how ready each brief is, and move from problem to proposal with less uncertainty.</p></div>
        <div className="hero-stat glass-panel"><span className="hero-stat-label">Live catalog</span><strong>{loading ? '—' : tasks?.total ?? 0}</strong><small>{tasks?.total === 1 ? 'published task' : 'published tasks'}</small></div>
      </header>

      <div className="filters-panel glass-panel" aria-label="Catalog filters">
        <div className="filter-copy"><span className="eyebrow">Find your fit</span><strong>Filter the catalog</strong></div>
        <label>Topic<input placeholder="e.g. Reporting" value={topic} onChange={(event) => resetPage(setTopic)(event.target.value)} /></label>
        <label>Search<input maxLength={200} placeholder="Search briefs" value={q} onChange={(event) => resetPage(setQ)(event.target.value)} /></label>
        <Select label="Readiness" value={readiness} options={readinessOptions} onChange={resetPage(setReadiness)} />
        <Select label="Sort" value={sort} options={sortOptions} onChange={resetPage(setSort)} />
      </div>

      {error && <div className="feedback feedback-error" role="alert"><strong>Catalog unavailable</strong><span>{error}</span></div>}
      {loading && <div className="catalog-grid skeleton-grid" aria-label="Loading tasks"><LoadingState /><LoadingState /><LoadingState /></div>}
      {!loading && !error && tasks?.items.length === 0 && <EmptyState title="No published tasks match these filters" description="Try a different search or clear a filter." />}
      {!loading && !error && Boolean(tasks?.items.length) && <>
        <ul className="card-list catalog-grid">{tasks.items.map((task, index) => <li className="task-card" key={task.id} style={{ '--delay': `${Math.min(index, 6) * 45}ms` }}>
          <div className="card-topline"><span className="task-id">TASK {String(task.id).padStart(2, '0')}</span>{task.topic && <span className="status-badge topic-badge">{task.topic}</span>}</div>
          <div className="card-heading"><h2>{task.title || `Task #${task.id}`}</h2></div>
          <p className="task-excerpt">{task.context || 'No context provided yet.'}</p>
          <ReadinessScore task={task} compact />
          <Link className="card-action" to={`/tasks/${task.id}`}>Open challenge <span aria-hidden="true">→</span></Link>
        </li>)}</ul>
        <div className="pagination-controls"><span>Page {tasks.page} of {Math.max(tasks.pages, 1)} · {tasks.total} tasks</span><div className="button-row"><button className="secondary" disabled={tasks.page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</button><button className="secondary" disabled={tasks.page >= tasks.pages} onClick={() => setPage((current) => current + 1)}>Next</button></div></div>
      </>}
    </section>
  )
}
