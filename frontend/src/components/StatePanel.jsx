export function LoadingState({ title = 'Loading', lines = 3, compact = false, announce = true }) {
  return (
    <div className={`state-panel state-panel-loading${compact ? ' is-compact' : ''}`} role={announce ? 'status' : undefined} aria-hidden={announce ? undefined : true}>
      {announce && <span className="sr-only">{title}</span>}
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
