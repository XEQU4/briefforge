import { useState } from 'react'
import { Link, useLocation } from 'react-router'
import { createTask } from '../api/tasks'
import OrganizationPicker from '../components/OrganizationPicker'

export default function TaskDraft() {
  const location = useLocation()
  const [draftText, setDraftText] = useState('')
  const [topic, setTopic] = useState('')
  const [organizationId, setOrganizationId] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const value = await createTask(draftText, topic || null, organizationId)
      setResult(value)
    } catch (reason) {
      setError(reason.status === 403 ? 'You no longer have access to that organization. Select another one and retry.' : reason.message)
    } finally { setLoading(false) }
  }

  return (
    <section className="page draft-page">
      <header className="page-header split-header">
        <div><span className="eyebrow">Business workspace</span><h1>Start with the problem, not the paperwork.</h1><p>Describe the need in your own words. The platform will identify what is missing and turn it into a clearer brief.</p></div>
        <div className="mini-flow glass-panel" aria-label="Task creation flow"><span className="is-active">01 Draft</span><span>02 Clarify</span><span>03 Improve</span><span>04 Publish</span></div>
      </header>

      <div className="two-column-layout">
        <div className="draft-flow-column">
          <div className="form-panel feature-panel">
            <div className="panel-heading"><span className="eyebrow">Organization</span><h2>Choose a workspace</h2><p>Only members can create tasks for their organization.</p></div>
            <OrganizationPicker initialSelectedId={location.state?.organizationId} onSelectionChange={setOrganizationId} />
          </div>
        <form className="form-panel feature-panel" onSubmit={submit}>
          <div className="panel-heading"><span className="eyebrow">Step 01</span><h2>Describe the business need</h2><p>Short and imperfect is fine. Specific details can be added after clarification.</p></div>
          <label>Problem or need<textarea required placeholder="Example: We need a service that helps employees prepare monthly reports faster..." value={draftText} onChange={(event) => setDraftText(event.target.value)} /></label>
          <label>Topic <span className="optional-label">Optional</span><input placeholder="Reporting, logistics, education..." value={topic} onChange={(event) => setTopic(event.target.value)} /></label>
          <div className="form-footer"><span className="form-hint">Your text stays editable before publication.</span><button disabled={loading || !organizationId}>{loading ? 'Creating draft…' : 'Generate clarifying questions'}</button></div>
        </form>
        </div>
        <aside className="side-note glass-panel"><span className="eyebrow">What happens next</span><h2>AI-assisted, human-confirmed.</h2><ul className="feature-list"><li><strong>Clarify</strong><span>Get at least three targeted follow-up questions.</span></li><li><strong>Structure</strong><span>Turn answers into an editable task card.</span></li><li><strong>Score</strong><span>See readiness and concrete improvement suggestions.</span></li></ul></aside>
      </div>

      {error && <div className="feedback feedback-error" role="alert"><strong>Draft was not created</strong><span>{error}</span></div>}
      {result && <div className="question-preview feature-panel entrance-card">
        <div className="panel-heading"><span className="eyebrow">Draft #{result.task.id}</span><h2>Clarifying questions are ready</h2><p>Continue to answer these questions and unlock the editable task card.</p></div>
        <ol className="question-list">{result.questions.map((question, index) => <li key={question.id}><span>{String(index + 1).padStart(2, '0')}</span><p>{question.question_text}</p></li>)}</ol>
        <div className="form-footer"><span className="form-hint">Your draft and questions are saved, so this workflow can be reopened after a refresh.</span><Link className="small-primary-link" to={`/business/tasks/${result.task.id}`}>Continue to task</Link></div>
      </div>}
    </section>
  )
}
