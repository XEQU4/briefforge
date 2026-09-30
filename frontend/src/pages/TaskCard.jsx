import { useEffect, useRef, useState } from 'react'
import { answerTask, confirmTask, getTaskRating, updateTask } from '../api/tasks'
import ReadinessScore from '../components/ReadinessScore'
import { LoadingState } from '../components/StatePanel'
import uiError from '../utils/uiError'

const fields = ['title', 'context', 'need', 'users', 'data_materials', 'constraints', 'expected_result', 'success_criteria', 'contact', 'interaction_format', 'topic']
const fieldLabels = { title: 'Title', context: 'Context', need: 'Business need', users: 'Users', data_materials: 'Data and materials', constraints: 'Constraints', expected_result: 'Expected result', success_criteria: 'Success criteria', contact: 'Contact', interaction_format: 'Interaction format', topic: 'Topic' }
const longFields = new Set(['context', 'need', 'users', 'data_materials', 'constraints', 'expected_result', 'success_criteria', 'interaction_format'])
const statusLabels = { draft: 'Draft', clarifying: 'Clarifying', card_ready: 'Ready to review', confirmed: 'Confirmed' }

export default function TaskCard(props) {
  return <TaskCardEditor key={props.taskId || props.task?.id} {...props} />
}

function TaskCardEditor({ task, questions = [], taskId, onConfirmed }) {
  const id = taskId || task?.id
  const [answers, setAnswers] = useState(() => Object.fromEntries(questions.map((question) => [question.id, question.answer_text || ''])))
  const touchedAnswers = useRef(new Set())
  const [card, setCard] = useState(task || null)
  const [rating, setRating] = useState(null)
  const [ratingError, setRatingError] = useState('')
  const ratingRequest = useRef(0)
  const [action, setAction] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    setAnswers((current) => {
      const next = { ...current }
      questions.forEach((question) => {
        if (!touchedAnswers.current.has(question.id)) next[question.id] = question.answer_text || ''
      })
      return next
    })
  }, [questions])

  const status = card?.status
  const isClarifying = status === 'clarifying' || status === 'draft'
  const canEditCard = status === 'card_ready' || status === 'confirmed'

  useEffect(() => {
    const request = ++ratingRequest.current
    setRating(null)
    setRatingError('')
    if (id && canEditCard) {
      getTaskRating(id).then((value) => {
        if (request === ratingRequest.current) setRating(value)
      }).catch(() => {
        if (request === ratingRequest.current) setRatingError('Unable to load readiness. Use Save & recalculate to retry.')
      })
    }
    return () => { ratingRequest.current += 1 }
  }, [id, canEditCard])

  if (!id) return <div className="feedback feedback-error" role="alert">Task id is missing.</div>

  const currentStep = status === 'confirmed' ? 3 : canEditCard ? 2 : 1
  const cardPayload = () => Object.fromEntries(fields.map((field) => [field, card?.[field] ?? null]))

  async function submitAnswers(event) {
    event.preventDefault()
    const request = ratingRequest.current
    setAction('answers'); setError(''); setSuccess('')
    try {
      const generatedCard = await answerTask(id, questions.map((question) => answers[question.id] || ''))
      if (request !== ratingRequest.current) return
      setCard(generatedCard)
    } catch (reason) {
      if (request === ratingRequest.current) setError(uiError(reason, 'Unable to build the task card. Your answers are still here; please try again.'))
    } finally { if (request === ratingRequest.current) setAction(null) }
  }

  async function saveAndRecalculate() {
    const request = ++ratingRequest.current
    setRatingError('')
    setAction('recalculate'); setError(''); setSuccess('')
    try {
      const savedCard = await updateTask(id, cardPayload())
      if (request !== ratingRequest.current) return
      setCard(savedCard)
      const value = await getTaskRating(id)
      if (request !== ratingRequest.current) return
      setRating(value)
      setSuccess('Task saved. Readiness and guidance are up to date.')
    } catch (reason) {
      if (request === ratingRequest.current) {
        setError(uiError(reason, 'Unable to save and update readiness. Please try again.'))
        if (!rating) setRatingError('Unable to load readiness. Use Save & recalculate to retry.')
      }
    } finally { if (request === ratingRequest.current) setAction(null) }
  }

  async function publish() {
    const request = ratingRequest.current
    setAction('publish'); setError(''); setSuccess('')
    try {
      await updateTask(id, cardPayload())
      if (request !== ratingRequest.current) return
      const confirmedTask = await confirmTask(id)
      if (request !== ratingRequest.current) return
      setCard(confirmedTask)
      onConfirmed?.(confirmedTask)
    } catch (reason) {
      if (request === ratingRequest.current) setError(uiError(reason, 'Unable to confirm this task. Please try again.'))
    } finally { if (request === ratingRequest.current) setAction(null) }
  }

  return (
    <section className="page task-card-page">
      <header className="page-header split-header compact-header"><div><span className="eyebrow">Task #{id}</span><h1>Shape a brief students can act on.</h1><p>Clarify the need, review the generated card, then improve the score before publishing.</p></div><div className="status-orb glass-panel"><span>Current status</span><strong>{statusLabels[status] || status || 'Draft'}</strong></div></header>

      <div className="stepper" aria-label="Task preparation progress">{['Clarify', 'Review & improve', 'Publish'].map((label, index) => <div className={currentStep > index + 1 ? 'is-complete' : currentStep === index + 1 ? 'is-active' : ''} key={label}><span>{index + 1}</span><strong>{label}</strong></div>)}</div>

      {error && <div className="feedback feedback-error" role="alert"><strong>Something needs attention</strong><span>{error}</span></div>}
      {success && <div className="feedback feedback-success" role="status"><strong>Changes saved</strong><span>{success}</span></div>}

      {isClarifying && questions.length > 0 && (
        <form className="form-panel feature-panel" onSubmit={submitAnswers} aria-busy={action === 'answers'}>
          <div className="panel-heading"><span className="eyebrow">Step 01 · Clarify</span><h2>Fill the gaps in the original brief</h2><p>Your answers stay in place if the request fails, so you can retry safely.</p></div>
          <div className="question-fields">{questions.map((question, index) => <label key={question.id}><span className="question-label"><small>{String(index + 1).padStart(2, '0')}</small>{question.question_text}</span><textarea aria-label={question.question_text} value={answers[question.id] || ''} onChange={(event) => { touchedAnswers.current.add(question.id); setAnswers((current) => ({ ...current, [question.id]: event.target.value })) }} placeholder="Add the detail the team will need..." /></label>)}</div>
          <div className="form-footer"><span className="form-hint">Answers are used to generate the editable card.</span><button disabled={action !== null}>{action === 'answers' ? 'Building card…' : 'Save answers & build card'}</button></div>
        </form>
      )}

      {canEditCard && card && (
        <div className="editor-layout">
          <div className="feature-panel editor-panel">
            <div className="panel-heading"><span className="eyebrow">Step 02 · Review</span><h2>Editable task card</h2><p>Everything below remains under business control. Improve missing areas, then recalculate readiness.</p></div>
            <div className="field-grid">{fields.map((field) => {
              const Input = longFields.has(field) ? 'textarea' : 'input'
              return <label className="field-label" key={field}>{fieldLabels[field]}<Input aria-label={fieldLabels[field]} value={card[field] || ''} onChange={(event) => setCard({ ...card, [field]: event.target.value })} /></label>
            })}</div>
            <div className="task-actions"><button className="secondary" disabled={action !== null} onClick={saveAndRecalculate}>{action === 'recalculate' ? 'Recalculating…' : 'Save & recalculate'}</button><button disabled={action !== null || status === 'confirmed'} onClick={publish}>{action === 'publish' ? 'Publishing…' : status === 'confirmed' ? 'Published' : 'Publish task'}</button></div>
          </div>

          <aside className="editor-sidebar">
            {ratingError ? <div className="feedback feedback-error" role="alert">{ratingError}</div>
              : rating ? <ReadinessScore task={card} rating={rating} />
                : <LoadingState compact lines={2} title="Loading readiness" />}
            <div className="glass-panel helper-panel"><span className="eyebrow">Scoring tip</span><h2>Specific beats verbose.</h2><p>Concrete users, available data, measurable success criteria and a clear interaction format raise readiness most effectively.</p></div>
          </aside>
        </div>
      )}
    </section>
  )
}
