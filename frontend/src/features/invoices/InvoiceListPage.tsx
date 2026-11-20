import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { Page, InvoiceDetail, BillingRunView, PropertyOut, RoomOut } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';
import { PageState } from '../../components/PageState';
import { Badge } from '../../components/Badge';
import { formatVnd, formatDateVi, isOverdue, periodEndInclusive } from '../../lib/utils/format';

interface Building { id: string; name: string; property_id: string; }
interface Floor { id: string; floor_number: number; building_id: string; name: string | null; }

function translateBillingRunError(msg: string) {
  if (msg.includes('Select the first day of a closed billing month')) {
    return 'Vui lòng chọn ngày đầu tiên của một tháng đã kết thúc (ví dụ: tháng 10/2026 nếu hôm nay là 11/2026).';
  }
  return msg;
}

export function InvoiceListPage() {
  const [params] = useSearchParams();
  const [data, setData] = useState<Page<InvoiceDetail> | null>(null);
  
  // Filters
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [status, setStatus] = useState('');
  const [billingMonth, setBillingMonth] = useState('');
  const contractId = params.get('contract_id') ?? '';
  
  // Location Filters
  const [properties, setProperties] = useState<PropertyOut[]>([]);
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [floors, setFloors] = useState<Floor[]>([]);
  const [allRooms, setAllRooms] = useState<RoomOut[]>([]);
  const [propertyId, setPropertyId] = useState('');
  const [buildingId, setBuildingId] = useState('');
  const [floorId, setFloorId] = useState('');
  const [roomId, setRoomId] = useState('');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [roomDetails, setRoomDetails] = useState<Record<string, {prop: string, bld: string, flr: string}>>({});

  const [runs, setRuns] = useState<BillingRunView[]>([]);
  const [showRuns, setShowRuns] = useState(false);
  const [newMonth, setNewMonth] = useState('');
  const [creatingRun, setCreatingRun] = useState(false);

   useEffect(() => {
    async function loadMeta() {
      try {
        const propRes = await api.get<Page<PropertyOut>>('/api/v1/properties?page_size=100');
        setProperties(propRes.items);
        const roomRes = await api.get<Page<RoomOut>>('/api/v1/rooms?page_size=100');
        setAllRooms(roomRes.items);

        const detailMap: Record<string, {prop: string, bld: string, flr: string}> = {};
        
        // Tải TẤT CẢ các dãy của TẤT CẢ khu trọ cùng lúc (Song song)
        await Promise.all(propRes.items.map(async (p) => {
          const bRes = await api.get<Page<Building>>(`/api/v1/properties/${p.id}/buildings?page_size=100`);
          
          // Tải TẤT CẢ các tầng của TẤT CẢ dãy cùng lúc
          await Promise.all(bRes.items.map(async (b) => {
            const fRes = await api.get<Page<Floor>>(`/api/v1/buildings/${b.id}/floors?page_size=100`);
            
            for (const f of fRes.items) {
              const roomsInFloor = roomRes.items.filter(r => r.floor_id === f.id);
              for (const r of roomsInFloor) {
                // Cập nhật detailMap với đầy đủ thông tin Khu - Dãy - Tầng (kèm tên nếu có)
                detailMap[r.id] = { 
                  prop: p.name, 
                  bld: b.name, 
                  flr: f.name ? `${f.floor_number} - ${f.name}` : String(f.floor_number) 
                };
              }
            }
          }));
        }));

        setRoomDetails(detailMap);
      } catch (e) { 
        console.error('Lỗi tải danh mục:', e); 
      }
    }
    loadMeta();
  }, []);

  // Load buildings based on property
  useEffect(() => {
    if (!propertyId) { setBuildings([]); setBuildingId(''); return; }
    api.get<Page<Building>>(`/api/v1/properties/${propertyId}/buildings?page_size=100`)
      .then(res => setBuildings(res.items))
      .catch(console.error);
  }, [propertyId]);

  // Load floors based on building
  useEffect(() => {
    if (!buildingId) { setFloors([]); setFloorId(''); return; }
    api.get<Page<Floor>>(`/api/v1/buildings/${buildingId}/floors?page_size=100`)
      .then(res => setFloors(res.items))
      .catch(console.error);
  }, [buildingId]);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const q = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (status) q.set('status', status);
      if (billingMonth) q.set('billing_month', `${billingMonth}-01`);
      if (contractId) q.set('contract_id', contractId);
      const res = await api.get<Page<InvoiceDetail>>(`/api/v1/invoices?${q.toString()}`);
      setData(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được hóa đơn.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, status, billingMonth, contractId]);

  useEffect(() => { load(); }, [load]);

  const loadRuns = useCallback(async () => {
    try {
      const res = await api.get<Page<BillingRunView>>('/api/v1/billing-runs?page_size=20');
      setRuns(res.items);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { if (showRuns) loadRuns(); }, [showRuns, loadRuns]);

  async function createRun(e: React.FormEvent) {
    e.preventDefault();
    if (!newMonth) return;
    setCreatingRun(true);
    try {
      await api.postIdempotent('/api/v1/billing-runs', { billing_month: `${newMonth}-01` });
      setNewMonth('');
      await loadRuns();
      alert('Đã gửi yêu cầu tạo hóa đơn tự động. Vui lòng đợi hệ thống xử lý.');
    } catch (err) {
      const raw = err instanceof ApiError ? err.message : 'Không tạo được tiến trình.';
      alert(translateBillingRunError(raw));
    } finally {
      setCreatingRun(false);
    }
  }

  // Lọc danh sách hóa đơn ở Client-side dựa trên Khu/Dãy/Tầng/Phòng
  const filteredItems = (data?.items ?? []).filter(inv => {
    if (!propertyId && !buildingId && !floorId && !roomId) return true;
    const room = allRooms.find(r => r.id === inv.room_id);
    if (!room) return false;
    
    if (roomId && inv.room_id !== roomId) return false;
    if (propertyId && room.property_id !== propertyId) return false;
    if (floorId && room.floor_id !== floorId) return false;
    if (buildingId) {
      const floor = floors.find(f => f.id === room.floor_id);
      if (floor && floor.building_id !== buildingId) return false;
    }
    return true;
  });

  // Danh sách phòng để hiển thị ở ô Select
  const availableRooms = allRooms.filter(r => {
    if (floorId) return r.floor_id === floorId;
    if (buildingId) {
      const floor = floors.find(f => f.id === r.floor_id);
      return floor?.building_id === buildingId;
    }
    if (propertyId) return r.property_id === propertyId;
    return true;
  });

  return (
    <div className="page-container">
      <style>{`
        @media print {
          .no-print { display: none !important; }
          .data-table { border: none !important; }
          .invoice-print-only { display: block !important; }
          .invoice-print-block { page-break-inside: avoid; border-bottom: 1px solid #000; padding: 20px 0; }
          .invoice-print-block:last-child { border-bottom: none; }
        }
      `}</style>

      <div className="page-header no-print">
        <h1 className="page-title">Quản lý Hóa đơn</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-primary" style={{ background: 'var(--jade)', borderColor: 'var(--jade-2)' }} onClick={() => window.print()}>
            In tất cả hóa đơn (PDF)
          </button>
          <button className="btn-secondary" onClick={() => setShowRuns((v) => !v)}>
            {showRuns ? 'Ẩn lịch sử chạy' : 'Xem lịch sử chạy tự động'}
          </button>
        </div>
      </div>

      {showRuns && (
        <div className="property-card no-print" style={{ marginBottom: 24, padding: 20, border: '1px solid var(--gold-3)' }}>
          <h3 style={{ marginBottom: 16 }}>Chạy lập hóa đơn tự động (Billing Runs)</h3>
          <form onSubmit={createRun} style={{ display: 'flex', gap: 16, alignItems: 'flex-end', marginBottom: 20, flexWrap: 'wrap' }}>
            <div className="login-field" style={{ marginBottom: 0 }}>
              <label>Chọn tháng cần tạo hóa đơn</label>
              <input type="month" value={newMonth} onChange={(e) => setNewMonth(e.target.value)} required />
            </div>
            <button className="btn-primary" type="submit" disabled={creatingRun}>
              {creatingRun ? 'Đang xử lý...' : 'Bắt đầu tạo'}
            </button>
          </form>
          <table className="data-table">
            <thead>
              <tr><th>Tháng</th><th>Hình thức</th><th>Trạng thái</th><th>Đã tạo</th><th>Đang chờ</th><th>Bỏ qua</th><th>Lỗi</th></tr>
            </thead>
            <tbody>
              {runs.length === 0 && <tr><td colSpan={7} className="empty-row">Chưa có lịch sử chạy.</td></tr>}
              {runs.map((r) => (
                <tr key={r.id}>
                  <td>{formatDateVi(r.billing_month)}</td>
                  <td>{r.trigger_type === 'MANUAL' ? 'Thủ công' : 'Tự động'}</td>
                  <td><Badge value={r.status} /></td>
                  <td>{r.issued_count}</td>
                  <td>{r.waiting_count}</td>
                  <td>{r.skipped_count}</td>
                  <td>{r.failed_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="filter-bar no-print" style={{ flexWrap: 'wrap' }}>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">Tất cả trạng thái</option>
          <option value="DRAFT">Nháp</option>
          <option value="ISSUED">Đã phát hành</option>
          <option value="PAID">Đã thanh toán</option>
          <option value="VOID">Đã hủy</option>
        </select>
        <input type="month" value={billingMonth} onChange={(e) => { setBillingMonth(e.target.value); setPage(1); }} placeholder="Lọc theo tháng" />
        
        {/* CÁC BỘ LỌC VỊ TRÍ */}
        <select value={propertyId} onChange={(e) => { 
          setPropertyId(e.target.value); setBuildingId(''); setFloorId(''); setRoomId(''); setPage(1); 
        }}>
          <option value="">Tất cả Khu trọ</option>
          {properties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>

        <select value={buildingId} onChange={(e) => { 
          setBuildingId(e.target.value); setFloorId(''); setRoomId(''); setPage(1); 
        }} disabled={!propertyId}>
          <option value="">Tất cả Dãy</option>
          {buildings.map(b => <option key={b.id} value={b.id}>Dãy {b.name}</option>)}
        </select>

        <select value={floorId} onChange={(e) => { 
  setFloorId(e.target.value); setRoomId(''); setPage(1); 
}} disabled={!buildingId}>
  <option value="">Tất cả Tầng</option>
  {floors.map(f => (
    <option key={f.id} value={f.id}>
      Tầng {f.floor_number}{f.name ? ` - ${f.name}` : ''}
    </option>
  ))}
</select>

        <select value={roomId} onChange={(e) => { setRoomId(e.target.value); setPage(1); }} disabled={!propertyId}>
          <option value="">Tất cả Phòng</option>
          {availableRooms.map(r => <option key={r.id} value={r.id}>{r.room_code}</option>)}
        </select>

        {contractId && <span className="text-muted" style={{ padding: 8 }}>Đang lọc theo hợp đồng: {contractId.slice(0, 8)}…</span>}
      </div>

      <PageState loading={loading} error={error} empty={!loading && !error && filteredItems.length === 0} emptyText="Không có hóa đơn nào." onRetry={load}>
        {/* Bảng hiển thị trên màn hình */}
        <table className="data-table no-print">
          <thead>
            <tr>
              <th>Mã HĐ</th>
              <th>Khu trọ</th>
              <th>Dãy</th>
              <th>Tầng</th>
              <th>Phòng</th>
              <th>Kỳ hạn</th>
              <th>Tổng tiền</th>
              <th>Trạng thái</th>
              <th>Hạn chót</th>
              <th>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((inv) => {
              const roomInfo = roomDetails[inv.room_id];
              return (
                <tr key={inv.id}>
                  <td style={{ fontWeight: 'bold' }}>{inv.invoice_code}</td>
                  <td>{roomInfo?.prop || '—'}</td>
                  <td>{roomInfo?.bld || '—'}</td>
                  <td>{roomInfo?.flr || '—'}</td>
                  <td style={{ fontWeight: 'bold', color: 'var(--cinnabar-2)' }}>{inv.room_code_snapshot}</td>
                  <td>{formatDateVi(inv.period_start)} — {formatDateVi(periodEndInclusive(inv.period_end))}</td>
                  <td className="text-amount">{formatVnd(inv.total_amount)}</td>
                  <td>
                    <Badge value={inv.status} />
                    {isOverdue(inv.status, inv.due_date) && (
                      <span style={{ marginLeft: 8, color: 'var(--cinnabar-3)', fontSize: 12, fontWeight: 'bold' }}>Quá hạn</span>
                    )}
                  </td>
                  <td>{formatDateVi(inv.due_date)}</td>
                  <td>
                    <Link to={`/hoa-don/${inv.id}`} style={{ color: 'var(--gold-2)', fontWeight: 'bold', textDecoration: 'underline' }}>
                      Chi tiết
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Phần in PDF */}
        <div className="invoice-print-only" style={{ display: 'none' }}>
          {filteredItems.map((inv) => {
            const roomInfo = roomDetails[inv.room_id];
            return (
              <div key={inv.id} className="invoice-print-block">
                <div style={{ textAlign: 'center', marginBottom: 12 }}>
                  <h3 style={{ margin: 0 }}>HÓA ĐƠN TIỀN NHÀ</h3>
                  <div style={{ fontStyle: 'italic' }}>Mã: {inv.invoice_code}</div>
                  <div>Kỳ: {formatDateVi(inv.period_start)} — {formatDateVi(periodEndInclusive(inv.period_end))}</div>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <div><strong>Khách thuê:</strong> {inv.tenant_name_snapshot}</div>
                  <div><strong>Phòng:</strong> {inv.room_code_snapshot} {roomInfo ? `(${roomInfo.prop} - ${roomInfo.bld} - Tầng ${roomInfo.flr})` : ''}</div>
                  <div><strong>Email:</strong> {inv.tenant_email_snapshot || '—'}</div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, paddingTop: 6, borderTop: '2px solid #000', fontWeight: 'bold' }}>
                  <span>TỔNG CỘNG</span>
                  <span>{formatVnd(inv.total_amount)}</span>
                </div>
                <div style={{ marginTop: 6, fontSize: 13 }}>Hạn thanh toán: {formatDateVi(inv.due_date)}</div>
              </div>
            );
          })}
        </div>

        <div className="no-print">
          {data && <Pagination page={data.meta.page} pageSize={data.meta.page_size} total={data.meta.total} onPageChange={setPage} />}
        </div>
      </PageState>
    </div>
  );
}