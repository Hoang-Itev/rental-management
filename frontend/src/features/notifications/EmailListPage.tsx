import { useState, useEffect } from 'react';
import { api } from '../../lib/api/client';
import type { Page } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';

// Type dựa trên EmailJobView của Notification
interface EmailJob {
  id: string;
  email_type: string;
  recipient_email: string;
  subject: string;
  status: string;
  attempt_count: number;
  last_error: string | null;
  sent_at: string | null;
}

export function EmailListPage() {
  const [data, setData] = useState<Page<EmailJob> | null>(null);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const q = new URLSearchParams({ page: page.toString(), page_size: '10' });
    if (status) q.append('status', status);
    api.get<Page<EmailJob>>(`/api/v1/email-jobs?${q.toString()}`)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, status]);

  async function handleRetry(id: string) {
    try {
      await api.post(`/api/v1/email-jobs/${id}/retry`);
      // Reload
      const q = new URLSearchParams({ page: page.toString(), page_size: '10' });
      if (status) q.append('status', status);
      const res = await api.get<Page<EmailJob>>(`/api/v1/email-jobs?${q.toString()}`);
      setData(res);
    } catch (e: any) {
      alert(e.message || 'Lỗi retry');
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Lịch sử gửi Email</h1>
      </div>

      <div className="filter-bar">
        <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}>
          <option value="">Tất cả</option>
          <option value="PENDING">Đang chờ (PENDING)</option>
          <option value="SENT">Đã gửi (SENT)</option>
          <option value="FAILED">Thất bại (FAILED)</option>
        </select>
      </div>

      {loading ? <div className="loading-text">Đang tải...</div> : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Loại Email</th>
                <th>Người nhận</th>
                <th>Tiêu đề</th>
                <th>Trạng thái</th>
                <th>Lỗi</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map(job => (
                <tr key={job.id}>
                  <td>{job.email_type}</td>
                  <td>{job.recipient_email}</td>
                  <td>{job.subject}</td>
                  <td>
                    <span className={`badge ${job.status === 'SENT' ? 'active' : job.status === 'FAILED' ? 'inactive' : ''}`}>
                      {job.status}
                    </span>
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--cinnabar-3)' }}>{job.last_error || '—'}</td>
                  <td>
                    {job.status === 'FAILED' && (
                      <button className="btn-secondary" onClick={() => handleRetry(job.id)}>Gửi lại</button>
                    )}
                  </td>
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