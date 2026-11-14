import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type { Page, PropertyOut } from '../../lib/api/types';
import { PageState } from '../../components/PageState';
import { ConfirmDialog } from '../../components/ConfirmDialog';

interface Building {
  id: string;
  property_id: string;
  name: string;
  status: 'ACTIVE' | 'INACTIVE';
}

interface Floor {
  id: string;
  building_id: string;
  floor_number: number;
  name: string | null;
  status: 'ACTIVE' | 'INACTIVE';
}

interface Props {
  property: PropertyOut;
  onClose: () => void;
}

export function BuildingPanel({ property, onClose }: Props) {
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [floorsByBuilding, setFloorsByBuilding] = useState<Record<string, Floor[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [buildingForm, setBuildingForm] = useState<{ open: boolean; editing: Building | null; name: string }>({
    open: false, editing: null, name: '',
  });
  const [floorForm, setFloorForm] = useState<{ open: boolean; buildingId: string | null; editing: Floor | null; floor_number: string; name: string }>({
    open: false, buildingId: null, editing: null, floor_number: '1', name: '',
  });
  const [roomForm, setRoomForm] = useState<{ open: boolean; floorId: string | null; rooms: { room_code: string; area_m2: string; listed_rent: string }[] }>({
    open: false, floorId: null, rooms: [{ room_code: '', area_m2: '20', listed_rent: '2000000' }],
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ kind: 'building' | 'floor'; id: string; name: string } | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<Page<Building>>(
        `/api/v1/properties/${property.id}/buildings?page=1&page_size=100`,
      );
      setBuildings(res.items);
      const map: Record<string, Floor[]> = {};
      await Promise.all(res.items.map(async (b) => {
        const f = await api.get<Page<Floor>>(`/api/v1/buildings/${b.id}/floors?page=1&page_size=100`);
        map[b.id] = f.items;
      }));
      setFloorsByBuilding(map);
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

  async function submitRooms(e: React.FormEvent) {
    e.preventDefault();
    if (!roomForm.floorId) return;
    const rooms = roomForm.rooms
      .map((r) => ({ room_code: r.room_code.trim(), area_m2: r.area_m2.trim(), listed_rent: Number(r.listed_rent) }))
      .filter((r) => r.room_code);
    if (rooms.length === 0) { setFormError('Cần ít nhất một mã phòng.'); return; }
    const seen = new Set<string>();
    for (const r of rooms) {
      if (!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(r.room_code)) {
        setFormError(`Mã phòng không hợp lệ: ${r.room_code}`);
        return;
      }
      if (seen.has(r.room_code.toUpperCase())) { setFormError(`Mã phòng trùng: ${r.room_code}`); return; }
      seen.add(r.room_code.toUpperCase());
      if (!(Number(r.area_m2) > 0)) { setFormError(`Diện tích phải > 0: ${r.room_code}`); return; }
      if (!(Number.isInteger(r.listed_rent) && r.listed_rent >= 0)) { setFormError(`Giá thuê không hợp lệ: ${r.room_code}`); return; }
    }
    setSubmitting(true); setFormError(null);
    try {
      await api.postIdempotent(
        `/api/v1/floors/${roomForm.floorId}/rooms/bulk`,
        { rooms },
      );
      setRoomForm({ open: false, floorId: null, rooms: [{ room_code: '', area_m2: '20', listed_rent: '2000000' }] });
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Lỗi khi tạo phòng.');
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

        <PageState
          loading={loading}
          error={error}
          empty={!loading && !error && buildings.length === 0}
          emptyText="Chưa có dãy nào."
          onRetry={load}
        >
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
            <button
              className="btn-secondary"
              onClick={() => { setBuildingForm({ open: true, editing: null, name: '' }); setFormError(null); }}
            >
              + Thêm dãy
            </button>
          </div>

          {buildings.map((b) => (
            <div key={b.id} style={{ border: '1px solid var(--gold-3)', padding: 16, marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <strong style={{ color: 'var(--gold-2)' }}>Dãy {b.name}</strong>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button className="btn-secondary" onClick={() => { setFloorForm({ open: true, buildingId: b.id, editing: null, floor_number: '1', name: '' }); setFormError(null); }}>
                    + Tầng
                  </button>
                  <button className="btn-secondary" onClick={() => { setBuildingForm({ open: true, editing: b, name: b.name }); setFormError(null); }}>Sửa</button>
                  {b.status === 'ACTIVE' && (
                    <button className="btn-secondary" style={{ color: 'var(--cinnabar-3)' }} onClick={() => setConfirm({ kind: 'building', id: b.id, name: b.name })}>Vô hiệu hóa</button>
                  )}
                </div>
              </div>

              {(floorsByBuilding[b.id] ?? []).length === 0 && (
                <p className="text-muted" style={{ fontSize: 13 }}>Chưa có tầng.</p>
              )}

              {(floorsByBuilding[b.id] ?? []).map((f) => (
                <div key={f.id} style={{ padding: '8px 0', borderTop: '1px dashed var(--gold-3)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>Tầng {f.floor_number}{f.name ? ` — ${f.name}` : ''}</span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button className="btn-secondary" onClick={() => { setRoomForm({ open: true, floorId: f.id, rooms: [{ room_code: '', area_m2: '20', listed_rent: '2000000' }] }); setFormError(null); }}>
                        + Phòng
                      </button>
                      <button className="btn-secondary" onClick={() => { setFloorForm({ open: true, buildingId: b.id, editing: f, floor_number: String(f.floor_number), name: f.name ?? '' }); setFormError(null); }}>Sửa</button>
                      {f.status === 'ACTIVE' && (
                        <button className="btn-secondary" style={{ color: 'var(--cinnabar-3)' }} onClick={() => setConfirm({ kind: 'floor', id: f.id, name: `tầng ${f.floor_number} dãy ${b.name}` })}>Vô hiệu hóa</button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </PageState>

        {buildingForm.open && (
          <div className="modal-backdrop active" style={{ position: 'fixed' }} onClick={(e) => e.target === e.currentTarget && setBuildingForm({ open: false, editing: null, name: '' })}>
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

        {floorForm.open && (
          <div className="modal-backdrop active" style={{ position: 'fixed' }} onClick={(e) => e.target === e.currentTarget && setFloorForm({ open: false, buildingId: null, editing: null, floor_number: '1', name: '' })}>
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

        {roomForm.open && (
          <div className="modal-backdrop active" style={{ position: 'fixed' }} onClick={(e) => e.target === e.currentTarget && setRoomForm({ open: false, floorId: null, rooms: [{ room_code: '', area_m2: '20', listed_rent: '2000000' }] })}>
            <div className="room-modal" style={{ width: 640 }}>
              <button className="modal-close" onClick={() => setRoomForm({ open: false, floorId: null, rooms: [{ room_code: '', area_m2: '20', listed_rent: '2000000' }] })}>×</button>
              <h2 className="modal-title">Thêm phòng (tối đa 100)</h2>
              {formError && <div className="login-error">{formError}</div>}
              <form onSubmit={submitRooms}>
                {roomForm.rooms.map((r, idx) => (
                  <div key={idx} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 8, marginBottom: 8 }}>
                    <input placeholder="Mã phòng (VD A101)" value={r.room_code} onChange={(e) => {
                      const rooms = [...roomForm.rooms];
                      rooms[idx] = { ...rooms[idx], room_code: e.target.value };
                      setRoomForm({ ...roomForm, rooms });
                    }} required />
                    <input type="number" step="0.01" min="0.01" placeholder="Diện tích m²" value={r.area_m2} onChange={(e) => {
                      const rooms = [...roomForm.rooms];
                      rooms[idx] = { ...rooms[idx], area_m2: e.target.value };
                      setRoomForm({ ...roomForm, rooms });
                    }} required />
                    <input type="number" min="0" step="1000" placeholder="Giá niêm yết" value={r.listed_rent} onChange={(e) => {
                      const rooms = [...roomForm.rooms];
                      rooms[idx] = { ...rooms[idx], listed_rent: e.target.value };
                      setRoomForm({ ...roomForm, rooms });
                    }} required />
                    <button type="button" className="btn-secondary" onClick={() => {
                      setRoomForm({ ...roomForm, rooms: roomForm.rooms.filter((_, i) => i !== idx) });
                    }} disabled={roomForm.rooms.length <= 1}>X</button>
                  </div>
                ))}
                <button type="button" className="btn-secondary" onClick={() => setRoomForm({ ...roomForm, rooms: [...roomForm.rooms, { room_code: '', area_m2: '20', listed_rent: '2000000' }] })} disabled={roomForm.rooms.length >= 100}>
                  + Thêm dòng
                </button>
                <div className="modal-actions" style={{ marginTop: 20 }}>
                  <button type="button" className="modal-btn" onClick={() => setRoomForm({ open: false, floorId: null, rooms: [{ room_code: '', area_m2: '20', listed_rent: '2000000' }] })} disabled={submitting}>Hủy</button>
                  <button type="submit" className="modal-btn primary" disabled={submitting}>{submitting ? 'Đang tạo…' : 'Tạo phòng'}</button>
                </div>
              </form>
            </div>
          </div>
        )}

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