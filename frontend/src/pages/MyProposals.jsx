import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { listMyProposals } from '../api/proposals'
import { EmptyState, LoadingState } from '../components/StatePanel'

const PAGE_SIZE = 10

export default function MyProposals() {
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [reload, setReload] = useState(0)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    listMyProposals({ page, page_size: PAGE_SIZE, status })
      .then((value) => { if (active) setResult(value) })
      .catch((reason) => { if (active) setError(reason) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, status, reload])

  return (
    <section className="page my-proposals-page">
      <header className="page-header"><span className="eyebrow">Student workspace</span><h1>My proposals.</h1><p>Track the proposals you submitted and see organization decisions.</p></header>
      <div className="filters-panel glass-panel"><label>Proposal status<select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}><option value="">All proposals</option><option value="pending">Pending</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option></select></label>{result && <span className="muted">{result.total} proposals</span>}</div>
      {error && <div className="feedback feedback-error" role="alert"><strong>Unable to load your proposals.</strong><span>Please retry. Only proposals you personally submitted are included.</span><button className="secondary" onClick={() => setReload((value) => value + 1)}>Retry</button></div>}
      {loading && <LoadingState title="Loading your proposals" />}
      {!loading && !error && result?.items.length === 0 && <EmptyState title={status ? `No ${status} proposals` : 'No proposals yet'} description={status ? 'Choose another status to see more of your proposal history.' : 'Submit a proposal from a published task to start your history.'} action={<Link to="/tasks">Browse tasks</Link>} />}
      {!loading && !error && Boolean(result?.items.length) && <>
        <ul className="card-list proposal-grid">{result.items.map((proposal) => <li className="proposal-card" key={proposal.id}>
          <div className="card-topline"><span className="task-id">PROPOSAL {String(proposal.id).padStart(2, '0')}</span><span className={`status-badge status-${proposal.status}`}>{proposal.status}</span></div>
          <h2>{proposal.idea}</h2><p>{proposal.plan || 'No plan provided.'}</p>
          <div className="proposal-meta"><span>Task #{proposal.task_id}</span><span>Team #{proposal.team_id}</span>{proposal.created_at && <span>Submitted {new Date(proposal.created_at).toLocaleDateString()}</span>}</div>
          {proposal.link && <a href={proposal.link} target="_blank" rel="noreferrer">Open prototype ↗</a>}
        </li>)}</ul>
        <div className="pagination-controls"><span>Page {result.page} of {Math.max(result.pages, 1)} · {result.total} proposals</span><div className="button-row"><button className="secondary" disabled={result.page <= 1 || loading} onClick={() => setPage((current) => current - 1)}>Previous</button><button className="secondary" disabled={result.page >= result.pages || loading} onClick={() => setPage((current) => current + 1)}>Next</button></div></div>
      </>}
    </section>
  )
}
