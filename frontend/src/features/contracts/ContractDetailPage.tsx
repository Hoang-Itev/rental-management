import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { api, ApiError, getAccessToken } from '../../lib/api/client';
import type { ContractOut, Page, TermOut, TenantOut } from '../../lib/api/types';
import { formatDateVi, formatDateTimeVi, contractStatusLabel } from '../../lib/utils/format';
import { Badge } from '../../components/Badge';
import { PageState } from '../../components/PageState';

interface EventOut {
  id: string;
  event_type: string;
  occurred_at: string;
  reason: string | null;
  details: Record<string, unknown>;
}

type ActionKind = 'confirm' | 'end' | 'cancel' | 'renew';

const ACTION_TITLES: Record<ActionKind, string> = {
  confirm: 'Xác nhận hợp đồng',
  end: 'Ghi nhận bàn giao',
  cancel: 'Hủy hợp đồng',
  renew: 'Gia hạn hợp đồng',
};

const ACTION_LABELS: Record<ActionKind, string> = {
  confirm: 'Xác nhận',
  end: 'Ghi nhận',
  cancel: 'Hủy hợp đồng',
  renew: 'Gia hạn',
};

export function ContractDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [contract, setContract] = useState<ContractOut | null>(null);
  const [tenant, setTenant] = useState<TenantOut | null>(null);
  const [roomLocation, setRoomLocation] = useState<string>('');
  const [terms, setTerms] = useState<TermOut[]>([]);
  const [events, setEvents] = useState<EventOut[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [action, setAction] = useState<ActionKind | null>(null);
  const [endDate, setEndDate] = useState('');
  const [renewEnd, setRenewEnd] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // State cho Upload File
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [c, t, e] = await Promise.all([
        api.get<ContractOut>(`/api/v1/contracts/${id}`),
        api.get<Page<TermOut>>(`/api/v1/contracts/${id}/terms?page_size=100`),
        api.get<Page<EventOut>>(`/api/v1/contracts/${id}/events?page_size=100`),
      ]);
      setContract(c);
      setTerms(t.items);
      setEvents(e.items);

      // 1. Lấy thông tin người thuê
      if (c.representative_tenant_id) {
        try {
          const tenantData = await api.get<TenantOut>(`/api/v1/tenants/${c.representative_tenant_id}`);
          setTenant(tenantData);
        } catch {}
      }

      // 2. Lấy thông tin Vị trí (Khu - Dãy - Tầng)
      try {
        const roomData = await api.get<any>(`/api/v1/rooms/${c.room_id}`);
        const floor = await api.get<any>(`/api/v1/floors/${roomData.floor_id}`);
        const building = await api.get<any>(`/api/v1/buildings/${floor.building_id}`);
        const prop = await api.get<any>(`/api/v1/properties/${roomData.property_id}`);
        
        const bName = building.name ? `Dãy ${building.name}` : '';
        const fName = floor.name ? `Tầng ${floor.floor_number} - ${floor.name}` : `Tầng ${floor.floor_number}`;
        setRoomLocation(`[${prop.name}] - ${bName ? bName + ' - ' : ''}${fName} : ${roomData.room_code}`);
      } catch {
        setRoomLocation(`Phòng ${c.room_code_snapshot}`);
      }

    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Không tải được hợp đồng.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  function openAction(kind: ActionKind) {
    setAction(kind);
    setActionError(null);
    setReason('');
    setEndDate('');
    setRenewEnd('');
  }

  function closeAction() {
    if (submitting) return;
    setAction(null);
    setActionError(null);
  }

  async function submitAction(e: React.FormEvent) {
    e.preventDefault();
    if (!action || !contract) return;
    setActionError(null);

    if (action === 'end' && (!endDate || !reason.trim())) { setActionError('Cần nhập ngày và lý do.'); return; }
    if (action === 'cancel' && !reason.trim()) { setActionError('Cần lý do hủy.'); return; }
    if (action === 'renew' && !renewEnd) { setActionError('Cần ngày kết thúc mới.'); return; }

    setSubmitting(true);
    try {
      if (action === 'confirm') await api.post(`/api/v1/contracts/${contract.id}/confirm`);
      else if (action === 'end') await api.post(`/api/v1/contracts/${contract.id}/end`, { actual_end_date: endDate, reason: reason.trim() });
      else if (action === 'cancel') await api.post(`/api/v1/contracts/${contract.id}/cancel`, { reason: reason.trim() });
      else if (action === 'renew') await api.post(`/api/v1/contracts/${contract.id}/renew`, { new_end_date: renewEnd, reason: reason.trim() || null });
      
      setAction(null);
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Thao tác thất bại.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !contract) return;
    
    setUploading(true);
    setUploadError(null);
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`/api/v1/contracts/${contract.id}/upload`, {
        method: 'POST',
        headers: { 
          Authorization: `Bearer ${getAccessToken()}` 
        },
        body: formData,
      });
      
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || err.message || 'Upload thất bại');
      }
      
      await load(); // Reload để lấy attachment_url mới
    } catch (err: any) {
      setUploadError(err.message || 'Không thể upload file.');
    } finally {
      setUploading(false);
    }
  }

  const dangerAction = action === 'cancel' || action === 'end';

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Hợp đồng: {contract?.contract_code ?? '…'}</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-secondary" onClick={() => window.print()}>In bản nháp</button>
          <button className="btn-secondary" onClick={() => navigate('/hop-dong')}>← Quay lại</button>
        </div>
      </div>

      {actionError && !action && <div className="login-error">{actionError}</div>}

      <PageState loading={loading} error={error} onRetry={load}>
        {contract && (
          <div id="contract-print-area">
            
            {/* KHỐI 1: THÔNG TIN PHÒNG & HỢP ĐỒNG */}
            <h3 style={{ marginBottom: 12 }}>Thông tin Hợp đồng & Phòng</h3>
            <div className="detail-grid">
              <div className="detail-item"><label>Phòng (Vị trí)</label><div>{roomLocation}</div></div>
              <div className="detail-item"><label>Trạng thái HĐ</label><div><Badge value={contract.status} /> {contractStatusLabel(contract.status)}</div></div>
              <div className="detail-item"><label>Bắt đầu</label><div>{formatDateVi(contract.start_date)}</div></div>
              <div className="detail-item"><label>Kết thúc (bao gồm)</label><div>{formatDateVi(contract.end_date)}</div></div>
              <div className="detail-item"><label>Bàn giao thực tế</label><div>{contract.actual_end_date ? formatDateVi(contract.actual_end_date) : '—'}</div></div>
              <div className="detail-item"><label>Tiền cọc</label><div>{contract.deposit_amount != null ? contract.deposit_amount.toLocaleString('vi-VN') + ' đ' : '—'}</div></div>
            </div>

            {/* KHỐI 2: THÔNG TIN NGƯỜI THUÊ */}
            <h3 style={{ marginTop: 28, marginBottom: 12 }}>Thông tin Người đại diện</h3>
            <div className="detail-grid">
              <div className="detail-item"><label>Họ tên</label><div>{tenant?.full_name || '—'}</div></div>
              <div className="detail-item"><label>Số điện thoại</label><div>{tenant?.phone || '—'}</div></div>
              <div className="detail-item"><label>Email</label><div>{tenant?.email || '—'}</div></div>
              <div className="detail-item"><label>Ghi chú</label><div>{tenant?.note || '—'}</div></div>
            </div>

            {/* KHỐI 3: ĐÍNH KÈM HỢP ĐỒNG GIẤY */}
            <h3 style={{ marginTop: 28, marginBottom: 12 }}>Hợp đồng giấy đính kèm</h3>
            <div style={{ padding: 16, border: '1px dashed var(--gold-3)', background: 'var(--night-1)', borderRadius: 4 }}>
              {contract.attachment_url ? (
                <div>
                  <p style={{ color: 'var(--jade-hi)', marginBottom: 8 }}>✓ Đã tải lên tệp đính kèm.</p>
                  <a href={contract.attachment_url} target="_blank" rel="noreferrer" className="btn-secondary" style={{ textDecoration: 'none', display: 'inline-block' }}>
                    Xem file đã tải
                  </a>
                </div>
              ) : (
                <div>
                  <p className="text-muted" style={{ fontSize: 13, marginBottom: 12 }}>
                    Tải lên bản scan/chụp ảnh hợp đồng giấy đã ký kết bên ngoài để lưu trữ.
                  </p>
                  <input 
                    type="file" 
                    accept="image/*,application/pdf" 
                    onChange={handleFileUpload} 
                    disabled={uploading}
                    style={{ display: 'none' }}
                    id="contract-upload"
                  />
                  <label htmlFor="contract-upload" className="btn-secondary" style={{ display: 'inline-block', cursor: 'pointer' }}>
                    {uploading ? 'Đang tải lên...' : 'Tải ảnh/PDF lên'}
                  </label>
                  {uploadError && <p style={{ color: 'var(--cinnabar-3)', fontSize: 12, marginTop: 8 }}>{uploadError}</p>}
                </div>
              )}
            </div>

            {/* CÁC NÚT THAO TÁC */}
            <div className="action-bar" style={{ marginTop: 28, display: 'flex', gap: 8, flexWrap: 'wrap' }} data-html2canvas-ignore="true">
              {contract.status === 'DRAFT' && (
                <>
                  <button className="btn-primary" onClick={() => openAction('confirm')}>Xác nhận (lên lịch)</button>
                  <button className="btn-secondary" style={{ color: 'var(--cinnabar-3)' }} onClick={() => openAction('cancel')}>Hủy hợp đồng</button>
                </>
              )}
              {contract.status === 'SCHEDULED' && (
                <button className="btn-secondary" style={{ color: 'var(--cinnabar-3)' }} onClick={() => openAction('cancel')}>Hủy hợp đồng</button>
              )}
              {(contract.status === 'ACTIVE' || contract.status === 'EXPIRED_PENDING') && (
                <>
                  <button className="btn-primary" style={{ background: 'var(--cinnabar-2)' }} onClick={() => openAction('end')}>Ghi nhận bàn giao</button>
                  <button className="btn-secondary" onClick={() => openAction('renew')}>Gia hạn</button>
                </>
              )}
              <Link className="btn-secondary" to={`/hoa-don?contract_id=${contract.id}`} style={{ textDecoration: 'none' }}>Xem hóa đơn</Link>
            </div>

            {/* BẢNG GIÁ VÀ SỰ KIỆN */}
            <h3 style={{ marginTop: 28 }}>Lịch sử giá thuê</h3>
            <table className="data-table">
              <thead>
                <tr><th>Từ ngày</th><th>Đến ngày (exclusive)</th><th>Tiền phòng</th><th>Điện</th><th>Nước</th><th>Phí DV</th></tr>
              </thead>
              <tbody>
                {terms.length === 0 && <tr><td colSpan={6} className="empty-row">Chưa có điều khoản.</td></tr>}
                {terms.map((t) => (
                  <tr key={t.id}>
                    <td>{formatDateVi(t.effective_from)}</td>
                    <td>{t.effective_to ? formatDateVi(t.effective_to) : 'Không giới hạn'}</td>
                    <td className="text-amount">{t.monthly_rent.toLocaleString('vi-VN')} đ</td>
                    <td>{t.electricity_unit_price.toLocaleString('vi-VN')} đ</td>
                    <td>{t.water_unit_price.toLocaleString('vi-VN')} đ</td>
                    <td>{t.monthly_service_fee.toLocaleString('vi-VN')} đ</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h3 style={{ marginTop: 28 }}>Lịch sử sự kiện</h3>
            <table className="data-table">
              <thead>
                <tr><th>Thời điểm</th><th>Sự kiện</th><th>Lý do</th></tr>
              </thead>
              <tbody>
                {events.length === 0 && <tr><td colSpan={3} className="empty-row">Chưa có sự kiện.</td></tr>}
                {events.map((e) => (
                  <tr key={e.id}>
                    <td>{formatDateTimeVi(e.occurred_at)}</td>
                    <td>{e.event_type}</td>
                    <td>{e.reason || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </PageState>

      {action && contract && (
        <div className="modal-backdrop active" data-html2canvas-ignore="true" onClick={(e) => e.target === e.currentTarget && closeAction()}>
          <div className="room-modal" style={{ width: 480 }}>
            <button className="modal-close" onClick={closeAction} disabled={submitting}>×</button>
            <h2 className="modal-title">{ACTION_TITLES[action]}</h2>

            <form onSubmit={submitAction}>
              {action === 'end' && (
                <div className="login-field">
                  <label>Ngày bàn giao thực tế *</label>
                  <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} max={new Date().toISOString().slice(0, 10)} min={contract.start_date} required />
                </div>
              )}
              {action === 'renew' && (
                <div className="login-field">
                  <label>Ngày kết thúc mới * (sau {formatDateVi(contract.end_date)})</label>
                  <input type="date" value={renewEnd} onChange={(e) => setRenewEnd(e.target.value)} min={contract.end_date} required />
                </div>
              )}
              {(action === 'end' || action === 'cancel' || action === 'renew') && (
                <div className="login-field">
                  <label>{action === 'renew' ? 'Lý do (tùy chọn)' : 'Lý do *'}</label>
                  <textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} required={action !== 'renew'} />
                </div>
              )}
              {actionError && <div className="login-error">{actionError}</div>}
              <div className="modal-actions">
                <button type="button" className="modal-btn" onClick={closeAction} disabled={submitting}>Hủy</button>
                <button type="submit" className="modal-btn primary" style={dangerAction ? { background: 'var(--cinnabar-2)' } : undefined} disabled={submitting}>
                  {submitting ? 'Đang xử lý…' : ACTION_LABELS[action]}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}