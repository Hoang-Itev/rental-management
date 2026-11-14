import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type { Page, EmailJobView } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';
import { PageState } from '../../components/PageState';
import { Badge } from '../../components/Badge';
import { formatDateTimeVi } from '../../lib/utils/format';

export function EmailListPage() {
  const [data, setData] = useState<Page<EmailJobView> | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [status, setStatus] = useState('');
  const [emailType, setEmailType] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const q = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (status) q.set('status', status);
      if (emailType) q.set('email_type', emailType);
      const res = await api.get<Page<EmailJobView>>(`/api/v1/email-jobs?${q.toString()}`);
      setData(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được email job.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, status, emailType]);

  useEffect(() => { load(); }, [load]);

  async function retry(id: string) {
    setRetrying(id);
    try {
      await api.post(`/api/v1/email-jobs/${id}/retry`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Không thể retry.');
    } finally {
      setRetrying(null);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Lịch sử gửi Email</h1>
      </div>

      <div className="filter-bar">
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">Mọi trạng thái</option>
          <option value="PENDING">Chờ</option>
          <option value="SENDING">Đang gửi</option>
          <option value="SENT">Đã gửi</option>
          <option value="FAILED">Thất bại</option>
          <option value="SKIPPED">Bỏ qua</option>
        </select>
        <select value={emailType} onChange={(e) => { setEmailType(e.target.value); setPage(1); }}>
          <option value="">Mọi loại</option>
          <option value="INVOICE">Hóa đơn</option>
          <option value="REMINDER">Nhắc nợ</option>
          <option value="PAYMENT_RECEIPT">Biên nhận</option>
          <option value="CONTRACT_EXPIRING">Hợp đồng sắp hết hạn</option>
        </select>
      </div>

      <PageState loading={loading} error={error} empty={!loading && !error && (data?.items.length ?? 0) === 0} emptyText="Chưa có email job." onRetry={load}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Loại</th>
              <th>Người nhận</th>
              <th>Tiêu đề</th>
              <th>Trạng thái</th>
              <th>Lần thử</th>
              <th>Lỗi</th>
              <th>Gửi lúc</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((job) => (
              <tr key={job.id}>
                <td>{job.email_type}</td>
                <td>{job.recipient_email}</td>
                <td>{job.subject}</td>
                <td><Badge value={job.status} /></td>
                <td>{job.attempt_count}</td>
                <td style={{ fontSize: 12, color: 'var(--cinnabar-3)' }}>{job.last_error || '—'}</td>
                <td>{job.sent_at ? formatDateTimeVi(job.sent_at) : '—'}</td>
                <td>
                  {job.status === 'FAILED' && (
                    <button className="btn-secondary" disabled={retrying === job.id} onClick={() => retry(job.id)}>
                      {retrying === job.id ? 'Đang retry…' : 'Gửi lại'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && <Pagination page={data.meta.page} pageSize={data.meta.page_size} total={data.meta.total} onPageChange={setPage} />}
      </PageState>
    </div>
  );
}