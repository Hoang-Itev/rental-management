import { useState } from 'react';
import type { RoomOut } from '../../lib/api/types';
import { formatVnd } from '../../lib/utils/format';
import { api, ApiError } from '../../lib/api/client';

interface Props {
  room: RoomOut;
  locationName?: string;
  onClose: () => void;
  onUpdate?: () => void;
}

const stateLabels: Record<RoomOut['display_occupancy'], string> = {
  OCCUPIED: 'Đang thuê',
  VACANT: 'Trống',
  INACTIVE: 'Ngừng sử dụng',
};

export function RoomModal({ room, locationName, onClose, onUpdate }: Props) {
  const [isEditing, setIsEditing] = useState(false);
  const [form, setForm] = useState({
    room_code: room.room_code,
    area_m2: String(room.area_m2),
    listed_rent: String(room.listed_rent),
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // SỬA LẠI LOGIC: Chỉ không cho sửa khi đang OCCUPIED (Đang thuê)
  // Còn VACANT (Trống) và INACTIVE (Ngừng) đều được sửa
  const canEdit = room.display_occupancy !== 'OCCUPIED';

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    
    if (!form.room_code.trim()) { setError('Mã phòng không được để trống.'); return; }
    if (!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(form.room_code)) { 
      setError('Mã phòng chỉ chứa chữ, số, gạch dưới, chấm, gạch ngang.'); 
      return; 
    }
    const area = Number(form.area_m2);
    const rent = Number(form.listed_rent);
    if (!(area > 0)) { setError('Diện tích phải lớn hơn 0.'); return; }
    if (!Number.isInteger(rent) || rent < 0) { setError('Giá thuê phải là số nguyên >= 0.'); return; }

    setSubmitting(true);
    try {
      await api.patch(`/api/v1/rooms/${room.id}`, {
        room_code: form.room_code.trim(),
        area_m2: area,
        listed_rent: rent,
      });
      setIsEditing(false);
      if (onUpdate) onUpdate();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError('Mã phòng này đã tồn tại trong Khu trọ. Vui lòng chọn mã khác.');
      } else {
        setError(err instanceof ApiError ? err.message : 'Lỗi khi cập nhật phòng.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="room-modal" style={{ width: 480 }}>
        <button className="modal-close" onClick={onClose} aria-label="Đóng">×</button>
        <div className="modal-eyebrow">Chi tiết phòng</div>
        <h2 className="modal-title">{room.room_code}</h2>
        
        <div style={{ marginBottom: 12 }}>
          <span className="text-muted" style={{ fontSize: 13, marginRight: 8 }}>Vị trí:</span>
          <strong style={{ color: 'var(--gold-2)', fontSize: 14 }}>
            {locationName || 'Đang tải...'}
          </strong>
        </div>

        <span className={`modal-state ${room.display_occupancy.toLowerCase()}`}>
          {stateLabels[room.display_occupancy]}
        </span>

        {isEditing ? (
          <form onSubmit={handleSave} style={{ marginTop: 20 }}>
            {error && <div className="login-error">{error}</div>}
            <div className="login-field">
              <label>Mã phòng *</label>
              <input value={form.room_code} onChange={(e) => setForm({ ...form, room_code: e.target.value })} required />
            </div>
            <div className="login-field">
              <label>Diện tích (m²) *</label>
              <input type="number" step="0.01" min="0.01" value={form.area_m2} onChange={(e) => setForm({ ...form, area_m2: e.target.value })} required />
            </div>
            <div className="login-field">
              <label>Giá niêm yết (VNĐ) *</label>
              <input type="number" min="0" step="1000" value={form.listed_rent} onChange={(e) => setForm({ ...form, listed_rent: e.target.value })} required />
            </div>
            <div className="modal-actions">
              <button type="button" className="modal-btn" onClick={() => setIsEditing(false)} disabled={submitting}>Hủy</button>
              <button type="submit" className="modal-btn primary" disabled={submitting}>{submitting ? 'Đang lưu...' : 'Lưu thay đổi'}</button>
            </div>
          </form>
        ) : (
          <>
            <div className="modal-grid" style={{ marginTop: 20 }}>
              <div>
                <div className="label">Diện tích</div>
                <div className="value">{room.area_m2.toFixed(1)} m²</div>
              </div>
              <div>
                <div className="label">Giá niêm yết</div>
                <div className="value text-amount">{formatVnd(room.listed_rent)}</div>
              </div>
              <div>
                <div className="label">Mã phòng</div>
                <div className="value">{room.room_code}</div>
              </div>
              <div>
                <div className="label">Trạng thái vận hành</div>
                <div className="value">{room.status === 'ACTIVE' ? 'Hoạt động' : 'Ngừng'}</div>
              </div>
            </div>
            <div className="modal-divider" />
            <div className="modal-actions">
              <button className="modal-btn" onClick={onClose}>Đóng</button>
              {canEdit && (
                <button className="modal-btn primary" onClick={() => setIsEditing(true)}>Sửa phòng</button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}