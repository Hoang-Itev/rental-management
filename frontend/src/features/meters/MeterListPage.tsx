import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type {
  Page, RoomOut, MeterOut, RoomMeterList, CutoffOut, MeterAlertOut, ReadingOut,
} from '../../lib/api/types';
import { formatDateTimeVi } from '../../lib/utils/format';
import { PageState } from '../../components/PageState';
import { Badge } from '../../components/Badge';
import { Pagination } from '../../components/Pagination';
import { ConfirmDialog } from '../../components/ConfirmDialog';

type Tab = 'room' | 'cutoffs' | 'alerts' | 'bulk';

function translateAlertType(type: string) {
  switch (type) {
    case 'OFFLINE': return 'Mất kết nối';
    case 'READING_DECREASE': return 'Số bị giảm';
    case 'LATE_AFTER_CUTOFF': return 'Số về muộn';
    case 'CONFLICTING_DUPLICATE': return 'Dữ liệu trùng lặp';
    default: return type;
  }
}

function translateAlertDetail(type: string, detail: Record<string, unknown>) {
  if (type === 'OFFLINE') {
    return `Không nhận được tín hiệu trong ${detail.offline_minutes || 20} phút qua. (Lần cuối: ${formatDateTimeVi(String(detail.last_seen_at))})`;
  }
  if (type === 'READING_DECREASE') {
    return `Số mới (${detail.incoming}) nhỏ hơn số cũ (${detail.before}). Có thể nhập sai hoặc đồng hồ bị quay lùi.`;
  }
  if (type === 'CONFLICTING_DUPLICATE') {
    return `Có 2 chỉ số khác nhau cùng ghi nhận trong 1 thời điểm. Số đã lưu: ${detail.stored}, số mới tới: ${detail.incoming}.`;
  }
  if (type === 'LATE_AFTER_CUTOFF') {
    return `Có số đo mới gửi về muộn sau khi đã chốt kỳ. Giá trị muộn: ${detail.late_value}, giá trị đã chốt: ${detail.confirmed_value}.`;
  }
  return JSON.stringify(detail);
}

