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
    setSubmitting(true); setFormError(null);
    try {
      const body = { floor_number: n, name: floorForm.name.trim() || null };
      if (floorForm.editing) {
        await api.patch(`/api/v1/floors/${floorForm.editing.id}`, body);
      } else {
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

  async function doDeactivate() {
    if (!confirm) return;
    setConfirmLoading(true);
    try {
      if (confirm.kind === 'building') await api.delete(`/api/v1/buildings/${confirm.id}`);
      else await api.delete(`/api/v1/floors/${confirm.id}`);
      setConfirm(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Không thể vô hiệu hóa.');
    } finally {
      setConfirmLoading(false);
    }
  }

  return (
    <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="room-modal" style={{ width: 'min(900px, 96vw)', maxHeight: '90vh', overflowY: 'auto' }}>
        <button className="modal-close" onClick={onClose}>×</button>
        <div className="modal-eyebrow">Cấu trúc</div>
        <h2 className="modal-title">{property.name}</h2>
        <p className="text-muted" style={{ marginBottom: 16 }}>{property.address}</p>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
          <button className="btn-secondary" onClick={() => { setBuildingForm({ open: true, editing: null, name: '' }); setFormError(null); }}>
            + Thêm dãy
          </button>
        </div>

        <PageState loading={loading} error={error} empty={!loading && !error && buildings.length === 0} emptyText="Chưa có dãy nào." onRetry={load}>
          {buildings.map((b) => (
            <div key={b.id} style={{ border: '1px solid var(--gold-3)', padding: 16, marginBottom: 16 }}>
              <div className="building-header">
                {/* Dãy mặc định + Tên bạn đặt */}
                <strong className="building-title">Dãy {b.name}</strong>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button className="btn-secondary" onClick={() => { setFloorForm({ open: true, buildingId: b.id, editing: null, floor_number: '1', name: '' }); setFormError(null); }}>+ Tầng</button>
                  <button className="btn-secondary" onClick={() => { setBuildingForm({ open: true, editing: b, name: b.name }); setFormError(null); }}>Sửa</button>
                  {b.status === 'ACTIVE' && (
                    <button className="btn-secondary" style={{ color: 'var(--cinnabar-3)' }} onClick={() => setConfirm({ kind: 'building', id: b.id, name: b.name })}>Vô hiệu hóa</button>
                  )}
                </div>
              </div>

              {(floorsByBuilding[b.id] ?? []).length === 0 && (
                <p className="text-muted" style={{ fontSize: 13, marginTop: 8 }}>Chưa có tầng.</p>
              )}

              {(floorsByBuilding[b.id] ?? []).map((f) => {
                const roomsInFloor = roomsByFloor[f.id] || [];
                return (
                  <div key={f.id} style={{ padding: '12px 0', borderTop: '1px dashed var(--gold-3)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      {/* Tầng mặc định + Tên bạn đặt */}
                      <span style={{ fontWeight: 'bold' }}>
                        Tầng {f.floor_number}{f.name ? ` — ${f.name}` : ''}
                      </span>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button className="btn-secondary" onClick={() => setBulkRoomFloorId(f.id)}>+ Phòng</button>
                        <button className="btn-secondary" onClick={() => { setFloorForm({ open: true, buildingId: b.id, editing: f, floor_number: String(f.floor_number), name: f.name ?? '' }); setFormError(null); }}>Sửa</button>
                        {f.status === 'ACTIVE' && (
                          <button className="btn-secondary" style={{ color: 'var(--cinnabar-3)' }} onClick={() => setConfirm({ kind: 'floor', id: f.id, name: `tầng ${f.floor_number} dãy ${b.name}` })}>Vô hiệu hóa</button>
                        )}
                      </div>
                    </div>
                    
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {roomsInFloor.length === 0 && <span className="text-muted" style={{ fontSize: 12 }}>Chưa có phòng.</span>}
                      {roomsInFloor.map(room => (
                        <div 
                          key={room.id} 
                          style={{ 
                            padding: '6px 12px', 
                            border: '1px solid var(--gold-3)', 
                            borderRadius: 4, 
                            fontSize: 13, 
                            background: room.display_occupancy === 'OCCUPIED' ? 'rgba(232, 71, 43, 0.1)' : 'rgba(61, 138, 122, 0.1)',
                            color: room.display_occupancy === 'OCCUPIED' ? 'var(--cinnabar-3)' : 'var(--jade-hi)'
                          }}
                          title={room.display_occupancy === 'OCCUPIED' ? 'Đang thuê' : 'Trống'}
                        >
                          {room.room_code}
                        </div>
                      ))}
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
                <div className="login-field">
                  <label>Số tầng * (-5..200)</label>
                  <input type="number" value={floorForm.floor_number} onChange={(e) => setFloorForm({ ...floorForm, floor_number: e.target.value })} required />
                </div>
                <div className="login-field">
                  <label>Tên (tùy chọn)</label>
                  <input value={floorForm.name} onChange={(e) => setFloorForm({ ...floorForm, name: e.target.value })} />
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
            message={`Sẽ chuyển "${confirm.name}" sang INACTIVE. Chỉ thành công khi không còn phần tử con ACTIVE.`}
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