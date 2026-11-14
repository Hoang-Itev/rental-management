import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { Page, ContractOut, RoomOut } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';
import { PageState } from '../../components/PageState';
import { Badge } from '../../components/Badge';
import { formatDateVi } from '../../lib/utils/format';

export function ContractListPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<Page<ContractOut> | null>(null);
  const [rooms, setRooms] = useState<RoomOut[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [status, setStatus] = useState('');
  const [roomId, setRoomId] = useState('');
  const [mode, setMode] = useState<'all' | 'expiring'>('all');
  const [withinDays, setWithinDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Page<RoomOut>>('/api/v1/rooms?page_size=100')
      .then((r) => setRooms(r.items))
      .catch(() => setRooms([]));
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      if (mode === 'expiring') {
        const res = await api.get<Page<ContractOut>>(
          `/api/v1/contracts/expiring?within_days=${withinDays}&page=${page}&page_size=${pageSize}`,
        );
        setData(res);
      } else {
        const q = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
        if (status) q.set('status', status);
        if (roomId) q.set('room_id', roomId);
        const res = await api.get<Page<ContractOut>>(`/api/v1/contracts?${q.toString()}`);
        setData(res);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được hợp đồng.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, status, roomId, mode, withinDays]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Hợp đồng</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-secondary" onClick={() => navigate(-1)}>← Quay lại</button>
          <Link to="/hop-dong/tao-moi" className="btn-primary" style={{ textDecoration: 'none' }}>Tạo hợp đồng mới</Link>
        </div>
      </div>

      <div className="filter-bar">
        <select value={mode} onChange={(e) => { setMode(e.target.value as 'all' | 'expiring'); setPage(1); }}>
          <option value="all">Tất cả hợp đồng</option>
          <option value="expiring">Sắp hết hạn</option>
        </select>

        {mode === 'all' ? (
          <>
            <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">Mọi trạng thái</option>
              <option value="DRAFT">Nháp</option>
              <option value="SCHEDULED">Đã lên lịch</option>
              <option value="ACTIVE">Đang hiệu lực</option>
              <option value="EXPIRED_PENDING">Chờ bàn giao</option>
              <option value="ENDED">Đã kết thúc</option>
              <option value="CANCELLED">Đã hủy</option>
            </select>
            <select value={roomId} onChange={(e) => { setRoomId(e.target.value); setPage(1); }}>
              <option value="">Mọi phòng</option>
              {rooms.map((r) => <option key={r.id} value={r.id}>{r.room_code}</option>)}
            </select>
          </>
        ) : (
          <select value={withinDays} onChange={(e) => { setWithinDays(Number(e.target.value)); setPage(1); }}>
            <option value={7}>Trong 7 ngày</option>
            <option value={14}>Trong 14 ngày</option>
            <option value={30}>Trong 30 ngày</option>
            <option value={90}>Trong 90 ngày</option>
          </select>
        )}
      </div>

      <PageState loading={loading} error={error} empty={!loading && !error && (data?.items.length ?? 0) === 0} emptyText="Không có hợp đồng." onRetry={load}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Mã HĐ</th>
              <th>Phòng</th>
              <th>Bắt đầu</th>
              <th>Kết thúc</th>
              <th>Trạng thái</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((c) => (
              <tr key={c.id}>
                <td>{c.contract_code}</td>
                <td>{c.room_code_snapshot}</td>
                <td>{formatDateVi(c.start_date)}</td>
                <td>{formatDateVi(c.end_date)}</td>
                <td><Badge value={c.status} /></td>
                <td><Link to={`/hop-dong/${c.id}`}>Chi tiết</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && <Pagination page={data.meta.page} pageSize={data.meta.page_size} total={data.meta.total} onPageChange={setPage} />}
      </PageState>
    </div>
  );
}