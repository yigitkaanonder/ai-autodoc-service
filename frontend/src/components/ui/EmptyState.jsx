import './EmptyState.css'

function EmptyState({ icon, title, message, action }) {
  return (
    <div className="ui-empty">
      {icon && <div className="ui-empty-icon">{icon}</div>}
      {title && <div className="ui-empty-title">{title}</div>}
      {message && <div className="ui-empty-message">{message}</div>}
      {action && <div className="ui-empty-action">{action}</div>}
    </div>
  )
}

export default EmptyState