export function MeterListPage() {
  const [tab, setTab] = useState<Tab>('room');
  const [rooms, setRooms] = useState<RoomOut[]>([]);
  const [selectedRoom, setSelectedRoom] = useState('');
  const [meters, setMeters] = useState<MeterOut[]>([]);
  const [cutoffs, setCutoffs] = useState<CutoffOut[]>([]);
  const [loadingMeters, setLoadingMeters] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Readings
  const [readingsFor, setReadingsFor] = useState<MeterOut | null>(null);
  const [readings, setReadings] = useState<ReadingOut[]>([]);
  const [readingsLoading, setReadingsLoading] = useState(false);

  // Confirm cutoff modal
  const [activeCutoff, setActiveCutoff] = useState<CutoffOut | null>(null);
  const [manualValue, setManualValue] = useState('');
  const [manualReason, setManualReason] = useState('');
  const [confirming, setConfirming] = useState(false);

  // Global PENDING cutoffs
  const [pendingCutoffs, setPendingCutoffs] = useState<CutoffOut[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);

  // ALERTS (Lịch sử, lọc, phân trang)
  const [alerts, setAlerts] = useState<MeterAlertOut[]>([]);
  const [alertsTotal, setAlertsTotal] = useState(0);
  const [alertsPage, setAlertsPage] = useState(1);
  const [alertsStatus, setAlertsStatus] = useState<'OPEN' | 'RESOLVED' | ''>('OPEN'); // Mặc định lọc OPEN
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [resolving, setResolving] = useState<string | null>(null);
  
  // Modal nhập ghi chú khi xử lý
  const [resolveTarget, setResolveTarget] = useState<MeterAlertOut | null>(null);
  const [resolveNote, setResolveNote] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<MeterAlertOut | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Map để hiển thị Mã phòng thay vì Meter ID
  const [meterRooms, setMeterRooms] = useState<Record<string, string>>({});

  // Bulk Update
  const [bulkRows, setBulkRows] = useState<any[]>([]);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkSaving, setBulkSaving] = useState(false);

  useEffect(() => {
    api.get<Page<RoomOut>>('/api/v1/rooms?page_size=100')
      .then(async (r) => {
        setRooms(r.items);
        const map: Record<string, string> = {};
        for (const room of r.items) {
          try {
            const m = await api.get<RoomMeterList>(`/api/v1/rooms/${room.id}/meters`);
            m.items.forEach(meter => {
              map[meter.id] = room.room_code;
            });
          } catch {}
        }
        setMeterRooms(map);
      })
      .catch(() => setRooms([]));
  }, []);

  const loadRoomData = useCallback(async () => {
    if (!selectedRoom) { setMeters([]); setCutoffs([]); return; }
    setLoadingMeters(true); setError(null);
    try {
      const m = await api.get<RoomMeterList>(`/api/v1/rooms/${selectedRoom}/meters`);
      setMeters(m.items);
      const c = await api.get<Page<CutoffOut>>(`/api/v1/meter-cutoffs?room_id=${selectedRoom}&page_size=100`);
      setCutoffs(c.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được thông tin đồng hồ.');
    } finally {
      setLoadingMeters(false);
    }
  }, [selectedRoom]);

  useEffect(() => { loadRoomData(); }, [loadRoomData]);

  const loadPending = useCallback(async () => {
    setPendingLoading(true); setError(null);
    try {
      const res = await api.get<Page<CutoffOut>>('/api/v1/meter-cutoffs?status=PENDING&page_size=100');
      setPendingCutoffs(res.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được danh sách chờ chốt số.');
    } finally {
      setPendingLoading(false);
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    setAlertsLoading(true); setError(null);
    try {
      let url = `/api/v1/meter-alerts?page=${alertsPage}&page_size=10`;
      if (alertsStatus) url += `&status=${alertsStatus}`;
      const res = await api.get<Page<MeterAlertOut>>(url);
      setAlerts(res.items);
      setAlertsTotal(res.meta.total);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được cảnh báo.');
    } finally {
      setAlertsLoading(false);
    }
  }, [alertsPage, alertsStatus]);

  useEffect(() => {
    if (tab === 'cutoffs') loadPending();
    if (tab === 'alerts') loadAlerts();
  }, [tab, loadPending, loadAlerts]);

  async function openReadings(m: MeterOut) {
    setReadingsFor(m); setReadings([]); setReadingsLoading(true);
    try {
      const res = await api.get<Page<ReadingOut>>(`/api/v1/meters/${m.id}/readings?page_size=50`);
      setReadings(res.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được chỉ số.');
    } finally {
      setReadingsLoading(false);
    }
  }

  async function submitConfirmCutoff(e: React.FormEvent) {
    e.preventDefault();
    if (!activeCutoff) return;
    if (manualReason.trim().length < 8) { setError('Lý do phải có ít nhất 8 ký tự.'); return; }
    setConfirming(true); setError(null);
    try {
      await api.post(`/api/v1/meter-cutoffs/${activeCutoff.id}/confirm`, {
        reading_value: manualValue,
        manual_reason: manualReason.trim(),
      });
      setActiveCutoff(null); setManualValue(''); setManualReason('');
      await loadRoomData();
      if (tab === 'cutoffs') await loadPending();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Lỗi khi xác nhận.');
    } finally {
      setConfirming(false);
    }
  }

  async function executeResolve() {
    if (!resolveTarget) return;
    if (resolveNote.trim().length < 8) { setError('Ghi chú phải có ít nhất 8 ký tự.'); return; }
    setResolving(resolveTarget.id); setError(null);
    try {
      await api.post(`/api/v1/meter-alerts/${resolveTarget.id}/resolve`, { 
        resolution_note: resolveNote.trim() 
      });
      setResolveTarget(null);
      setResolveNote('');
      await loadAlerts();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Không thể xử lý cảnh báo.');
    } finally {
      setResolving(null);
    }
  }

  async function doDeleteAlert() {
    if (!deleteTarget) return;
    setDeleting(true); setError(null);
    try {
      await api.delete(`/api/v1/meter-alerts/${deleteTarget.id}`);
      setDeleteTarget(null);
      await loadAlerts();
    } catch (err) {
      // Dịch lỗi sang tiếng Việt
      if (err instanceof ApiError && err.status === 404) {
        setError('Tính năng Xóa cảnh báo chưa được cập nhật ở máy chủ (Lỗi 404).');
      } else {
        setError(err instanceof ApiError ? err.message : 'Không thể xóa cảnh báo.');
      }
    } finally {
      setDeleting(false);
    }
  }

  // --- HÀM XỬ LÝ GHI SỐ HÀNG LOẠT ---
  async function loadBulkRows() {
    setBulkLoading(true); setError(null);
    try {
      const contracts = await api.get<any>('/api/v1/contracts?status=ACTIVE&page_size=100');
      const rows = [];
      for (const c of contracts.items) {
        const meters = await api.get<any>(`/api/v1/rooms/${c.room_id}/meters`);
        const elec = meters.items.find((m: any) => m.meter_type === 'ELECTRICITY');
        const water = meters.items.find((m: any) => m.meter_type === 'WATER');
        
        rows.push({
          contract_id: c.id,
          room_code: c.room_code_snapshot,
          elec_meter_id: elec?.id,
          water_meter_id: water?.id,
          elec_val: '',
          water_val: '',
        });
      }
      setBulkRows(rows);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Lỗi tải dữ liệu ghi số.');
    } finally {
      setBulkLoading(false);
    }
  }

  async function saveBulk() {
    const validRows = bulkRows.filter(r => r.elec_val || r.water_val);
    if (validRows.length === 0) { setError('Chưa nhập số nào.'); return; }
    
    setBulkSaving(true); setError(null);
    try {
      for (const r of validRows) {
        if (r.elec_val) {
          const elecCutoffs = await api.get<any>(`/api/v1/meter-cutoffs?meter_id=${r.elec_meter_id}&status=PENDING&page_size=1`);
          if (elecCutoffs.items.length > 0) {
             await api.post(`/api/v1/meter-cutoffs/${elecCutoffs.items[0].id}/confirm`, {
               reading_value: Number(r.elec_val), manual_reason: 'Ghi số hàng loạt'
             });
          }
        }
        if (r.water_val) {
          const waterCutoffs = await api.get<any>(`/api/v1/meter-cutoffs?meter_id=${r.water_meter_id}&status=PENDING&page_size=1`);
          if (waterCutoffs.items.length > 0) {
             await api.post(`/api/v1/meter-cutoffs/${waterCutoffs.items[0].id}/confirm`, {
               reading_value: Number(r.water_val), manual_reason: 'Ghi số hàng loạt'
             });
          }
        }
      }
      alert('Đã lưu thành công!');
      setBulkRows([]);
    } catch (e: any) {
      setError('Lỗi: ' + (e.message || 'Không thể lưu.'));
    } finally {
      setBulkSaving(false);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Đồng hồ điện nước</h1>
      </div>

      <div className="filter-bar">
        <button className={`btn-secondary ${tab === 'room' ? 'primary' : ''}`} onClick={() => setTab('room')}>Theo phòng</button>
        <button className={`btn-secondary ${tab === 'cutoffs' ? 'primary' : ''}`} onClick={() => setTab('cutoffs')}>Chốt số chờ xử lý</button>
        <button className={`btn-secondary ${tab === 'bulk' ? 'primary' : ''}`} onClick={() => { setTab('bulk'); if (bulkRows.length === 0) loadBulkRows(); }}>Ghi số hàng loạt</button>
        <button className={`btn-secondary ${tab === 'alerts' ? 'primary' : ''}`} onClick={() => setTab('alerts')}>Cảnh báo</button>
      </div>

      {error && <div className="login-error">{error}</div>}

      {tab === 'room' && (
        <>
          <div className="filter-bar">
            <select value={selectedRoom} onChange={(e) => setSelectedRoom(e.target.value)}>
              <option value="">— Chọn phòng —</option>
              {rooms.map((r) => <option key={r.id} value={r.id}>{r.room_code}</option>)}
            </select>
          </div>

          <PageState
            loading={loadingMeters}
            error={null}
            empty={!loadingMeters && !!selectedRoom && meters.length === 0}
            emptyText="Phòng này chưa có đồng hồ (có thể chờ sự kiện RoomCreated)."
          >
            <div className="property-grid">
              {meters.map((m) => (
                <div key={m.id} className="property-card">
                  <h3>{m.meter_type === 'ELECTRICITY' ? 'Điện' : 'Nước'}</h3>
                  <p>Mã: {m.meter_code}</p>
                  <p>Đơn vị: {m.unit}</p>
                  <Badge value={m.status} />
                  <div style={{ marginTop: 12 }}>
                    <button className="btn-secondary" onClick={() => openReadings(m)}>Xem chỉ số</button>
                  </div>
                </div>
              ))}
            </div>

            <h3 style={{ marginTop: 28 }}>Các mốc chốt số</h3>
            <table className="data-table">
              <thead>
                <tr><th>Loại</th><th>Thời điểm</th><th>Chỉ số</th><th>Trạng thái</th><th></th></tr>
              </thead>
              <tbody>
                {cutoffs.length === 0 && <tr><td colSpan={5} className="empty-row">Chưa có mốc chốt số nào.</td></tr>}
                {cutoffs.map((c) => (
                  <tr key={c.id}>
                    <td>{c.cutoff_type === 'MONTHLY' ? 'Chốt tháng' : c.cutoff_type === 'CONTRACT_START' ? 'Bắt đầu HĐ' : 'Kết thúc HĐ'}</td>
                    <td>{formatDateTimeVi(c.cutoff_at)}</td>
                    <td>{c.reading_value ?? '—'}</td>
                    <td><Badge value={c.status} /></td>
                    <td>
                      {c.status === 'PENDING' && (
                        <button className="btn-secondary" onClick={() => setActiveCutoff(c)}>Chốt số</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </PageState>
        </>
      )}

      {tab === 'cutoffs' && (
        <PageState
          loading={pendingLoading}
          error={null}
          empty={!pendingLoading && pendingCutoffs.length === 0}
          emptyText="Không có mốc chốt số nào đang chờ xử lý."
          onRetry={loadPending}
        >
          <table className="data-table">
            <thead>
              <tr><th>Mã phòng</th><th>Loại mốc</th><th>Thời điểm chốt</th><th></th></tr>
            </thead>
            <tbody>
              {pendingCutoffs.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 'bold', color: 'var(--cinnabar-2)' }}>
                    {meterRooms[c.meter_id] || 'Chưa rõ'}
                  </td>
                  <td>{c.cutoff_type === 'MONTHLY' ? 'Chốt tháng' : c.cutoff_type === 'CONTRACT_START' ? 'Bắt đầu HĐ' : 'Kết thúc HĐ'}</td>
                  <td>{formatDateTimeVi(c.cutoff_at)}</td>
                  <td><button className="btn-secondary" onClick={() => setActiveCutoff(c)}>Chốt số</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </PageState>
      )}

      {tab === 'bulk' && (
        <div>
          <PageState loading={bulkLoading} error={null} empty={!bulkLoading && bulkRows.length === 0} emptyText="Không có phòng nào đang thuê để ghi số." onRetry={loadBulkRows}>
            <div style={{ background: 'var(--night-1)', padding: 16, borderRadius: 4, border: '1px solid var(--gold-3)' }}>
              <p className="text-muted" style={{ marginBottom: 12, fontSize: 13 }}>
                Nhập số điện/nước mới cho từng phòng. Hệ thống sẽ tự động chốt vào mốc chờ gần nhất. Để trống nếu phòng đó không thay đổi số.
              </p>
              <table className="data-table">
                <thead>
                  <tr><th>Phòng</th><th>Số điện mới (kWh)</th><th>Số nước mới (m³)</th></tr>
                </thead>
                <tbody>
                  {bulkRows.map((r, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 'bold' }}>{r.room_code}</td>
                      <td><input type="number" step="0.01" value={r.elec_val} onChange={e => { const n=[...bulkRows]; n[i].elec_val = e.target.value; setBulkRows(n); }} placeholder="Nhập số..." style={{ width: '100%', padding: 6 }} /></td>
                      <td><input type="number" step="0.01" value={r.water_val} onChange={e => { const n=[...bulkRows]; n[i].water_val = e.target.value; setBulkRows(n); }} placeholder="Nhập số..." style={{ width: '100%', padding: 6 }} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                 <button className="btn-secondary" onClick={loadBulkRows} disabled={bulkSaving}>Tải lại</button>
                 <button className="btn-primary" onClick={saveBulk} disabled={bulkSaving}>{bulkSaving ? 'Đang lưu...' : 'Lưu tất cả'}</button>
              </div>
            </div>
          </PageState>
        </div>
      )}

      {tab === 'alerts' && (
        <>
          <div className="filter-bar">
            <select value={alertsStatus} onChange={e => { setAlertsStatus(e.target.value as any); setAlertsPage(1); }}>
              <option value="">Tất cả cảnh báo</option>
              <option value="OPEN">Đang mở (Cần xử lý)</option>
              <option value="RESOLVED">Đã xử lý</option>
            </select>
          </div>

          <PageState
            loading={alertsLoading}
            error={null}
            empty={!alertsLoading && alerts.length === 0}
            emptyText="Không có cảnh báo nào."
            onRetry={loadAlerts}
          >
            <table className="data-table">
              <thead>
                <tr><th>Mã phòng</th><th>Loại cảnh báo</th><th>Phát hiện lúc</th><th>Chi tiết / Ghi chú</th><th>Trạng thái</th><th>Thao tác</th></tr>
              </thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id}>
                    <td style={{ fontWeight: 'bold', color: 'var(--cinnabar-2)' }}>
                      {meterRooms[a.meter_id] || 'Chưa rõ'}
                    </td>
                    <td>
                      <span style={{ color: a.alert_type === 'OFFLINE' ? 'var(--cinnabar-3)' : 'var(--amber)', fontWeight: 600 }}>
                        {translateAlertType(a.alert_type)}
                      </span>
                    </td>
                    <td>{formatDateTimeVi(a.detected_at)}</td>
                    <td style={{ fontSize: 13, maxWidth: 300 }}>
                      {a.status === 'RESOLVED' && a.resolution_note ? (
                        <span style={{ color: 'var(--jade-2)', fontStyle: 'italic' }}>
                          Ghi chú: {a.resolution_note}
                        </span>
                      ) : (
                        translateAlertDetail(a.alert_type, a.detail)
                      )}
                    </td>
                    <td><Badge value={a.status} /></td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {a.status === 'OPEN' && (
                          <button className="btn-primary" style={{ padding: '4px 12px' }} onClick={() => { setResolveTarget(a); setResolveNote(''); }}>
                            Đã kiểm tra
                          </button>
                        )}
                        <button className="btn-secondary" style={{ padding: '4px 12px', color: 'var(--cinnabar-3)' }} onClick={() => setDeleteTarget(a)}>
                          Xóa
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {alertsTotal > 0 && (
              <Pagination page={alertsPage} pageSize={10} total={alertsTotal} onPageChange={setAlertsPage} />
            )}
          </PageState>
        </>
      )}

      {/* MODAL NHẬP GHI CHÚ KHI XỬ LÝ CẢNH BÁO */}
      {resolveTarget && (
        <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && setResolveTarget(null)}>
          <div className="room-modal" style={{ width: 460 }}>
            <button className="modal-close" onClick={() => setResolveTarget(null)}>×</button>
            <h2 className="modal-title">Đã kiểm tra cảnh báo</h2>
            <p className="text-muted" style={{ marginBottom: 16 }}>
              Vui lòng nhập ghi chú xử lý (VD: Đã sửa lại đồng hồ, đã thay pin...)
            </p>
            <div className="login-field">
              <label>Ghi chú xử lý (≥ 8 ký tự) *</label>
              <textarea rows={3} value={resolveNote} onChange={(e) => setResolveNote(e.target.value)} required />
            </div>
            <div className="modal-actions">
              <button className="modal-btn" onClick={() => setResolveTarget(null)}>Hủy</button>
              <button className="modal-btn primary" onClick={executeResolve} disabled={resolving === resolveTarget.id}>
                {resolving === resolveTarget.id ? 'Đang lưu...' : 'Xác nhận đã xử lý'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL XÓA CẢNH BÁO */}
      {deleteTarget && (
        <ConfirmDialog
          title="Xóa cảnh báo?"
          message={`Cảnh báo của phòng ${meterRooms[deleteTarget.meter_id] || 'Không rõ'} sẽ bị xóa vĩnh viễn khỏi hệ thống.`}
          confirmLabel="Xóa"
          variant="danger"
          loading={deleting}
          onCancel={() => setDeleteTarget(null)}
          onConfirm={doDeleteAlert}
        />
      )}

      {/* MODAL CHỐT SỐ */}
      {activeCutoff && (
        <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && setActiveCutoff(null)}>
          <div className="room-modal" style={{ width: 420 }}>
            <button className="modal-close" onClick={() => setActiveCutoff(null)}>×</button>
            <h2 className="modal-title">Chốt số thủ công</h2>
            <p className="text-muted">
              {activeCutoff.cutoff_type} — {formatDateTimeVi(activeCutoff.cutoff_at)}
            </p>
            <form onSubmit={submitConfirmCutoff}>
              <div className="login-field">
                <label>Chỉ số tích lũy thực tế *</label>
                <input type="number" step="0.001" min="0" value={manualValue} onChange={(e) => setManualValue(e.target.value)} required />
              </div>
              <div className="login-field">
                <label>Lý do (≥ 8 ký tự) *</label>
                <input value={manualReason} onChange={(e) => setManualReason(e.target.value)} required />
              </div>
              <div className="modal-actions">
                <button type="button" className="modal-btn" onClick={() => setActiveCutoff(null)} disabled={confirming}>Hủy</button>
                <button type="submit" className="modal-btn primary" disabled={confirming}>{confirming ? 'Đang lưu…' : 'Xác nhận'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {readingsFor && (
        <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && setReadingsFor(null)}>
          <div className="room-modal" style={{ width: 'min(760px, 96vw)' }}>
            <button className="modal-close" onClick={() => setReadingsFor(null)}>×</button>
            <h2 className="modal-title">Chỉ số — {readingsFor.meter_code}</h2>
            {readingsLoading ? (
              <div className="loading-text">Đang tải…</div>
            ) : readings.length === 0 ? (
              <div className="empty-row">Chưa có chỉ số.</div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr><th>Đo lúc</th><th>Giá trị</th><th>Trạng thái</th><th>Ghi chú</th></tr>
                </thead>
                <tbody>
                  {readings.map((r, i) => (
                    <tr key={i}>
                      <td>{formatDateTimeVi(r.measured_at)}</td>
                      <td>{String(r.reading_value)}</td>
                      <td><Badge value={r.validation_status} /></td>
                      <td>{r.anomaly_reason || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}