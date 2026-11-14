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

  const [confirm, setConfirm] = useState<{ property: PropertyOut } | null>(null);
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

  async function doDeactivate() {
    if (!confirm) return;
    setConfirmLoading(true);
    try {
      await api.delete(`/api/v1/properties/${confirm.property.id}`);
      setConfirm(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Không thể vô hiệu hóa.');
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
        <div className="property-grid">
          {properties.map((p) => (
            <div key={p.id} className="property-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <h3>{p.name}</h3>
                <Badge value={p.status} />
              </div>
              <p className="text-muted">{p.address}</p>
              {p.description && <p style={{ fontSize: 13 }}>{p.description}</p>}
              <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                <button className="btn-secondary" onClick={() => setSelected(p)}>Xem cấu trúc</button>
                <button className="btn-secondary" onClick={() => openEdit(p)}>Sửa</button>
                {p.status === 'ACTIVE' && (
                  <button
                    className="btn-secondary"
                    style={{ color: 'var(--cinnabar-3)' }}
                    onClick={() => setConfirm({ property: p })}
                  >
                    Vô hiệu hóa
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {total > 0 && (
          <div className="pagination">
            <span className="page-info">Trang {page} / {totalPages} ({total} khu trọ)</span>
            <div className="page-actions">
              <button className="page-btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Trước</button>
              <button className="page-btn" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Sau</button>
            </div>
          </div>
        )}
      </PageState>

      {showForm && (
        <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && setShowForm(false)}>
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

      {confirm && (
        <ConfirmDialog
          title="Vô hiệu hóa khu trọ?"
          message={`Khu trọ "${confirm.property.name}" sẽ chuyển sang INACTIVE. Chỉ thực hiện được khi không còn dãy ACTIVE.`}
          confirmLabel="Vô hiệu hóa"
          variant="danger"
          loading={confirmLoading}
          onCancel={() => setConfirm(null)}
          onConfirm={doDeactivate}
        />
      )}

      {selected && (
        <BuildingPanel property={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}