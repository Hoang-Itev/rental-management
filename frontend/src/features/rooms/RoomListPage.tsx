import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { Page, RoomOut, PropertyOut } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';
import { SearchBar } from '../../components/SearchBar';
import { PageState } from '../../components/PageState';
import { RoomModal } from './RoomModal';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { formatVnd } from '../../lib/utils/format';

interface Building { id: string; name: string; property_id: string; }
interface Floor { id: string; floor_number: number; building_id: string; name: string | null; }

export function RoomListPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<Page<RoomOut> | null>(null);
  const [properties, setProperties] = useState<PropertyOut[]>([]);
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [floors, setFloors] = useState<Floor[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState('');
  const [occupancy, setOccupancy] = useState('');
  const [propertyId, setPropertyId] = useState('');
  const [buildingId, setBuildingId] = useState('');
  const [floorId, setFloorId] = useState('');
  
  const [selectedRoom, setSelectedRoom] = useState<RoomOut | null>(null);
  const [roomLocation, setRoomLocation] = useState<string>('');
  
  const [confirmInactive, setConfirmInactive] = useState<RoomOut | null>(null);
  const [deactivating, setDeactivating] = useState(false);

  useEffect(() => {
    api.get<Page<PropertyOut>>('/api/v1/properties?page_size=100')
      .then(res => setProperties(res.items))
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!propertyId) { setBuildings([]); setBuildingId(''); return; }
    api.get<Page<Building>>(`/api/v1/properties/${propertyId}/buildings?page_size=100`)
      .then(res => setBuildings(res.items))
      .catch(console.error);
  }, [propertyId]);

  useEffect(() => {
    if (!buildingId) { setFloors([]); setFloorId(''); return; }
    api.get<Page<Floor>>(`/api/v1/buildings/${buildingId}/floors?page_size=100`)
      .then(res => setFloors(res.items))
      .catch(console.error);
  }, [buildingId]);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const q = new URLSearchParams({ page: String(page), page_size: '100' });
      if (status) q.set('status', status);
      if (occupancy) q.set('occupancy', occupancy);
      if (propertyId) q.set('property_id', propertyId);
      
      const res = await api.get<Page<RoomOut>>(`/api/v1/rooms?${q.toString()}`);
      setData(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được danh sách phòng.');
    } finally {
      setLoading(false);
    }
  }, [page, status, occupancy, propertyId]);

  useEffect(() => { load(); }, [load]);

  const visibleItems = (data?.items ?? []).filter((r) => {
    if (keyword && !r.room_code.toLowerCase().includes(keyword.toLowerCase())) return false;
    if (floorId && r.floor_id !== floorId) return false;
    return true;
  });

  async function handleViewDetail(room: RoomOut) {
    setSelectedRoom(room);
    setRoomLocation('Đang tải...');
    try {
      const prop = properties.find(p => p.id === room.property_id);
      const propName = prop ? prop.name : 'Khu trọ';
      
      const floorRes = await api.get<Floor>(`/api/v1/floors/${room.floor_id}`);
      let buildingName = '';
      
      if (floorRes.building_id) {
        const b = buildings.find(x => x.id === floorRes.building_id);
        if (b) buildingName = b.name;
        else {
          try {
            const bRes = await api.get<Building>(`/api/v1/buildings/${floorRes.building_id}`);
            buildingName = bRes.name;
          } catch {}
        }
      }

      const floorName = floorRes.name ? ` - ${floorRes.name}` : '';
      const location = [
        propName, 
        buildingName ? `Dãy ${buildingName}` : '', 
        `Tầng ${floorRes.floor_number}${floorName}`
      ].filter(Boolean).join(' - ');
      
      setRoomLocation(location);
    } catch (e) {
      setRoomLocation('Không xác định được vị trí');
    }
  }

  async function doDeactivate() {
    if (!confirmInactive) return;
    setDeactivating(true);
    try {
      await api.delete(`/api/v1/rooms/${confirmInactive.id}`);
      setConfirmInactive(null);
      await load();
    } catch (err) {
      alert(err instanceof ApiError ? err.message : 'Không thể chuyển sang Ngừng.');
    } finally {
      setDeactivating(false);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Danh sách tất cả Phòng</h1>
      </div>

      <div className="filter-bar" style={{ flexWrap: 'wrap' }}>
        <SearchBar onSearch={setKeyword} placeholder="Tìm mã phòng..." />
        
        <select value={propertyId} onChange={(e) => { setPropertyId(e.target.value); setBuildingId(''); setFloorId(''); setPage(1); }}>
          <option value="">Tất cả khu trọ</option>
          {properties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>

        <select value={buildingId} onChange={(e) => { setBuildingId(e.target.value); setFloorId(''); setPage(1); }} disabled={!propertyId}>
          <option value="">Tất cả dãy</option>
          {buildings.map(b => <option key={b.id} value={b.id}>Dãy {b.name}</option>)}
        </select>

        <select value={floorId} onChange={(e) => { setFloorId(e.target.value); setPage(1); }} disabled={!buildingId}>
          <option value="">Tất cả tầng</option>
          {floors.map(f => <option key={f.id} value={f.id}>Tầng {f.floor_number}{f.name ? ` - ${f.name}` : ''}</option>)}
        </select>

        <select value={occupancy} onChange={(e) => { setOccupancy(e.target.value); setPage(1); }}>
          <option value="">Mọi tình trạng</option>
          <option value="VACANT">Trống</option>
          <option value="OCCUPIED">Đang thuê</option>
          <option value="INACTIVE">Ngừng</option>
        </select>
      </div>

      <PageState loading={loading} error={error} empty={!loading && !error && visibleItems.length === 0} emptyText="Không tìm thấy phòng nào." onRetry={load}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Mã phòng</th>
              <th>Diện tích</th>
              <th>Giá niêm yết</th>
              <th>Trạng thái</th>
              <th>Tình trạng</th>
              <th style={{ width: 320 }}>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {visibleItems.map((r) => (
              <tr key={r.id}>
                <td style={{ fontWeight: 'bold' }}>{r.room_code}</td>
                <td>{r.area_m2} m²</td>
                <td className="text-amount">{formatVnd(r.listed_rent)}</td>
                <td>{r.status === 'ACTIVE' ? 'Hoạt động' : 'Ngừng'}</td>
                <td>
                  <span style={{ 
                    fontWeight: 600,
                    color: r.display_occupancy === 'OCCUPIED' ? 'var(--cinnabar-3)' : r.display_occupancy === 'VACANT' ? 'var(--jade-2)' : 'var(--stone-2)'
                  }}>
                    {r.display_occupancy === 'OCCUPIED' ? 'Đang thuê' : r.display_occupancy === 'VACANT' ? 'Trống' : 'Ngừng'}
                  </span>
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button className="btn-secondary" onClick={() => handleViewDetail(r)}>Chi tiết</button>
                    
                    {r.status === 'ACTIVE' && r.display_occupancy === 'VACANT' && (
                      <>
                        <button className="btn-primary" style={{ padding: '4px 12px' }} onClick={() => navigate(`/hop-dong/tao-moi?room_id=${r.id}`)}>
                          Gán khách
                        </button>
                        <button className="btn-secondary" style={{ color: 'var(--cinnabar-3)', borderColor: 'var(--cinnabar-2)' }} onClick={() => setConfirmInactive(r)}>
                          Ngừng
                        </button>
                      </>
                    )}

                    {r.status === 'ACTIVE' && r.display_occupancy === 'OCCUPIED' && (
                      <button className="btn-secondary" style={{ color: 'var(--cinnabar-3)' }} onClick={() => navigate(`/hop-dong?room_id=${r.id}`)}>
                        Xem HĐ
                      </button>
                    )}
                    
                    {r.status === 'INACTIVE' && (
                      <button className="btn-secondary" onClick={async () => {
                        if(confirm('Mở lại phòng này?')) {
                          await api.patch(`/api/v1/rooms/${r.id}`, { status: 'ACTIVE' });
                          load();
                        }
                      }}>
                        Mở lại
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && <Pagination page={data.meta.page} pageSize={data.meta.page_size} total={data.meta.total} onPageChange={setPage} />}
      </PageState>

      {selectedRoom && (
        <RoomModal 
          room={selectedRoom} 
          locationName={roomLocation} 
          onClose={() => setSelectedRoom(null)} 
          onUpdate={() => { setSelectedRoom(null); load(); }}
        />
      )}

      {confirmInactive && (
        <ConfirmDialog
          title="Ngừng sử dụng phòng?"
          message={`Phòng ${confirmInactive.room_code} sẽ chuyển sang trạng thái INACTIVE (Ngừng). Bạn có thể mở lại sau.`}
          confirmLabel="Ngừng"
          variant="danger"
          loading={deactivating}
          onCancel={() => setConfirmInactive(null)}
          onConfirm={doDeactivate}
        />
      )}
    </div>
  );
}