const levelLabels = { draft: 'Draft', working: 'Working', ready: 'Ready', priority: 'Priority' }
const breakdownLabels = {
  'context+need': 'Context & need',
  data_materials: 'Data & materials',
  expected_result: 'Expected result',
  success_criteria: 'Success criteria',
  constraints: 'Constraints',
  users: 'Users',
  'contact+interaction_format': 'Business connection',
}

export default function ReadinessScore({ task, rating, compact = false }) {
  const score = rating?.score ?? task?.rating_score ?? 0
  const level = rating?.readiness_level ?? task?.readiness_level
  const breakdown = rating?.breakdown || task?.rating_breakdown || {}
  const missing = rating?.missing_fields || []
  const suggestions = rating?.suggestions || []
  const safeScore = Math.max(0, Math.min(100, Number(score) || 0))

  return (
    <section className={`readiness-score${compact ? ' is-compact' : ''}`} aria-label="Readiness score">
      <div className="readiness-head"><div><span className="readiness-kicker">Readiness</span><strong>{safeScore}<small>/100</small></strong></div>{level && <span className={`status-badge readiness-${level}`}>{levelLabels[level] || level}</span>}</div>
      <div className="readiness-meter" aria-hidden="true"><span style={{ width: `${safeScore}%` }} /></div>

      {!compact && Object.keys(breakdown).length > 0 && (
        <details className="score-details"><summary>Score breakdown <span aria-hidden="true">+</span></summary><div className="score-grid">{Object.entries(breakdown).map(([key, value]) => <div key={key}><span>{breakdownLabels[key] || key}</span><strong>{value}</strong></div>)}</div></details>
      )}

      {!compact && missing.length > 0 && <p className="missing-copy"><strong>Missing:</strong> {missing.join(', ')}</p>}
      {!compact && suggestions.length > 0 && <div className="suggestions"><span className="eyebrow">How to improve</span><ul>{suggestions.map((suggestion, index) => <li key={`${index}-${suggestion}`}>{suggestion}</li>)}</ul></div>}
    </section>
  )
}
