import type { RoomOut } from '../../lib/api/types';
import { formatVnd } from '../../lib/utils/format';

interface Props {
  room: RoomOut;
  onClose: () => void;
}

const stateLabels: Record<RoomOut['display_occupancy'], string> = {
  OCCUPIED: 'Đang thuê',
  VACANT: 'Trống',
  INACTIVE: 'Ngừng sử dụng',
};

export function RoomModal({ room, onClose }: Props) {
  return (
    <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="room-modal">
        <button className="modal-close" onClick={onClose} aria-label="Đóng">
          ×
        </button>
        <div className="modal-eyebrow">Chi tiết phòng</div>
        <h2 className="modal-title">{room.room_code}</h2>
        <span className={`modal-state ${room.display_occupancy.toLowerCase()}`}>
          {stateLabels[room.display_occupancy]}
        </span>

        <div className="modal-grid">
          <div>
            <div className="label">Diện tích</div>
            <div className="value">{room.area_m2.toFixed(1)} m²</div>
          </div>
          <div>
            <div className="label">Giá niêm yết</div>
            <div className="value gold">{formatVnd(room.listed_rent)}</div>
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
          <button className="modal-btn" onClick={onClose}>
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}