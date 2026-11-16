import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type {
  Page, RoomOut, MeterOut, RoomMeterList, CutoffOut, MeterAlertOut, ReadingOut, PropertyOut
} from '../../lib/api/types';
import { formatDateTimeVi } from '../../lib/utils/format';
import { PageState } from '../../components/PageState';
import { Badge } from '../../components/Badge';
import { Pagination } from '../../components/Pagination';

type Tab = 'room' | 'cutoffs' | 'bulk' | 'alerts';

interface Building { id: string; name: string; property_id: string; }
interface Floor { id: string; floor_number: number; building_id: string; name: string | null; }

function formatMeterValue(val: string | number | null | undefined) {
  if (val === null || val === undefined) return '—';
  const str = String(val);
  if (str.endsWith('.000')) return str.slice(0, -4);
  return str; 
}

function getCutoffTypeLabel(type: string) {
  if (type === 'CONTRACT_START') return 'Bắt đầu HĐ';
  if (type === 'CONTRACT_END') return 'Kết thúc HĐ';
  if (type === 'MONTHLY') return 'Chốt tháng';
  return type;
}

function translateAlertType(type: string) {
  switch (type) {
    case 'OFFLINE': return 'Mất kết nối';
    case 'READING_DECREASE': return 'Số bị giảm';
    case 'LATE_AFTER_CUTOFF': return 'Số về muộn';
    case 'CONFLICTING_DUPLICATE': return 'Dữ liệu trùng lặp';
    default: return type;
  }
}

function translateError(msg: string) {
  if (msg.includes('Manual reading is below previous confirmed cutoff')) {
    return 'Số bạn nhập nhỏ hơn số của mốc chốt trước đó.';
  }
  if (msg.includes('Manual reading exceeds next confirmed cutoff')) {
    return 'Số bạn nhập lớn hơn số của mốc chốt tiếp theo.';
  }
  if (msg.includes('A manual reason of at least 8 characters is required')) {
    return 'Lý do phải có ít nhất 8 ký tự.';
  }
  if (msg.includes('Only PENDING cutoffs can be confirmed')) {
    return 'Chỉ có thể chốt những mốc đang ở trạng thái Chờ xử lý.';
  }
  if (msg.includes('Future cutoff cannot be confirmed')) {
    return 'Không thể chốt số cho mốc ở tương lai.';
  }
  return msg;
}

