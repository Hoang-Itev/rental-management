import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type { Page, TenantOut, ContractOut } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';
import { PageState } from '../../components/PageState';
import { ConfirmDialog } from '../../components/ConfirmDialog';

interface FormState {
  full_name: string;
  email: string;
  phone: string;
  note: string;
}

const empty: FormState = { full_name: '', email: '', phone: '', note: '' };

export function TenantListPage() {
  const [data, setData] = useState<Page<TenantOut> | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<TenantOut | null>(null);
  const [form, setForm] = useState<FormState>(empty);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  
  // State cho việc Xóa
  const [confirmDelete, setConfirmDelete] = useState<TenantOut | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await api.get<Page<TenantOut>>(`/api/v1/tenants?page=${page}&page_size=${pageSize}`);
      setData(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được danh sách người thuê.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => { load(); }, [load]);

  function openCreate() {
    setEditing(null);
    setForm(empty);
    setFormError(null);
    setOpen(true);
  }

  function openEdit(t: TenantOut) {
    setEditing(t);
    setForm({ full_name: t.full_name, email: t.email ?? '', phone: t.phone ?? '', note: t.note ?? '' });
    setFormError(null);
    setOpen(true);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!form.full_name.trim()) { setFormError('Họ tên bắt buộc.'); return; }
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) { setFormError('Email không hợp lệ.'); return; }
    if (form.phone && form.phone.trim().length < 5) { setFormError('SĐT quá ngắn.'); return; }
    
    setSubmitting(true);
    try {
      const body = {
        full_name: form.full_name.trim(),
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        note: form.note.trim() || null,
      };
      if (editing) await api.patch(`/api/v1/tenants/${editing.id}`, body);
      else await api.post('/api/v1/tenants', body);
      setOpen(false);
      await load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : 'Lỗi khi lưu.');
    } finally {
      setSubmitting(false);
    }
  }

  async function doDelete() {
    if (!confirmDelete) return;
    setDeleting(true);
    setError(null);
    
    try {
      // 1. Kiểm tra xem khách này có hợp đồng nào đang hiệu lực không
      // Vì API hiện tại không hỗ trợ lọc theo tenant_id, ta tải 100 hợp đồng gần nhất về và tự lọc.
      const contractsRes = await api.get<Page<ContractOut>>('/api/v1/contracts?page_size=100');
      
      const activeContracts = contractsRes.items.filter(
        (c) => c.representative_tenant_id === confirmDelete.id && 
               ['ACTIVE', 'SCHEDULED', 'EXPIRED_PENDING'].includes(c.status)
      );

      if (activeContracts.length > 0) {
        setError(`Không thể xóa! Người thuê "${confirmDelete.full_name}" đang có hợp đồng hiệu lực (${activeContracts[0].contract_code}). Vui lòng vào mục Hợp đồng để Ghi nhận bàn giao trước.`);
        setConfirmDelete(null);
        setDeleting(false);
        return;
      }

      // 2. Nếu không vướng hợp đồng, tiến hành gọi API xóa
      // (Lưu ý: Backend hiện tại chưa code API DELETE /tenants/{id}. 
      // Nếu bạn đã code API này ở Backend, nó sẽ chạy. Nếu chưa, nó sẽ báo lỗi 404/405).
      await api.delete(`/api/v1/tenants/${confirmDelete.id}`);
      
      setConfirmDelete(null);
      await load();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 405)) {
         setError('Backend chưa hỗ trợ tính năng Xóa người thuê (Cần bổ sung API DELETE /api/v1/tenants/{id}).');
      } else {
         setError(err instanceof ApiError ? err.message : 'Không thể xóa người thuê này.');
      }
      setConfirmDelete(null);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1 className="page-title">Hồ sơ Người thuê</h1>
        <button className="btn-primary" onClick={openCreate}>Thêm người thuê</button>
      </div>

      <p className="text-muted" style={{ marginBottom: 12, fontSize: 13 }}>
        Người đại diện cần có email trước khi xác nhận hợp đồng để nhận hóa đơn.
      </p>

      {error && <div className="login-error">{error}</div>}

      <PageState loading={loading} error={null} empty={!loading && (data?.items.length ?? 0) === 0} emptyText="Chưa có người thuê." onRetry={load}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Họ tên</th>
              <th>Email</th>
              <th>Điện thoại</th>
              <th>Ghi chú</th>
              <th style={{ width: 160 }}>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((t) => (
              <tr key={t.id}>
                <td style={{ fontWeight: 'bold' }}>{t.full_name}</td>
                <td>{t.email || <span className="text-muted">—</span>}</td>
                <td>{t.phone || <span className="text-muted">—</span>}</td>
                <td>{t.note || <span className="text-muted">—</span>}</td>
                <td>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn-secondary" onClick={() => openEdit(t)}>Sửa</button>
                    <button 
                      className="btn-secondary" 
                      style={{ color: 'var(--cinnabar-3)', borderColor: 'var(--cinnabar-2)' }} 
                      onClick={() => setConfirmDelete(t)}
                    >
                      Xóa
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && <Pagination page={data.meta.page} pageSize={data.meta.page_size} total={data.meta.total} onPageChange={setPage} />}
      </PageState>

      {open && (
        <div className="modal-backdrop active" onClick={(e) => e.target === e.currentTarget && setOpen(false)}>
          <div className="room-modal" style={{ width: 500 }}>
            <button className="modal-close" onClick={() => setOpen(false)}>×</button>
            <h2 className="modal-title">{editing ? 'Sửa người thuê' : 'Thêm người thuê'}</h2>
            {formError && <div className="login-error">{formError}</div>}
            <form onSubmit={submit}>
              <div className="login-field">
                <label>Họ và tên *</label>
                <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
              </div>
              <div className="login-field">
                <label>Email (cần có để nhận hóa đơn)</label>
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </div>
              <div className="login-field">
                <label>Số điện thoại</label>
                <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </div>
              <div className="login-field">
                <label>Ghi chú</label>
                <textarea rows={3} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
              </div>
              <div className="modal-actions">
                <button type="button" className="modal-btn" onClick={() => setOpen(false)} disabled={submitting}>Hủy</button>
                <button type="submit" className="modal-btn primary" disabled={submitting}>{submitting ? 'Đang lưu…' : 'Lưu'}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {confirmDelete && (
        <ConfirmDialog
          title="Xóa người thuê?"
          message={`Bạn có chắc muốn xóa hồ sơ "${confirmDelete.full_name}"? Hệ thống sẽ kiểm tra xem người này còn hợp đồng nào đang hiệu lực không trước khi xóa.`}
          confirmLabel="Kiểm tra & Xóa"
          variant="danger"
          loading={deleting}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={doDelete}
        />
      )}
    </div>
  );
}