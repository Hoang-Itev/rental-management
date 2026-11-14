import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type {
  Page, RoomOut, MeterOut, RoomMeterList, CutoffOut, MeterAlertOut, ReadingOut,
} from '../../lib/api/types';
import { formatDateTimeVi } from '../../lib/utils/format';
import { PageState } from '../../components/PageState';
import { Badge } from '../../components/Badge';

type Tab = 'room' | 'cutoffs' | 'alerts';

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

  // Alerts
  const [alerts, setAlerts] = useState<MeterAlertOut[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [resolving, setResolving] = useState<string | null>(null);

  useEffect(() => {
    api.get<Page<RoomOut>>('/api/v1/rooms?page_size=100')
      .then((r) => setRooms(r.items))
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
      setError(e instanceof ApiError ? e.message : 'Không tải được cutoff PENDING.');
    } finally {
      setPendingLoading(false);
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    setAlertsLoading(true); setError(null);
    try {
      const res = await api.get<Page<MeterAlertOut>>('/api/v1/meter-alerts?status=OPEN&page_size=100');
      setAlerts(res.items);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được cảnh báo.');
    } finally {
      setAlertsLoading(false);
    }
  }, []);

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

  async function resolveAlert(a: MeterAlertOut) {
    const note = prompt('Ghi chú xử lý (ít nhất 8 ký tự):');
    if (!note || note.trim().length < 8) { setError('Ghi chú phải ≥ 8 ký tự.'); return; }
    setResolving(a.id);
    try {
      await api.post(`/api/v1/meter-alerts/${a.id}/resolve`, { resolution_note: note.trim() });
      await loadAlerts();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Không thể xử lý cảnh báo.');
    } finally {
      setResolving(null);
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
        <button className={`btn-secondary ${tab === 'alerts' ? 'primary' : ''}`} onClick={() => setTab('alerts')}>Cảnh báo mở</button>
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
                {cutoffs.length === 0 && <tr><td colSpan={5} className="empty-row">Chưa có cutoff.</td></tr>}
                {cutoffs.map((c) => (
                  <tr key={c.id}>
                    <td>{c.cutoff_type}</td>
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
          emptyText="Không có cutoff PENDING."
          onRetry={loadPending}
        >
          <table className="data-table">
            <thead>
              <tr><th>Meter ID</th><th>Loại</th><th>Thời điểm</th><th></th></tr>
            </thead>
            <tbody>
              {pendingCutoffs.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontSize: 12 }}>{c.meter_id}</td>
                  <td>{c.cutoff_type}</td>
                  <td>{formatDateTimeVi(c.cutoff_at)}</td>
                  <td><button className="btn-secondary" onClick={() => setActiveCutoff(c)}>Chốt số</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </PageState>
      )}

      {tab === 'alerts' && (
        <PageState
          loading={alertsLoading}
          error={null}
          empty={!alertsLoading && alerts.length === 0}
          emptyText="Không có cảnh báo mở."
          onRetry={loadAlerts}
        >
          <table className="data-table">
            <thead>
              <tr><th>Loại</th><th>Meter ID</th><th>Phát hiện</th><th>Chi tiết</th><th></th></tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.id}>
                  <td>{a.alert_type}</td>
                  <td style={{ fontSize: 12 }}>{a.meter_id}</td>
                  <td>{formatDateTimeVi(a.detected_at)}</td>
                  <td style={{ fontSize: 12 }}><code>{JSON.stringify(a.detail)}</code></td>
                  <td>
                    <button className="btn-secondary" disabled={resolving === a.id} onClick={() => resolveAlert(a)}>
                      {resolving === a.id ? 'Đang xử lý…' : 'Xử lý'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </PageState>
      )}

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