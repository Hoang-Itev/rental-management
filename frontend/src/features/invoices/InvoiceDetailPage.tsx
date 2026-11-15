import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { InvoiceDetail, PaymentAttemptView, AdjustmentView, Page } from '../../lib/api/types';
import { formatVnd, formatDateVi, formatDateTimeVi, periodEndInclusive } from '../../lib/utils/format';
import { Badge } from '../../components/Badge';
import { PageState } from '../../components/PageState';
import { ConfirmDialog } from '../../components/ConfirmDialog';

// Hàm dịch tên cột hiển thị sang tiếng Việt
function translateDescription(desc: string) {
  if (desc.startsWith('Rent')) return 'Tiền thuê phòng';
  if (desc.startsWith('Service')) return 'Phí dịch vụ';
  if (desc.startsWith('Electricity')) return 'Tiền điện tiêu thụ';
  if (desc.startsWith('Water')) return 'Tiền nước tiêu thụ';
  return desc;
}

export function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [attempts, setAttempts] = useState<PaymentAttemptView[]>([]);
  const [adjustments, setAdjustments] = useState<AdjustmentView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [roomLocation, setRoomLocation] = useState<string>('');

  const [confirmAction, setConfirmAction] = useState<{ kind: 'issue' | 'void' | 'reissue' | 'reminder'; requireReason?: boolean } | null>(null);
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
      
      try {
        const roomData = await api.get<any>(`/api/v1/rooms/${inv.room_id}`);
        const floor = await api.get<any>(`/api/v1/floors/${roomData.floor_id}`);
        const building = await api.get<any>(`/api/v1/buildings/${floor.building_id}`);
        const prop = await api.get<any>(`/api/v1/properties/${roomData.property_id}`);
        setRoomLocation(`[${prop.name}] - Dãy ${building.name} - Tầng ${floor.floor_number}`);
      } catch {
        setRoomLocation('Không xác định');
      }

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
    if (!confirmAction || !invoice) return;
    setConfirmLoading(true); setActionError(null);
    try {
      if (confirmAction.kind === 'issue') await api.post(`/api/v1/invoices/${invoice.id}/issue`);
      else if (confirmAction.kind === 'void') await api.post(`/api/v1/invoices/${invoice.id}/void`, { reason: reason ?? '' });
      else if (confirmAction.kind === 'reissue') await api.post(`/api/v1/invoices/${invoice.id}/reissue`, { reason: reason ?? '' });
      else if (confirmAction.kind === 'reminder') await api.post(`/api/v1/invoices/${invoice.id}/reminders`);
      setConfirmAction(null);
      if (confirmAction.kind === 'reissue') { navigate(0); } else { await load(); }
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Thao tác thất bại.');
    } finally { setConfirmLoading(false); }
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
    } finally { setAdjustSubmitting(false); }
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
      <style>{`
        @media print {
          body { background: white !important; color: black !important; }
          .no-print { display: none !important; }
          #print-area { display: block !important; padding: 0 !important; border: none !important; background: white !important; }
          .invoice-table th, .invoice-table td { border-color: black !important; color: black !important; }
          .invoice-decorations { display: none !important; }
        }
      `}</style>

      <div className="page-header no-print">
        <h1 className="page-title">Hóa đơn: {invoice?.invoice_code ?? '…'}</h1>
        <button className="btn-secondary" onClick={() => navigate('/hoa-don')}>Quay lại</button>
      </div>

      {actionError && <div className="login-error no-print">{actionError}</div>}

      <PageState loading={loading} error={error} onRetry={load}>
        {invoice && (
          <div id="print-area" style={{ position: 'relative', background: 'var(--night-1)', padding: 40, borderRadius: 8, border: '1px solid var(--gold-3)', overflow: 'hidden' }}>
            
            {/* HIỆU ỨNG PHỐ CỔ (BỊ ẨN KHI IN) */}
            <div className="invoice-decorations" style={{ position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.15, zIndex: 0 }}>
              {/* Đèn lồng góc trái */}
              <svg style={{ position: 'absolute', top: 20, left: 20, width: 60, height: 90, animation: 'lanternSwing 5s ease-in-out infinite' }} viewBox="0 0 24 30" fill="none" stroke="var(--cinnabar-2)" strokeWidth="1.5">
                <path d="M12 2v4" /><rect x="8" y="6" width="8" height="16" rx="4" fill="var(--cinnabar-2)" fillOpacity="0.3" /><path d="M9 22h6M12 22v4" /><path d="M8 10h8M8 14h8M8 18h8" strokeOpacity="0.5" />
              </svg>
              {/* Mây góc phải */}
              <svg style={{ position: 'absolute', top: 30, right: 30, width: 80, height: 40, animation: 'cloudDrift 20s linear infinite' }} viewBox="0 0 100 50" fill="var(--gold-3)" opacity="0.5">
                <path d="M10,40 Q20,20 40,30 Q60,10 80,25 Q95,30 90,40 Z" />
              </svg>
              {/* Lá trúc rơi */}
              <svg style={{ position: 'absolute', bottom: 40, left: 40, width: 20, height: 40, animation: 'leafFall 8s linear infinite' }} viewBox="0 0 10 20">
                <ellipse cx="5" cy="10" rx="3" ry="9" fill="var(--moss)" />
              </svg>
              <svg style={{ position: 'absolute', bottom: 80, right: 50, width: 15, height: 30, animation: 'leafFall 12s linear infinite', animationDelay: '2s' }} viewBox="0 0 10 20">
                <ellipse cx="5" cy="10" rx="3" ry="9" fill="var(--moss)" />
              </svg>
            </div>

            {/* NỘI DUNG HÓA ĐƠN */}
            <div style={{ position: 'relative', zIndex: 1 }}>
              <div style={{ textAlign: 'center', marginBottom: 40 }}>
                <h2 style={{ color: 'var(--cinnabar-2)', fontSize: 28, marginBottom: 8, textTransform: 'uppercase', fontFamily: "'Cormorant Garamond', serif" }}>Hóa Đơn Tiền Nhà</h2>
                <p style={{ color: 'var(--ink-soft)', fontStyle: 'italic' }}>Mã hóa đơn: {invoice.invoice_code}</p>
                <p style={{ color: 'var(--ink-soft)' }}>Kỳ hạn: Từ {formatDateVi(invoice.period_start)} đến {formatDateVi(periodEndInclusive(invoice.period_end))}</p>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 30 }}>
                <div>
                  <h4 style={{ color: 'var(--gold-3)', marginBottom: 8, textTransform: 'uppercase' }}>Đơn vị lập hóa đơn</h4>
                  <div style={{ fontWeight: 'bold', fontSize: 16 }}>Hệ thống Quản lý Nhà trọ Minh An</div>
                  <div style={{ color: 'var(--ink-soft)', fontSize: 14 }}>Địa chỉ: Hội An, Quảng Nam</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <h4 style={{ color: 'var(--gold-3)', marginBottom: 8, textTransform: 'uppercase' }}>Thông tin khách hàng</h4>
                  <div style={{ fontWeight: 'bold', fontSize: 16 }}>{invoice.tenant_name_snapshot}</div>
                  <div style={{ color: 'var(--ink-soft)', fontSize: 14 }}>Vị trí: {roomLocation}</div>
                  <div style={{ color: 'var(--cinnabar-2)', fontWeight: 'bold', fontSize: 15 }}>Phòng: {invoice.room_code_snapshot}</div>
                  <div style={{ color: 'var(--ink-soft)', fontSize: 14 }}>Email: {invoice.tenant_email_snapshot || '—'}</div>
                </div>
              </div>

              <table className="invoice-table" style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 30 }}>
                <thead>
                  <tr style={{ background: 'rgba(212, 163, 64, 0.1)' }}>
                    <th style={{ padding: 10, borderBottom: '2px solid var(--gold-3)', textAlign: 'left' }}>STT</th>
                    <th style={{ padding: 10, borderBottom: '2px solid var(--gold-3)', textAlign: 'left' }}>Nội dung</th>
                    <th style={{ padding: 10, borderBottom: '2px solid var(--gold-3)', textAlign: 'center' }}>Số lượng</th>
                    <th style={{ padding: 10, borderBottom: '2px solid var(--gold-3)', textAlign: 'right' }}>Đơn giá</th>
                    <th style={{ padding: 10, borderBottom: '2px solid var(--gold-3)', textAlign: 'right' }}>Thành tiền</th>
                  </tr>
                </thead>
                <tbody>
                  {invoice.items.map((item, index) => (
                    <tr key={item.id}>
                      <td style={{ padding: 10, borderBottom: '1px solid var(--stone)' }}>{index + 1}</td>
                      <td style={{ padding: 10, borderBottom: '1px solid var(--stone)' }}>{translateDescription(item.description)}</td>
                      <td style={{ padding: 10, borderBottom: '1px solid var(--stone)', textAlign: 'center' }}>{item.quantity} {item.unit}</td>
                      <td style={{ padding: 10, borderBottom: '1px solid var(--stone)', textAlign: 'right' }}>{formatVnd(Number(item.unit_price))}</td>
                      <td style={{ padding: 10, borderBottom: '1px solid var(--stone)', textAlign: 'right', fontWeight: 'bold' }}>{formatVnd(item.amount)}</td>
                    </tr>
                  ))}
                  <tr>
                    <td colSpan={4} style={{ padding: 15, textAlign: 'right', fontWeight: 'bold', fontSize: 16 }}>TỔNG CỘNG:</td>
                    {/* SỬA MÀU TỔNG TIỀN: SANG MÀU ĐỎ ĐÔ ĐỂ DỄ ĐỌC Ở CHẾ ĐỘ SÁNG */}
                    <td style={{ padding: 15, textAlign: 'right', fontWeight: 'bold', fontSize: 22, color: 'var(--cinnabar-2)' }}>{formatVnd(invoice.total_amount)}</td>
                  </tr>
                </tbody>
              </table>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 40 }}>
                <div style={{ fontStyle: 'italic', color: 'var(--ink-soft)', fontSize: 13 }}>
                  Hạn thanh toán: <strong style={{ color: 'var(--cinnabar-2)' }}>{formatDateVi(invoice.due_date)}</strong><br/>
                  Vui lòng thanh toán đúng hạn để tránh gián đoạn dịch vụ.
                </div>
                <div style={{ textAlign: 'center', minWidth: 200 }}>
                  <div style={{ fontStyle: 'italic', color: 'var(--ink-soft)', marginBottom: 60 }}>Ngày ... tháng ... năm ...</div>
                  <div style={{ fontWeight: 'bold' }}>Người lập hóa đơn</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </PageState>

      {invoice && (
        <div className="action-bar no-print" style={{ marginTop: 20, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {/* CHỈ GIỮ LẠI DUY NHẤT 1 NÚT IN Ở ĐÂY */}
            <button className="btn-primary" style={{ background: 'var(--jade)', borderColor: 'var(--jade-2)' }} onClick={() => window.print()}>In hóa đơn (PDF)</button>
           {invoice.status === 'DRAFT' && <button className="btn-primary" onClick={() => setConfirmAction({ kind: 'issue' })}>Phát hành hóa đơn</button>}
           {invoice.status === 'ISSUED' && (
              <>
                <button className="btn-secondary" onClick={() => setConfirmAction({ kind: 'reminder' })}>Gửi nhắc nợ</button>
                <button className="btn-primary" style={{ background: 'var(--cinnabar-2)' }} onClick={() => setConfirmAction({ kind: 'void', requireReason: true })}>Hủy</button>
                <button className="btn-secondary" onClick={() => setConfirmAction({ kind: 'reissue', requireReason: true })}>Phát hành lại</button>
              </>
            )}
            {invoice.status === 'PAID' && <button className="btn-secondary" onClick={() => setAdjustForm({ open: true, reason: '', amount_delta: '' })}>Tạo điều chỉnh</button>}
        </div>
      )}

      {/* PHẦN MODALS (Giữ nguyên) */}
      {adjustForm.open && invoice && (
        <div className="modal-backdrop active no-print" onClick={(e) => e.target === e.currentTarget && setAdjustForm({ open: false, reason: '', amount_delta: '' })}>
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

      {confirmAction && (
        <div className="no-print">
          <ConfirmDialog
            title={confirmAction.kind === 'issue' ? 'Phát hành hóa đơn?' : confirmAction.kind === 'void' ? 'Hủy hóa đơn?' : confirmAction.kind === 'reissue' ? 'Phát hành lại?' : 'Gửi nhắc nợ?'}
            message={confirmAction.kind === 'issue' ? 'Hệ thống sẽ tính lại và phát hành nếu đủ dữ liệu.' : undefined}
            confirmLabel="Xác nhận"
            variant={confirmAction.kind === 'void' ? 'danger' : 'primary'}
            requireReason={!!confirmAction.requireReason}
            reasonLabel="Lý do"
            loading={confirmLoading}
            onCancel={() => setConfirmAction(null)}
            onConfirm={runAction}
          />
        </div>
      )}
    </div>
  );
}