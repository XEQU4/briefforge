import { useState } from 'react'
import { createTask } from '../api/tasks'

export default function TaskDraft({ onCreated }) {
  const [draftText, setDraftText] = useState('')
  const [topic, setTopic] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const value = await createTask(draftText, topic || null)
      setResult(value)
      onCreated?.(value)
    } catch (reason) {
      setError(reason.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="page draft-page">
      <header className="page-header split-header">
        <div><span className="eyebrow">Business workspace</span><h1>Start with the problem, not the paperwork.</h1><p>Describe the need in your own words. The platform will identify what is missing and turn it into a clearer brief.</p></div>
        <div className="mini-flow glass-panel" aria-label="Task creation flow"><span className="is-active">01 Draft</span><span>02 Clarify</span><span>03 Improve</span><span>04 Publish</span></div>
      </header>

      <div className="two-column-layout">
        <form className="form-panel feature-panel" onSubmit={submit}>
          <div className="panel-heading"><span className="eyebrow">Step 01</span><h2>Describe the business need</h2><p>Short and imperfect is fine. Specific details can be added after clarification.</p></div>
          <label>Problem or need<textarea required placeholder="Example: We need a service that helps employees prepare monthly reports faster..." value={draftText} onChange={(event) => setDraftText(event.target.value)} /></label>
          <label>Topic <span className="optional-label">Optional</span><input placeholder="Reporting, logistics, education..." value={topic} onChange={(event) => setTopic(event.target.value)} /></label>
          <div className="form-footer"><span className="form-hint">Your text stays editable before publication.</span><button disabled={loading}>{loading ? 'Creating draft…' : 'Generate clarifying questions'}</button></div>
        </form>

        <aside className="side-note glass-panel"><span className="eyebrow">What happens next</span><h2>AI-assisted, human-confirmed.</h2><ul className="feature-list"><li><strong>Clarify</strong><span>Get at least three targeted follow-up questions.</span></li><li><strong>Structure</strong><span>Turn answers into an editable task card.</span></li><li><strong>Score</strong><span>See readiness and concrete improvement suggestions.</span></li></ul></aside>
      </div>

      {error && <div className="feedback feedback-error" role="alert"><strong>Draft was not created</strong><span>{error}</span></div>}

      {result && (
        <div className="question-preview feature-panel entrance-card">
          <div className="panel-heading"><span className="eyebrow">Draft #{result.task.id}</span><h2>Clarifying questions are ready</h2><p>Continue to answer these questions and unlock the editable task card.</p></div>
          <ol className="question-list">{result.questions.map((question, index) => <li key={question.id}><span>{String(index + 1).padStart(2, '0')}</span><p>{question.question_text}</p></li>)}</ol>
        </div>
      )}
    </section>
  )
}
