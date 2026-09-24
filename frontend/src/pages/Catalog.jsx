import { useEffect, useState } from 'react'
import { listTasks } from '../api/tasks'
import ReadinessScore from '../components/ReadinessScore'
import { EmptyState, LoadingState } from '../components/StatePanel'
import Select from '../components/Select'

const readinessOptions = [
  { value: '', label: 'All levels' },
  { value: 'draft', label: 'Draft' },
  { value: 'working', label: 'Working' },
  { value: 'ready', label: 'Ready' },
  { value: 'priority', label: 'Priority' },
]

const sortOptions = [
  { value: '', label: 'Newest first' },
  { value: 'rating', label: 'Highest rating' },
]

export default function Catalog({ onSelect }) {
  const [tasks, setTasks] = useState([])
  const [topic, setTopic] = useState('')
  const [readiness, setReadiness] = useState('')
  const [sort, setSort] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    listTasks({ topic, readiness_level: readiness, sort })
      .then((value) => { if (active) setTasks(value) })
      .catch((reason) => { if (active) setError(reason.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [topic, readiness, sort])

  return (
    <section className="page catalog-page">
      <header className="hero bento-hero">
        <div className="hero-copy">
          <span className="eyebrow">Open opportunity board</span>
          <h1>Turn real business needs into student-ready challenges.</h1>
          <p>Explore confirmed tasks, understand how ready each brief is, and move from problem to proposal with less uncertainty.</p>
        </div>
        <div className="hero-stat glass-panel">
          <span className="hero-stat-label">Live catalog</span>
          <strong>{loading ? '—' : tasks.length}</strong>
          <small>{tasks.length === 1 ? 'matching task' : 'matching tasks'}</small>
        </div>
      </header>

      <div className="filters-panel glass-panel" aria-label="Catalog filters">
        <div className="filter-copy"><span className="eyebrow">Find your fit</span><strong>Filter the catalog</strong></div>
        <label>Topic<input placeholder="e.g. Reporting" value={topic} onChange={(event) => setTopic(event.target.value)} /></label>
        <Select label="Readiness" value={readiness} options={readinessOptions} onChange={setReadiness} />
        <Select label="Sort" value={sort} options={sortOptions} onChange={setSort} />
      </div>

      {error && <div className="feedback feedback-error" role="alert"><strong>Catalog unavailable</strong><span>{error}</span></div>}
      {loading && <div className="catalog-grid skeleton-grid" aria-label="Loading tasks"><LoadingState /><LoadingState /><LoadingState /></div>}
      {!loading && !error && tasks.length === 0 && <EmptyState title="No confirmed tasks match these filters" description="Try clearing a filter, or switch to Business mode and publish a new challenge." />}

      {!loading && !error && tasks.length > 0 && (
        <ul className="card-list catalog-grid">
          {tasks.map((task, index) => (
            <li className="task-card" key={task.id} style={{ '--delay': `${Math.min(index, 6) * 45}ms` }}>
              <div className="card-topline"><span className="task-id">TASK {String(task.id).padStart(2, '0')}</span>{task.topic && <span className="status-badge topic-badge">{task.topic}</span>}</div>
              <div className="card-heading"><h2>{task.title || `Task #${task.id}`}</h2></div>
              <p className="task-excerpt">{task.context || 'No context provided yet.'}</p>
              <ReadinessScore task={task} compact />
              <button className="card-action" onClick={() => onSelect?.(task)}>Open challenge <span aria-hidden="true">↗</span></button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
