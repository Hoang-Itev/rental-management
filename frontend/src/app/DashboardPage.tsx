import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../features/auth/AuthContext';
import { api, ApiError } from '../lib/api/client';
import type { Page, RoomOut } from '../lib/api/types';
import { RoomScene } from '../features/rooms/RoomScene';
import { RoomModal } from '../features/rooms/RoomModal';
import { RoomPinModal } from '../features/rooms/RoomPinModal';
import '../styles/dashboard.css';

const PINNED_KEY = 'dashboard_pinned_rooms';

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const [allRooms, setAllRooms] = useState<RoomOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [mode, setMode] = useState<'dawn' | 'night'>(() => {
    return (localStorage.getItem('theme-mode') as 'dawn' | 'night') || 'night';
  });
  
  const [selectedRoom, setSelectedRoom] = useState<RoomOut | null>(null);
  const [showPinModal, setShowPinModal] = useState(false);
  
  // Đọc danh sách phòng đã ghim
  const [pinnedIds, setPinnedIds] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(PINNED_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch { return []; }
  });

  useEffect(() => {
    document.body.classList.toggle('dawn', mode === 'dawn');
    localStorage.setItem('theme-mode', mode);
  }, [mode]);

  const loadRooms = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<Page<RoomOut>>('/api/v1/rooms?page=1&page_size=100');
      setAllRooms(data.items);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        logout();
      } else {
        setError('Không tải được danh sách phòng.');
      }
    } finally {
      setLoading(false);
    }
  }, [logout]);

  useEffect(() => {
    loadRooms();
  }, [loadRooms]);

  // Lọc các phòng được ghim để hiển thị
  const displayRooms = useMemo(() => {
    if (pinnedIds.length === 0) return []; // Hoặc có thể return allRooms.slice(0, 12) nếu muốn
    return allRooms.filter(r => pinnedIds.includes(r.id)).slice(0, 12);
  }, [allRooms, pinnedIds]);

  const summary = useMemo(() => {
    const occupied = displayRooms.filter((r) => r.display_occupancy === 'OCCUPIED').length;
    const vacant = displayRooms.filter((r) => r.display_occupancy === 'VACANT').length;
    const inactive = displayRooms.filter((r) => r.display_occupancy === 'INACTIVE').length;
    return { occupied, vacant, inactive, total: displayRooms.length };
  }, [displayRooms]);

  function handleSavePins(ids: string[]) {
    setPinnedIds(ids);
    localStorage.setItem(PINNED_KEY, JSON.stringify(ids));
    setShowPinModal(false);
  }

  return (
    <div className="dash-root">
      <header className="dash-header">
        <div>
          <div className="dash-eyebrow">Nhà trọ Minh An · Hội An</div>
          <h1 className="dash-title">Phố cổ</h1>
          <div className="dash-subtitle">
            Chào {user?.full_name ?? ''} · Đang hiển thị {summary.total} phòng (Trống: {summary.vacant}, Thuê: {summary.occupied})
          </div>
        </div>
        <div className="dash-actions">
          <button className="btn-secondary" onClick={() => setShowPinModal(true)}>
            Chọn phòng hiển thị
          </button>
          <button
            className="mode-toggle-btn"
            onClick={() => setMode((m) => (m === 'dawn' ? 'night' : 'dawn'))}
            title="Đổi chế độ ngày/đêm"
          >
            {mode === 'dawn' ? (
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
            )}
          </button>
        </div>
      </header>

      {loading && <div className="boot-loader">Đang tải sân vườn…</div>}
      {error && !loading && <div className="dash-error">{error}</div>}

      {!loading && !error && displayRooms.length === 0 && (
        <div className="dash-error" style={{ marginTop: 40 }}>
          Chưa có phòng nào được chọn hiển thị. <br/>
          <button className="btn-primary" style={{ marginTop: 16 }} onClick={() => setShowPinModal(true)}>
            Chọn phòng ngay
          </button>
        </div>
      )}

      {!loading && !error && displayRooms.length > 0 && (
        <RoomScene rooms={displayRooms} onSelect={setSelectedRoom} mode={mode} />
      )}

      {selectedRoom && (
        <RoomModal room={selectedRoom} onClose={() => setSelectedRoom(null)} />
      )}

      {showPinModal && (
        <RoomPinModal
          rooms={allRooms}
          pinnedIds={pinnedIds}
          onSave={handleSavePins}
          onClose={() => setShowPinModal(false)}
        />
      )}
    </div>
  );
}