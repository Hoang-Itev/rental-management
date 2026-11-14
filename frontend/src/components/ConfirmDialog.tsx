import { useState } from 'react';

interface Props {
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'primary';
  requireReason?: boolean;
  reasonLabel?: string;
  loading?: boolean;
  onConfirm: (reason?: string) => void | Promise<void>;
  onCancel: () => void;
}

export function ConfirmDialog({
  title, message, confirmLabel = 'Xác nhận', cancelLabel = 'Hủy',
  variant = 'primary', requireReason, reasonLabel = 'Lý do', loading,
  onConfirm, onCancel,
}: Props) {
  const [reason, setReason] = useState('');
  const disabled = requireReason && reason.trim().length < 1;
  return (
    <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="room-modal" style={{ width: 440 }}>
        <button className="modal-close" onClick={onCancel}>×</button>
        <h2 className="modal-title">{title}</h2>
        {message && <p style={{ marginBottom: 16 }}>{message}</p>}
        {requireReason && (
          <div className="login-field">
            <label>{reasonLabel}</label>
            <textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
        )}
        <div className="modal-actions">
          <button className="modal-btn" onClick={onCancel} disabled={loading}>{cancelLabel}</button>
          <button
            className={`modal-btn ${variant === 'danger' ? 'primary' : ''}`}
            onClick={() => onConfirm(requireReason ? reason.trim() : undefined)}
            disabled={loading || disabled}
            style={variant === 'danger' ? { background: 'var(--cinnabar-2)' } : undefined}
          >
            {loading ? 'Đang xử lý…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}