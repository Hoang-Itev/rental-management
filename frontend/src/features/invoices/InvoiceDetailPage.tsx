import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { InvoiceDetail, PaymentAttemptView, AdjustmentView, Page } from '../../lib/api/types';
import { formatVnd, formatDateVi, formatDateTimeVi, periodEndInclusive } from '../../lib/utils/format';
import { Badge } from '../../components/Badge';
import { PageState } from '../../components/PageState';
import { ConfirmDialog } from '../../components/ConfirmDialog';

export function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [attempts, setAttempts] = useState<PaymentAttemptView[]>([]);
  const [adjustments, setAdjustments] = useState<AdjustmentView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [confirm, setConfirm] = useState<{ kind: 'issue' | 'void' | 'reissue' | 'reminder'; requireReason?: boolean } | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);

  const [adjustForm, setAdjustForm] = useState<{ open: boolean; reason: string; amount_delta: string }>({
    open: false, reason: '', amount_delta: '',
  });
  const [adjustSubmitting, setAdjustSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true); setError(null);
    try {
      const inv = await api.get<InvoiceDetail>(`/api/v1/invoices/${id}`);
      setInvoice(inv);
      const [a, adj] = await Promise.all([
        api.get<Page<PaymentAttemptView>>(`/api/v1/invoices/${id}/payment-attempts?page_size=50`),
        api.get<Page<AdjustmentView>>(`/api/v1/invoices/${id}/adjustments?page_size=50`),
      ]);
      setAttempts(a.items);
      setAdjustments(adj.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được hóa đơn.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  async function runAction(reason?: string) {
    if (!confirm || !invoice) return;
    setConfirmLoading(true); setActionError(null);
    try {
      if (confirm.kind === 'issue') await api.post(`/api/v1/invoices/${invoice.id}/issue`);
      else if (confirm.kind === 'void') await api.post(`/api/v1/invoices/${invoice.id}/void`, { reason: reason ?? '' });
      else if (confirm.kind === 'reissue') await api.post(`/api/v1/invoices/${invoice.id}/reissue`, { reason: reason ?? '' });
      else if (confirm.kind === 'reminder') await api.post(`/api/v1/invoices/${invoice.id}/reminders`);
      setConfirm(null);
      if (confirm.kind === 'reissue') {
        navigate(0);
      } else {
        await load();
      }
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Thao tác thất bại.');
    } finally {
      setConfirmLoading(false);
    }
  }

  async function createAdjustment(e: React.FormEvent) {
    e.preventDefault();
    if (!invoice) return;
    const delta = Number(adjustForm.amount_delta);
    if (!Number.isInteger(delta) || delta === 0) { setActionError('Chênh lệch phải là số nguyên khác 0.'); return; }
    if (!adjustForm.reason.trim()) { setActionError('Lý do bắt buộc.'); return; }
    setAdjustSubmitting(true); setActionError(null);
    try {
      await api.post(`/api/v1/invoices/${invoice.id}/adjustments`, {
        reason: adjustForm.reason.trim(),
        amount_delta: delta,
      });
      setAdjustForm({ open: false, reason: '', amount_delta: '' });
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Lỗi khi tạo adjustment.');
    } finally {
      setAdjustSubmitting(false);
    }
  }

  async function resolveAdjustment(a: AdjustmentView, status: 'RESOLVED' | 'REJECTED') {
    const note = prompt('Ghi chú xử lý:');
    if (!note || note.trim().length < 1) return;
    try {
      await api.post(`/api/v1/invoice-adjustments/${a.id}/resolve`, { status, resolution_note: note.trim() });
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Lỗi khi xử lý adjustment.');
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Hóa đơn: {invoice?.invoice_code ?? '…'}</h1>
        <button className="btn-secondary" onClick={() => navigate('/hoa-don')}>Quay lại</button>
      </div>

      {actionError && <div className="login-error">{actionError}</div>}

      <PageState loading={loading} error={error} onRetry={load}>
        {invoice && (
          <>
            <div className="detail-grid">
              <div className="detail-item"><label>Phòng</label><div>{invoice.room_code_snapshot}</div></div>
              <div className="detail-item"><label>Trạng thái</label><div><Badge value={invoice.status} /></div></div>
              <div className="detail-item"><label>Kỳ (bao gồm ngày cuối)</label><div>{formatDateVi(invoice.period_start)} — {formatDateVi(periodEndInclusive(invoice.period_end))}</div></div>
              <div className="detail-item"><label>Hạn thanh toán</label><div>{formatDateVi(invoice.due_date)}</div></div>
              <div className="detail-item"><label>Tổng cộng</label><div className="text-amount">{formatVnd(invoice.total_amount)}</div></div>
              <div className="detail-item"><label>Revision</label><div>{invoice.revision}</div></div>
              {invoice.blocked_reason && (
                <div className="detail-item"><label>Blocked</label><div style={{ color: 'var(--cinnabar-3)' }}>{invoice.blocked_reason}</div></div>
              )}
              {invoice.void_reason && (
                <div className="detail-item"><label>Lý do hủy</label><div>{invoice.void_reason}</div></div>
              )}
            </div>

            <div className="action-bar" style={{ marginTop: 20, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {invoice.status === 'DRAFT' && (
                <button className="btn-primary" onClick={() => setConfirm({ kind: 'issue' })}>Phát hành</button>
              )}
              {invoice.status === 'ISSUED' && (
                <>
                  <button className="btn-secondary" onClick={() => setConfirm({ kind: 'reminder' })}>Gửi nhắc nợ</button>
                  <button className="btn-primary" style={{ background: 'var(--cinnabar-2)' }} onClick={() => setConfirm({ kind: 'void', requireReason: true })}>Hủy</button>
                  <button className="btn-secondary" onClick={() => setConfirm({ kind: 'reissue', requireReason: true })}>Phát hành lại</button>
                </>
              )}
              {invoice.status === 'PAID' && (
                <button className="btn-secondary" onClick={() => setAdjustForm({ open: true, reason: '', amount_delta: '' })}>Tạo điều chỉnh</button>
              )}
            </div>

            <h3 style={{ marginTop: 28 }}>Chi tiết khoản</h3>
            <table className="data-table">
              <thead>
                <tr><th>Diễn giải</th><th>SL</th><th>Đơn giá</th><th>Thành tiền</th></tr>
              </thead>
              <tbody>
                {invoice.items.length === 0 && <tr><td colSpan={4} className="empty-row">Chưa có dòng.</td></tr>}
                {invoice.items.map((it) => (
                  <tr key={it.id}>
                    <td>{it.description}</td>
                    <td>{it.quantity} {it.unit}</td>
                    <td>{formatVnd(Number(it.unit_price))}</td>
                    <td className="text-amount">{formatVnd(it.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h3 style={{ marginTop: 28 }}>Lần thử thanh toán</h3>
            <table className="data-table">
              <thead>
                <tr><th>Provider</th><th>Order</th><th>Số tiền</th><th>Trạng thái</th><th>Xác nhận lúc</th></tr>
              </thead>
              <tbody>
                {attempts.length === 0 && <tr><td colSpan={5} className="empty-row">Chưa có lần thử.</td></tr>}
                {attempts.map((a) => (
                  <tr key={a.id}>
                    <td>{a.provider}</td>
                    <td style={{ fontSize: 12 }}>{a.order_id}</td>
                    <td className="text-amount">{formatVnd(a.amount)}</td>
                    <td><Badge value={a.status} /></td>
                    <td>{a.confirmed_at ? formatDateTimeVi(a.confirmed_at) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h3 style={{ marginTop: 28 }}>Điều chỉnh</h3>
            <table className="data-table">
              <thead>
                <tr><th>Lý do</th><th>Chênh lệch</th><th>Trạng thái</th><th>Ghi chú</th><th></th></tr>
              </thead>
              <tbody>
                {adjustments.length === 0 && <tr><td colSpan={5} className="empty-row">Chưa có điều chỉnh.</td></tr>}
                {adjustments.map((a) => (
                  <tr key={a.id}>
                    <td>{a.reason}</td>
                    <td className="text-amount">{a.amount_delta.toLocaleString('vi-VN')} đ</td>
                    <td><Badge value={a.status} /></td>
                    <td>{a.resolution_note || '—'}</td>
                    <td>
                      {a.status === 'OPEN' && (
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn-secondary" onClick={() => resolveAdjustment(a, 'RESOLVED')}>Đã xử lý</button>
                          <button className="btn-secondary" style={{ color: 'var(--cinnabar-3)' }} onClick={() => resolveAdjustment(a, 'REJECTED')}>Từ chối</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </PageState>

      {adjustForm.open && invoice && (
        <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && setAdjustForm({ open: false, reason: '', amount_delta: '' })}>
          <div className="room-modal" style={{ width: 440 }}>
            <button className="modal-close" onClick={() => setAdjustForm({ open: false, reason: '', amount_delta: '' })}>×</button>
            <h2 className="modal-title">Tạo điều chỉnh</h2>
            <form onSubmit={createAdjustment}>
              <div className="login-field">
                <label>Lý do *</label>
                <textarea rows={2} value={adjustForm.reason} onChange={(e) => setAdjustForm({ ...adjustForm, reason: e.target.value })} required />
              </div>
              <div className="login-field">
                <label>Chênh lệch (VNĐ, âm/dương, khác 0) *</label>
                <input type="number" step="1" value={adjustForm.amount_delta} onChange={(e) => setAdjustForm({ ...adjustForm, amount_delta: e.target.value })} required />
              </div>
              <div className="modal-actions">
                <button type="button" className="modal-btn" onClick={() => setAdjustForm({ open: false, reason: '', amount_delta: '' })} disabled={adjustSubmitting}>Hủy</button>
                <button type="submit" className="modal-btn primary" disabled={adjustSubmitting}>{adjustSubmitting ? 'Đang lưu…' : 'Tạo'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {confirm && (
        <ConfirmDialog
          title={
            confirm.kind === 'issue' ? 'Phát hành hóa đơn?' :
            confirm.kind === 'void' ? 'Hủy hóa đơn?' :
            confirm.kind === 'reissue' ? 'Phát hành lại?' : 'Gửi nhắc nợ?'
          }
          message={
            confirm.kind === 'issue'
              ? 'Hệ thống sẽ tính lại và phát hành nếu đủ dữ liệu. Nếu thiếu cutoff, hóa đơn vẫn DRAFT với blocked_reason.'
              : undefined
          }
          confirmLabel="Xác nhận"
          variant={confirm.kind === 'void' ? 'danger' : 'primary'}
          requireReason={!!confirm.requireReason}
          reasonLabel="Lý do"
          loading={confirmLoading}
          onCancel={() => setConfirm(null)}
          onConfirm={runAction}
        />
      )}
    </div>
  );
}