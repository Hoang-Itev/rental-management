import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../lib/api/client';
import type { Page, ContractOut } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';
import { formatDateVi } from '../../lib/utils/format';

export function ContractListPage() {
  const [data, setData] = useState<Page<ContractOut> | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const q = new URLSearchParams({ page: page.toString(), page_size: '10' });
    if (status) q.append('status', status);
    api.get<Page<ContractOut>>(`/api/v1/contracts?${q.toString()}`)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, status]);

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Hợp đồng</h1>
        <Link to="/hop-dong/tao-moi" className="btn-primary" style={{ textDecoration: 'none' }}>Tạo hợp đồng mới</Link>
      </div>

      <div className="filter-bar">
        <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}>
          <option value="">Tất cả trạng thái</option>
          <option value="DRAFT">Nháp (DRAFT)</option>
          <option value="SCHEDULED">Đã lên lịch (SCHEDULED)</option>
          <option value="ACTIVE">Đang hiệu lực (ACTIVE)</option>
          <option value="EXPIRED_PENDING">Chờ bàn giao</option>
          <option value="ENDED">Đã kết thúc</option>
        </select>
      </div>

      {loading ? <div className="loading-text">Đang tải...</div> : (
        <>
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
              {data?.items.map(c => (
                <tr key={c.id}>
                  <td>{c.contract_code}</td>
                  <td>{c.room_code_snapshot}</td>
                  <td>{formatDateVi(c.start_date)}</td>
                  <td>{formatDateVi(c.end_date)}</td>
                  <td><span className="badge">{c.status}</span></td>
                  <td><Link to={`/hop-dong/${c.id}`} style={{ color: 'var(--gold)' }}>Chi tiết</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
          {data && <Pagination page={data.meta.page} pageSize={data.meta.page_size} total={data.meta.total} onPageChange={setPage} />}
        </>
      )}
    </div>
  );
}