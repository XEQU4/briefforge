import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { listProposals, updateProposal } from '../api/proposals'
import { EmptyState, LoadingState } from '../components/StatePanel'

const PAGE_SIZE = 10

export default function ProposalReview() {
  const { taskId } = useParams()
  const [page, setPage] = useState(1)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(null)
  const [actionError, setActionError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    listProposals(taskId, page, PAGE_SIZE).then((value) => { if (active) setResult(value) }).catch((reason) => { if (active) setError(reason) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [taskId, page])

  async function decide(proposal, status) {
    setPending(proposal.id)
    setActionError('')
    try {
      const value = await updateProposal(proposal.id, status)
      setResult((current) => ({ ...current, items: current.items.map((item) => item.id === value.id ? value : item) }))
    } catch (reason) { setActionError(reason.message) } finally { setPending(null) }
  }

  if (loading) return <section className="page"><LoadingState title="Loading proposals" /></section>
  if (error?.status === 403) return <section className="page"><div className="feedback feedback-error" role="alert"><strong>You do not have access to these proposals.</strong><span>Only members of the task organization can review proposals.</span></div></section>
  if (error?.status === 404) return <section className="page"><EmptyState title="Task not found" description="This task may have been removed." action={<Link to="/business">Back to workspace</Link>} /></section>
  if (error) return <section className="page"><div className="feedback feedback-error" role="alert">Unable to load proposals: {error.message}</div></section>

  return (
    <section className="page proposal-review-page">
      <header className="page-header"><span className="eyebrow">Business workspace · Task #{taskId}</span><h1>Review proposals.</h1><p>Accept or reject pending proposals. Decisions are validated by the server.</p><Link to={`/business/tasks/${taskId}`}>Back to task</Link></header>
      {actionError && <div className="feedback feedback-error" role="alert">{actionError}</div>}
      {!result.items.length ? <EmptyState title="No proposals yet" description="When a team submits a proposal for this task, it will appear here." /> : <ul className="card-list proposal-grid">{result.items.map((proposal) => <li className="proposal-card" key={proposal.id}><div className="card-topline"><span className="proposal-team">Team #{proposal.team_id}</span><span className={`status-badge status-${proposal.status}`}>{proposal.status}</span></div><h2>{proposal.idea}</h2><p>{proposal.plan || 'No plan provided.'}</p><div className="proposal-meta">{proposal.deadline && <span>Deadline · {proposal.deadline}</span>}{proposal.link && <a href={proposal.link} target="_blank" rel="noreferrer">Open prototype ↗</a>}</div>{proposal.status === 'pending' && <div className="button-row"><button disabled={pending === proposal.id} onClick={() => decide(proposal, 'accepted')}>{pending === proposal.id ? 'Saving…' : 'Accept proposal'}</button><button className="danger-ghost" disabled={pending === proposal.id} onClick={() => decide(proposal, 'rejected')}>Reject</button></div>}</li>)}</ul>}
      {result.total > 0 && <div className="pagination-controls"><span>Page {result.page} of {Math.max(result.pages, 1)} · {result.total} proposals</span><div className="button-row"><button className="secondary" disabled={result.page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</button><button className="secondary" disabled={result.page >= result.pages} onClick={() => setPage((current) => current + 1)}>Next</button></div></div>}
    </section>
  )
}
