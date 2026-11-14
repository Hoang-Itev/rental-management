import { useState } from 'react';
import type { RoomOut } from '../../lib/api/types';

interface Props {
  rooms: RoomOut[];
  pinnedIds: string[];
  onSave: (ids: string[]) => void;
  onClose: () => void;
}

export function RoomPinModal({ rooms, pinnedIds, onSave, onClose }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set(pinnedIds));

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) {
      next.delete(id);
    } else {
      if (next.size >= 12) {
        alert('Chỉ được chọn tối đa 12 phòng để hiển thị trên sân vườn.');
        return;
      }
      next.add(id);
    }
    setSelected(next);
  }

  return (
    <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="room-modal" style={{ width: 'min(800px, 96vw)' }}>
        <button className="modal-close" onClick={onClose}>×</button>
        <h2 className="modal-title">Chọn phòng hiển thị trên Sân vườn (Tối đa 12)</h2>
        <p className="text-muted" style={{ marginBottom: 16 }}>
          Đã chọn: {selected.size}/12 phòng.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8, maxHeight: '50vh', overflowY: 'auto', padding: 4 }}>
          {rooms.map((r) => (
            <label key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 8, border: '1px solid var(--gold-3)', cursor: 'pointer', background: selected.has(r.id) ? 'var(--gold-3)' : 'transparent', borderRadius: 4 }}>
              <input 
                type="checkbox" 
                checked={selected.has(r.id)} 
                onChange={() => toggle(r.id)} 
              />
              <div>
                <div style={{ fontWeight: 'bold' }}>{r.room_code}</div>
                <div style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{r.display_occupancy}</div>
              </div>
            </label>
          ))}
        </div>

        <div className="modal-actions" style={{ marginTop: 20 }}>
          <button className="modal-btn" onClick={onClose}>Hủy</button>
          <button className="modal-btn primary" onClick={() => onSave(Array.from(selected))}>Lưu</button>
        </div>
      </div>
    </div>
  );
}