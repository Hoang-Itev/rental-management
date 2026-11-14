import { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { Page, InvoiceDetail, BillingRunView } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';
import { PageState } from '../../components/PageState';
import { Badge } from '../../components/Badge';
import { formatVnd, formatDateVi, isOverdue } from '../../lib/utils/format';

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

  const [runs, setRuns] = useState<BillingRunView[]>([]);
  const [showRuns, setShowRuns] = useState(false);
  const [newMonth, setNewMonth] = useState('');
  const [creatingRun, setCreatingRun] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const q = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (status) q.set('status', status);
      if (billingMonth) q.set('billing_month', billingMonth);
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
      <div className="page-header">
        <h1 className="page-title">Quản lý Hóa đơn</h1>
        <button className="btn-secondary" onClick={() => setShowRuns((v) => !v)}>
          {showRuns ? 'Ẩn lịch sử chạy tự động' : 'Xem lịch sử chạy tự động'}
        </button>
      </div>

      {showRuns && (
        <div className="property-card" style={{ marginBottom: 24, padding: 20, border: '1px solid var(--gold-3)' }}>
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
                  <td>{r.billing_month}</td>
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

      <div className="filter-bar">
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
              <th>Phòng</th>
              <th>Kỳ hạn</th>
              <th>Tổng tiền</th>
              <th>Trạng thái</th>
              <th>Hạn chót</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((inv) => (
              <tr key={inv.id}>
                <td>{inv.invoice_code}</td>
                <td>{inv.room_code_snapshot}</td>
                <td>{formatDateVi(inv.period_start)} — {formatDateVi(inv.period_end)}</td>
                <td className="text-amount">{formatVnd(inv.total_amount)}</td>
                <td>
                  <Badge value={inv.status} />
                  {isOverdue(inv.status, inv.due_date) && (
                    <span style={{ marginLeft: 8, color: 'var(--cinnabar-3)', fontSize: 12, fontWeight: 'bold' }}>Quá hạn</span>
                  )}
                </td>
                <td>{formatDateVi(inv.due_date)}</td>
                <td><Link to={`/hoa-don/${inv.id}`} className="btn-secondary" style={{ padding: '4px 12px', textDecoration: 'none' }}>Chi tiết</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && <Pagination page={data.meta.page} pageSize={data.meta.page_size} total={data.meta.total} onPageChange={setPage} />}
      </PageState>
    </div>
  );
}