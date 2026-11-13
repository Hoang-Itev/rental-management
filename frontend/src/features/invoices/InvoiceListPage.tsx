import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../lib/api/client';
import type { Page, InvoiceDetail } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';
import { formatVnd, formatDateVi } from '../../lib/utils/format';

export function InvoiceListPage() {
  const [data, setData] = useState<Page<InvoiceDetail> | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const q = new URLSearchParams({ page: page.toString(), page_size: '10' });
    if (status) q.append('status', status);
    api.get<Page<InvoiceDetail>>(`/api/v1/invoices?${q.toString()}`)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, status]);

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Quản lý Hóa đơn</h1>
      </div>

      <div className="filter-bar">
        <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}>
          <option value="">Tất cả trạng thái</option>
          <option value="DRAFT">Nháp (DRAFT)</option>
          <option value="ISSUED">Đã phát hành (ISSUED)</option>
          <option value="PAID">Đã thanh toán (PAID)</option>
          <option value="VOID">Đã hủy (VOID)</option>
        </select>
      </div>

      {loading ? <div className="loading-text">Đang tải...</div> : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Mã HĐ</th>
                <th>Phòng</th>
                <th>Kỳ</th>
                <th>Tổng tiền</th>
                <th>Trạng thái</th>
                <th>Hạn</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map(inv => (
                <tr key={inv.id}>
                  <td>{inv.invoice_code}</td>
                  <td>{inv.room_code_snapshot}</td>
                  <td>{formatDateVi(inv.period_start)} - {formatDateVi(inv.period_end)}</td>
                  {/* Đã xóa inline style, thay bằng class */}
                  <td style={{ fontWeight: 600 }} className="text-amount">{formatVnd(inv.total_amount)}</td>
                  <td>
                    <span className={`badge ${inv.status === 'PAID' ? 'active' : inv.status === 'VOID' ? 'inactive' : ''}`}>
                      {inv.status}
                    </span>
                  </td>
                  <td>{formatDateVi(inv.due_date)}</td>
                  <td><Link to={`/hoa-don/${inv.id}`}>Chi tiết</Link></td>
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