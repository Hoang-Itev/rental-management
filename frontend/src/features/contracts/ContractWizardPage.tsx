import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { RoomOut, TenantOut, Page } from '../../lib/api/types';
import { PageState } from '../../components/PageState';
import { formatVnd, formatDateVi } from '../../lib/utils/format';

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
      const [roomRes, tenantRes] = await Promise.all([
        api.get<Page<RoomOut>>('/api/v1/rooms?status=ACTIVE&occupancy=VACANT&page_size=100'),
        api.get<Page<TenantOut>>('/api/v1/tenants?page_size=100'),
      ]);
      setRooms(roomRes.items);
      setTenants(tenantRes.items);
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
    const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
    
    if (!form.room_id) return 'Chọn phòng.';
    if (!form.representative_tenant_id) return 'Chọn người đại diện.';
    if (!form.start_date) return 'Chọn ngày bắt đầu.';
    if (!form.end_date) return 'Chọn ngày kết thúc.';
    
    // Validate Ngày bắt đầu không ở quá khứ
    if (form.start_date < today) {
      return 'Ngày bắt đầu không được ở trong quá khứ.';
    }

    // Validate Ngày kết thúc phải sau Ngày bắt đầu
    if (form.end_date <= form.start_date) {
      return 'Ngày kết thúc phải lớn hơn ngày bắt đầu.';
    }
    
    // Validate Ngày kết thúc phải lớn hơn hiện tại
    if (form.end_date <= today) {
      return 'Ngày kết thúc phải lớn hơn ngày hiện tại.';
    }

    const payer = tenants.find((t) => t.id === form.representative_tenant_id);
    if (payer && !payer.email) {
      return 'Người đại diện chưa có email. Vào "Người thuê" để cập nhật trước khi xác nhận hợp đồng.';
    }

    const rent = Number(form.monthly_rent);
    const elec = Number(form.electricity_unit_price);
    const water = Number(form.water_unit_price);
    const service = Number(form.monthly_service_fee);
    if (!Number.isInteger(rent) || rent < 0) return 'Tiền thuê phải là số nguyên >= 0.';
    if (!Number.isInteger(elec) || elec < 0) return 'Giá điện phải là số nguyên >= 0.';
    if (!Number.isInteger(water) || water < 0) return 'Giá nước phải là số nguyên >= 0.';
    if (!Number.isInteger(service) || service < 0) return 'Phí dịch vụ phải là số nguyên >= 0.';

    return null;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const validationError = validate();
    if (validationError) {
      setFormError(validationError);
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/api/v1/contracts', {
        contract_code: form.contract_code.trim() || `HD-${Date.now()}`,
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
        },
      });
      navigate('/hop-dong');
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message || 'Lỗi khi tạo hợp đồng.');
      } else {
        setFormError('Lỗi kết nối. Vui lòng thử lại.');
      }
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
              <label>Chọn Phòng (ACTIVE &amp; Trống)</label>
              <select
                value={form.room_id}
                onChange={(e) => setField('room_id', e.target.value)}
                required
              >
                <option value="">— Chọn phòng —</option>
                {rooms.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.room_code} — niêm yết {formatVnd(r.listed_rent)}
                  </option>
                ))}
              </select>
              {rooms.length === 0 && (
                <p className="text-muted" style={{ fontSize: 12, marginTop: 4 }}>
                  Không có phòng trống. Tạo phòng trong mục "Khu trọ".
                </p>
              )}
            </div>

            <div className="login-field">
              <label>Người đại diện</label>
              <select
                value={form.representative_tenant_id}
                onChange={(e) => setField('representative_tenant_id', e.target.value)}
                required
              >
                <option value="">— Chọn người thuê —</option>
                {tenants.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.full_name}{t.phone ? ` (${t.phone})` : ''}{!t.email ? ' — thiếu email' : ''}
                  </option>
                ))}
              </select>
              {payerMissingEmail && (
                <p style={{ fontSize: 12, marginTop: 4, color: 'var(--cinnabar-3)' }}>
                  Người đại diện chưa có email — cần cập nhật trước khi xác nhận hợp đồng.
                </p>
              )}
            </div>
          </div>

          <div className="form-row">
            <div className="login-field">
              <label>Ngày bắt đầu</label>
              <input
                type="date"
                value={form.start_date}
                min={todayStr} // Chặn chọn ngày trong quá khứ
                onChange={(e) => setField('start_date', e.target.value)}
                required
              />
            </div>
            <div className="login-field">
              <label>Ngày kết thúc (bao gồm ngày này)</label>
              <input
                type="date"
                value={form.end_date}
                // Phải lớn hơn ngày bắt đầu VÀ lớn hơn ngày hiện tại
                min={form.start_date ? (form.start_date > todayStr ? form.start_date : todayStr) : todayStr}
                onChange={(e) => setField('end_date', e.target.value)}
                required
              />
            </div>
          </div>

          <h3>Điều khoản giá</h3>
          <div className="form-row">
            <div className="login-field">
              <label>Tiền thuê (VNĐ)</label>
              <input
                type="number"
                min={0}
                step={1000}
                value={form.monthly_rent}
                onChange={(e) => setField('monthly_rent', e.target.value)}
                required
              />
            </div>
            <div className="login-field">
              <label>Giá Điện (VNĐ/kWh)</label>
              <input
                type="number"
                min={0}
                step={100}
                value={form.electricity_unit_price}
                onChange={(e) => setField('electricity_unit_price', e.target.value)}
                required
              />
            </div>
            <div className="login-field">
              <label>Giá Nước (VNĐ/m³)</label>
              <input
                type="number"
                min={0}
                step={100}
                value={form.water_unit_price}
                onChange={(e) => setField('water_unit_price', e.target.value)}
                required
              />
            </div>
            <div className="login-field">
              <label>Phí dịch vụ (VNĐ/tháng)</label>
              <input
                type="number"
                min={0}
                step={1000}
                value={form.monthly_service_fee}
                onChange={(e) => setField('monthly_service_fee', e.target.value)}
                required
              />
            </div>
          </div>

          <div className="modal-actions" style={{ justifyContent: 'flex-start', marginTop: 30 }}>
            <button type="submit" className="btn-primary" disabled={submitting || payerMissingEmail}>
              {submitting ? 'Đang lưu…' : 'Lưu Nháp (DRAFT)'}
            </button>
            <p className="text-muted" style={{ fontSize: 12, marginLeft: 12 }}>
              DRAFT không giữ chỗ. Sau khi tạo, mở chi tiết để xác nhận (DRAFT → SCHEDULED).
            </p>
          </div>
        </form>
      </PageState>
    </div>
  );
}