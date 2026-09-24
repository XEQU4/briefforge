import { useEffect, useState } from 'react'
import { createProposal, listProposals, updateProposal } from '../api/proposals'
import { getTaskRating } from '../api/tasks'
import { createTeam, listTeams } from '../api/teams'
import ReadinessScore from '../components/ReadinessScore'
import { EmptyState, LoadingState } from '../components/StatePanel'

const detailFields = ['title', 'context', 'need', 'users', 'data_materials', 'constraints', 'expected_result', 'success_criteria', 'contact', 'interaction_format', 'topic']
const fieldLabels = { title: 'Title', context: 'Context', need: 'Business need', users: 'Users', data_materials: 'Data and materials', constraints: 'Constraints', expected_result: 'Expected result', success_criteria: 'Success criteria', contact: 'Contact', interaction_format: 'Interaction format', topic: 'Topic' }
const emptyProposal = { team_id: '', idea: '', plan: '', deadline: '', link: '' }
const emptyTeam = { name: '', interests: '', skills: '', technologies: '' }

export default function TaskDetail({ task, taskId, role = 'business' }) {
  const id = taskId || task?.id
  const [proposals, setProposals] = useState([])
  const [teams, setTeams] = useState([])
  const [rating, setRating] = useState(null)
  const [form, setForm] = useState(emptyProposal)
  const [teamForm, setTeamForm] = useState(emptyTeam)
  const [loading, setLoading] = useState(false)
  const [ratingLoading, setRatingLoading] = useState(true)
  const [teamsLoading, setTeamsLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [teamCreating, setTeamCreating] = useState(false)
  const [pendingAction, setPendingAction] = useState(null)
  const [success, setSuccess] = useState('')
  const [teamSuccess, setTeamSuccess] = useState('')
  const [error, setError] = useState('')
  const [proposalError, setProposalError] = useState('')
  const [teamsError, setTeamsError] = useState('')
  const [teamCreateError, setTeamCreateError] = useState('')

  useEffect(() => {
    if (!id) return
    let active = true
    setRatingLoading(true)
    getTaskRating(id).then((score) => { if (active) setRating(score) }).catch((reason) => { if (active) setError(reason.message) }).finally(() => { if (active) setRatingLoading(false) })
    return () => { active = false }
  }, [id])

  useEffect(() => {
    if (!id || role !== 'business') { setLoading(false); return }
    let active = true
    setLoading(true); setProposalError('')
    listProposals(id).then((items) => { if (active) setProposals(items) }).catch((reason) => { if (active) setProposalError(reason.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id, role])

  useEffect(() => {
    if (!id) return
    let active = true
    setTeamsLoading(true); setTeamsError('')
    listTeams().then((items) => { if (active) setTeams((current) => { const merged = new Map(items.map((team) => [team.id, team])); current.forEach((team) => merged.set(team.id, team)); return [...merged.values()] }) }).catch((reason) => { if (active) setTeamsError(reason.message) }).finally(() => { if (active) setTeamsLoading(false) })
    return () => { active = false }
  }, [id])

  if (!id) return <div className="feedback feedback-error" role="alert">Task id is missing.</div>

  const teamNames = new Map(teams.map((team) => [team.id, team.name]))

  async function submitProposal(event) {
    event.preventDefault(); setSubmitting(true); setError(''); setSuccess('')
    try {
      const value = await createProposal(id, { ...form, team_id: Number(form.team_id), plan: form.plan || null, deadline: form.deadline || null, link: form.link || null })
      setProposals((current) => [...current, value]); setForm(emptyProposal); setSuccess('Proposal submitted. Switch to Business view to review it.')
    } catch (reason) { setError(reason.message) } finally { setSubmitting(false) }
  }

  async function submitTeam(event) {
    event.preventDefault(); setTeamCreating(true); setTeamCreateError(''); setTeamSuccess('')
    try {
      const created = await createTeam({ name: teamForm.name, interests: teamForm.interests || null, skills: teamForm.skills || null, technologies: teamForm.technologies || null })
      setTeams((current) => [...current.filter((team) => team.id !== created.id), created])
      setForm((current) => ({ ...current, team_id: String(created.id) }))
      setTeamForm(emptyTeam); setTeamsError(''); setTeamSuccess(`Team “${created.name}” created and selected.`)
    } catch (reason) { setTeamCreateError(reason.message) } finally { setTeamCreating(false) }
  }

  async function setStatus(proposal, status) {
    setPendingAction(proposal.id); setError('')
    try {
      const value = await updateProposal(proposal.id, status)
      setProposals((current) => current.map((item) => item.id === value.id ? value : item)); setSuccess(`Proposal ${status}.`)
    } catch (reason) { setError(reason.message) } finally { setPendingAction(null) }
  }

  return (
    <section className="page detail-page">
      <header className="detail-hero">
        <div className="detail-title"><div className="card-topline"><span className="task-id">TASK {String(id).padStart(2, '0')}</span>{task?.topic && <span className="status-badge topic-badge">{task.topic}</span>}</div><h1>{task?.title || `Task #${id}`}</h1><p>{task?.need || task?.context || 'Open the task card to review the business challenge and available context.'}</p></div>
        <div className="detail-rating">{ratingLoading ? <LoadingState compact lines={2} /> : <ReadinessScore task={task} rating={rating} />}</div>
      </header>

      {error && <div className="feedback feedback-error" role="alert"><strong>Request failed</strong><span>{error}</span></div>}
      {success && <div className="feedback feedback-success" role="status"><strong>Done</strong><span>{success}</span></div>}

      <div className="section-heading"><div><span className="eyebrow">Brief overview</span><h2>Task information</h2></div><span className="section-note">Confirmed business context</span></div>
      <div className="detail-grid">{detailFields.map((field) => <article className={task?.[field] ? '' : 'is-empty'} key={field}><h3>{fieldLabels[field]}</h3><p>{task?.[field] || 'Not provided.'}</p></article>)}</div>

      {role === 'student' && (
        <div className="workspace-grid student-workspace">
          <form className="form-panel feature-panel" onSubmit={submitProposal}>
            <div className="panel-heading"><span className="eyebrow">Student workspace</span><h2>Submit a proposal</h2><p>Choose your team and outline a concrete approach. The business makes the final decision.</p></div>
            {teamsLoading && <LoadingState compact lines={2} title="Loading teams" />}
            {teamsError && <div className="feedback feedback-error" role="alert">Teams could not be loaded: {teamsError}</div>}
            {!teamsLoading && !teamsError && teams.length === 0 && <div className="inline-empty">No teams are available yet. Create one in the panel beside this form.</div>}
            <label>Team<select required disabled={teamsLoading || teams.length === 0} value={form.team_id} onChange={(event) => setForm({ ...form, team_id: event.target.value })}><option value="">Select a team</option>{teams.map((team) => <option key={team.id} value={team.id}>{team.name}</option>)}</select></label>
            <label>Solution idea<textarea required placeholder="Describe the core idea and why it fits the brief..." value={form.idea} onChange={(event) => setForm({ ...form, idea: event.target.value })} /></label>
            <label>Plan<textarea placeholder="Outline the main delivery steps..." value={form.plan} onChange={(event) => setForm({ ...form, plan: event.target.value })} /></label>
            <div className="form-grid"><label>Deadline<input placeholder="e.g. 3 days" value={form.deadline} onChange={(event) => setForm({ ...form, deadline: event.target.value })} /></label><label>Prototype link<input type="url" placeholder="https://..." value={form.link} onChange={(event) => setForm({ ...form, link: event.target.value })} /></label></div>
            <div className="form-footer"><span className="form-hint">You can retry safely if submission fails.</span><button disabled={submitting || teamsLoading || teams.length === 0 || !form.team_id}>{submitting ? 'Submitting…' : 'Submit proposal'}</button></div>
          </form>

          <section className="feature-panel team-creation"><div className="panel-heading"><span className="eyebrow">Team profile</span><h2>Create a team</h2><p>Not listed yet? Create a lightweight demo profile and it will be selected automatically.</p></div>{teamCreateError && <div className="feedback feedback-error" role="alert">{teamCreateError}</div>}{teamSuccess && <div className="feedback feedback-success" role="status">{teamSuccess}</div>}<form onSubmit={submitTeam}><label>Name<input required placeholder="Cyber Owls" value={teamForm.name} onChange={(event) => setTeamForm({ ...teamForm, name: event.target.value })} /></label><label>Interests<input placeholder="AI, education, automation" value={teamForm.interests} onChange={(event) => setTeamForm({ ...teamForm, interests: event.target.value })} /></label><label>Skills<input placeholder="Research, frontend, backend" value={teamForm.skills} onChange={(event) => setTeamForm({ ...teamForm, skills: event.target.value })} /></label><label>Technologies<input placeholder="React, FastAPI, Python" value={teamForm.technologies} onChange={(event) => setTeamForm({ ...teamForm, technologies: event.target.value })} /></label><button className="secondary" disabled={teamCreating}>{teamCreating ? 'Creating…' : 'Create & select team'}</button></form></section>
        </div>
      )}

      {role === 'business' && (
        <section className="proposal-section">
          <div className="section-heading"><div><span className="eyebrow">Business workspace</span><h2>Team proposals</h2></div><span className="section-note">Manual decision only</span></div>
          {teamsLoading && <p className="muted">Loading team names…</p>}
          {teamsError && <p className="muted">Team names are unavailable; proposal IDs are shown instead.</p>}
          {proposalError && <div className="feedback feedback-error" role="alert">{proposalError}</div>}
          {loading && <div className="proposal-grid"><LoadingState /><LoadingState /></div>}
          {!loading && !proposalError && proposals.length === 0 && <EmptyState title="No proposals yet" description="Switch to Student view on this page to submit a proposal, then return to Business view to review it." />}
          {!loading && proposals.length > 0 && <ul className="card-list proposal-grid">{proposals.map((proposal) => <li className="proposal-card" key={proposal.id}><div className="card-topline"><span className="proposal-team">{teamNames.get(proposal.team_id) || `Team #${proposal.team_id}`}</span><span className={`status-badge status-${proposal.status}`}>{proposal.status}</span></div><h3>{proposal.idea}</h3><p>{proposal.plan || 'No plan provided.'}</p><div className="proposal-meta">{proposal.deadline && <span>Deadline · {proposal.deadline}</span>}{proposal.link && <a href={proposal.link} target="_blank" rel="noreferrer">Open prototype ↗</a>}</div>{proposal.status === 'pending' && <div className="button-row"><button disabled={pendingAction === proposal.id} onClick={() => setStatus(proposal, 'accepted')}>{pendingAction === proposal.id ? 'Updating…' : 'Accept proposal'}</button><button className="danger-ghost" disabled={pendingAction === proposal.id} onClick={() => setStatus(proposal, 'rejected')}>Reject</button></div>}</li>)}</ul>}
        </section>
      )}
    </section>
  )
}
