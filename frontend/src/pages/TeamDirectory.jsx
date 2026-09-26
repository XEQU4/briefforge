import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { createTeam, listMyTeams, listTeams } from '../api/teams'
import { useAuth } from '../auth/AuthContext'
import { EmptyState, LoadingState } from '../components/StatePanel'

const PAGE_SIZE = 12

export default function TeamDirectory() {
  const { authenticated } = useAuth()
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [version, setVersion] = useState(0)
  const [result, setResult] = useState(null)
  const [myTeamIds, setMyTeamIds] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ name: '', interests: '', skills: '', technologies: '' })
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const [created, setCreated] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    Promise.all([
      listTeams(page, PAGE_SIZE, q),
      authenticated ? listMyTeams() : Promise.resolve({ items: [] }),
    ]).then(([teams, mine]) => {
      if (!active) return
      setResult(teams)
      setMyTeamIds(new Set(mine.items.map((team) => team.id)))
    }).catch((reason) => { if (active) setError(reason.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, q, authenticated, version])

  async function submit(event) {
    event.preventDefault()
    setCreating(true)
    setCreateError('')
    setCreated('')
    try {
      const team = await createTeam({ ...form, interests: form.interests || null, skills: form.skills || null, technologies: form.technologies || null })
      setCreated(`Team “${team.name}” created. You are its owner.`)
      setForm({ name: '', interests: '', skills: '', technologies: '' })
      setVersion((value) => value + 1)
      setPage(1)
    } catch (reason) { setCreateError(reason.message) } finally { setCreating(false) }
  }

  return (
    <section className="page teams-page">
      <header className="page-header"><span className="eyebrow">Student teams</span><h1>Find a team. Or start one.</h1><p>Public team profiles help businesses learn about your interests and skills. Membership stays private.</p></header>
      {authenticated && <form className="feature-panel team-create-form" onSubmit={submit}>
        <div className="panel-heading"><span className="eyebrow">Your team</span><h2>Create a team profile</h2><p>You’ll be added as the team owner automatically.</p></div>
        {createError && <div className="feedback feedback-error" role="alert">{createError}</div>}
        {created && <div className="feedback feedback-success" role="status">{created}</div>}
        <div className="form-grid"><label>Name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label>Interests<input value={form.interests} onChange={(event) => setForm({ ...form, interests: event.target.value })} /></label><label>Skills<input value={form.skills} onChange={(event) => setForm({ ...form, skills: event.target.value })} /></label><label>Technologies<input value={form.technologies} onChange={(event) => setForm({ ...form, technologies: event.target.value })} /></label></div>
        <button disabled={creating}>{creating ? 'Creating…' : 'Create team'}</button>
      </form>}
      <div className="filters-panel glass-panel team-filters"><label>Search teams<input value={q} onChange={(event) => { setQ(event.target.value); setPage(1) }} placeholder="Name, interests, skills…" /></label><span className="muted">{result ? `${result.total} teams` : 'Browse teams'}</span></div>
      {error && <div className="feedback feedback-error" role="alert">Unable to load teams: {error}</div>}
      {loading && <div className="catalog-grid skeleton-grid"><LoadingState /><LoadingState /><LoadingState /></div>}
      {!loading && !error && result?.items.length === 0 && <EmptyState title="No teams found" description="Try a different search, or create a team profile above." />}
      {!loading && !error && Boolean(result?.items.length) && <>
        <ul className="card-list catalog-grid team-grid">{result.items.map((team) => <li className="task-card team-card" key={team.id}><div className="card-topline"><span className="task-id">TEAM {String(team.id).padStart(2, '0')}</span>{myTeamIds.has(team.id) && <span className="status-badge topic-badge">Your team</span>}</div><h2>{team.name}</h2><p className="task-excerpt">{team.interests || team.skills || 'No profile details yet.'}</p><div className="team-profile-meta">{team.skills && <span><strong>Skills</strong> {team.skills}</span>}{team.technologies && <span><strong>Tools</strong> {team.technologies}</span>}</div><Link className="card-action" to={`/teams/${team.id}`}>View team <span aria-hidden="true">→</span></Link></li>)}</ul>
        <div className="pagination-controls"><span>Page {result.page} of {Math.max(result.pages, 1)} · {result.total} teams</span><div className="button-row"><button className="secondary" disabled={result.page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</button><button className="secondary" disabled={result.page >= result.pages} onClick={() => setPage((current) => current + 1)}>Next</button></div></div>
      </>}
    </section>
  )
}
