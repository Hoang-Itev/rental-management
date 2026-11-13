import { useState, useEffect } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type { Page, RoomOut, MeterOut, RoomMeterList, CutoffOut } from '../../lib/api/types';
import { formatDateVi } from '../../lib/utils/format';

export function MeterListPage() {
  const [rooms, setRooms] = useState<RoomOut[]>([]);
  const [selectedRoom, setSelectedRoom] = useState<string>('');
  const [meters, setMeters] = useState<MeterOut[]>([]);
  
  // Trạng thái cutoff
  const [cutoffs, setCutoffs] = useState<CutoffOut[]>([]);
  const [loadingMeters, setLoadingMeters] = useState(false);
  const [error, setError] = useState('');

  // Modal chốt số
  const [activeCutoff, setActiveCutoff] = useState<CutoffOut | null>(null);
  const [manualValue, setManualValue] = useState('');
  const [manualReason, setManualReason] = useState('');

  useEffect(() => {
    api.get<Page<RoomOut>>('/api/v1/rooms?page_size=100')
      .then(res => setRooms(res.items))
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!selectedRoom) return;
    setLoadingMeters(true);
    setError('');
    
    // Lấy danh sách đồng hồ của phòng
    api.get<RoomMeterList>(`/api/v1/rooms/${selectedRoom}/meters`)
      .then(async (res) => {
        setMeters(res.items);
        // Lấy các cutoff PENDING của toàn bộ đồng hồ thuộc phòng này
        const cRes = await api.get<Page<CutoffOut>>(`/api/v1/meter-cutoffs?room_id=${selectedRoom}&page_size=100`);
        setCutoffs(cRes.items);
      })
      .catch(() => setError('Không tải được thông tin đồng hồ.'))
      .finally(() => setLoadingMeters(false));
  }, [selectedRoom]);

  async function handleConfirmCutoff(e: React.FormEvent) {
    e.preventDefault();
    if (!activeCutoff) return;
    try {
      await api.post(`/api/v1/meter-cutoffs/${activeCutoff.id}/confirm`, {
        reading_value: manualValue,
        manual_reason: manualReason,
      });
      setActiveCutoff(null);
      setManualValue('');
      setManualReason('');
      // Reload cutoffs
      if (selectedRoom) {
        const cRes = await api.get<Page<CutoffOut>>(`/api/v1/meter-cutoffs?room_id=${selectedRoom}&page_size=100`);
        setCutoffs(cRes.items);
      }
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 422) {
        setError('Giá trị không hợp lệ hoặc lý do quá ngắn.');
      } else {
        setError(err.message || 'Lỗi khi xác nhận.');
      }
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Đồng hồ điện nước</h1>
      </div>

      <div className="filter-bar">
        <select value={selectedRoom} onChange={e => setSelectedRoom(e.target.value)}>
          <option value="">-- Chọn phòng để xem --</option>
          {rooms.map(r => <option key={r.id} value={r.id}>{r.room_code}</option>)}
        </select>
      </div>

      {error && <div className="login-error">{error}</div>}

      {loadingMeters && <div className="loading-text">Đang tải...</div>}

      {!loadingMeters && selectedRoom && (
        <>
          <h3>Danh sách đồng hồ</h3>
          <div className="property-grid">
            {meters.map(m => (
              <div key={m.id} className="property-card">
                <h3>{m.meter_type === 'ELECTRICITY' ? 'Điện' : 'Nước'}</h3>
                <p>Mã: {m.meter_code}</p>
                <p>Đơn vị: {m.unit}</p>
                <span className="badge active">{m.status}</span>
              </div>
            ))}
            {meters.length === 0 && <p>Phòng này chưa được khởi tạo đồng hồ.</p>}
          </div>

          <h3 style={{ marginTop: 40 }}>Các mốc chốt số</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Loại mốc</th>
                <th>Thời điểm chốt</th>
                <th>Chỉ số</th>
                <th>Trạng thái</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {cutoffs.map(c => (
                <tr key={c.id}>
                  <td>{c.cutoff_type}</td>
                  <td>{formatDateVi(c.cutoff_at.split('T')[0])}</td>
                  <td>{c.reading_value || '—'}</td>
                  <td>
                    <span className={`badge ${c.status === 'PENDING' ? 'inactive' : 'active'}`}>
                      {c.status}
                    </span>
                  </td>
                  <td>
                    {c.status === 'PENDING' && (
                      <button className="btn-secondary" onClick={() => setActiveCutoff(c)}>
                        Chốt số
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* Modal chốt số */}
      {activeCutoff && (
        <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && setActiveCutoff(null)}>
          <div className="room-modal" style={{ width: 400 }}>
            <button className="modal-close" onClick={() => setActiveCutoff(null)}>×</button>
            <h2 className="modal-title">Chốt số thủ công</h2>
            <p>Mốc: {activeCutoff.cutoff_type} - {formatDateVi(activeCutoff.cutoff_at.split('T')[0])}</p>
            <form onSubmit={handleConfirmCutoff}>
              <div className="login-field">
                <label>Chỉ số thực tế</label>
                <input type="number" step="0.001" value={manualValue} onChange={e => setManualValue(e.target.value)} required />
              </div>
              <div className="login-field">
                <label>Lý do (ít nhất 8 ký tự)</label>
                <input type="text" value={manualReason} onChange={e => setManualReason(e.target.value)} required />
              </div>
              <div className="modal-actions">
                <button type="submit" className="btn-primary">Xác nhận</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}