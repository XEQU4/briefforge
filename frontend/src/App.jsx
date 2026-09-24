import { useState } from 'react'
import Catalog from './pages/Catalog'
import TaskCard from './pages/TaskCard'
import TaskDetail from './pages/TaskDetail'
import TaskDraft from './pages/TaskDraft'

export default function App() {
  const [page, setPage] = useState('catalog')
  const [role, setRole] = useState('business')
  const [selectedTask, setSelectedTask] = useState(null)
  const [draft, setDraft] = useState(null)

  const openCatalog = () => setPage('catalog')
  const openTask = (task) => { setSelectedTask(task); setPage('detail') }
  const finishTask = (task) => { setSelectedTask(task); setDraft(null); setPage('catalog') }
  const changeRole = (nextRole) => {
    setRole(nextRole)
    if (nextRole === 'student' && (page === 'draft' || page === 'card')) {
      setDraft(null)
      setPage('catalog')
    }
  }

  return (
    <div className="app-root">
      <div className="aurora aurora-one" aria-hidden="true" />
      <div className="aurora aurora-two" aria-hidden="true" />
      <main className="app-shell">
        <nav className="topbar" aria-label="Main navigation">
          <button className="brand" type="button" onClick={openCatalog} aria-label="Open task catalog">
            <span className="brand-mark" aria-hidden="true"><span /></span>
            <span className="brand-copy"><strong>BriefForge</strong><small>Business Task Catalog</small></span>
          </button>

          <div className="nav-links" aria-label="Product navigation">
            <button className="nav-button" data-active={page === 'catalog' || page === 'detail'} onClick={openCatalog}>Catalog</button>
            {role === 'business' && <button className="nav-button" data-active={page === 'draft' || page === 'card'} onClick={() => setPage('draft')}>Create task</button>}
          </div>

          <div className="role-switch" aria-label="Demo role selector">
            <span>View as</span>
            <div className="segmented-control">
              <button aria-pressed={role === 'business'} onClick={() => changeRole('business')}>Business</button>
              <button aria-pressed={role === 'student'} onClick={() => changeRole('student')}>Student</button>
            </div>
          </div>
        </nav>

        <div className="page-stage">
          {page === 'catalog' && <Catalog onSelect={openTask} />}
          {page === 'detail' && <TaskDetail task={selectedTask} role={role} />}
          {page === 'draft' && <TaskDraft onCreated={(result) => setDraft(result)} />}
          {page === 'card' && draft && <TaskCard task={draft.task} questions={draft.questions} onConfirmed={finishTask} />}
          {page === 'draft' && draft && (
            <div className="continuation-bar">
              <div><span className="eyebrow">Draft created</span><strong>Continue to clarify and shape the task.</strong></div>
              <button onClick={() => setPage('card')}>Continue to task card <span aria-hidden="true">→</span></button>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
