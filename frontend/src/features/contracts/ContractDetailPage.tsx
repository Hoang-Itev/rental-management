import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../lib/api/client';
import type { ContractOut, Page, TermOut } from '../../lib/api/types';
import { formatDateVi } from '../../lib/utils/format';

export function ContractDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [contract, setContract] = useState<ContractOut | null>(null);
  const [terms, setTerms] = useState<TermOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState('');

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.get<ContractOut>(`/api/v1/contracts/${id}`),
      api.get<Page<TermOut>>(`/api/v1/contracts/${id}/terms`)
    ]).then(([c, t]) => {
      setContract(c);
      setTerms(t.items);
    }).catch(() => setActionError('Không tải được hợp đồng.'))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleConfirm() {
    if (!confirm('Xác nhận hợp đồng này? (DRAFT -> SCHEDULED)')) return;
    try {
      await api.post(`/api/v1/contracts/${id}/confirm`);
      navigate(0); // Reload
    } catch (e: any) {
      setActionError(e.message || 'Lỗi xác nhận');
    }
  }

  async function handleEnd() {
    const date = prompt('Nhập ngày bàn giao thực tế (YYYY-MM-DD):');
    if (!date) return;
    const reason = prompt('Lý do kết thúc:');
    if (!reason) return;
    try {
      await api.post(`/api/v1/contracts/${id}/end`, { actual_end_date: date, reason });
      navigate(0);
    } catch (e: any) {
      setActionError(e.message || 'Lỗi kết thúc');
    }
  }

  if (loading) return <div className="loading-text">Đang tải...</div>;
  if (!contract) return <div className="loading-text">{actionError}</div>;

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Hợp đồng: {contract.contract_code}</h1>
        <button className="btn-secondary" onClick={() => navigate('/hop-dong')}>Quay lại</button>
      </div>
      
      {actionError && <div className="login-error">{actionError}</div>}

      <div className="detail-grid">
        <div className="detail-item"><label>Phòng</label><div>{contract.room_code_snapshot}</div></div>
        <div className="detail-item"><label>Trạng thái</label><div>{contract.status}</div></div>
        <div className="detail-item"><label>Bắt đầu</label><div>{formatDateVi(contract.start_date)}</div></div>
        <div className="detail-item"><label>Kết thúc</label><div>{formatDateVi(contract.end_date)}</div></div>
      </div>

      <div className="action-bar">
        {contract.status === 'DRAFT' && (
          <button className="btn-primary" onClick={handleConfirm}>Xác nhận (Lên lịch)</button>
        )}
        {(contract.status === 'ACTIVE' || contract.status === 'EXPIRED_PENDING') && (
          <button className="btn-primary" style={{ background: 'var(--cinnabar-2)' }} onClick={handleEnd}>Ghi nhận kết thúc</button>
        )}
      </div>

      <h3>Lịch sử giá thuê (Terms)</h3>
      <table className="data-table">
        <thead>
          <tr><th>Từ ngày</th><th>Đến ngày</th><th>Tiền phòng</th><th>Điện</th><th>Nước</th></tr>
        </thead>
        <tbody>
          {terms.map(t => (
            <tr key={t.id}>
              <td>{formatDateVi(t.effective_from)}</td>
              <td>{t.effective_to ? formatDateVi(t.effective_to) : 'Vô hạn'}</td>
              <td>{t.monthly_rent.toLocaleString('vi-VN')} đ</td>
              <td>{t.electricity_unit_price} đ</td>
              <td>{t.water_unit_price} đ</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}