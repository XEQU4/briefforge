import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { listProposals, updateProposal } from '../api/proposals'
import { EmptyState, LoadingState } from '../components/StatePanel'
import uiError from '../utils/uiError'

const PAGE_SIZE = 10
const statusLabels = { pending: 'Pending', accepted: 'Accepted', rejected: 'Rejected' }

export default function ProposalReview() {
  const { taskId } = useParams()
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(null)
  const [actionError, setActionError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    listProposals(taskId, { page, page_size: PAGE_SIZE, status: statusFilter }).then((value) => { if (active) setResult(value) }).catch((reason) => { if (active) setError(reason) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [taskId, page, statusFilter])

  async function decide(proposal, status) {
    if (pending !== null || proposal.status !== 'pending') return
    setPending(proposal.id)
    setActionError('')
    try {
      const value = await updateProposal(proposal.id, status)
      setResult((current) => ({ ...current, items: current.items.map((item) => item.id === value.id ? value : item) }))
    } catch (reason) { setActionError(uiError(reason, 'Unable to save this decision. Please try again.')) } finally { setPending(null) }
  }

  if (loading) return <section className="page product-page"><LoadingState title="Loading proposals" /></section>
  if (error?.status === 403) return <section className="page product-page"><div className="feedback feedback-error" role="alert"><strong>You do not have access to these proposals.</strong><span>Only members of the task organization can review proposals.</span></div></section>
  if (error?.status === 404) return <section className="page product-page"><EmptyState title="Task not found" description="This task may have been removed." action={<Link to="/business">Back to workspace</Link>} /></section>
  if (error) return <section className="page product-page"><div className="feedback feedback-error" role="alert">Unable to load proposals. Please reload this page and try again.</div></section>

  return (
    <section className="page product-page proposal-review-page">
      <Link className="back-link" to={`/business/tasks/${taskId}`}>← Back to task</Link>
      <header className="product-page-header"><div><span className="eyebrow">Business workspace · Task #{taskId}</span><h1>Review proposals</h1><p>Review team approaches and accept or reject pending proposals.</p></div></header>
      <div className="product-toolbar proposal-toolbar" role="group" aria-label="Proposal filters"><label>Status<select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1) }}><option value="">All</option><option value="pending">Pending</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option></select></label><span className="result-count" role="status">{result.total} {result.total === 1 ? 'proposal' : 'proposals'}</span></div>
      {actionError && <div className="feedback feedback-error" role="alert">{actionError}</div>}
      {!result.items.length ? <EmptyState eyebrow="" title={statusFilter ? `No ${statusFilter} proposals` : 'No proposals yet'} description={statusFilter ? 'Choose another status to review proposals in that state.' : 'When a team submits a proposal for this task, it will appear here.'} /> : <ul className="card-list proposal-grid">{result.items.map((proposal) => <li className="proposal-row" key={proposal.id}>
        <div className="card-topline"><span className="proposal-team">Team #{proposal.team_id}</span><span className={`status-badge status-${proposal.status}`}>{statusLabels[proposal.status] || proposal.status}</span></div>
        <h2>{proposal.idea}</h2><p className="proposal-review-plan">{proposal.plan || 'No plan provided.'}</p>
        <div className="proposal-row-meta">{proposal.deadline && <span>Deadline · {proposal.deadline}</span>}{proposal.link && <a href={proposal.link} target="_blank" rel="noreferrer">Open prototype ↗</a>}</div>
        {proposal.status === 'pending' && <div className="product-actions"><button disabled={pending !== null} onClick={() => decide(proposal, 'accepted')}>{pending === proposal.id ? 'Saving…' : 'Accept proposal'}</button><button className="danger-ghost" disabled={pending !== null} onClick={() => decide(proposal, 'rejected')}>Reject</button></div>}
      </li>)}</ul>}
      {result.total > 0 && <div className="pagination-controls"><span>Page {result.page} of {Math.max(result.pages, 1)}</span><div className="button-row"><button className="secondary" disabled={result.page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</button><button className="secondary" disabled={result.page >= result.pages} onClick={() => setPage((current) => current + 1)}>Next</button></div></div>}
    </section>
  )
}
