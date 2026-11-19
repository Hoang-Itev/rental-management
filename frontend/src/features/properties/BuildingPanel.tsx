import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type { Page, PropertyOut, RoomOut } from '../../lib/api/types';
import { PageState } from '../../components/PageState';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { BulkRoomModal } from '../rooms/BulkRoomModal';

interface Building { id: string; property_id: string; name: string; status: 'ACTIVE' | 'INACTIVE'; }
interface Floor { id: string; building_id: string; floor_number: number; name: string | null; status: 'ACTIVE' | 'INACTIVE'; }

interface Props {
  property: PropertyOut;
  onClose: () => void;
}

export function BuildingPanel({ property, onClose }: Props) {
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [floorsByBuilding, setFloorsByBuilding] = useState<Record<string, Floor[]>>({});
  const [roomsByFloor, setRoomsByFloor] = useState<Record<string, RoomOut[]>>({});
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [buildingForm, setBuildingForm] = useState<{ open: boolean; editing: Building | null; name: string }>({ open: false, editing: null, name: '' });
  const [floorForm, setFloorForm] = useState<{ open: boolean; buildingId: string | null; editing: Floor | null; floor_number: string; name: string }>({ open: false, buildingId: null, editing: null, floor_number: '1', name: '' });
  const [bulkRoomFloorId, setBulkRoomFloorId] = useState<string | null>(null);
  
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ kind: 'building' | 'floor'; id: string; name: string } | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await api.get<Page<Building>>(`/api/v1/properties/${property.id}/buildings?page=1&page_size=100`);
      setBuildings(res.items);
      
      const fMap: Record<string, Floor[]> = {};
      const rMap: Record<string, RoomOut[]> = {};

      const allRooms = await api.get<Page<RoomOut>>(`/api/v1/rooms?property_id=${property.id}&page_size=100`);
      allRooms.items.forEach(room => {
        if (!rMap[room.floor_id]) rMap[room.floor_id] = [];
        rMap[room.floor_id].push(room);
      });

      await Promise.all(res.items.map(async (b) => {
        const floors = await api.get<Page<Floor>>(`/api/v1/buildings/${b.id}/floors?page=1&page_size=100`);
        fMap[b.id] = floors.items;
      }));
      
      setFloorsByBuilding(fMap);
      setRoomsByFloor(rMap);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được cấu trúc.');
    } finally {
      setLoading(false);
    }
  }, [property.id]);

  useEffect(() => { load(); }, [load]);

  async function submitBuilding(e: React.FormEvent) {
    e.preventDefault();
    if (!buildingForm.name.trim()) { setFormError('Tên dãy là bắt buộc.'); return; }
    setSubmitting(true); setFormError(null);
    try {
      if (buildingForm.editing) {
        await api.patch(`/api/v1/buildings/${buildingForm.editing.id}`, { name: buildingForm.name.trim() });
      } else {
        await api.post(`/api/v1/properties/${property.id}/buildings`, { name: buildingForm.name.trim() });
      }
      setBuildingForm({ open: false, editing: null, name: '' });
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Lỗi khi lưu dãy.');
    } finally {
      setSubmitting(false);
    }
  }

  async function submitFloor(e: React.FormEvent) {
    e.preventDefault();
    const n = Number(floorForm.floor_number);
    if (!Number.isFinite(n) || n < -5 || n > 200) { setFormError('Số tầng phải trong khoảng -5..200.'); return; }
    
    // Check trùng tên tầng ở Frontend (nếu có nhập tên)
    if (floorForm.name.trim()) {
      const currentBuildingFloors = floorsByBuilding[floorForm.buildingId!] || [];
      const isDuplicate = currentBuildingFloors.some(
        f => f.id !== floorForm.editing?.id && f.name?.toLowerCase() === floorForm.name.trim().toLowerCase()
      );
      if (isDuplicate) {
        setFormError('Tên tầng này đã tồn tại trong dãy. Vui lòng chọn tên khác.');
        return;
      }
    }

    setSubmitting(true); setFormError(null);
    try {
      if (floorForm.editing) {
        // KHI SỬA: Chỉ gửi mỗi name
        const body = { name: floorForm.name.trim() === '' ? null : floorForm.name.trim() };
        await api.patch(`/api/v1/floors/${floorForm.editing.id}`, body);
      } else {
        // KHI TẠO MỚI
        const body: any = { floor_number: n };
        if (floorForm.name.trim() !== '') body.name = floorForm.name.trim();
        await api.post(`/api/v1/buildings/${floorForm.buildingId}/floors`, body);
      }
      setFloorForm({ open: false, buildingId: null, editing: null, floor_number: '1', name: '' });
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Lỗi khi lưu tầng.');
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleStatus(kind: 'building' | 'floor', id: string, currentStatus: string) {
    if (currentStatus === 'ACTIVE') {
      setConfirm({ kind, id, name: kind === 'building' ? buildings.find(b => b.id === id)?.name || '' : `tầng ${floorsByBuilding[Object.keys(floorsByBuilding).find(k => floorsByBuilding[k].some(f => f.id === id)) || '']?.find(f => f.id === id)?.floor_number}` });
    } else {
      setConfirmLoading(true);
      try {
        const url = kind === 'building' ? `/api/v1/buildings/${id}` : `/api/v1/floors/${id}`;
        await api.patch(url, { status: 'ACTIVE' });
        await load();
      } catch (err) {
        alert(err instanceof ApiError ? err.message : 'Không thể mở lại.');
      } finally {
        setConfirmLoading(false);
      }
    }
  }

  async function doDeactivate() {
    if (!confirm) return;
    setConfirmLoading(true);
    try {
      const url = confirm.kind === 'building' ? `/api/v1/buildings/${confirm.id}` : `/api/v1/floors/${confirm.id}`;
      await api.delete(url);
      setConfirm(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Không thể vô hiệu hóa.');
    } finally {
      setConfirmLoading(false);
    }
  }

  return (
    <div className="modal-backdrop active" style={{ zIndex: 9999 }} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="room-modal" style={{ width: 'min(900px, 96vw)', maxHeight: '90vh', overflowY: 'auto' }}>
        <button className="modal-close" onClick={onClose}>×</button>
        <div className="modal-eyebrow">Cấu trúc</div>
        <h2 className="modal-title">{property.name}</h2>
        <p className="text-muted" style={{ marginBottom: 16 }}>{property.address}</p>

        {error && (
          <div className="login-error" style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{error}</span>
            <button className="btn-secondary" onClick={() => setError(null)}>Đóng</button>
          </div>
        )}

        {!error && (
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
            <button className="btn-secondary" onClick={() => { setBuildingForm({ open: true, editing: null, name: '' }); setFormError(null); }}>
              + Thêm dãy
            </button>
          </div>
        )}

        <PageState loading={loading} error={null} empty={!loading && buildings.length === 0} emptyText="Chưa có dãy nào." onRetry={load}>
          {buildings.map((b) => (
            <div key={b.id} style={{ border: '1px solid var(--gold-3)', padding: 16, marginBottom: 16, opacity: b.status === 'INACTIVE' ? 0.6 : 1 }}>
              <div className="building-header">
                <strong className="building-title">Dãy {b.name}</strong>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button className="btn-secondary" disabled={b.status === 'INACTIVE'} onClick={() => { setFloorForm({ open: true, buildingId: b.id, editing: null, floor_number: '1', name: '' }); setFormError(null); }}>+ Tầng</button>
                  <button className="btn-secondary" onClick={() => { setBuildingForm({ open: true, editing: b, name: b.name }); setFormError(null); }}>Sửa</button>
                  <button className="btn-secondary" style={{ color: b.status === 'ACTIVE' ? 'var(--cinnabar-3)' : 'var(--jade-hi)' }} onClick={() => toggleStatus('building', b.id, b.status)}>
                    {b.status === 'ACTIVE' ? 'Vô hiệu hóa' : 'Mở lại'}
                  </button>
                </div>
              </div>

              {(floorsByBuilding[b.id] ?? []).length === 0 && (
                <p className="text-muted" style={{ fontSize: 13, marginTop: 8 }}>Chưa có tầng.</p>
              )}

              {(floorsByBuilding[b.id] ?? []).map((f) => {
                const roomsInFloor = roomsByFloor[f.id] || [];
                return (
                  <div key={f.id} style={{ padding: '12px 0', borderTop: '1px dashed var(--gold-3)', opacity: f.status === 'INACTIVE' ? 0.6 : 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <span style={{ fontWeight: 'bold' }}>
                        Tầng {f.floor_number}{f.name ? ` — ${f.name}` : ''}
                      </span>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button className="btn-secondary" disabled={f.status === 'INACTIVE'} onClick={() => setBulkRoomFloorId(f.id)}>+ Phòng</button>
                        <button className="btn-secondary" onClick={() => { setFloorForm({ open: true, buildingId: b.id, editing: f, floor_number: String(f.floor_number), name: f.name ?? '' }); setFormError(null); }}>Sửa</button>
                        <button className="btn-secondary" style={{ color: f.status === 'ACTIVE' ? 'var(--cinnabar-3)' : 'var(--jade-hi)' }} onClick={() => toggleStatus('floor', f.id, f.status)}>
                          {f.status === 'ACTIVE' ? 'Vô hiệu hóa' : 'Mở lại'}
                        </button>
                      </div>
                    </div>
                    
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {roomsInFloor.length === 0 && <span className="text-muted" style={{ fontSize: 12 }}>Chưa có phòng.</span>}
                      {roomsInFloor.map(room => {
                        const isOccupied = room.display_occupancy === 'OCCUPIED';
                        const isInactive = room.display_occupancy === 'INACTIVE' || room.status === 'INACTIVE';
                        
                        const bgColor = isOccupied ? 'rgba(232, 71, 43, 0.1)' : isInactive ? 'rgba(138, 122, 90, 0.1)' : 'rgba(61, 138, 122, 0.1)';
                        const textColor = isOccupied ? 'var(--cinnabar-3)' : isInactive ? 'var(--stone-2)' : 'var(--jade-hi)';
                        const borderColor = isOccupied ? '1px solid var(--cinnabar-2)' : isInactive ? '1px dashed var(--stone-2)' : '1px solid var(--jade-2)';

                        return (
                          <div 
                            key={room.id} 
                            style={{ padding: '6px 12px', border: borderColor, borderRadius: 4, fontSize: 13, background: bgColor, color: textColor }}
                            title={isOccupied ? 'Đang thuê' : isInactive ? 'Ngừng sử dụng' : 'Trống'}
                          >
                            {room.room_code}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </PageState>

        {/* MODAL THÊM/SỬA DÃY */}
        {buildingForm.open && (
          <div className="modal-backdrop active" style={{ zIndex: 10000 }} onClick={(e) => e.target === e.currentTarget && setBuildingForm({ open: false, editing: null, name: '' })}>
            <div className="room-modal" style={{ width: 420 }}>
              <button className="modal-close" onClick={() => setBuildingForm({ open: false, editing: null, name: '' })}>×</button>
              <h2 className="modal-title">{buildingForm.editing ? 'Sửa dãy' : 'Thêm dãy'}</h2>
              {formError && <div className="login-error">{formError}</div>}
              <form onSubmit={submitBuilding}>
                <div className="login-field">
                  <label>Tên dãy *</label>
                  <input value={buildingForm.name} onChange={(e) => setBuildingForm({ ...buildingForm, name: e.target.value })} required />
                </div>
                <div className="modal-actions">
                  <button type="button" className="modal-btn" onClick={() => setBuildingForm({ open: false, editing: null, name: '' })} disabled={submitting}>Hủy</button>
                  <button type="submit" className="modal-btn primary" disabled={submitting}>{submitting ? 'Đang lưu…' : 'Lưu'}</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL THÊM/SỬA TẦNG */}
        {floorForm.open && (
          <div className="modal-backdrop active" style={{ zIndex: 10000 }} onClick={(e) => e.target === e.currentTarget && setFloorForm({ open: false, buildingId: null, editing: null, floor_number: '1', name: '' })}>
            <div className="room-modal" style={{ width: 420 }}>
              <button className="modal-close" onClick={() => setFloorForm({ open: false, buildingId: null, editing: null, floor_number: '1', name: '' })}>×</button>
              <h2 className="modal-title">{floorForm.editing ? 'Sửa tầng' : 'Thêm tầng'}</h2>
              {formError && <div className="login-error">{formError}</div>}
              <form onSubmit={submitFloor}>
                
                {/* ẨN Ô SỐ TẦNG KHI SỬA */}
                {!floorForm.editing && (
                  <div className="login-field">
                    <label>Số tầng *</label>
                    <input type="number" value={floorForm.floor_number} onChange={(e) => setFloorForm({ ...floorForm, floor_number: e.target.value })} required />
                  </div>
                )}

                <div className="login-field">
                  <label>Tên (tùy chọn)</label>
                  <input value={floorForm.name} onChange={(e) => setFloorForm({ ...floorForm, name: e.target.value })} placeholder="VD: Tầng trệt, Tầng lửng..." />
                </div>
                <div className="modal-actions">
                  <button type="button" className="modal-btn" onClick={() => setFloorForm({ open: false, buildingId: null, editing: null, floor_number: '1', name: '' })} disabled={submitting}>Hủy</button>
                  <button type="submit" className="modal-btn primary" disabled={submitting}>{submitting ? 'Đang lưu…' : 'Lưu'}</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL THÊM PHÒNG HÀNG LOẠT */}
        {bulkRoomFloorId && (
          <BulkRoomModal
            floorId={bulkRoomFloorId}
            onClose={() => setBulkRoomFloorId(null)}
            onSuccess={() => { setBulkRoomFloorId(null); load(); }}
          />
        )}

        {/* CONFIRM DIALOG */}
        {confirm && (
          <ConfirmDialog
            title="Vô hiệu hóa?"
            message={`Hệ thống sẽ chuyển "${confirm.name}" và TOÀN BỘ phòng bên trong sang trạng thái Ngừng. Chỉ thực hiện được khi không có phòng nào đang cho thuê.`}
            confirmLabel="Vô hiệu hóa"
            variant="danger"
            loading={confirmLoading}
            onCancel={() => setConfirm(null)}
            onConfirm={doDeactivate}
          />
        )}
      </div>
    </div>
  );
}