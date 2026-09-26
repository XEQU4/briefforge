import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { archiveTask, getTask, publishTask, unpublishTask } from '../api/tasks'
import ReadinessScore from '../components/ReadinessScore'
import { EmptyState, LoadingState } from '../components/StatePanel'

const fields = [
  ['context', 'Context'], ['need', 'Business need'], ['users', 'Users'],
  ['data_materials', 'Data and materials'], ['constraints', 'Constraints'],
  ['expected_result', 'Expected result'], ['success_criteria', 'Success criteria'],
  ['contact', 'Contact'], ['interaction_format', 'Interaction format'],
]

export default function BusinessTask() {
  const { taskId } = useParams()
  const [task, setTask] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [action, setAction] = useState('')
  const [actionError, setActionError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    getTask(taskId).then((value) => { if (active) setTask(value) }).catch((reason) => { if (active) setError(reason) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [taskId])

  async function changePublication(nextAction) {
    setAction(nextAction)
    setActionError('')
    try {
      const actions = { publish: publishTask, unpublish: unpublishTask, archive: archiveTask }
      setTask(await actions[nextAction](taskId))
    } catch (reason) {
      setActionError(reason.message)
    } finally { setAction('') }
  }

  if (loading) return <section className="page"><LoadingState title="Loading business task" /></section>
  if (error?.status === 404) return <section className="page"><EmptyState title="Task not found" description="This task may have been removed or the link may be incorrect." action={<Link to="/business">Back to workspace</Link>} /></section>
  if (error?.status === 403) return <section className="page"><div className="feedback feedback-error" role="alert"><strong>You do not have access to this task.</strong><span>Ask an organization member to share access with you.</span></div></section>
  if (error) return <section className="page"><div className="feedback feedback-error" role="alert">Unable to load task: {error.message}</div></section>

  const canPublish = task.status === 'confirmed' && task.publication_status !== 'published'
  return (
    <section className="page business-task-page">
      <header className="page-header split-header">
        <div><span className="eyebrow">Business task #{task.id}</span><h1>{task.title || 'Untitled challenge'}</h1><p>{task.need || task.context || 'Review and manage this organization task.'}</p></div>
        <div className="status-orb glass-panel"><span>Content · Visibility</span><strong>{task.status} · {task.publication_status}</strong></div>
      </header>
      <div className="publication-panel feature-panel">
        <div><span className="eyebrow">Publication</span><h2>Manage catalog visibility</h2><p>The server checks your organization membership and task state for every action.</p></div>
        <div className="button-row publication-actions">
          {canPublish && <button disabled={Boolean(action)} onClick={() => changePublication('publish')}>{action === 'publish' ? 'Publishing…' : 'Publish'}</button>}
          {task.publication_status !== 'unpublished' && <button className="secondary" disabled={Boolean(action)} onClick={() => changePublication('unpublish')}>{action === 'unpublish' ? 'Unpublishing…' : task.publication_status === 'archived' ? 'Restore as unpublished' : 'Unpublish'}</button>}
          {task.publication_status !== 'archived' && <button className="danger-ghost" disabled={Boolean(action)} onClick={() => changePublication('archive')}>{action === 'archive' ? 'Archiving…' : 'Archive'}</button>}
        </div>
        {actionError && <div className="feedback feedback-error" role="alert">{actionError}</div>}
      </div>
      <div className="section-heading"><div><span className="eyebrow">Task card</span><h2>Challenge details</h2></div><ReadinessScore task={task} compact /></div>
      <div className="detail-grid">{fields.map(([key, label]) => <article className={task[key] ? '' : 'is-empty'} key={key}><h3>{label}</h3><p>{task[key] || 'Not provided.'}</p></article>)}</div>
      <div className="form-footer"><span className="form-hint">Proposal review is available only to members of this task’s organization.</span><Link className="small-primary-link" to={`/business/tasks/${task.id}/proposals`}>Review proposals</Link></div>
    </section>
  )
}
