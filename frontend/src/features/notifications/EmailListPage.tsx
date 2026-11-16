import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type { Page, EmailJobView } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';
import { PageState } from '../../components/PageState';
import { Badge } from '../../components/Badge';
import { formatDateTimeVi } from '../../lib/utils/format';

// Hàm dịch Loại email sang tiếng Việt
function translateEmailType(type: string) {
  switch (type) {
    case 'INVOICE': return 'Hóa đơn';
    case 'REMINDER': return 'Nhắc nợ';
    case 'PAYMENT_RECEIPT': return 'Biên nhận';
    case 'CONTRACT_EXPIRING': return 'Sắp hết hạn';
    default: return type;
  }
}

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
      setError(e instanceof ApiError ? e.message : 'Không tải được danh sách email.');
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
      setError(err instanceof ApiError ? err.message : 'Không thể gửi lại email.');
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
          <option value="PENDING">Đang chờ</option>
          <option value="SENT">Đã gửi</option>
          <option value="FAILED">Thất bại</option>
          <option value="SKIPPED">Bỏ qua</option>
        </select>

        <select value={emailType} onChange={(e) => { setEmailType(e.target.value); setPage(1); }}>
          <option value="">Mọi loại</option>
          <option value="INVOICE">Hóa đơn</option>
          <option value="REMINDER">Nhắc nợ</option>
          <option value="PAYMENT_RECEIPT">Biên nhận</option>
          <option value="CONTRACT_EXPIRING">Sắp hết hạn</option>
        </select>
      </div>

      <PageState loading={loading} error={error} empty={!loading && !error && (data?.items.length ?? 0) === 0} emptyText="Không có email nào." onRetry={load}>
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
              <th>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((job) => (
              <tr key={job.id}>
                <td style={{ fontWeight: 'bold' }}>{translateEmailType(job.email_type)}</td>
                <td>{job.recipient_email}</td>
                <td style={{ maxWidth: 200, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={job.subject}>
                  {job.subject}
                </td>
                <td><Badge value={job.status} /></td>
                <td style={{ textAlign: 'center' }}>{job.attempt_count}</td>
                <td style={{ maxWidth: 150, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={job.last_error || ''}>
                  {job.last_error || '—'}
                </td>
                <td>{job.sent_at ? formatDateTimeVi(job.sent_at) : '—'}</td>
                <td>
                  {job.status === 'FAILED' && (
                    <button 
                      className="btn-secondary" 
                      style={{ padding: '4px 12px', fontSize: 12 }} 
                      onClick={() => retry(job.id)}
                      disabled={retrying === job.id}
                    >
                      {retrying === job.id ? 'Đang gửi...' : 'Gửi lại'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ marginTop: 20 }}>
          {data && <Pagination page={data.meta.page} pageSize={data.meta.page_size} total={data.meta.total} onPageChange={setPage} />}
        </div>
      </PageState>
    </div>
  );
}