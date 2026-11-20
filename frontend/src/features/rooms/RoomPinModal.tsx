import { useState, useEffect } from 'react';
import type { RoomOut } from '../../lib/api/types';
import { api } from '../../lib/api/client';

interface Props {
  rooms: RoomOut[];
  pinnedIds: string[];
  onSave: (ids: string[]) => void;
  onClose: () => void;
}

// Hàm dịch trạng thái phòng sang tiếng Việt
function translateOccupancy(status: string) {
  if (status === 'VACANT') return 'Trống';
  if (status === 'OCCUPIED') return 'Đang thuê';
  if (status === 'INACTIVE') return 'Ngừng';
  return status;
}

export function RoomPinModal({ rooms, pinnedIds, onSave, onClose }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set(pinnedIds));
  const [roomDetails, setRoomDetails] = useState<Record<string, {prop: string, bld: string, flr: string}>>({});

  // Tự động tải thông tin Khu/Dãy/Tầng để hiển thị
  useEffect(() => {
    async function loadMeta() {
      try {
        const propRes = await api.get<any>('/api/v1/properties?page_size=100');
        const detailMap: Record<string, {prop: string, bld: string, flr: string}> = {};
        
        for (const p of propRes.items) {
          const bRes = await api.get<any>(`/api/v1/properties/${p.id}/buildings?page_size=100`);
          for (const b of bRes.items) {
            const fRes = await api.get<any>(`/api/v1/buildings/${b.id}/floors?page_size=100`);
            for (const f of fRes.items) {
              const roomsInFloor = rooms.filter(r => r.floor_id === f.id);
              for (const r of roomsInFloor) {
                detailMap[r.id] = {
  prop: p.name,
  bld: b.name,
  flr: f.name ? `${f.floor_number} - ${f.name}` : String(f.floor_number),
};
              }
            }
          }
        }
        setRoomDetails(detailMap);
      } catch (e) {
        console.error(e);
      }
    }
    if (rooms.length > 0) loadMeta();
  }, [rooms]);

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
      <div className="room-modal" style={{ width: 'min(850px, 96vw)' }}>
        <button className="modal-close" onClick={onClose}>×</button>
        <h2 className="modal-title">Chọn phòng hiển thị trên Sân vườn (Tối đa 12)</h2>
        <p className="text-muted" style={{ marginBottom: 16 }}>
          Đã chọn: {selected.size}/12 phòng.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12, maxHeight: '60vh', overflowY: 'auto', padding: 4 }}>
          {rooms.map((r) => {
            const info = roomDetails[r.id];
            const isSelected = selected.has(r.id);
            
            return (
              <label 
                key={r.id} 
                style={{ 
                  display: 'flex', alignItems: 'flex-start', gap: 10, padding: 12, 
                  border: isSelected ? '2px solid var(--cinnabar-2)' : '1px solid var(--gold-3)', 
                  cursor: 'pointer', 
                  background: isSelected ? 'rgba(212, 163, 64, 0.2)' : 'var(--night-1)', 
                  borderRadius: 6,
                  transition: 'all 0.2s'
                }}
              >
                <input 
                  type="checkbox" 
                  checked={isSelected} 
                  onChange={() => toggle(r.id)} 
                  style={{ marginTop: 4, width: 16, height: 16, cursor: 'pointer' }}
                />
                <div style={{ flex: 1 }}>
                  {/* Tên phòng in đậm, rõ màu */}
                  <div style={{ fontWeight: 'bold', fontSize: 16, color: isSelected ? 'var(--cinnabar-2)' : 'var(--ink-soft)' }}>
                    {r.room_code}
                  </div>
                  
                  {/* Địa chỉ Khu - Dãy - Tầng */}
                  <div style={{ fontSize: 12, color: 'var(--ink-soft)', marginBottom: 4 }}>
                    {info ? `${info.prop} - Dãy ${info.bld} - Tầng ${info.flr}` : 'Đang tải vị trí...'}
                  </div>

                  {/* Trạng thái phòng */}
                  <div style={{ 
                    fontSize: 12, 
                    fontWeight: 600,
                    color: r.display_occupancy === 'VACANT' ? 'var(--jade-hi)' : 'var(--amber)',
                  }}>
                    {translateOccupancy(r.display_occupancy)}
                  </div>
                </div>
              </label>
            );
          })}
        </div>

        <div className="modal-actions" style={{ marginTop: 20 }}>
          <button className="modal-btn" onClick={onClose}>Hủy</button>
          <button className="modal-btn primary" onClick={() => onSave(Array.from(selected))}>Lưu</button>
        </div>
      </div>
    </div>
  );
}