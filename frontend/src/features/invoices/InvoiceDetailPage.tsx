import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../lib/api/client';
import type { InvoiceDetail } from '../../lib/api/types';
import { formatVnd, formatDateVi } from '../../lib/utils/format';

export function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadInvoice = useCallback(() => {
    if (!id) return;
    setLoading(true);
    api.get<InvoiceDetail>(`/api/v1/invoices/${id}`)
      .then(setInvoice)
      .catch(() => setError('Không tải được hóa đơn.'))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { loadInvoice(); }, [loadInvoice]);

  async function handleIssue() {
    if (!confirm('Phát hành hóa đơn này? (DRAFT -> ISSUED)')) return;
    try {
      await api.post(`/api/v1/invoices/${id}/issue`);
      loadInvoice();
    } catch (e: any) {
      alert(e.message || 'Lỗi phát hành');
    }
  }

  async function handleVoid() {
    const reason = prompt('Nhập lý do hủy hóa đơn:');
    if (!reason) return;
    try {
      await api.post(`/api/v1/invoices/${id}/void`, { reason });
      loadInvoice();
    } catch (e: any) {
      alert(e.message || 'Lỗi hủy hóa đơn');
    }
  }

  async function handleReissue() {
    const reason = prompt('Nhập lý do phát hành lại:');
    if (!reason) return;
    try {
      await api.post(`/api/v1/invoices/${id}/reissue`, { reason });
      navigate(0); // Tải lại trang (vì id mới được tạo)
    } catch (e: any) {
      alert(e.message || 'Lỗi phát hành lại');
    }
  }

  if (loading) return <div className="loading-text">Đang tải...</div>;
  if (!invoice) return <div className="loading-text">{error}</div>;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Hóa đơn: {invoice.invoice_code}</h1>
        <button className="btn-secondary" onClick={() => navigate('/hoa-don')}>Quay lại</button>
      </div>

      <div className="detail-grid">
        <div className="detail-item"><label>Phòng</label><div>{invoice.room_code_snapshot}</div></div>
        <div className="detail-item"><label>Trạng thái</label><div>{invoice.status}</div></div>
        <div className="detail-item"><label>Kỳ</label><div>{formatDateVi(invoice.period_start)} - {formatDateVi(invoice.period_end)}</div></div>
        <div className="detail-item"><label>Tổng cộng</label><div style={{ color: 'var(--gold)' }}>{formatVnd(invoice.total_amount)}</div></div>
      </div>

      <div className="action-bar">
        {invoice.status === 'DRAFT' && (
          <button className="btn-primary" onClick={handleIssue}>Phát hành</button>
        )}
        {invoice.status === 'ISSUED' && (
          <>
            <button className="btn-primary" style={{ background: 'var(--cinnabar-2)' }} onClick={handleVoid}>Hủy hóa đơn</button>
            <button className="btn-secondary" onClick={handleReissue}>Phát hành lại</button>
          </>
        )}
      </div>

      <h3>Chi tiết các khoản</h3>
      <table className="data-table">
        <thead>
          <tr><th>Diễn giải</th><th>SL</th><th>Đơn giá</th><th>Thành tiền</th></tr>
        </thead>
        <tbody>
          {invoice.items.map((it, idx) => (
            <tr key={idx}>
              <td>{it.description}</td>
              <td>{it.quantity} {it.unit}</td>
              <td>{formatVnd(it.unit_price)}</td>
              <td style={{ fontWeight: 600 }}>{formatVnd(it.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}