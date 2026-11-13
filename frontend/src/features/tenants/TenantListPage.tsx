import { useState, useEffect, useCallback } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type { Page, TenantOut } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';

export function TenantListPage() {
  const [data, setData] = useState<Page<TenantOut> | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  
  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({ full_name: '', email: '', phone: '' });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const fetchTenants = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<Page<TenantOut>>(`/api/v1/tenants?page=${page}&page_size=10`);
      setData(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { fetchTenants(); }, [fetchTenants]);

  // Hàm Validate Form
  function validateForm() {
    const errors: Record<string, string> = {};
    if (!formData.full_name.trim()) {
      errors.full_name = 'Họ tên không được để trống';
    }
    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errors.email = 'Email không hợp lệ';
    }
    if (formData.phone && formData.phone.length < 5) {
      errors.phone = 'Số điện thoại quá ngắn';
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validateForm()) return;

    setSubmitting(true);
    try {
      await api.post('/api/v1/tenants', {
        full_name: formData.full_name.trim(),
        email: formData.email.trim() || null,
        phone: formData.phone.trim() || null,
      });
      setIsModalOpen(false);
      setFormData({ full_name: '', email: '', phone: '' });
      fetchTenants(); // Reload danh sách
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setFormErrors({ global: 'Dữ liệu không hợp lệ từ máy chủ. Vui lòng kiểm tra lại.' });
      } else {
        setFormErrors({ global: 'Đã có lỗi xảy ra khi lưu dữ liệu.' });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Hồ sơ Người thuê</h1>
        <button className="btn-primary" onClick={() => setIsModalOpen(true)}>
          Thêm người thuê
        </button>
      </div>

      {loading ? (
        <div className="loading-text">Đang tải dữ liệu...</div>
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Họ tên</th>
                <th>Email</th>
                <th>Điện thoại</th>
                <th>Ghi chú</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((t) => (
                <tr key={t.id}>
                  <td>{t.full_name}</td>
                  <td>{t.email || '—'}</td>
                  <td>{t.phone || '—'}</td>
                  <td>{t.note || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data && <Pagination page={data.meta.page} pageSize={data.meta.page_size} total={data.meta.total} onPageChange={setPage} />}
        </>
      )}

      {/* Modal Form */}
      {isModalOpen && (
        <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && setIsModalOpen(false)}>
          <div className="room-modal" style={{ width: 500 }}>
            <button className="modal-close" onClick={() => setIsModalOpen(false)}>×</button>
            <h2 className="modal-title">Thêm Người Thuê</h2>
            
            {formErrors.global && <div className="login-error">{formErrors.global}</div>}

            <form onSubmit={handleSubmit}>
              <div className="login-field">
                <label>Họ và tên *</label>
                <input
                  type="text"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                />
                {formErrors.full_name && <div className="field-error">{formErrors.full_name}</div>}
              </div>

              <div className="login-field">
                <label>Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                />
                {formErrors.email && <div className="field-error">{formErrors.email}</div>}
              </div>

              <div className="login-field">
                <label>Số điện thoại</label>
                <input
                  type="text"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                />
                {formErrors.phone && <div className="field-error">{formErrors.phone}</div>}
              </div>

              <div className="modal-actions" style={{ marginTop: 24 }}>
                <button type="button" className="modal-btn" onClick={() => setIsModalOpen(false)}>Hủy</button>
                <button type="submit" className="modal-btn primary" disabled={submitting}>
                  {submitting ? 'Đang lưu...' : 'Lưu lại'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}