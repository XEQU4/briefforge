import safeWebUrl from '../utils/safeWebUrl'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { listMyProposals } from '../api/proposals'
import { EmptyState, LoadingState } from '../components/StatePanel'
import useListQuery from '../hooks/useListQuery'

const PAGE_SIZE = 10
const querySchema = { status: { options: ['', 'pending', 'accepted', 'rejected'] } }
const statusLabels = { pending: 'Pending', accepted: 'Accepted', rejected: 'Rejected' }

export default function MyProposals() {
  const { status, page, update, fitPage } = useListQuery(querySchema)
  const [reload, setReload] = useState(0)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    listMyProposals({ page, page_size: PAGE_SIZE, status })
      .then((value) => { if (active && fitPage(value.pages)) setResult(value) })
      .catch((reason) => { if (active) setError(reason) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, status, reload, fitPage])

  return (
    <section className="page product-page my-proposals-page">
      <header className="product-page-header"><div><span className="eyebrow">Team workspace</span><h1>My proposals</h1><p>Track proposals you submitted and organization decisions.</p></div></header>
      <div className="product-toolbar proposal-toolbar" role="group" aria-label="Proposal filters">
        <label>Status<select value={status} onChange={(event) => update({ status: event.target.value })}><option value="">All</option><option value="pending">Pending</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option></select></label>
        <span className="result-count" role="status">{!loading && !error && result ? `${result.total} ${result.total === 1 ? 'proposal' : 'proposals'}` : loading ? 'Loading proposals…' : ''}</span>
      </div>
      {error && <div className="feedback feedback-error" role="alert"><strong>Unable to load your proposals.</strong><span>Please retry. Only proposals you personally submitted are included.</span><button className="secondary" onClick={() => setReload((value) => value + 1)}>Retry</button></div>}
      {loading && <LoadingState announce={false} />}
      {!loading && !error && result?.items.length === 0 && <EmptyState eyebrow="" title={status ? `No ${status} proposals` : 'No proposals yet'} description={status ? 'Choose another status to see more of your proposal history.' : 'Submit a proposal to a published challenge to start your history.'} action={status ? <button className="text-button" onClick={() => update({ status: '' })}>Show all proposals</button> : <Link to="/tasks">Explore challenges</Link>} />}
      {!loading && !error && Boolean(result?.items.length) && <>
        <ul className="card-list proposal-list">{result.items.map((proposal) => {
        const prototypeLink = safeWebUrl(proposal.link)
        return <li className="proposal-row" key={proposal.id}>
          <div className="proposal-row-heading"><h2>{proposal.idea}</h2><span className={`status-badge status-${proposal.status}`}>{statusLabels[proposal.status] || proposal.status}</span></div>
          {proposal.plan && <p className="proposal-excerpt">{proposal.plan}</p>}
          <div className="proposal-row-meta">
            <Link to={`/tasks/${proposal.task_id}`}>Task #{proposal.task_id}</Link>
            <Link to={`/teams/${proposal.team_id}`}>Team #{proposal.team_id}</Link>
            {proposal.created_at && <span>Submitted <time dateTime={proposal.created_at}>{new Date(proposal.created_at).toLocaleDateString()}</time></span>}
            {prototypeLink && <a href={prototypeLink} target="_blank" rel="noreferrer">Open prototype ↗</a>}
          </div>
        </li> })}</ul>
        <div className="pagination-controls"><span>Page {result.page} of {Math.max(result.pages, 1)}</span><div className="button-row"><button className="secondary" disabled={result.page <= 1 || loading} onClick={() => update({ page: page - 1 })}>Previous</button><button className="secondary" disabled={result.page >= result.pages || loading} onClick={() => update({ page: page + 1 })}>Next</button></div></div>
      </>}
    </section>
  )
}
