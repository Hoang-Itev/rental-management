import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { Page, ContractOut, RoomOut, PropertyOut } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';
import { PageState } from '../../components/PageState';
import { Badge } from '../../components/Badge';
import { formatDateVi } from '../../lib/utils/format';

interface Building { id: string; name: string; property_id: string; }
interface Floor { id: string; floor_number: number; building_id: string; name: string | null; }

export function ContractListPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<Page<ContractOut> | null>(null);
  
  // State lưu trữ toàn bộ danh mục
  const [properties, setProperties] = useState<PropertyOut[]>([]);
  const [allBuildings, setAllBuildings] = useState<Building[]>([]);
  const [allFloors, setAllFloors] = useState<Floor[]>([]);
  const [allRooms, setAllRooms] = useState<RoomOut[]>([]);
  
  // State cho bộ lọc (sẽ dùng để hiển thị dropdown)
  const [filterBuildings, setFilterBuildings] = useState<Building[]>([]);
  const [filterFloors, setFilterFloors] = useState<Floor[]>([]);

  const [propertyId, setPropertyId] = useState('');
  const [buildingId, setBuildingId] = useState('');
  const [floorId, setFloorId] = useState('');
  const [roomId, setRoomId] = useState('');

  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [status, setStatus] = useState('');
  const [mode, setMode] = useState<'all' | 'expiring'>('all');
  const [withinDays, setWithinDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Tải TOÀN BỘ danh mục 1 lần
  useEffect(() => {
    const fetchAllMeta = async () => {
      try {
        const propRes = await api.get<Page<PropertyOut>>('/api/v1/properties?page_size=100');
        setProperties(propRes.items);
        
        const roomRes = await api.get<Page<RoomOut>>('/api/v1/rooms?page_size=100');
        setAllRooms(roomRes.items);

        const bldList: Building[] = [];
        const flrList: Floor[] = [];

        for (const p of propRes.items) {
          const bRes = await api.get<Page<Building>>(`/api/v1/properties/${p.id}/buildings?page_size=100`);
          bldList.push(...bRes.items);
          
          for (const b of bRes.items) {
            const fRes = await api.get<Page<Floor>>(`/api/v1/buildings/${b.id}/floors?page_size=100`);
            flrList.push(...fRes.items);
          }
        }
        setAllBuildings(bldList);
        setAllFloors(flrList);
      } catch (e) {
        console.error('Lỗi tải dữ liệu danh mục', e);
      }
    };
    fetchAllMeta();
  }, []);

  // Cập nhật dropdown Dãy dựa theo Khu
  useEffect(() => {
    if (!propertyId) { setFilterBuildings([]); setBuildingId(''); return; }
    setFilterBuildings(allBuildings.filter(b => b.property_id === propertyId));
  }, [propertyId, allBuildings]);

  // Cập nhật dropdown Tầng dựa theo Dãy
  useEffect(() => {
    if (!buildingId) { setFilterFloors([]); setFloorId(''); return; }
    setFilterFloors(allFloors.filter(f => f.building_id === buildingId));
  }, [buildingId, allFloors]);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      if (mode === 'expiring') {
        const res = await api.get<Page<ContractOut>>(
          `/api/v1/contracts/expiring?within_days=${withinDays}&page=${page}&page_size=${pageSize}`,
        );
        setData(res);
      } else {
        const q = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
        if (status) q.set('status', status);
        if (roomId) q.set('room_id', roomId);
        
        const res = await api.get<Page<ContractOut>>(`/api/v1/contracts?${q.toString()}`);
        setData(res);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được hợp đồng.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, status, roomId, mode, withinDays]);

  useEffect(() => { load(); }, [load]);

  const filteredItems = (data?.items ?? []).filter(c => {
    if (!propertyId && !buildingId && !floorId) return true;
    const room = allRooms.find(r => r.id === c.room_id);
    if (!room) return false;
    
    if (propertyId && room.property_id !== propertyId) return false;
    if (floorId && room.floor_id !== floorId) return false;
    if (buildingId) {
      const floor = allFloors.find(f => f.id === room.floor_id);
      if (floor && floor.building_id !== buildingId) return false;
    }
    return true;
  });

  const availableRooms = allRooms.filter(r => {
    if (floorId) return r.floor_id === floorId;
    if (buildingId) {
      const floor = allFloors.find(f => f.id === r.floor_id);
      return floor?.building_id === buildingId;
    }
    if (propertyId) return r.property_id === propertyId;
    return true;
  });

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Hợp đồng</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-secondary" onClick={() => navigate(-1)}>← Quay lại</button>
          <Link to="/hop-dong/tao-moi" className="btn-primary" style={{ textDecoration: 'none' }}>Tạo hợp đồng mới</Link>
        </div>
      </div>

      <div className="filter-bar" style={{ flexWrap: 'wrap' }}>
        <select value={mode} onChange={(e) => { setMode(e.target.value as 'all' | 'expiring'); setPage(1); }}>
          <option value="all">Tất cả hợp đồng</option>
          <option value="expiring">Sắp hết hạn</option>
        </select>

        {mode === 'all' && (
          <>
            <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">Mọi trạng thái</option>
              <option value="DRAFT">Nháp</option>
              <option value="SCHEDULED">Đã lên lịch</option>
              <option value="ACTIVE">Đang hiệu lực</option>
              <option value="EXPIRED_PENDING">Chờ bàn giao</option>
              <option value="ENDED">Đã kết thúc</option>
              <option value="CANCELLED">Đã hủy</option>
            </select>

            <select value={propertyId} onChange={(e) => { 
              setPropertyId(e.target.value); 
              setBuildingId(''); setFloorId(''); setRoomId(''); setPage(1); 
            }}>
              <option value="">Tất cả Khu trọ</option>
              {properties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>

            <select value={buildingId} onChange={(e) => { 
              setBuildingId(e.target.value); 
              setFloorId(''); setRoomId(''); setPage(1); 
            }} disabled={!propertyId}>
              <option value="">Tất cả Dãy</option>
              {filterBuildings.map(b => <option key={b.id} value={b.id}>Dãy {b.name}</option>)}
            </select>

            <select value={floorId} onChange={(e) => { 
              setFloorId(e.target.value); 
              setRoomId(''); setPage(1); 
            }} disabled={!buildingId}>
              <option value="">Tất cả Tầng</option>
              {filterFloors.map(f => <option key={f.id} value={f.id}>Tầng {f.floor_number}{f.name ? ` - ${f.name}` : ''}</option>)}
            </select>

            <select value={roomId} onChange={(e) => { setRoomId(e.target.value); setPage(1); }} disabled={!propertyId}>
              <option value="">Tất cả Phòng</option>
              {availableRooms.map(r => <option key={r.id} value={r.id}>{r.room_code}</option>)}
            </select>
          </>
        )}

        {mode === 'expiring' && (
          <select value={withinDays} onChange={(e) => { setWithinDays(Number(e.target.value)); setPage(1); }}>
            <option value={7}>Trong 7 ngày</option>
            <option value={14}>Trong 14 ngày</option>
            <option value={30}>Trong 30 ngày</option>
            <option value={90}>Trong 90 ngày</option>
          </select>
        )}
      </div>

      <PageState loading={loading} error={error} empty={!loading && !error && filteredItems.length === 0} emptyText="Không có hợp đồng." onRetry={load}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Mã HĐ</th>
              <th>Khu trọ</th>
              <th>Dãy</th>
              <th>Tầng</th>
              <th>Phòng</th>
              <th>Thời hạn</th>
              <th>Trạng thái</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((c) => {
              // Tìm từ mảng ALL để đảm bảo luôn có dữ liệu
              const room = allRooms.find(r => r.id === c.room_id);
              const prop = properties.find(p => p.id === room?.property_id);
              const floor = allFloors.find(f => f.id === room?.floor_id);
              const building = allBuildings.find(b => b.id === floor?.building_id);

              return (
                <tr key={c.id}>
                  <td style={{ fontWeight: 'bold' }}>{c.contract_code}</td>
                  <td>{prop ? prop.name : '—'}</td>
                  <td>{building ? building.name : '—'}</td>
                  <td>
  {floor ? (
    <>
      {floor.floor_number}
      {floor.name ? ` - ${floor.name}` : ''}
    </>
  ) : '—'}
</td>
                  <td style={{ fontWeight: 'bold', color: 'var(--cinnabar-2)' }}>
                    {room?.room_code || c.room_code_snapshot}
                  </td>
                  <td>
                    <div style={{ fontSize: 13 }}>{formatDateVi(c.start_date)}</div>
                    <div style={{ fontSize: 13, color: 'var(--ink-soft)' }}>đến {formatDateVi(c.end_date)}</div>
                  </td>
                  <td><Badge value={c.status} /></td>
                  <td>
                    <Link to={`/hop-dong/${c.id}`} style={{ color: 'var(--gold-2)', fontWeight: 'bold', textDecoration: 'underline' }}>
                      Chi tiết
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {data && <Pagination page={data.meta.page} pageSize={data.meta.page_size} total={data.meta.total} onPageChange={setPage} />}
      </PageState>
    </div>
  );
}