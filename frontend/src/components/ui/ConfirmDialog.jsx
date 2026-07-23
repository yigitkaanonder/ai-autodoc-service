import Modal from './Modal.jsx'
import Button from './Button.jsx'
import './ConfirmDialog.css'

function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  danger = false,
  onConfirm,
  onCancel,
}) {
  const onClose = onCancel || onConfirm

  return (
    <Modal open={open} onClose={onClose} title={title} width={420}>
      <p className="ui-confirm-message">{message}</p>
      <div className="ui-confirm-actions">
        {onCancel && (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            {cancelLabel}
          </Button>
        )}
        <Button variant={danger ? 'danger' : 'primary'} size="sm" onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  )
}

export default ConfirmDialog
