export function LoadingState({ title = 'Loading', lines = 3, compact = false }) {
  return (
    <div className={`state-panel state-panel-loading${compact ? ' is-compact' : ''}`} role="status" aria-live="polite">
      <span className="sr-only">{title}</span>
      <div className="skeleton skeleton-title" />
      {Array.from({ length: lines }, (_, index) => <div className="skeleton skeleton-line" key={index} />)}
    </div>
  )
}

export function EmptyState({ eyebrow = 'Nothing here yet', title, description, action }) {
  return (
    <div className="state-panel empty-state">
      <span className="eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {action}
    </div>
  )
}
