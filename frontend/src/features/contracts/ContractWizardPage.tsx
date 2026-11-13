import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { RoomOut, TenantOut, Page } from '../../lib/api/types';

export function ContractWizardPage() {
  const navigate = useNavigate();
  const [rooms, setRooms] = useState<RoomOut[]>([]);
  const [tenants, setTenants] = useState<TenantOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [form, setForm] = useState({
    contract_code: '',
    room_id: '',
    representative_tenant_id: '',
    start_date: '',
    end_date: '',
    monthly_rent: 2000000,
    electricity_unit_price: 3500,
    water_unit_price: 15000,
    monthly_service_fee: 100000,
  });

  useEffect(() => {
    // Chỉ lấy phòng trống và người thuê
    Promise.all([
      api.get<Page<RoomOut>>('/api/v1/rooms?occupancy=VACANT&page_size=100'),
      api.get<Page<TenantOut>>('/api/v1/tenants?page_size=100')
    ]).then(([roomRes, tenantRes]) => {
      setRooms(roomRes.items);
      setTenants(tenantRes.items);
    }).finally(() => setLoading(false));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (!form.room_id || !form.representative_tenant_id) {
      setError('Vui lòng chọn phòng và người đại diện.');
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/api/v1/contracts', {
        contract_code: form.contract_code || `HD-${Date.now()}`,
        room_id: form.room_id,
        representative_tenant_id: form.representative_tenant_id,
        start_date: form.start_date,
        end_date: form.end_date,
        initial_terms: {
          effective_from: form.start_date,
          monthly_rent: Number(form.monthly_rent),
          electricity_unit_price: Number(form.electricity_unit_price),
          water_unit_price: Number(form.water_unit_price),
          monthly_service_fee: Number(form.monthly_service_fee),
        }
      });
      navigate('/hop-dong');
    } catch (err: any) {
      if (err instanceof ApiError && err.status === 422) {
        setError('Dữ liệu không hợp lệ. Kiểm tra lại ngày tháng hoặc giá trị.');
      } else {
        setError(err.message || 'Lỗi khi tạo hợp đồng.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="loading-text">Đang tải dữ liệu...</div>;

  return (
    <div className="page-container">
      <h1 className="page-title">Tạo Hợp đồng mới</h1>
      <form className="contract-form" onSubmit={submit}>
        {error && <div className="login-error">{error}</div>}
        
        <div className="form-row">
          <div className="login-field">
            <label>Chọn Phòng (Trống)</label>
            <select value={form.room_id} onChange={e => setForm({ ...form, room_id: e.target.value })} required>
              <option value="">-- Chọn phòng --</option>
              {rooms.map(r => <option key={r.id} value={r.id}>{r.room_code} (Giá: {r.listed_rent})</option>)}
            </select>
          </div>
          <div className="login-field">
            <label>Người đại diện</label>
            <select value={form.representative_tenant_id} onChange={e => setForm({ ...form, representative_tenant_id: e.target.value })} required>
              <option value="">-- Chọn người thuê --</option>
              {tenants.map(t => <option key={t.id} value={t.id}>{t.full_name} ({t.phone || 'Không SĐT'})</option>)}
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="login-field">
            <label>Ngày bắt đầu</label>
            <input type="date" value={form.start_date} onChange={e => setForm({ ...form, start_date: e.target.value })} required />
          </div>
          <div className="login-field">
            <label>Ngày kết thúc</label>
            <input type="date" value={form.end_date} onChange={e => setForm({ ...form, end_date: e.target.value })} required />
          </div>
        </div>

        <h3>Điều khoản giá</h3>
        <div className="form-row">
          <div className="login-field">
            <label>Tiền thuê (VNĐ)</label>
            <input type="number" value={form.monthly_rent} onChange={e => setForm({ ...form, monthly_rent: Number(e.target.value) })} required />
          </div>
          <div className="login-field">
            <label>Giá Điện (VNĐ/kWh)</label>
            <input type="number" value={form.electricity_unit_price} onChange={e => setForm({ ...form, electricity_unit_price: Number(e.target.value) })} required />
          </div>
          <div className="login-field">
            <label>Giá Nước (VNĐ/m3)</label>
            <input type="number" value={form.water_unit_price} onChange={e => setForm({ ...form, water_unit_price: Number(e.target.value) })} required />
          </div>
        </div>

        <div className="modal-actions" style={{ justifyContent: 'flex-start', marginTop: 30 }}>
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? 'Đang lưu...' : 'Lưu Nháp (DRAFT)'}
          </button>
        </div>
      </form>
    </div>
  );
}