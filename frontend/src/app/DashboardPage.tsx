import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../features/auth/AuthContext';
import { api, ApiError } from '../lib/api/client';
import type { Page, RoomOut } from '../lib/api/types';
import { RoomScene } from '../features/rooms/RoomScene';
import { RoomModal } from '../features/rooms/RoomModal';
import '../styles/dashboard.css';

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const [rooms, setRooms] = useState<RoomOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [mode, setMode] = useState<'dawn' | 'night'>(() => {
    return (localStorage.getItem('theme-mode') as 'dawn' | 'night') || 'night';
  });
  
  const [selectedRoom, setSelectedRoom] = useState<RoomOut | null>(null);

  useEffect(() => {
    document.body.classList.toggle('dawn', mode === 'dawn');
    localStorage.setItem('theme-mode', mode);
  }, [mode]);

  const loadRooms = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<Page<RoomOut>>('/api/v1/rooms?page=1&page_size=100');
      setRooms(data.items);
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

  const summary = useMemo(() => {
    const occupied = rooms.filter((r) => r.display_occupancy === 'OCCUPIED').length;
    const vacant = rooms.filter((r) => r.display_occupancy === 'VACANT').length;
    const inactive = rooms.filter((r) => r.display_occupancy === 'INACTIVE').length;
    return { occupied, vacant, inactive, total: rooms.length };
  }, [rooms]);

  return (
    <div className="dash-root">
      <header className="dash-header">
        <div>
          <div className="dash-eyebrow">Nhà trọ Minh An · Hội An</div>
          <h1 className="dash-title">Phố cổ</h1>
          <div className="dash-subtitle">
            Chào {user?.full_name ?? ''} · {summary.total} phòng · {summary.occupied} đang thuê ·{' '}
            {summary.vacant} trống
          </div>
        </div>
        <div className="dash-actions">
          <button
            className="mode-toggle-btn"
            onClick={() => setMode((m) => (m === 'dawn' ? 'night' : 'dawn'))}
            title="Đổi chế độ ngày/đêm"
          >
            {mode === 'dawn' ? (
              // Icon Mặt Trăng (để chuyển sang Đêm)
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            ) : (
              // Icon Mặt Trời (để chuyển sang Ngày)
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
            )}
          </button>
        </div>
      </header>

      {loading && <div className="boot-loader">Đang tải sân vườn…</div>}
      {error && !loading && <div className="dash-error">{error}</div>}

      {!loading && !error && (
        <RoomScene rooms={rooms} onSelect={setSelectedRoom} mode={mode} />
      )}

      {selectedRoom && (
        <RoomModal room={selectedRoom} onClose={() => setSelectedRoom(null)} />
      )}
    </div>
  );
}