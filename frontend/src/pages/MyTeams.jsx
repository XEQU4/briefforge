import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { listMyTeams } from '../api/teams'
import { EmptyState, LoadingState } from '../components/StatePanel'
import uiError from '../utils/uiError'

const PAGE_SIZE = 12

export default function MyTeams() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedPage = Number(searchParams.get('page') || 1)
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    listMyTeams(page, PAGE_SIZE).then((value) => {
      if (!active) return
      const lastPage = Math.max(value.pages, 1)
      if (page > lastPage || (searchParams.has('page') && searchParams.get('page') !== String(page))) {
        const next = new URLSearchParams(searchParams)
        next.set('page', String(Math.min(page, lastPage)))
        setSearchParams(next, { replace: true })
      }
      setResult(value)
    }).catch((reason) => { if (active) setError(uiError(reason, 'Please try loading your teams again.')) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, reload, searchParams, setSearchParams])

  function changePage(value) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current)
      next.set('page', String(value))
      return next
    })
  }

  const teamActions = <div className="my-teams-actions"><Link to="/teams">Browse teams</Link><Link className="small-primary-link" to="/teams#create-team">Create a team</Link></div>

  return (
    <section className="page my-teams-page">
      <header className="page-header account-page-header">
        <span className="eyebrow">Team workspace</span>
        <h1>My teams</h1>
        <p>The teams you belong to, together in one place.</p>
        <div className="my-teams-actions"><Link to="/proposals/mine">My proposals</Link><Link to="/tasks">Explore challenges</Link></div>
      </header>
      {error && <div className="feedback feedback-error" role="alert"><strong>Unable to load your teams.</strong><span>{error}</span><button className="secondary" onClick={() => setReload((value) => value + 1)}>Retry</button></div>}
      {loading && <LoadingState title="Loading your teams" />}
      {!loading && !error && result?.total === 0 && <EmptyState eyebrow="No teams yet" title="You're not part of a team yet." description="Browse public team profiles or create a team to start working on challenges." action={teamActions} />}
      {!loading && !error && result?.total > 0 && <>
        <div className="my-teams-toolbar"><span>{result.total} {result.total === 1 ? 'team' : 'teams'}</span>{teamActions}</div>
        <ul className="card-list my-teams-grid">{result.items.map((team) => <li className="my-team-card" key={team.id}>
          <h2><Link to={`/teams/${team.id}`}>{team.name}</Link></h2>
          <dl>{[['interests', 'Interests'], ['skills', 'Skills'], ['technologies', 'Technologies']].map(([field, label]) => team[field] && <div key={field}><dt>{label}</dt><dd>{team[field]}</dd></div>)}</dl>
          {!team.interests && !team.skills && !team.technologies && <p>No profile details yet.</p>}
          <Link className="my-team-link" to={`/teams/${team.id}`}>View team <span aria-hidden="true">→</span></Link>
        </li>)}</ul>
        {result.pages > 1 && <div className="pagination-controls"><span>Page {result.page} of {result.pages}</span><div className="button-row"><button className="secondary" disabled={result.page <= 1} onClick={() => changePage(result.page - 1)}>Previous</button><button className="secondary" disabled={result.page >= result.pages} onClick={() => changePage(result.page + 1)}>Next</button></div></div>}
      </>}
    </section>
  )
}
