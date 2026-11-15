import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { RoomOut, TenantOut, Page, ContractOut } from '../../lib/api/types';
import { PageState } from '../../components/PageState';
import { formatVnd } from '../../lib/utils/format';

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
  initial_electricity: string;
  initial_water: string;
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
  initial_electricity: '0',
  initial_water: '0',
};

export function ContractWizardPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preSelectedRoomId = searchParams.get('room_id') || '';

  const [rooms, setRooms] = useState<RoomOut[]>([]);
  const [tenants, setTenants] = useState<TenantOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  
  const [form, setForm] = useState<FormState>({
    ...initialForm,
    room_id: preSelectedRoomId,
  });

  async function loadOptions() {
    setLoading(true);
    setLoadError(null);
    try {
      const roomRes = await api.get<Page<RoomOut>>('/api/v1/rooms?status=ACTIVE&occupancy=VACANT&page_size=100');
      setRooms(roomRes.items);

      const [tenantRes, contractRes] = await Promise.all([
        api.get<Page<TenantOut>>('/api/v1/tenants?page_size=100'),
        api.get<Page<ContractOut>>('/api/v1/contracts?page_size=100')
      ]);

      const activeTenantIds = new Set(
        contractRes.items
          .filter(c => ['ACTIVE', 'SCHEDULED', 'EXPIRED_PENDING'].includes(c.status))
          .map(c => c.representative_tenant_id)
      );

      const availableTenants = tenantRes.items.filter(t => !activeTenantIds.has(t.id));
      setTenants(availableTenants);

    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : 'Không tải được danh sách phòng/người thuê.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadOptions(); }, []);

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

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
        initial_electricity: Number(form.initial_electricity),
        initial_water: Number(form.initial_water),
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

      <PageState loading={loading} error={loadError} onRetry={loadOptions}>
        <form className="contract-form" onSubmit={submit}>
          {formError && <div className="login-error">{formError}</div>}

          <div className="form-row">
            <div className="login-field">
              <label>Chọn Phòng (Chỉ hiện phòng Trống)</label>
              <select value={form.room_id} onChange={(e) => setField('room_id', e.target.value)} required>
                <option value="">— Chọn phòng —</option>
                {rooms.map((r) => (
                  <option key={r.id} value={r.id}>{r.room_code} — niêm yết {formatVnd(r.listed_rent)}</option>
                ))}
              </select>
              {rooms.length === 0 && (
                <p className="text-muted" style={{ fontSize: 12, marginTop: 4, color: 'var(--cinnabar-3)' }}>
                  Không có phòng trống nào. Vui lòng kiểm tra lại.
                </p>
              )}
            </div>

            <div className="login-field">
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
              {tenants.length === 0 && (
                <p className="text-muted" style={{ fontSize: 12, marginTop: 4 }}>
                  Không có khách thuê nào đang trống (tất cả đã có hợp đồng).
                </p>
              )}
            </div>
          </div>

          <div className="form-row">
            <div className="login-field">
              <label>Ngày bắt đầu</label>
              <input type="date" value={form.start_date} min={todayStr} onChange={(e) => setField('start_date', e.target.value)} required />
            </div>
            <div className="login-field">
              <label>Ngày kết thúc (bao gồm ngày này)</label>
              <input type="date" value={form.end_date} min={form.start_date || todayStr} onChange={(e) => setField('end_date', e.target.value)} required />
            </div>
          </div>

          <div className="form-row" style={{ background: 'var(--night-1)', padding: 12, borderRadius: 4, border: '1px dashed var(--gold-3)' }}>
            <div className="login-field">
              <label>Số điện ban đầu (kWh)</label>
              <input type="number" step="0.01" min="0" value={form.initial_electricity} onChange={(e) => setField('initial_electricity', e.target.value)} />
            </div>
            <div className="login-field">
              <label>Số nước ban đầu (m³)</label>
              <input type="number" step="0.01" min="0" value={form.initial_water} onChange={(e) => setField('initial_water', e.target.value)} />
            </div>
          </div>

          <h3>Điều khoản giá</h3>
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
            <button type="submit" className="btn-primary" disabled={submitting || payerMissingEmail || rooms.length === 0 || tenants.length === 0}>
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