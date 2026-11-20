import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../../lib/api/client';
import type { Page, TenantOut } from '../../lib/api/types';
import { Pagination } from '../../components/Pagination';
import { PageState } from '../../components/PageState';

interface FormState {
  full_name: string;
  email: string;
  phone: string;
  note: string;
}

const empty: FormState = { full_name: '', email: '', phone: '', note: '' };

export function TenantListPage() {
  const [data, setData] = useState<Page<TenantOut> | null>(null);
  const [allTenants, setAllTenants] = useState<TenantOut[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<TenantOut | null>(null);
  const [form, setForm] = useState<FormState>(empty);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadAllTenants = useCallback(async (): Promise<TenantOut[]> => {
    const batchSize = 100;
    const firstRes = await api.get<Page<TenantOut>>(`/api/v1/tenants?page=1&page_size=${batchSize}`);
    const items = [...firstRes.items];
    const totalCount = firstRes.meta?.total ?? items.length;
    const totalPages = Math.max(1, Math.ceil(totalCount / batchSize));

    for (let p = 2; p <= totalPages; p++) {
      const nextRes = await api.get<Page<TenantOut>>(`/api/v1/tenants?page=${p}&page_size=${batchSize}`);
      if (nextRes.items.length === 0) break;
      items.push(...nextRes.items);
    }

    setAllTenants(items);
    return items;
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<Page<TenantOut>>(`/api/v1/tenants?page=${page}&page_size=${pageSize}`);
      setData(res);
      try {
        await loadAllTenants();
      } catch {
        // Vẫn giữ danh sách trang hiện tại nếu tải toàn bộ để check trùng bị lỗi
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không tải được danh sách người thuê.');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, loadAllTenants]);

  useEffect(() => {
    load();
  }, [load]);

  function openCreate() {
    setEditing(null);
    setForm(empty);
    setFormError(null);
    setOpen(true);
  }

  function openEdit(t: TenantOut) {
    setEditing(t);
    setForm({
      full_name: t.full_name,
      email: t.email ?? '',
      phone: t.phone ?? '',
      note: t.note ?? '',
    });
    setFormError(null);
    setOpen(true);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    const trimmedName = form.full_name.trim();
    const trimmedEmail = form.email.trim();
    const trimmedPhone = form.phone.trim();
    const trimmedNote = form.note.trim();

    if (!trimmedName) {
      setFormError('Họ tên bắt buộc.');
      return;
    }

    if (trimmedEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      setFormError('Email không hợp lệ.');
      return;
    }

    if (trimmedPhone) {
      if (!/^\d+$/.test(trimmedPhone)) {
        setFormError('Số điện thoại chỉ được chứa chữ số.');
        return;
      }
      if (trimmedPhone.length < 9 || trimmedPhone.length > 11) {
        setFormError('Số điện thoại phải từ 9 đến 11 chữ số.');
        return;
      }
    }

    setSubmitting(true);
    try {
      let latestTenants = allTenants;
      try {
        latestTenants = await loadAllTenants();
      } catch {
        // Dùng tạm allTenants nếu gọi lại danh sách lỗi
      }

      const otherTenants = latestTenants.filter((t) => !editing || t.id !== editing.id);

      if (
        trimmedEmail &&
        otherTenants.some((t) => (t.email ?? '').trim().toLowerCase() === trimmedEmail.toLowerCase())
      ) {
        setFormError('Email này đã được sử dụng bởi người thuê khác.');
        setSubmitting(false);
        return;
      }

      if (trimmedPhone && otherTenants.some((t) => (t.phone ?? '').trim() === trimmedPhone)) {
        setFormError('Số điện thoại này đã được sử dụng bởi người thuê khác.');
        setSubmitting(false);
        return;
      }

      const body = {
        full_name: trimmedName,
        email: trimmedEmail || null,
        phone: trimmedPhone || null,
        note: trimmedNote || null,
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
              <th style={{ width: 100 }}>Thao tác</th>
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
                  <button className="btn-secondary" onClick={() => openEdit(t)}>Sửa</button>
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
    </div>
  );
}