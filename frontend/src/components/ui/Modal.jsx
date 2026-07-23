import { useEffect, useRef } from 'react'
import './Modal.css'

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

function getFocusable(container) {
  return Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR))
}

function Modal({ open, onClose, title, ariaLabel, children, width = 480, bodyClassName = '' }) {
  const dialogRef = useRef(null)
  const previouslyFocused = useRef(null)

  useEffect(() => {
    if (!open) return

    previouslyFocused.current = document.activeElement

    const focusables = getFocusable(dialogRef.current)
    ;(focusables[0] || dialogRef.current).focus()

    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key !== 'Tab') return

      const items = getFocusable(dialogRef.current)
      if (items.length === 0) {
        e.preventDefault()
        return
      }
      const first = items[0]
      const last = items[items.length - 1]

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      previouslyFocused.current?.focus()
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="ui-modal-overlay" onClick={onClose}>
      <div
        ref={dialogRef}
        className="ui-modal"
        style={{ '--ui-modal-width': `${width}px` }}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel || (typeof title === 'string' ? title : undefined)}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div className="ui-modal-head">
            <div className="ui-modal-title">{title}</div>
            <button className="ui-modal-close" onClick={onClose} aria-label="Close">
              ×
            </button>
          </div>
        )}
        <div className={`ui-modal-body ${bodyClassName}`.trim()}>{children}</div>
      </div>
    </div>
  )
}

export default Modal
