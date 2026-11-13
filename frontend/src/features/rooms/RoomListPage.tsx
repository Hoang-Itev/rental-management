import { useState, useEffect, useCallback } from 'react';
import { api } from '../../lib/api/client';
import type { Page, RoomOut } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';
import { SearchBar } from '../../components/SearchBar';
import { formatVnd } from '../../lib/utils/format';

export function RoomListPage() {
  const [data, setData] = useState<Page<RoomOut> | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<string>('');

  const fetchRooms = useCallback(async () => {
    setLoading(true);
    try {
      // Gọi API list rooms có phân trang, truyền query params
      const q = new URLSearchParams({
        page: page.toString(),
        page_size: '10',
        ...(status ? { status } : {}),
      });
      // Lưu ý: Backend Room API hiện tại chưa hỗ trợ search keyword qua query param, 
      // ta sẽ filter tạm ở client sau khi fetch để đảm bảo UX.
      const res = await api.get<Page<RoomOut>>(`/api/v1/rooms?${q.toString()}`);
      
      // Client-side search filter fallback
      if (keyword) {
        const filteredItems = res.items.filter(r => 
          r.room_code.toLowerCase().includes(keyword.toLowerCase())
        );
        setData({ items: filteredItems, meta: res.meta });
      } else {
        setData(res);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, status, keyword]);

  useEffect(() => {
    fetchRooms();
  }, [fetchRooms]);

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Danh sách Phòng</h1>
        <button className="btn-primary">Thêm phòng mới</button>
      </div>

      <div className="filter-bar">
        <SearchBar onSearch={setKeyword} placeholder="Tìm mã phòng..." />
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">Tất cả trạng thái</option>
          <option value="ACTIVE">Đang hoạt động</option>
          <option value="INACTIVE">Ngừng sử dụng</option>
        </select>
      </div>

      {loading ? (
        <div className="loading-text">Đang tải dữ liệu...</div>
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Mã phòng</th>
                <th>Diện tích</th>
                <th>Giá niêm yết</th>
                <th>Trạng thái</th>
                <th>Người thuê</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((room) => (
                <tr key={room.id}>
                  <td>{room.room_code}</td>
                  <td>{room.area_m2} m²</td>
                  <td>{formatVnd(room.listed_rent)}</td>
                  <td>
                    <span className={`badge ${room.status.toLowerCase()}`}>
                      {room.status === 'ACTIVE' ? 'Hoạt động' : 'Ngừng'}
                    </span>
                  </td>
                  <td>
                    {room.display_occupancy === 'OCCUPIED' ? 'Đang thuê' : 'Trống'}
                  </td>
                </tr>
              ))}
              {data?.items.length === 0 && (
                <tr><td colSpan={5} className="empty-row">Không tìm thấy phòng nào.</td></tr>
              )}
            </tbody>
          </table>
          
          {data && (
            <Pagination 
              page={data.meta.page} 
              pageSize={data.meta.page_size} 
              total={data.meta.total} 
              onPageChange={setPage} 
            />
          )}
        </>
      )}
    </div>
  );
}