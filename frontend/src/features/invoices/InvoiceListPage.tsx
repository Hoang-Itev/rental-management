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

export function InvoiceListPage() {
  const [params] = useSearchParams();
  const [data, setData] = useState<Page<InvoiceDetail> | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [status, setStatus] = useState('');
  const [billingMonth, setBillingMonth] = useState('');
  const contractId = params.get('contract_id') ?? '';
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [properties, setProperties] = useState<PropertyOut[]>([]);
  const [allRooms, setAllRooms] = useState<RoomOut[]>([]);
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
        for (const p of propRes.items) {
          const bRes = await api.get<Page<Building>>(`/api/v1/properties/${p.id}/buildings?page_size=100`);
          for (const b of bRes.items) {
            const fRes = await api.get<Page<Floor>>(`/api/v1/buildings/${b.id}/floors?page_size=100`);
            for (const f of fRes.items) {
              const roomsInFloor = roomRes.items.filter(r => r.floor_id === f.id);
              for (const r of roomsInFloor) {
                detailMap[r.id] = { prop: p.name, bld: b.name, flr: String(f.floor_number) };
              }
            }
          }
        }
        setRoomDetails(detailMap);
      } catch (e) { console.error(e); }
    }
    loadMeta();
  }, []);

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
      alert(err instanceof ApiError ? err.message : 'Không tạo được tiến trình.');
    } finally {
      setCreatingRun(false);
    }
  }

  return (
    <div className="page-container">
      <style>{`
        @media print {
          .no-print { display: none !important; }
          .data-table { border: none !important; }
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

      <div className="filter-bar no-print">
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">Tất cả trạng thái</option>
          <option value="DRAFT">Nháp</option>
          <option value="ISSUED">Đã phát hành</option>
          <option value="PAID">Đã thanh toán</option>
          <option value="VOID">Đã hủy</option>
        </select>
        <input type="month" value={billingMonth} onChange={(e) => { setBillingMonth(e.target.value); setPage(1); }} placeholder="Lọc theo tháng" />
        {contractId && <span className="text-muted" style={{ padding: 8 }}>Đang lọc theo hợp đồng: {contractId.slice(0, 8)}…</span>}
      </div>

      <PageState loading={loading} error={error} empty={!loading && !error && (data?.items.length ?? 0) === 0} emptyText="Không có hóa đơn nào." onRetry={load}>
        <table className="data-table">
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
              <th className="no-print">Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((inv) => {
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
                  <td className="no-print">
                    <Link to={`/hoa-don/${inv.id}`} style={{ color: 'var(--gold-2)', fontWeight: 'bold', textDecoration: 'underline' }}>
                      Chi tiết
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="no-print">
          {data && <Pagination page={data.meta.page} pageSize={data.meta.page_size} total={data.meta.total} onPageChange={setPage} />}
        </div>
      </PageState>
    </div>
  );
}