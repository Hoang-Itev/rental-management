import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { RoomOut, TenantOut, Page, ContractOut, PropertyOut } from '../../lib/api/types';
import { PageState } from '../../components/PageState';
import { formatVnd } from '../../lib/utils/format';

interface Building { id: string; name: string; property_id: string; }
interface Floor { id: string; floor_number: number; building_id: string; name: string | null; }

interface FormState {
  contract_code: string;
  room_id: string;
  representative_tenant_id: string;
  start_date: string;
  end_date: string;
  monthly_rent: string;
  electricity_unit_price: string;
  water_unit_price: string;
  monthly_service_fee: string;
  deposit_amount: string; // <-- THÊM DÒNG NÀY
}

const initialForm: FormState = {
  contract_code: '',
  room_id: '',
  representative_tenant_id: '',
  start_date: '',
  end_date: '',
  monthly_rent: '2000000',
  electricity_unit_price: '3500',
  water_unit_price: '15000',
  monthly_service_fee: '100000',
  deposit_amount: '0', // <-- THÊM DÒNG NÀY
};

export function ContractWizardPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preSelectedRoomId = searchParams.get('room_id') || '';

  const [properties, setProperties] = useState<PropertyOut[]>([]);
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [floors, setFloors] = useState<Floor[]>([]);
  const [rooms, setRooms] = useState<RoomOut[]>([]);
  const [tenants, setTenants] = useState<TenantOut[]>([]);

  const [propertyId, setPropertyId] = useState('');
  const [buildingId, setBuildingId] = useState('');
  const [floorId, setFloorId] = useState('');

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [form, setForm] = useState<FormState>({
    ...initialForm,
    room_id: preSelectedRoomId,
  });

  useEffect(() => {
    async function loadOptions() {
      setLoading(true);
      setLoadError(null);
      try {
        const [propRes, roomRes, tenantRes, contractRes] = await Promise.all([
          api.get<Page<PropertyOut>>('/api/v1/properties?page_size=100'),
          api.get<Page<RoomOut>>('/api/v1/rooms?status=ACTIVE&occupancy=VACANT&page_size=100'),
          api.get<Page<TenantOut>>('/api/v1/tenants?page_size=100'),
          api.get<Page<ContractOut>>('/api/v1/contracts?page_size=100')
        ]);

        setProperties(propRes.items);
        setRooms(roomRes.items);

        const activeTenantIds = new Set(
          contractRes.items
            .filter(c => ['ACTIVE', 'SCHEDULED', 'EXPIRED_PENDING'].includes(c.status))
            .map(c => c.representative_tenant_id)
        );
        setTenants(tenantRes.items.filter(t => !activeTenantIds.has(t.id)));

        if (preSelectedRoomId) {
          const room = roomRes.items.find(r => r.id === preSelectedRoomId);
          if (room) {
            setPropertyId(room.property_id);
            setFloorId(room.floor_id);
          }
        }
      } catch (err) {
        setLoadError(err instanceof ApiError ? err.message : 'Không tải được danh sách.');
      } finally {
        setLoading(false);
      }
    }
    loadOptions();
  }, [preSelectedRoomId]);

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

  useEffect(() => {
    if (floorId && floors.length > 0 && !buildingId) {
      const f = floors.find(x => x.id === floorId);
      if (f) setBuildingId(f.building_id);
    }
  }, [floorId, floors, buildingId]);

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const availableRooms = rooms.filter(r => {
    if (floorId) return r.floor_id === floorId;
    if (propertyId) return r.property_id === propertyId;
    return true;
  });

  useEffect(() => {
    if (form.room_id) {
      const room = rooms.find(r => r.id === form.room_id);
      if (room && room.listed_rent) {
        setField('monthly_rent', String(room.listed_rent));
      }
    }
  }, [form.room_id, rooms]);

  function validate(): string | null {
    const today = new Date().toISOString().split('T')[0];
    if (!form.room_id) return 'Vui lòng chọn phòng.';
    if (!form.representative_tenant_id) return 'Vui lòng chọn người đại diện.';
    if (!form.start_date) return 'Chọn ngày bắt đầu.';
    if (!form.end_date) return 'Chọn ngày kết thúc.';
    if (form.start_date < today) return 'Ngày bắt đầu không được ở trong quá khứ.';
    if (form.end_date <= form.start_date) return 'Ngày kết thúc phải lớn hơn ngày bắt đầu.';
    if (form.end_date <= today) return 'Ngày kết thúc phải lớn hơn ngày hiện tại.';

    const payer = tenants.find((t) => t.id === form.representative_tenant_id);
    if (payer && !payer.email) return 'Người đại diện chưa có email. Cần cập nhật trước.';

    return null;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const validationError = validate();
    if (validationError) { setFormError(validationError); return; }
    
    setSubmitting(true);
    try {
      await api.post('/api/v1/contracts', {
        contract_code: form.contract_code.trim() || `HD-${Date.now()}`,
        room_id: form.room_id,
        representative_tenant_id: form.representative_tenant_id,
        start_date: form.start_date,
        end_date: form.end_date,
        deposit_amount: Number(form.deposit_amount) || null, // <-- THÊM DÒNG NÀY
        initial_terms: {
          effective_from: form.start_date,
          monthly_rent: Number(form.monthly_rent),
          electricity_unit_price: Number(form.electricity_unit_price),
          water_unit_price: Number(form.water_unit_price),
          monthly_service_fee: Number(form.monthly_service_fee),
        },
      });
      navigate('/hop-dong');
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Lỗi khi tạo hợp đồng.');
    } finally {
      setSubmitting(false);
    }
  }

  const payer = tenants.find((t) => t.id === form.representative_tenant_id);
  const payerMissingEmail = payer && !payer.email;
  const todayStr = new Date().toISOString().split('T')[0];

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Tạo Hợp đồng mới</h1>
        <button className="btn-secondary" onClick={() => navigate('/hop-dong')}>← Quay lại</button>
      </div>

      <PageState loading={loading} error={loadError}>
        <form className="contract-form" onSubmit={submit}>
          {formError && <div className="login-error">{formError}</div>}

          <h3 style={{ marginBottom: 12, color: 'var(--gold-2)' }}>1. Chọn Phòng trống</h3>
          <div className="form-row" style={{ background: 'var(--night-1)', padding: 16, borderRadius: 4, border: '1px dashed var(--gold-3)', marginBottom: 24 }}>
            
            <div className="login-field">
              <label>Khu trọ</label>
              <select value={propertyId} onChange={(e) => { 
                setPropertyId(e.target.value); setBuildingId(''); setFloorId(''); setField('room_id', ''); 
              }}>
                <option value="">— Tất cả Khu trọ —</option>
                {properties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>

            <div className="login-field">
              <label>Dãy</label>
              <select value={buildingId} onChange={(e) => { 
                setBuildingId(e.target.value); setFloorId(''); setField('room_id', ''); 
              }} disabled={!propertyId}>
                <option value="">— Tất cả Dãy —</option>
                {buildings.map(b => <option key={b.id} value={b.id}>Dãy {b.name}</option>)}
              </select>
            </div>

            <div className="login-field">
              <label>Tầng</label>
              <select value={floorId} onChange={(e) => { 
                setFloorId(e.target.value); setField('room_id', ''); 
              }} disabled={!buildingId}>
                <option value="">— Tất cả Tầng —</option>
                {floors.map(f => <option key={f.id} value={f.id}>Tầng {f.floor_number}{f.name ? ` - ${f.name}` : ''}</option>)}
              </select>
            </div>

            <div className="login-field" style={{ gridColumn: '1 / -1' }}>
              <label>Chọn Phòng (Chỉ hiện phòng Trống)</label>
              <select value={form.room_id} onChange={(e) => setField('room_id', e.target.value)} required>
                <option value="">— Chọn phòng —</option>
                {availableRooms.map((r) => (
                  <option key={r.id} value={r.id}>{r.room_code} — Giá: {formatVnd(r.listed_rent)}</option>
                ))}
              </select>
              {availableRooms.length === 0 && (
                <p className="text-muted" style={{ fontSize: 12, marginTop: 4, color: 'var(--cinnabar-3)' }}>
                  Không có phòng trống nào ở khu vực này.
                </p>
              )}
            </div>
          </div>

          <h3 style={{ marginBottom: 12, color: 'var(--gold-2)' }}>2. Thông tin Khách thuê & Thời hạn</h3>
          <div className="form-row">
            <div className="login-field" style={{ gridColumn: '1 / -1' }}>
              <label>Người đại diện</label>
              <select value={form.representative_tenant_id} onChange={(e) => setField('representative_tenant_id', e.target.value)} required>
                <option value="">— Chọn người thuê —</option>
                {tenants.map((t) => (
                  <option key={t.id} value={t.id}>{t.full_name}{t.phone ? ` (${t.phone})` : ''}{!t.email ? ' — Thiếu email' : ''}</option>
                ))}
              </select>
              {payerMissingEmail && (
                <p style={{ fontSize: 12, marginTop: 4, color: 'var(--cinnabar-3)' }}>
                  Người này chưa có email. Hãy vào mục "Người thuê" để cập nhật.
                </p>
              )}
            </div>

            <div className="login-field">
              <label>Ngày bắt đầu</label>
              <input type="date" value={form.start_date} min={todayStr} onChange={(e) => setField('start_date', e.target.value)} required />
            </div>
            <div className="login-field">
              <label>Ngày kết thúc (bao gồm ngày này)</label>
              <input type="date" value={form.end_date} min={form.start_date || todayStr} onChange={(e) => setField('end_date', e.target.value)} required />
            </div>
            
            {/* THÊM Ô NHẬP TIỀN CỌC */}
            <div className="login-field">
              <label>Tiền cọc (VNĐ)</label>
              <input type="number" min={0} step={1000} value={form.deposit_amount} onChange={(e) => setField('deposit_amount', e.target.value)} />
            </div>
          </div>

          <h3 style={{ marginTop: 24, marginBottom: 12, color: 'var(--gold-2)' }}>3. Điều khoản giá</h3>
          <div className="form-row">
            <div className="login-field">
              <label>Tiền thuê (VNĐ/tháng)</label>
              <input type="number" min={0} step={1000} value={form.monthly_rent} onChange={(e) => setField('monthly_rent', e.target.value)} required />
            </div>
            <div className="login-field">
              <label>Giá Điện (VNĐ/kWh)</label>
              <input type="number" min={0} step={100} value={form.electricity_unit_price} onChange={(e) => setField('electricity_unit_price', e.target.value)} required />
            </div>
            <div className="login-field">
              <label>Giá Nước (VNĐ/m³)</label>
              <input type="number" min={0} step={100} value={form.water_unit_price} onChange={(e) => setField('water_unit_price', e.target.value)} required />
            </div>
            <div className="login-field">
              <label>Phí dịch vụ (VNĐ/tháng)</label>
              <input type="number" min={0} step={1000} value={form.monthly_service_fee} onChange={(e) => setField('monthly_service_fee', e.target.value)} required />
            </div>
          </div>

          <div className="modal-actions" style={{ justifyContent: 'flex-start', marginTop: 30 }}>
            <button type="submit" className="btn-primary" disabled={submitting || payerMissingEmail || availableRooms.length === 0}>
              {submitting ? 'Đang lưu…' : 'Lưu Nháp (DRAFT)'}
            </button>
            <p className="text-muted" style={{ fontSize: 12, marginLeft: 12 }}>
              DRAFT không giữ chỗ. Sau khi tạo, mở chi tiết để xác nhận.
            </p>
          </div>
        </form>
      </PageState>
    </div>
  );
}