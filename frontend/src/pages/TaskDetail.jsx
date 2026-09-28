import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router'
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
const EMPTY_FORM = { idea: '', plan: '', deadline: '', link: '' }

export default function TaskDetail() {
  const { taskId } = useParams()
  const { authenticated, loading: authLoading, refreshUser } = useAuth()
  const location = useLocation()
  const returnLocation = useRef(location)
  returnLocation.current = location
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [task, setTask] = useState(null)
  const [rating, setRating] = useState(null)
  const [teams, setTeams] = useState([])
  const [form, setForm] = useState(EMPTY_FORM)
  const [loading, setLoading] = useState(true)
  const [teamsLoading, setTeamsLoading] = useState(false)
  const [teamsLoaded, setTeamsLoaded] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [ratingError, setRatingError] = useState('')
  const [proposalError, setProposalError] = useState('')
  const [success, setSuccess] = useState('')
  const submittingRef = useRef(false)
  const requestedTeam = searchParams.get('team') || ''
  const teamId = teams.some((team) => String(team.id) === requestedTeam) ? requestedTeam : ''

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    setRating(null)
    setRatingError('')
    getTask(taskId).then((value) => {
      if (!active) return
      setTask(value)
      getTaskRating(taskId).then((score) => { if (active) setRating(score) }).catch((reason) => { if (active) setRatingError(reason.message) })
    }).catch(async (reason) => {
      if (!active) return
      if (reason.status === 401) {
        try { await refreshUser() } catch {}
        if (active) navigate('/login', { replace: true, state: { from: returnLocation.current } })
      } else setError(reason)
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [taskId, navigate, refreshUser])

  useEffect(() => {
    setTeamsLoaded(false)
    if (!authenticated) { setTeams([]); setTeamsLoading(false); return undefined }
    let active = true
    setTeamsLoading(true)
    listMyTeams().then((value) => { if (active) { setTeams(value.items); setTeamsLoaded(true) } }).catch((reason) => { if (active) setProposalError(reason.message) }).finally(() => { if (active) setTeamsLoading(false) })
    return () => { active = false }
  }, [authenticated])

  useEffect(() => {
    if (!authenticated || !teamsLoaded || !requestedTeam || teamId) return
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      next.delete('team')
      return next
    }, { replace: true })
  }, [authenticated, teamsLoaded, requestedTeam, teamId, setSearchParams])

  function selectTeam(id) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      if (id) next.set('team', id)
      else next.delete('team')
      return next
    })
  }

  async function submitProposal(event) {
    event.preventDefault()
    if (submittingRef.current || !teamId) return
    submittingRef.current = true
    setSubmitting(true)
    setProposalError('')
    setSuccess('')
    try {
      await createProposal(taskId, {
        ...form,
        team_id: Number(teamId),
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

  if (loading) return <section className="page product-page"><LoadingState title="Loading challenge" /></section>
  if (error?.status === 404) return <section className="page product-page"><EmptyState eyebrow="" title="Challenge not found" description="This challenge may have been removed or is no longer available." action={<Link to="/tasks">Explore challenges</Link>} /></section>
  if (error?.status === 403) return <section className="page product-page"><div className="feedback feedback-error" role="alert"><strong>You do not have access to this challenge.</strong><span>Ask an organization member to share it with you.</span></div></section>
  if (error) return <section className="page product-page"><div className="feedback feedback-error" role="alert">Unable to load this challenge. Please try again.</div><Link to="/tasks">Back to challenges</Link></section>

  return (
    <section className="page product-page public-challenge-page">
      <Link to="/tasks" className="back-link">← Back to challenges</Link>
      <header className="product-page-header challenge-header">
        <div><span className="eyebrow">Published challenge · #{task.id}</span><h1>{task.title || `Challenge #${task.id}`}</h1>{task.topic && <span className="status-badge topic-badge">{task.topic}</span>}<p>{task.need || task.context || 'Review the business challenge and available context.'}</p></div>
        <div className="challenge-rating">{rating ? <ReadinessScore task={task} rating={rating} /> : ratingError ? <p role="status">Readiness rating is temporarily unavailable.</p> : <LoadingState compact lines={2} title="Loading rating" />}</div>
      </header>
      <section aria-labelledby="challenge-information">
        <h2 className="product-section-title" id="challenge-information">Challenge information</h2>
        <dl className="challenge-fields">{fields.map(([key, label]) => <div className={task[key] ? '' : 'is-empty'} key={key}><dt>{label}</dt><dd>{task[key] || 'Not provided'}</dd></div>)}</dl>
      </section>

      {!authenticated && !authLoading && <section className="proposal-invite"><h2>Interested in this challenge?</h2><p>Sign in and choose your team to submit a proposal.</p><Link className="small-primary-link" to="/login" state={{ from: location }}>Sign in to submit a proposal</Link></section>}
      {authenticated && <section className="challenge-proposal" aria-labelledby="proposal-heading">
        <div className="section-heading"><h2 id="proposal-heading">Submit a proposal</h2><Link to="/my-teams">My teams</Link></div>
        {proposalError && <div className="feedback feedback-error" role="alert">{proposalError}</div>}
        {success && <div className="feedback feedback-success" role="status"><span>{success}</span><Link to="/proposals/mine">My proposals</Link></div>}
        {teamsLoading && <LoadingState compact lines={2} title="Loading your teams" />}
        {!teamsLoading && teamsLoaded && !teams.length && <EmptyState eyebrow="" title="Create a team to submit a proposal" description="Proposals are submitted on behalf of a team you belong to." action={<div className="product-actions"><Link className="small-primary-link" to="/teams#create-team">Create a team</Link><Link to="/teams">Browse teams</Link></div>} />}
        {teams.length > 0 && <form className="proposal-submit-form" onSubmit={submitProposal}>
          <div className="proposal-team-picker"><label>Your team<select required value={teamId} onChange={(event) => selectTeam(event.target.value)}><option value="">Select your team</option>{teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select></label><p className="proposal-helper" role="status">{teamId ? `Submitting for ${teams.find((team) => String(team.id) === teamId)?.name}.` : 'Choose a team you belong to.'}</p></div>
          <label className="proposal-idea">Solution idea<textarea required value={form.idea} onChange={(event) => setForm({ ...form, idea: event.target.value })} placeholder="Describe your approach to this challenge…" /></label>
          <label className="proposal-plan">Plan (optional)<textarea value={form.plan} onChange={(event) => setForm({ ...form, plan: event.target.value })} placeholder="Outline the main delivery steps…" /></label>
          <div className="form-grid"><label>Deadline (optional)<input value={form.deadline} onChange={(event) => setForm({ ...form, deadline: event.target.value })} placeholder="e.g. 3 days" /></label><label>Prototype link (optional)<input type="url" value={form.link} onChange={(event) => setForm({ ...form, link: event.target.value })} placeholder="https://…" /></label></div>
          <div className="form-footer"><span className="proposal-helper">The organization will review your proposal.</span><button disabled={submitting || teamsLoading || !teamId}>{submitting ? 'Submitting…' : 'Submit proposal'}</button></div>
        </form>}
      </section>}
    </section>
  )
}
