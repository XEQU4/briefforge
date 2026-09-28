import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { listTasks } from '../api/tasks'
import ReadinessScore from '../components/ReadinessScore'
import { EmptyState, LoadingState } from '../components/StatePanel'
import Select from '../components/Select'
import useListQuery from '../hooks/useListQuery'

const PAGE_SIZE = 12
const readinessOptions = [
  { value: '', label: 'All levels' },
  { value: 'draft', label: 'Draft' },
  { value: 'working', label: 'Working' },
  { value: 'ready', label: 'Ready' },
  { value: 'priority', label: 'Priority' },
]
const sortOptions = [{ value: 'newest', label: 'Newest first' }, { value: 'rating', label: 'Highest rating' }]
const querySchema = {
  q: { maxLength: 200 }, topic: {},
  readiness: { options: readinessOptions.map(({ value }) => value) },
  sort: { default: 'newest', options: sortOptions.map(({ value }) => value) },
}

export default function Catalog() {
  const { q, topic, readiness, sort, page, update, fitPage } = useListQuery(querySchema)
  const [tasks, setTasks] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [reload, setReload] = useState(0)
  const filtered = Boolean(q || topic || readiness || sort !== 'newest')
  const clearFilters = () => update({ q: '', topic: '', readiness: '', sort: 'newest' })

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(false)
    listTasks({ topic, readiness_level: readiness, sort, q, page, page_size: PAGE_SIZE })
      .then((value) => { if (active && fitPage(value.pages)) setTasks(value) })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [topic, readiness, sort, q, page, reload, fitPage])

  return (
    <section className="page product-page catalog-page">
      <header className="product-page-header">
        <div><span className="eyebrow">Explore</span><h1>Business challenges</h1><p>Browse published challenges and find opportunities that match your team.</p></div>
        <span className="result-count" role="status">{!loading && !error && tasks ? `${tasks.total} published ${tasks.total === 1 ? 'challenge' : 'challenges'}` : loading ? 'Loading challenges…' : ''}</span>
      </header>

      <div className="product-toolbar catalog-toolbar" role="group" aria-label="Catalog filters">
        <label className="toolbar-search">Search challenges<input type="search" maxLength={200} placeholder="Search by keyword" value={q} onChange={(event) => update({ q: event.target.value })} /></label>
        <label>Topic<input placeholder="e.g. Reporting" value={topic} onChange={(event) => update({ topic: event.target.value })} /></label>
        <Select label="Readiness" value={readiness} options={readinessOptions} onChange={(value) => update({ readiness: value })} />
        <Select label="Sort" value={sort} options={sortOptions} onChange={(value) => update({ sort: value })} />
        {filtered && <button className="text-button" onClick={clearFilters}>Clear filters</button>}
      </div>

      {error && <div className="feedback feedback-error" role="alert"><strong>Unable to load challenges.</strong><span>Please try again.</span><button className="secondary" onClick={() => setReload((value) => value + 1)}>Retry</button></div>}
      {loading && <div className="catalog-grid catalog-skeletons" aria-label="Loading challenges"><LoadingState announce={false} lines={5} /><LoadingState announce={false} lines={5} /><LoadingState announce={false} lines={5} /></div>}
      {!loading && !error && tasks?.items.length === 0 && <EmptyState eyebrow="" title={filtered ? 'No challenges match these filters' : 'No published challenges yet'} description={filtered ? 'Try adjusting your search or filters.' : 'Published business challenges will appear here.'} action={filtered && <button className="text-button" onClick={clearFilters}>Clear filters</button>} />}
      {!loading && !error && Boolean(tasks?.items.length) && <>
        <ul className="card-list catalog-grid">{tasks.items.map((task, index) => <li className="task-card" key={task.id} style={{ '--delay': `${Math.min(index, 6) * 45}ms` }}>
          {task.topic && <span className="status-badge topic-badge" title={task.topic}>{task.topic}</span>}
          <h2>{task.title || `Challenge #${task.id}`}</h2>
          <p className="task-excerpt">{task.need || task.context || 'Explore this business challenge.'}</p>
          <ReadinessScore task={task} compact />
          <Link className="card-action" to={`/tasks/${task.id}`}>Open challenge <span aria-hidden="true">→</span></Link>
        </li>)}</ul>
        <div className="pagination-controls"><span>Page {tasks.page} of {Math.max(tasks.pages, 1)}</span><div className="button-row"><button className="secondary" disabled={tasks.page <= 1} onClick={() => update({ page: page - 1 })}>Previous</button><button className="secondary" disabled={tasks.page >= tasks.pages} onClick={() => update({ page: page + 1 })}>Next</button></div></div>
      </>}
    </section>
  )
}