export function MeterListPage() {
  const [tab, setTab] = useState<Tab>('cutoffs');
  
  const [properties, setProperties] = useState<PropertyOut[]>([]);
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [floors, setFloors] = useState<Floor[]>([]);
  const [allRooms, setAllRooms] = useState<RoomOut[]>([]);
  
  const [roomDetails, setRoomDetails] = useState<Record<string, {prop: string, bld: string, flr: string, code: string}>>({});
  const [meterMap, setMeterMap] = useState<Record<string, {prop: string, bld: string, flr: string, code: string, type: string}>>({});

  const [filterPropId, setFilterPropId] = useState('');
  const [filterBldId, setFilterBldId] = useState('');
  const [filterFlrId, setFilterFlrId] = useState('');
  const [selectedRoom, setSelectedRoom] = useState('');

  const [pendingType, setPendingType] = useState<'ALL' | 'ELECTRICITY' | 'WATER'>('ALL');
  const [pendingPage, setPendingPage] = useState(1);
  const [pendingTotal, setPendingTotal] = useState(0);

  const [meters, setMeters] = useState<MeterOut[]>([]);
  const [cutoffs, setCutoffs] = useState<CutoffOut[]>([]);
  const [loadingMeters, setLoadingMeters] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [readingsFor, setReadingsFor] = useState<MeterOut | null>(null);
  const [readings, setReadings] = useState<ReadingOut[]>([]);
  const [readingsLoading, setReadingsLoading] = useState(false);
  const [readingsError, setReadingsError] = useState<string | null>(null);

  const [activeCutoff, setActiveCutoff] = useState<CutoffOut | null>(null);
  const [manualValue, setManualValue] = useState('');
  const [manualReason, setManualReason] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null); 

  const [pendingCutoffs, setPendingCutoffs] = useState<CutoffOut[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);

  const [alerts, setAlerts] = useState<MeterAlertOut[]>([]);
  const [alertsTotal, setAlertsTotal] = useState(0);
  const [alertsPage, setAlertsPage] = useState(1);
  const [alertsStatus, setAlertsStatus] = useState<'OPEN' | 'RESOLVED' | ''>('OPEN');
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [resolving, setResolving] = useState<string | null>(null);
  const [resolveTarget, setResolveTarget] = useState<MeterAlertOut | null>(null);
  const [resolveNote, setResolveNote] = useState('');

  const [bulkRows, setBulkRows] = useState<any[]>([]);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkSaving, setBulkSaving] = useState(false);

  useEffect(() => {
    async function loadMeta() {
      try {
        const propRes = await api.get<Page<PropertyOut>>('/api/v1/properties?page_size=100');
        setProperties(propRes.items);
        
        const roomRes = await api.get<Page<RoomOut>>('/api/v1/rooms?page_size=100');
        setAllRooms(roomRes.items);

        const detailMap: Record<string, {prop: string, bld: string, flr: string, code: string}> = {};
        const mMap: Record<string, {prop: string, bld: string, flr: string, code: string, type: string}> = {};

        for (const p of propRes.items) {
          const bRes = await api.get<Page<Building>>(`/api/v1/properties/${p.id}/buildings?page_size=100`);
          for (const b of bRes.items) {
            const fRes = await api.get<Page<Floor>>(`/api/v1/buildings/${b.id}/floors?page_size=100`);
            for (const f of fRes.items) {
              const roomsInFloor = roomRes.items.filter(r => r.floor_id === f.id);
              for (const r of roomsInFloor) {
                const info = { prop: p.name, bld: b.name, flr: String(f.floor_number), code: r.room_code };
                detailMap[r.id] = info;
                
                try {
                  const m = await api.get<RoomMeterList>(`/api/v1/rooms/${r.id}/meters`);
                  m.items.forEach(meter => { 
                    mMap[meter.id] = { ...info, type: meter.meter_type }; 
                  });
                } catch {}
              }
            }
          }
        }
        setRoomDetails(detailMap);
        setMeterMap(mMap);
      } catch (e) { console.error(e); }
    }
    loadMeta();
  }, []);

  useEffect(() => {
    if (!filterPropId) { setBuildings([]); setFilterBldId(''); return; }
    api.get<Page<Building>>(`/api/v1/properties/${filterPropId}/buildings?page_size=100`)
      .then(res => setBuildings(res.items))
      .catch(console.error);
  }, [filterPropId]);

  useEffect(() => {
    if (!filterBldId) { setFloors([]); setFilterFlrId(''); return; }
    api.get<Page<Floor>>(`/api/v1/buildings/${filterBldId}/floors?page_size=100`)
      .then(res => setFloors(res.items))
      .catch(console.error);
  }, [filterBldId]);

  const filteredRooms = allRooms.filter(r => {
    if (filterFlrId) return r.floor_id === filterFlrId;
    if (filterPropId) return r.property_id === filterPropId;
    return true;
  });

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
    } finally { setLoadingMeters(false); }
  }, [selectedRoom]);

  useEffect(() => { loadRoomData(); }, [loadRoomData]);

  const loadPending = useCallback(async () => {
    setPendingLoading(true); setError(null);
    try {
      let url = `/api/v1/meter-cutoffs?status=PENDING&page=${pendingPage}&page_size=10`;
      const res = await api.get<Page<CutoffOut>>(url);
      
      let items = res.items;
      if (pendingType !== 'ALL') {
        items = items.filter(c => meterMap[c.meter_id]?.type === pendingType);
      }
      
      setPendingCutoffs(items);
      setPendingTotal(res.meta.total);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được danh sách.');
    } finally { setPendingLoading(false); }
  }, [pendingPage, pendingType, meterMap]);

  const loadAlerts = useCallback(async () => {
    setAlertsLoading(true); setError(null);
    try {
      let url = `/api/v1/meter-alerts?page=${alertsPage}&page_size=20`;
      if (alertsStatus) url += `&status=${alertsStatus}`;
      const res = await api.get<Page<MeterAlertOut>>(url);
      setAlerts(res.items);
      setAlertsTotal(res.meta.total);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được cảnh báo.');
    } finally { setAlertsLoading(false); }
  }, [alertsPage, alertsStatus]);

  useEffect(() => {
    if (tab === 'cutoffs') loadPending();
    if (tab === 'alerts') loadAlerts();
  }, [tab, loadPending, loadAlerts]);

  async function openReadings(m: MeterOut) {
    setReadingsFor(m); 
    setReadings([]); 
    setReadingsError(null);
    setReadingsLoading(true);
    try {
      const res = await api.get<Page<ReadingOut>>(`/api/v1/meters/${m.id}/readings?page_size=50`);
      setReadings(res.items);
    } catch (e) { 
      if (e instanceof ApiError && e.status === 404) {
        setReadingsError('Không tìm thấy dữ liệu đồng hồ này.');
      } else {
        setReadingsError('Lỗi tải chỉ số.');
      }
    }
    finally { setReadingsLoading(false); }
  }

  async function submitConfirmCutoff(e: React.FormEvent) {
    e.preventDefault();
    if (!activeCutoff) return;
    setModalError(null); 
    
    if (manualReason.trim().length < 8) { 
      setModalError('Lỗi: Lý do phải có ít nhất 8 ký tự.'); 
      return; 
    }
    
    setConfirming(true);
    try {
      await api.post(`/api/v1/meter-cutoffs/${activeCutoff.id}/confirm`, {
        reading_value: manualValue,
        manual_reason: manualReason.trim(),
      });
      setActiveCutoff(null); setManualValue(''); setManualReason('');
      await loadRoomData();
      if (tab === 'cutoffs') await loadPending();
      alert('Chốt số thành công!');
    } catch (err: any) {
      let msg = 'Lỗi khi xác nhận.';
      if (err instanceof ApiError) {
         if (typeof err.body?.detail === 'string') msg = err.body.detail;
         else if (err.message) msg = err.message;
      }
      setModalError(`Lỗi: ${translateError(msg)}`);
    } finally { setConfirming(false); }
  }

  async function executeResolve() {
    if (!resolveTarget) return;
    if (resolveNote.trim().length < 8) { setError('Ghi chú phải có ít nhất 8 ký tự.'); return; }
    setResolving(resolveTarget.id); setError(null);
    try {
      await api.post(`/api/v1/meter-alerts/${resolveTarget.id}/resolve`, { resolution_note: resolveNote.trim() });
      setResolveTarget(null); setResolveNote(''); await loadAlerts();
    } catch (err) { setError(err instanceof ApiError ? err.message : 'Lỗi xử lý cảnh báo.'); }
    finally { setResolving(null); }
  }

  async function loadBulkRows() {
    setBulkLoading(true); setError(null);
    try {
      const contracts = await api.get<any>('/api/v1/contracts?status=ACTIVE&page_size=100');
      const rows = [];
      for (const c of contracts.items) {
        const meters = await api.get<any>(`/api/v1/rooms/${c.room_id}/meters`);
        const elec = meters.items.find((m: any) => m.meter_type === 'ELECTRICITY');
        const water = meters.items.find((m: any) => m.meter_type === 'WATER');
        const info = roomDetails[c.room_id];
        
        rows.push({
          contract_id: c.id,
          room_code: info ? info.code : c.room_code_snapshot,
          property_name: info ? info.prop : '—',
          building_name: info ? info.bld : '—',
          floor_name: info ? info.flr : '—',
          elec_meter_id: elec?.id,
          water_meter_id: water?.id,
          elec_val: '',
          water_val: '',
        });
      }
      setBulkRows(rows);
    } catch (e) { setError(e instanceof ApiError ? e.message : 'Lỗi tải dữ liệu.'); }
    finally { setBulkLoading(false); }
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
             await api.post(`/api/v1/meter-cutoffs/${elecCutoffs.items[0].id}/confirm`, { reading_value: Number(r.elec_val), manual_reason: 'Ghi số hàng loạt' });
          }
        }
        if (r.water_val) {
          const waterCutoffs = await api.get<any>(`/api/v1/meter-cutoffs?meter_id=${r.water_meter_id}&status=PENDING&page_size=1`);
          if (waterCutoffs.items.length > 0) {
             await api.post(`/api/v1/meter-cutoffs/${waterCutoffs.items[0].id}/confirm`, { reading_value: Number(r.water_val), manual_reason: 'Ghi số hàng loạt' });
          }
        }
      }
      alert('Đã lưu thành công!');
      setBulkRows([]);
    } catch (e: any) { setError('Lỗi: ' + (e.message || 'Không thể lưu.')); }
    finally { setBulkSaving(false); }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Đồng hồ điện nước</h1>
      </div>

      <div className="filter-bar" style={{ marginBottom: 12 }}>
        <button className={`btn-secondary ${tab === 'cutoffs' ? 'primary' : ''}`} onClick={() => setTab('cutoffs')}>Chốt số chờ xử lý</button>
        <button className={`btn-secondary ${tab === 'bulk' ? 'primary' : ''}`} onClick={() => { setTab('bulk'); if (bulkRows.length === 0) loadBulkRows(); }}>Ghi số hàng loạt</button>
        <button className={`btn-secondary ${tab === 'room' ? 'primary' : ''}`} onClick={() => setTab('room')}>Tra cứu theo phòng</button>
        <button className={`btn-secondary ${tab === 'alerts' ? 'primary' : ''}`} onClick={() => setTab('alerts')}>Cảnh báo</button>
      </div>

      <div style={{ padding: '12px 16px', background: 'rgba(212, 163, 64, 0.05)', borderLeft: '4px solid var(--gold-3)', marginBottom: 24, fontSize: 14, color: 'var(--ink-soft)' }}>
        {tab === 'cutoffs' && <span><strong>Hộp thư đến:</strong> Hệ thống tự động tạo các mốc chốt. Bạn thấy phòng nào ở đây nghĩa là cần nhập số cho phòng đó.</span>}
        {tab === 'bulk' && <span><strong>Ghi số nhanh:</strong> Dùng vào ngày 1 hàng tháng. Nhập số cho tất cả các phòng đang thuê cùng 1 lúc rồi bấm Lưu.</span>}
        {tab === 'room' && <span><strong>Tra cứu:</strong> Lọc theo Khu/Dãy/Tầng để chọn phòng, xem lịch sử tất cả các mốc chốt số của phòng đó.</span>}
        {tab === 'alerts' && <span><strong>Cảnh báo:</strong> Xem các lỗi bất thường (mất tín hiệu, số bị giảm). Bấm "Xử lý" để đánh dấu đã kiểm tra.</span>}
      </div>

      {error && <div className="login-error">{error}</div>}

      {tab === 'cutoffs' && (
        <>
          <div className="filter-bar">
            <select value={pendingType} onChange={e => { setPendingType(e.target.value as any); setPendingPage(1); }}>
              <option value="ALL">Tất cả đồng hồ (Điện & Nước)</option>
              <option value="ELECTRICITY">Chỉ hiện Điện</option>
              <option value="WATER">Chỉ hiện Nước</option>
            </select>
          </div>

          <PageState loading={pendingLoading} error={null} empty={!pendingLoading && pendingCutoffs.length === 0} emptyText="Tuyệt vời! Không có phòng nào đang chờ chốt số." onRetry={loadPending}>
            <table className="data-table">
              <thead>
                <tr><th>Khu trọ</th><th>Dãy</th><th>Tầng</th><th>Mã phòng</th><th>Đồng hồ</th><th>Loại mốc</th><th>Thời điểm chốt</th><th></th></tr>
              </thead>
              <tbody>
                {pendingCutoffs.map((c) => {
                  const info = meterMap[c.meter_id];
                  const isElec = info?.type === 'ELECTRICITY';
                  return (
                    <tr key={c.id}>
                      <td>{info?.prop || '—'}</td>
                      <td>{info?.bld || '—'}</td>
                      <td>{info?.flr || '—'}</td>
                      <td style={{ fontWeight: 'bold', color: 'var(--cinnabar-2)' }}>{info?.code || c.meter_id.slice(0,8)}</td>
                      <td style={{ color: isElec ? 'var(--amber)' : 'var(--jade-hi)', fontWeight: 'bold' }}>
                        {isElec ? 'Điện' : 'Nước'}
                      </td>
                      <td>{getCutoffTypeLabel(c.cutoff_type)}</td>
                      <td>{formatDateTimeVi(c.cutoff_at)}</td>
                      <td>
                        <button className="btn-secondary" onClick={() => setActiveCutoff(c)}>
                          Chốt {isElec ? 'Điện' : 'Nước'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {pendingTotal > 0 && <Pagination page={pendingPage} pageSize={10} total={pendingTotal} onPageChange={setPendingPage} />}
          </PageState>
        </>
      )}

      {tab === 'room' && (
        <>
          <div className="filter-bar" style={{ background: 'var(--night-1)', padding: 16, borderRadius: 4, border: '1px solid var(--gold-3)' }}>
            <select value={filterPropId} onChange={(e) => { 
              setFilterPropId(e.target.value); setFilterBldId(''); setFilterFlrId(''); setSelectedRoom(''); 
            }}>
              <option value="">— Tất cả Khu trọ —</option>
              {properties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>

            <select value={filterBldId} onChange={(e) => { 
              setFilterBldId(e.target.value); setFilterFlrId(''); setSelectedRoom(''); 
            }} disabled={!filterPropId}>
              <option value="">— Tất cả Dãy —</option>
              {buildings.map(b => <option key={b.id} value={b.id}>Dãy {b.name}</option>)}
            </select>

            <select value={filterFlrId} onChange={(e) => { 
              setFilterFlrId(e.target.value); setSelectedRoom(''); 
            }} disabled={!filterBldId}>
              <option value="">— Tất cả Tầng —</option>
              {floors.map(f => <option key={f.id} value={f.id}>Tầng {f.floor_number}</option>)}
            </select>

            <select value={selectedRoom} onChange={(e) => setSelectedRoom(e.target.value)} disabled={!filterPropId}>
              <option value="">— Chọn phòng để xem —</option>
              {filteredRooms.map((r) => <option key={r.id} value={r.id}>{r.room_code}</option>)}
            </select>
          </div>

          <PageState loading={loadingMeters} error={null} empty={!loadingMeters && !!selectedRoom && meters.length === 0} emptyText="Phòng này chưa có đồng hồ.">
            <div className="property-grid">
              {meters.map((m) => (
                <div key={m.id} className="property-card">
                  <h3>{m.meter_type === 'ELECTRICITY' ? 'Điện' : 'Nước'}</h3>
                  <p>Mã: {m.meter_code}</p>
                  <Badge value={m.status} />
                  <div style={{ marginTop: 12 }}>
                    <button className="btn-secondary" onClick={() => openReadings(m)}>Xem chỉ số (IoT)</button>
                  </div>
                </div>
              ))}
            </div>

            <h3 style={{ marginTop: 28 }}>Các mốc chốt số (Tay)</h3>
            <table className="data-table">
              <thead>
                <tr><th>Đồng hồ</th><th>Loại mốc</th><th>Thời điểm</th><th>Chỉ số</th><th>Trạng thái</th><th>Ghi chú / Lý do</th><th></th></tr>
              </thead>
              <tbody>
                {cutoffs.length === 0 && <tr><td colSpan={7} className="empty-row">Chưa có mốc chốt số nào.</td></tr>}
                {cutoffs.map((c) => {
                  const info = meterMap[c.meter_id];
                  const isElec = info?.type === 'ELECTRICITY';
                  return (
                    <tr key={c.id}>
                      <td style={{ color: isElec ? 'var(--amber)' : 'var(--jade-hi)', fontWeight: 'bold' }}>
                        {isElec ? 'Điện' : 'Nước'}
                      </td>
                      <td>{getCutoffTypeLabel(c.cutoff_type)}</td>
                      <td>{formatDateTimeVi(c.cutoff_at)}</td>
                      <td style={{ fontWeight: 'bold', color: 'var(--cinnabar-2)' }}>
                        {formatMeterValue(c.reading_value)}
                      </td>
                      <td><Badge value={c.status} /></td>
                      <td style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{c.manual_reason || '—'}</td>
                      <td>
                        {c.status === 'PENDING' && (
                          <button className="btn-secondary" onClick={() => setActiveCutoff(c)}>
                            Chốt {isElec ? 'Điện' : 'Nước'}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </PageState>
        </>
      )}

      {tab === 'bulk' && (
        <div>
          <PageState loading={bulkLoading} error={null} empty={!bulkLoading && bulkRows.length === 0} emptyText="Không có phòng nào đang thuê để ghi số." onRetry={loadBulkRows}>
            <div style={{ background: 'var(--night-1)', padding: 16, borderRadius: 4, border: '1px solid var(--gold-3)' }}>
              <table className="data-table">
                <thead>
                  <tr><th>Khu trọ</th><th>Dãy</th><th>Tầng</th><th>Phòng</th><th>Số điện mới (kWh)</th><th>Số nước mới (m³)</th></tr>
                </thead>
                <tbody>
                  {bulkRows.map((r, i) => (
                    <tr key={i}>
                      <td>{r.property_name}</td>
                      <td>{r.building_name}</td>
                      <td>{r.floor_name}</td>
                      <td style={{ fontWeight: 'bold', color: 'var(--cinnabar-2)' }}>{r.room_code}</td>
                      <td><input type="number" step="0.01" value={r.elec_val} onChange={e => { const n=[...bulkRows]; n[i].elec_val = e.target.value; setBulkRows(n); }} placeholder="Nhập..." style={{ width: '100%', padding: 6 }} /></td>
                      <td><input type="number" step="0.01" value={r.water_val} onChange={e => { const n=[...bulkRows]; n[i].water_val = e.target.value; setBulkRows(n); }} placeholder="Nhập..." style={{ width: '100%', padding: 6 }} /></td>
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

          <PageState loading={alertsLoading} error={null} empty={!alertsLoading && alerts.length === 0} emptyText="Không có cảnh báo nào." onRetry={loadAlerts}>
            <table className="data-table">
              <thead>
                <tr><th>Khu trọ</th><th>Dãy</th><th>Tầng</th><th>Mã phòng</th><th>Đồng hồ</th><th>Loại</th><th>Chi tiết</th><th>Thao tác</th></tr>
              </thead>
              <tbody>
                {alerts.map((a) => {
                  const info = meterMap[a.meter_id];
                  const isElec = info?.type === 'ELECTRICITY';
                  return (
                    <tr key={a.id}>
                      <td>{info?.prop || '—'}</td>
                      <td>{info?.bld || '—'}</td>
                      <td>{info?.flr || '—'}</td>
                      <td style={{ fontWeight: 'bold', color: 'var(--cinnabar-2)' }}>{info?.code || a.meter_id.slice(0,8)}</td>
                      <td style={{ color: isElec ? 'var(--amber)' : 'var(--jade-hi)', fontWeight: 'bold' }}>
                        {isElec ? 'Điện' : 'Nước'}
                      </td>
                      <td><span style={{ color: a.alert_type === 'OFFLINE' ? 'var(--cinnabar-3)' : 'var(--amber)', fontWeight: 600 }}>{translateAlertType(a.alert_type)}</span></td>
                      <td style={{ fontSize: 13, maxWidth: 300 }}>
                        {a.status === 'RESOLVED' && a.resolution_note ? (
                          <span style={{ color: 'var(--jade-2)', fontStyle: 'italic' }}>Ghi chú: {a.resolution_note}</span>
                        ) : `Mất tín hiệu...`}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 6 }}>
                          {a.status === 'OPEN' && (
                            <button className="btn-primary" style={{ padding: '4px 12px' }} onClick={() => { setResolveTarget(a); setResolveNote(''); }}>Xử lý</button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {alertsTotal > 0 && <Pagination page={alertsPage} pageSize={20} total={alertsTotal} onPageChange={setAlertsPage} />}
          </PageState>
        </>
      )}

      {resolveTarget && (
        <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && setResolveTarget(null)}>
          <div className="room-modal" style={{ width: 460 }}>
            <button className="modal-close" onClick={() => setResolveTarget(null)}>×</button>
            <h2 className="modal-title">Đã kiểm tra cảnh báo</h2>
            <div className="login-field">
              <label>Ghi chú xử lý (≥ 8 ký tự) *</label>
              <textarea rows={3} value={resolveNote} onChange={(e) => setResolveNote(e.target.value)} required />
            </div>
            <div className="modal-actions">
              <button className="modal-btn" onClick={() => setResolveTarget(null)}>Hủy</button>
              <button className="modal-btn primary" onClick={executeResolve} disabled={resolving === resolveTarget.id}>
                {resolving === resolveTarget.id ? 'Đang lưu...' : 'Xác nhận'}
              </button>
            </div>
          </div>
        </div>
      )}

      {activeCutoff && (
        <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && setActiveCutoff(null)}>
          <div className="room-modal" style={{ width: 420 }}>
            <button className="modal-close" onClick={() => setActiveCutoff(null)}>×</button>
            
            <h2 className="modal-title">
              Chốt số {meterMap[activeCutoff.meter_id]?.type === 'ELECTRICITY' ? 'Điện' : 'Nước'}
            </h2>
            
            <p className="text-muted">{getCutoffTypeLabel(activeCutoff.cutoff_type)} — {formatDateTimeVi(activeCutoff.cutoff_at)}</p>
            
            <div style={{ background: 'rgba(197, 46, 26, 0.1)', padding: 10, borderRadius: 4, marginBottom: 16, fontSize: 13, color: 'var(--cinnabar-2)', border: '1px solid var(--cinnabar-3)' }}>
              <strong>Lưu ý:</strong> Nhập số <b>tổng cộng dồn</b> trên mặt đồng hồ. Số này <b>không được nhỏ hơn</b> số của lần chốt trước đó.
            </div>

            <form onSubmit={submitConfirmCutoff}>
              <div className="login-field">
                <label>Chỉ số tích lũy thực tế ({meterMap[activeCutoff.meter_id]?.type === 'ELECTRICITY' ? 'kWh' : 'm³'}) *</label>
                <input type="number" step="0.001" min="0" value={manualValue} onChange={(e) => setManualValue(e.target.value)} required />
              </div>
              <div className="login-field">
                <label>Lý do (≥ 8 ký tự) *</label>
                <input value={manualReason} onChange={(e) => setManualReason(e.target.value)} placeholder="VD: Chốt số theo hình ảnh chụp..." required />
              </div>
              
              {modalError && <div className="login-error" style={{ marginBottom: 16 }}>{modalError}</div>}

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
            <h2 className="modal-title">Lịch sử đo tự động (IoT) — {readingsFor.meter_code}</h2>
            {readingsLoading ? (
              <div className="loading-text">Đang tải…</div>
            ) : readingsError ? (
              <div className="login-error">{readingsError}</div>
            ) : readings.length === 0 ? (
              <div className="empty-row">Chưa có dữ liệu từ cảm biến.</div>
            ) : (
              <table className="data-table">
                <thead><tr><th>Đo lúc</th><th>Giá trị</th><th>Trạng thái</th><th>Ghi chú</th></tr></thead>
                <tbody>
                  {readings.map((r, i) => (
                    <tr key={i}>
                      <td>{formatDateTimeVi(r.measured_at)}</td>
                      <td style={{ fontWeight: 'bold', color: 'var(--cinnabar-2)' }}>{formatMeterValue(r.reading_value)}</td>
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