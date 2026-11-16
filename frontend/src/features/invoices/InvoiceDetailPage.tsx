import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { InvoiceDetail } from '../../lib/api/types';
import { formatVnd, formatDateVi, periodEndInclusive } from '../../lib/utils/format';
import { PageState } from '../../components/PageState';
import { ConfirmDialog } from '../../components/ConfirmDialog';

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
  const [originalInvoice, setOriginalInvoice] = useState<InvoiceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [roomLocation, setRoomLocation] = useState<string>('');
  const [cashNote, setCashNote] = useState<string>('');

  const [confirmAction, setConfirmAction] = useState<{ kind: 'issue' | 'void' | 'reissue' | 'reminder'; requireReason?: boolean } | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [cashModalOpen, setCashModalOpen] = useState(false);
  const [cashLoading, setCashLoading] = useState(false);
  const [cashError, setCashError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true); setError(null);
    try {
      const inv = await api.get<InvoiceDetail>(`/api/v1/invoices/${id}`);
      setInvoice(inv);
      
      // Nếu là hóa đơn phát hành lại, lấy thông tin hóa đơn gốc để xem lý do
      if (inv.replaces_invoice_id) {
        try {
          const oldInv = await api.get<InvoiceDetail>(`/api/v1/invoices/${inv.replaces_invoice_id}`);
          setOriginalInvoice(oldInv);
        } catch {
          setOriginalInvoice(null);
        }
      } else {
        setOriginalInvoice(null);
      }

      try {
        const roomData = await api.get<any>(`/api/v1/rooms/${inv.room_id}`);
        const floor = await api.get<any>(`/api/v1/floors/${roomData.floor_id}`);
        const building = await api.get<any>(`/api/v1/buildings/${floor.building_id}`);
        const prop = await api.get<any>(`/api/v1/properties/${roomData.property_id}`);
        setRoomLocation(`[${prop.name}] - Dãy ${building.name} - Tầng ${floor.floor_number}`);
      } catch {
        setRoomLocation('Không xác định');
      }
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
      
      // Nếu là reissue, API trả về hóa đơn MỚI. Cần chuyển hướng sang trang của hóa đơn mới.
      if (confirmAction.kind === 'reissue') {
        const res = await api.post<any>(`/api/v1/invoices/${invoice.id}/reissue`, { reason: reason ?? '' });
        // res chính là InvoiceDetail của hóa đơn mới
        if (res && res.id) {
          navigate(`/hoa-don/${res.id}`);
        } else {
          await load(); // Fallback nếu backend không trả về object
        }
      } else {
        await load();
      }
      setConfirmAction(null);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Thao tác thất bại.');
    } finally { setConfirmLoading(false); }
  }

  async function submitCashPayment(e: React.FormEvent) {
    e.preventDefault();
    if (!invoice) return;
    if (cashNote.trim().length < 8) {
      setCashError('Ghi chú phải có ít nhất 8 ký tự.');
      return;
    }
    setCashLoading(true); setCashError(null);
    try {
      await api.post(`/api/v1/invoices/${invoice.id}/mark-paid`, { note: cashNote.trim() });
      setCashModalOpen(false);
      setCashNote('');
      await load();
    } catch (err) {
      setCashError(err instanceof ApiError ? err.message : 'Không thể xác nhận thu tiền mặt.');
    } finally { setCashLoading(false); }
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
          .invoice-print-block { page-break-inside: avoid; }
        }
        @keyframes lanternSwing {
          0%, 100% { transform: rotate(-5deg); }
          50% { transform: rotate(5deg); }
        }
        @keyframes cloudDrift {
          0% { transform: translateX(0); }
          50% { transform: translateX(-20px); }
          100% { transform: translateX(0); }
        }
        @keyframes leafFall {
          0% { transform: translateY(0) rotate(0deg); opacity: 1; }
          100% { transform: translateY(100px) rotate(90deg); opacity: 0; }
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
            
            <div className="invoice-decorations no-print" style={{ position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.15, zIndex: 0 }}>
              <svg style={{ position: 'absolute', top: 20, left: 20, width: 60, height: 90, animation: 'lanternSwing 5s ease-in-out infinite' }} viewBox="0 0 24 30" fill="none" stroke="var(--cinnabar-2)" strokeWidth="1.5">
                <path d="M12 2v4" /><rect x="8" y="6" width="8" height="16" rx="4" fill="var(--cinnabar-2)" fillOpacity="0.3" /><path d="M9 22h6M12 22v4" /><path d="M8 10h8M8 14h8M8 18h8" strokeOpacity="0.5" />
              </svg>
              <svg style={{ position: 'absolute', top: 30, right: 30, width: 80, height: 40, animation: 'cloudDrift 20s linear infinite' }} viewBox="0 0 100 50" fill="var(--gold-3)" opacity="0.5">
                <path d="M10,40 Q20,20 40,30 Q60,10 80,25 Q95,30 90,40 Z" />
              </svg>
            </div>

            <div className="invoice-print-block" style={{ position: 'relative', zIndex: 1 }}>
              <div style={{ textAlign: 'center', marginBottom: 30 }}>
                <h2 style={{ color: 'var(--cinnabar-2)', fontSize: 28, marginBottom: 8, textTransform: 'uppercase', fontFamily: "'Cormorant Garamond', serif" }}>Hóa Đơn Tiền Nhà</h2>
                <p style={{ color: 'var(--ink-soft)', fontStyle: 'italic' }}>Mã hóa đơn: {invoice.invoice_code}</p>
                <p style={{ color: 'var(--ink-soft)' }}>Kỳ hạn: Từ {formatDateVi(invoice.period_start)} đến {formatDateVi(periodEndInclusive(invoice.period_end))}</p>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
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

              {/* Hiển thị lý do VOID / Reissue nếu có */}
              {invoice.status === 'VOID' && (
                <div style={{ border: '1px solid var(--cinnabar-2)', background: 'rgba(197,46,26,0.08)', padding: 12, marginBottom: 20, borderRadius: 4 }}>
                  <div style={{ fontWeight: 'bold', color: 'var(--cinnabar-2)', marginBottom: 4 }}>Hóa đơn đã bị HỦY</div>
                  <div style={{ fontSize: 14 }}><strong>Lý do hủy:</strong> {invoice.void_reason || '—'}</div>
                  <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>Thời điểm hủy: {invoice.voided_at ? new Date(invoice.voided_at).toLocaleString('vi-VN') : '—'}</div>
                </div>
              )}
              
              {invoice.replaces_invoice_id && (
                <div style={{ border: '1px solid var(--gold-3)', background: 'rgba(212,163,64,0.08)', padding: 12, marginBottom: 20, borderRadius: 4 }}>
                  <div style={{ fontWeight: 'bold', color: 'var(--cinnabar-2)' }}>Đây là hóa đơn phát hành lại</div>
                  <div style={{ fontSize: 14 }}>Thay thế hóa đơn gốc (Mã: {originalInvoice ? originalInvoice.invoice_code : invoice.replaces_invoice_id.slice(0, 8) + '...'})</div>
                  {originalInvoice && originalInvoice.void_reason && (
                    <div style={{ fontSize: 14, marginTop: 4 }}><strong>Lý do phát hành lại:</strong> {originalInvoice.void_reason}</div>
                  )}
                  <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>Lần phát hành: #{invoice.revision}</div>
                </div>
              )}

              {/* Dạng văn bản dọc thay cho bảng ngang, tránh cắt cột */}
              <div style={{ marginBottom: 20 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '30px 1fr 120px 140px', fontWeight: 'bold', borderBottom: '2px solid var(--gold-3)', paddingBottom: 8, marginBottom: 4, fontSize: 13, textTransform: 'uppercase', color: 'var(--gold-3)' }}>
                  <div>STT</div>
                  <div>Nội dung</div>
                  <div style={{ textAlign: 'right' }}>Số lượng</div>
                  <div style={{ textAlign: 'right' }}>Thành tiền</div>
                </div>
                {invoice.items.map((item, index) => (
                  <div key={item.id} style={{ display: 'grid', gridTemplateColumns: '30px 1fr 120px 140px', padding: '8px 0', borderBottom: '1px dashed var(--stone)', fontSize: 14 }}>
                    <div>{index + 1}</div>
                    <div>
                      <div>{translateDescription(item.description)}</div>
                      <div style={{ fontSize: 12, color: 'var(--ink-soft)' }}>Đơn giá: {formatVnd(Number(item.unit_price))}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>{item.quantity} {item.unit}</div>
                    <div style={{ textAlign: 'right', fontWeight: 'bold' }}>{formatVnd(item.amount)}</div>
                  </div>
                ))}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px', padding: '12px 0', borderTop: '2px solid var(--gold-3)', marginTop: 4 }}>
                  <div style={{ textAlign: 'right', fontWeight: 'bold', fontSize: 16 }}>TỔNG CỘNG:</div>
                  <div style={{ textAlign: 'right', fontWeight: 'bold', fontSize: 22, color: 'var(--cinnabar-2)' }}>{formatVnd(invoice.total_amount)}</div>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 30 }}>
                <div style={{ fontStyle: 'italic', color: 'var(--ink-soft)', fontSize: 13 }}>
                  Hạn thanh toán: <strong style={{ color: 'var(--cinnabar-2)' }}>{formatDateVi(invoice.due_date)}</strong><br/>
                  {invoice.status === 'PAID' && invoice.paid_at && (
                    <>Đã thanh toán lúc: <strong>{new Date(invoice.paid_at).toLocaleString('vi-VN')}</strong></>
                  )}
                  {invoice.status !== 'PAID' && 'Vui lòng thanh toán đúng hạn để tránh gián đoạn dịch vụ.'}
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
            <button className="btn-primary" style={{ background: 'var(--jade)', borderColor: 'var(--jade-2)' }} onClick={() => window.print()}>In hóa đơn (PDF)</button>
           {invoice.status === 'DRAFT' && <button className="btn-primary" onClick={() => setConfirmAction({ kind: 'issue' })}>Phát hành hóa đơn</button>}
           {invoice.status === 'ISSUED' && (
              <>
                <button className="btn-secondary" onClick={() => setConfirmAction({ kind: 'reminder' })}>Gửi nhắc nợ</button>
                <button className="btn-primary" style={{ background: 'var(--jade)', borderColor: 'var(--jade-2)' }} onClick={() => { setCashNote(''); setCashError(null); setCashModalOpen(true); }}>Thu tiền mặt</button>
                <button className="btn-secondary" onClick={() => setConfirmAction({ kind: 'reissue', requireReason: true })}>Phát hành lại</button>
                <button className="btn-primary" style={{ background: 'var(--cinnabar-2)' }} onClick={() => setConfirmAction({ kind: 'void', requireReason: true })}>Hủy</button>
              </>
            )}
            {invoice.status === 'VOID' && (
              <button className="btn-secondary" onClick={() => setConfirmAction({ kind: 'reissue', requireReason: true })}>Phát hành lại</button>
            )}
        </div>
      )}

      {cashModalOpen && invoice && (
        <div className="modal-backdrop active no-print" onClick={(e) => e.target === e.currentTarget && !cashLoading && setCashModalOpen(false)}>
          <div className="room-modal" style={{ width: 460 }}>
            <button className="modal-close" onClick={() => !cashLoading && setCashModalOpen(false)}>×</button>
            <h2 className="modal-title">Xác nhận thu tiền mặt</h2>
            <p style={{ marginBottom: 16, fontSize: 14, color: 'var(--ink-soft)' }}>
              Hóa đơn <strong>{invoice.invoice_code}</strong> — Tổng tiền: <strong style={{ color: 'var(--cinnabar-2)' }}>{formatVnd(invoice.total_amount)}</strong>
            </p>
            <form onSubmit={submitCashPayment}>
              <div className="login-field">
                <label>Ghi chú (≥ 8 ký tự) *</label>
                <textarea rows={3} value={cashNote} onChange={(e) => setCashNote(e.target.value)} placeholder="VD: Khách đã đưa đủ tiền mặt tại phòng..." required />
              </div>
              {cashError && <div className="login-error" style={{ marginBottom: 16 }}>{cashError}</div>}
              <div className="modal-actions">
                <button type="button" className="modal-btn" onClick={() => setCashModalOpen(false)} disabled={cashLoading}>Hủy</button>
                <button type="submit" className="modal-btn primary" disabled={cashLoading}>{cashLoading ? 'Đang lưu…' : 'Xác nhận đã thu'}</button>
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