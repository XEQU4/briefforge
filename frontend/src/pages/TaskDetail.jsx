import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { createProposal } from '../api/proposals'
import { getTask, getTaskRating } from '../api/tasks'
import { listMyTeams } from '../api/teams'
import ReadinessScore from '../components/ReadinessScore'
import { EmptyState, LoadingState } from '../components/StatePanel'

const fields = [
  ['context', 'Context'], ['need', 'Business need'], ['users', 'Users'],
  ['data_materials', 'Data and materials'], ['constraints', 'Constraints'],
  ['expected_result', 'Expected result'], ['success_criteria', 'Success criteria'],
  ['contact', 'Contact'], ['interaction_format', 'Interaction format'],
]
const EMPTY_FORM = { team_id: '', idea: '', plan: '', deadline: '', link: '' }

export default function TaskDetail() {
  const { taskId } = useParams()
  const { authenticated, loading: authLoading, refreshUser } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [task, setTask] = useState(null)
  const [rating, setRating] = useState(null)
  const [teams, setTeams] = useState([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [loading, setLoading] = useState(true)
  const [teamsLoading, setTeamsLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [ratingError, setRatingError] = useState('')
  const [proposalError, setProposalError] = useState('')
  const [success, setSuccess] = useState('')
  const submittingRef = useRef(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    getTask(taskId).then((value) => {
      if (!active) return
      setTask(value)
      getTaskRating(taskId).then((score) => { if (active) setRating(score) }).catch((reason) => { if (active) setRatingError(reason.message) })
    }).catch(async (reason) => {
      if (!active) return
      if (reason.status === 401) {
        try { await refreshUser() } catch {}
        if (active) navigate('/login', { replace: true, state: { from: location } })
      } else setError(reason)
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [taskId, navigate, location, refreshUser])

  useEffect(() => {
    if (!authenticated) { setTeams([]); setTeamsLoading(false); return undefined }
    let active = true
    setTeamsLoading(true)
    listMyTeams().then((value) => { if (active) setTeams(value.items) }).catch((reason) => { if (active) setProposalError(reason.message) }).finally(() => { if (active) setTeamsLoading(false) })
    return () => { active = false }
  }, [authenticated])

  async function submitProposal(event) {
    event.preventDefault()
    if (submittingRef.current || !form.team_id) return
    submittingRef.current = true
    setSubmitting(true)
    setProposalError('')
    setSuccess('')
    try {
      await createProposal(taskId, {
        ...form,
        team_id: Number(form.team_id),
        plan: form.plan || null,
        deadline: form.deadline || null,
        link: form.link || null,
      })
      setForm(EMPTY_FORM)
      setSuccess('Proposal submitted. The organization can now review it.')
    } catch (reason) {
      if (reason.status === 401) setProposalError('Your session expired. Log in again to submit this proposal.')
      else setProposalError(reason.message)
    } finally { submittingRef.current = false; setSubmitting(false) }
  }

  if (loading) return <section className="page"><LoadingState title="Loading task" /></section>
  if (error?.status === 404) return <section className="page"><EmptyState title="Task not found" description="This task may have been removed or is no longer available." action={<Link to="/tasks">Browse tasks</Link>} /></section>
  if (error?.status === 403) return <section className="page"><div className="feedback feedback-error" role="alert"><strong>You do not have access to this task.</strong><span>Ask an organization member to share it with you.</span></div></section>
  if (error) return <section className="page"><div className="feedback feedback-error" role="alert">Unable to load task: {error.message}</div></section>

  return (
    <section className="page detail-page">
      <Link to="/tasks" className="back-link">← Back to tasks</Link>
      <header className="detail-hero">
        <div className="detail-title"><div className="card-topline"><span className="task-id">TASK {String(task.id).padStart(2, '0')}</span>{task.topic && <span className="status-badge topic-badge">{task.topic}</span>}</div><h1>{task.title || `Task #${task.id}`}</h1><p>{task.need || task.context || 'Review the business challenge and available context.'}</p></div>
        <div className="detail-rating">{rating ? <ReadinessScore task={task} rating={rating} /> : ratingError ? <div className="muted">Rating unavailable: {ratingError}</div> : <LoadingState compact lines={2} title="Loading rating" />}</div>
      </header>
      <div className="section-heading"><div><span className="eyebrow">Brief overview</span><h2>Task information</h2></div><span className="section-note">Published challenge</span></div>
      <div className="detail-grid">{fields.map(([key, label]) => <article className={task[key] ? '' : 'is-empty'} key={key}><h3>{label}</h3><p>{task[key] || 'Not provided.'}</p></article>)}</div>

      {!authenticated && !authLoading && <div className="feature-panel proposal-invite"><span className="eyebrow">Interested in this challenge?</span><h2>Sign in to submit a proposal.</h2><p>Proposal submission is available to authenticated members of a team.</p><Link className="small-primary-link" to="/login" state={{ from: location }}>Log in to continue</Link></div>}
      {authenticated && <div className="workspace-grid student-workspace">
        <form className="form-panel feature-panel" onSubmit={submitProposal}>
          <div className="panel-heading"><span className="eyebrow">Team workspace</span><h2>Submit a proposal</h2><p>Choose one of your teams and outline a concrete approach. The organization makes the final decision.</p></div>
          {proposalError && <div className="feedback feedback-error" role="alert">{proposalError}</div>}
          {success && <div className="feedback feedback-success" role="status"><span>{success}</span><Link to="/proposals/mine">View My proposals</Link></div>}
          {teamsLoading && <LoadingState compact lines={2} title="Loading your teams" />}
          {!teamsLoading && !teams.length && <EmptyState title="No team memberships found" description="Create a team profile first. Public team listings do not establish membership." action={<Link to="/teams">Browse or create a team</Link>} />}
          {teams.length > 0 && <>
            <label>Team<select required value={form.team_id} onChange={(event) => setForm({ ...form, team_id: event.target.value })}><option value="">Select your team</option>{teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select></label>
            <label>Solution idea<textarea required value={form.idea} onChange={(event) => setForm({ ...form, idea: event.target.value })} placeholder="Describe the core idea and why it fits the brief..." /></label>
            <label>Plan<textarea value={form.plan} onChange={(event) => setForm({ ...form, plan: event.target.value })} placeholder="Outline the main delivery steps..." /></label>
            <div className="form-grid"><label>Deadline<input value={form.deadline} onChange={(event) => setForm({ ...form, deadline: event.target.value })} placeholder="e.g. 3 days" /></label><label>Prototype link<input type="url" value={form.link} onChange={(event) => setForm({ ...form, link: event.target.value })} placeholder="https://..." /></label></div>
            <div className="form-footer"><span className="form-hint">Your team membership is checked by the backend.</span><button disabled={submitting || teamsLoading || !form.team_id}>{submitting ? 'Submitting…' : 'Submit proposal'}</button></div>
          </>}
        </form>
        <aside className="feature-panel team-creation"><div className="panel-heading"><span className="eyebrow">Team profile</span><h2>Need a team?</h2><p>Create a team profile and you’ll automatically become its owner.</p><Link to="/teams">Browse and manage teams</Link></div></aside>
      </div>}
    </section>
  )
}
