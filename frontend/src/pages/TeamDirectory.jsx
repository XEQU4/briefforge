import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { createTeam, listMyTeams, listTeams } from '../api/teams'
import { useAuth } from '../auth/AuthContext'
import { EmptyState, LoadingState } from '../components/StatePanel'
import useListQuery from '../hooks/useListQuery'

const PAGE_SIZE = 12
const querySchema = { q: { maxLength: 200 } }
const EMPTY_FORM = { name: '', interests: '', skills: '', technologies: '' }

export default function TeamDirectory() {
  const { authenticated } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const { q, page, update, fitPage } = useListQuery(querySchema)
  const [version, setVersion] = useState(0)
  const [result, setResult] = useState(null)
  const [myTeamIds, setMyTeamIds] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formOpen, setFormOpen] = useState(location.hash === '#create-team')
  const nameInput = useRef(null)
  const createTrigger = useRef(null)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const [created, setCreated] = useState(null)

  useEffect(() => {
    if (location.hash === '#create-team') setFormOpen(true)
  }, [location.hash])

  useEffect(() => {
    if (authenticated && formOpen) nameInput.current?.focus()
  }, [authenticated, formOpen])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(false)
    Promise.all([
      listTeams(page, PAGE_SIZE, q),
      authenticated ? listMyTeams() : Promise.resolve({ items: [] }),
    ]).then(([teams, mine]) => {
      if (!active) return
      if (fitPage(teams.pages)) setResult(teams)
      setMyTeamIds(new Set(mine.items.map((team) => team.id)))
    }).catch(() => { if (active) setError(true) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, q, authenticated, version, fitPage])

  function closeForm() {
    setFormOpen(false)
    if (location.hash === '#create-team') navigate({ pathname: location.pathname, search: location.search, hash: '' }, { replace: true })
    createTrigger.current?.focus()
  }

  async function submit(event) {
    event.preventDefault()
    if (creating) return
    setCreating(true)
    setCreateError('')
    setCreated(null)
    try {
      const team = await createTeam({ ...form, interests: form.interests || null, skills: form.skills || null, technologies: form.technologies || null })
      setCreated(team)
      setForm(EMPTY_FORM)
      closeForm()
      setVersion((value) => value + 1)
      update({ page: 1 })
    } catch (reason) { setCreateError(reason.message) } finally { setCreating(false) }
  }

  return (
    <section className="page product-page teams-page">
      <header className="product-page-header">
        <div><span className="eyebrow">Teams</span><h1>Find a team</h1><p>Explore student teams and their skills.</p></div>
        <div className="product-actions">{authenticated ? <><Link className="secondary" to="/my-teams">My teams</Link><button ref={createTrigger} aria-expanded={formOpen} aria-controls="create-team" onClick={() => formOpen ? closeForm() : setFormOpen(true)} disabled={creating}>{formOpen ? 'Close form' : 'Create team'}</button></> : <Link to="/login" state={{ from: { pathname: '/teams', hash: '#create-team' } }}>Sign in to create a team</Link>}</div>
      </header>
      {authenticated && created && <div className="feedback feedback-success" role="status"><span>Team “{created.name}” created. You are its owner.</span><Link to={`/teams/${created.id}`}>View team</Link></div>}
      {authenticated && <div id="create-team" hidden={!formOpen} className="team-create-section">
        {formOpen && <form className="team-create-form" onSubmit={submit}>
          <div className="panel-heading"><h2>Create a team</h2><p>You’ll be added as the team owner automatically.</p></div>
          {createError && <div className="feedback feedback-error" role="alert">{createError}</div>}
          <div className="form-grid">
            <label>Name<input ref={nameInput} required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
            <label>Interests (optional)<input value={form.interests} onChange={(event) => setForm({ ...form, interests: event.target.value })} /></label>
            <label>Skills (optional)<input value={form.skills} onChange={(event) => setForm({ ...form, skills: event.target.value })} /></label>
            <label>Technologies (optional)<input value={form.technologies} onChange={(event) => setForm({ ...form, technologies: event.target.value })} /></label>
          </div>
          <div className="product-actions"><button disabled={creating}>{creating ? 'Creating…' : 'Create team'}</button><button className="secondary" type="button" disabled={creating} onClick={closeForm}>Cancel</button></div>
        </form>}
      </div>}
      <div className="product-toolbar directory-toolbar" role="group" aria-label="Team search">
        <label className="toolbar-search">Search teams<input type="search" maxLength={200} value={q} onChange={(event) => update({ q: event.target.value })} placeholder="Name, interests, skills…" /></label>
        {q && <button className="text-button" onClick={() => update({ q: '' })}>Clear search</button>}
        <span className="result-count" role="status">{!loading && !error && result ? `${result.total} ${result.total === 1 ? 'team' : 'teams'}` : loading ? 'Loading teams…' : ''}</span>
      </div>
      {error && <div className="feedback feedback-error" role="alert"><strong>Unable to load teams.</strong><span>Please try again.</span><button className="secondary" onClick={() => setVersion((value) => value + 1)}>Retry</button></div>}
      {loading && <div className="catalog-grid team-skeletons"><LoadingState title="Loading teams" lines={4} /><LoadingState lines={4} /><LoadingState lines={4} /></div>}
      {!loading && !error && result?.items.length === 0 && <EmptyState eyebrow="" title={q ? 'No teams match your search' : 'No teams yet'} description={q ? 'Try a different name, interest, or skill.' : 'Public team profiles will appear here.'} action={q && <button className="text-button" onClick={() => update({ q: '' })}>Clear search</button>} />}
      {!loading && !error && Boolean(result?.items.length) && <>
        <ul className="card-list catalog-grid team-grid">{result.items.map((team) => <li className="task-card team-card" key={team.id}>
          <div className="team-card-heading"><h2>{team.name}</h2>{myTeamIds.has(team.id) && <span className="status-badge">Your team</span>}</div>
          {team.interests && <p className="task-excerpt">{team.interests}</p>}
          {(team.skills || team.technologies) && <dl className="team-profile-meta">{team.skills && <div><dt>Skills</dt><dd>{team.skills}</dd></div>}{team.technologies && <div><dt>Technologies</dt><dd>{team.technologies}</dd></div>}</dl>}
          <Link className="card-action" to={`/teams/${team.id}`}>View team <span aria-hidden="true">→</span></Link>
        </li>)}</ul>
        <div className="pagination-controls"><span>Page {result.page} of {Math.max(result.pages, 1)}</span><div className="button-row"><button className="secondary" disabled={result.page <= 1} onClick={() => update({ page: page - 1 })}>Previous</button><button className="secondary" disabled={result.page >= result.pages} onClick={() => update({ page: page + 1 })}>Next</button></div></div>
      </>}
    </section>
  )
}
