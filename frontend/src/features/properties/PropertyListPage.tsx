import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type { Page, PropertyOut } from '../../lib/api/types';
import { PageState } from '../../components/PageState';
import { Badge } from '../../components/Badge';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { BuildingPanel } from './BuildingPanel';

interface PropertyForm {
  name: string;
  address: string;
  description: string;
}

const emptyForm: PropertyForm = { name: '', address: '', description: '' };

export function PropertyListPage() {
  const [properties, setProperties] = useState<PropertyOut[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<PropertyOut | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<PropertyOut | null>(null);
  const [form, setForm] = useState<PropertyForm>(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [confirm, setConfirm] = useState<{ property: PropertyOut, action: 'deactivate' | 'activate' } | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<Page<PropertyOut>>(
        `/api/v1/properties?page=${page}&page_size=${pageSize}`,
      );
      setProperties(res.items);
      setTotal(res.meta.total);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được danh sách khu trọ.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => { load(); }, [load]);

  function openCreate() {
    setEditing(null);
    setForm(emptyForm);
    setFormError(null);
    setShowForm(true);
  }

  function openEdit(p: PropertyOut) {
    setEditing(p);
    setForm({ name: p.name, address: p.address, description: p.description ?? '' });
    setFormError(null);
    setShowForm(true);
  }

  async function submitForm(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!form.name.trim() || !form.address.trim()) {
      setFormError('Tên và địa chỉ là bắt buộc.');
      return;
    }
    setSubmitting(true);
    try {
      const body = {
        name: form.name.trim(),
        address: form.address.trim(),
        description: form.description.trim() || null,
      };
      if (editing) {
        await api.patch(`/api/v1/properties/${editing.id}`, body);
      } else {
        await api.post('/api/v1/properties', body);
      }
      setShowForm(false);
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Lỗi khi lưu khu trọ.');
    } finally {
      setSubmitting(false);
    }
  }

  async function doConfirmAction() {
    if (!confirm) return;
    setConfirmLoading(true);
    try {
      if (confirm.action === 'deactivate') {
        await api.delete(`/api/v1/properties/${confirm.property.id}`);
      } else {
        await api.patch(`/api/v1/properties/${confirm.property.id}`, { status: 'ACTIVE' });
      }
      setConfirm(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Thao tác thất bại.');
      setConfirm(null);
    } finally {
      setConfirmLoading(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Khu trọ & Cấu trúc</h1>
        <button className="btn-primary" onClick={openCreate}>Thêm khu trọ</button>
      </div>

      <PageState
        loading={loading}
        error={error}
        empty={!loading && !error && properties.length === 0}
        emptyText="Chưa có khu trọ nào."
        onRetry={load}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {properties.map((p) => (
            <div key={p.id} className="property-card-custom">
              
              {/* TRANG TRÍ: Cửa sổ & Đèn lồng */}
              <div className="property-decorations">
                <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--gold-3)' }}>
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <path d="M3 12h18M12 3v18" />
                </svg>
                <svg className="lantern-svg" width="24" height="30" viewBox="0 0 24 30" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--cinnabar-3)' }}>
                  <path d="M12 2v4" />
                  <rect x="8" y="6" width="8" height="16" rx="4" fill="var(--cinnabar-2)" fillOpacity="0.3" />
                  <path d="M9 22h6M12 22v4" />
                  <path d="M8 10h8M8 14h8M8 18h8" strokeOpacity="0.5" />
                </svg>
              </div>

              {/* NỘI DUNG KHU TRỌ */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16, position: 'relative', zIndex: 1, opacity: p.status === 'INACTIVE' ? 0.6 : 1 }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: 26, color: 'var(--gold-2)', fontFamily: "'Cormorant Garamond', serif" }}>
                    {p.name}
                  </h3>
                  <p className="text-muted" style={{ margin: '8px 0', fontSize: 15, fontStyle: 'italic' }}>
                    {p.address}
                  </p>
                  {p.description && (
                    <p style={{ margin: 0, fontSize: 14, opacity: 0.8 }}>{p.description}</p>
                  )}
                </div>
                
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 12 }}>
                  <Badge value={p.status} />
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                    <button className="btn-secondary" onClick={() => setSelected(p)}>
                      Xem cấu trúc
                    </button>
                    <button className="btn-secondary" onClick={() => openEdit(p)}>
                      Sửa
                    </button>
                    
                    {/* THÊM NÚT VÔ HIỆU HÓA / MỞ LẠI */}
                    {p.status === 'ACTIVE' ? (
                      <button
                        className="btn-secondary"
                        style={{ color: 'var(--cinnabar-3)', borderColor: 'var(--cinnabar-2)' }}
                        onClick={() => setConfirm({ property: p, action: 'deactivate' })}
                      >
                        Vô hiệu hóa
                      </button>
                    ) : (
                      <button
                        className="btn-secondary"
                        style={{ color: 'var(--jade-hi)', borderColor: 'var(--jade-2)' }}
                        onClick={() => setConfirm({ property: p, action: 'activate' })}
                      >
                        Mở lại
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {total > 0 && (
          <div className="pagination" style={{ marginTop: 24 }}>
            <span className="page-info">Trang {page} / {totalPages} ({total} khu trọ)</span>
            <div className="page-actions">
              <button className="page-btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Trước</button>
              <button className="page-btn" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Sau</button>
            </div>
          </div>
        )}
      </PageState>

      {/* MODAL THÊM/SỬA KHU TRỌ */}
      {showForm && (
        <div className="modal-backdrop active" style={{ zIndex: 9999 }} onClick={(e) => e.target === e.currentTarget && setShowForm(false)}>
          <div className="room-modal" style={{ width: 520 }}>
            <button className="modal-close" onClick={() => setShowForm(false)}>×</button>
            <h2 className="modal-title">{editing ? 'Sửa khu trọ' : 'Thêm khu trọ'}</h2>
            {formError && <div className="login-error">{formError}</div>}
            <form onSubmit={submitForm}>
              <div className="login-field">
                <label>Tên *</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
              </div>
              <div className="login-field">
                <label>Địa chỉ *</label>
                <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} required />
              </div>
              <div className="login-field">
                <label>Mô tả</label>
                <textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </div>
              <div className="modal-actions">
                <button type="button" className="modal-btn" onClick={() => setShowForm(false)} disabled={submitting}>Hủy</button>
                <button type="submit" className="modal-btn primary" disabled={submitting}>
                  {submitting ? 'Đang lưu…' : 'Lưu'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CONFIRM XÓA / MỞ LẠI */}
      {confirm && (
        <ConfirmDialog
          title={confirm.action === 'deactivate' ? "Vô hiệu hóa khu trọ?" : "Mở lại khu trọ?"}
          message={
            confirm.action === 'deactivate' 
              ? `Khu trọ "${confirm.property.name}" và TOÀN BỘ phòng bên trong sẽ chuyển sang trạng thái Ngừng. Chỉ thực hiện được khi không có phòng nào đang cho thuê.`
              : `Khu trọ "${confirm.property.name}" sẽ được mở lại. Bạn có chắc chắn không?`
          }
          confirmLabel={confirm.action === 'deactivate' ? "Vô hiệu hóa" : "Mở lại"}
          variant={confirm.action === 'deactivate' ? "danger" : "primary"}
          loading={confirmLoading}
          onCancel={() => setConfirm(null)}
          onConfirm={doConfirmAction}
        />
      )}

      {/* BUILDING PANEL */}
      {selected && (
        <BuildingPanel property={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}