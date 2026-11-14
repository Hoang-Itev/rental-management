const vndFormatter = new Intl.NumberFormat('vi-VN', {
  style: 'currency',
  currency: 'VND',
  maximumFractionDigits: 0,
});

export function formatVnd(value: number): string {
  return vndFormatter.format(value);
}

/** Backend dùng period_end exclusive — hiển thị cho người dùng phải trừ 1 ngày. */
export function periodEndInclusive(exclusiveIsoDate: string): string {
  const d = new Date(exclusiveIsoDate + 'T00:00:00');
  d.setDate(d.getDate() - 1);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function formatDateVi(isoDate: string): string {
  const [y, m, d] = isoDate.split('-');
  if (!y || !m || !d) return isoDate;
  return `${d}/${m}/${y}`;
}

export function formatDateTimeVi(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function contractStatusLabel(s: string): string {
  return (
    {
      DRAFT: 'Nháp',
      SCHEDULED: 'Đã lên lịch',
      ACTIVE: 'Đang hiệu lực',
      EXPIRED_PENDING: 'Chờ bàn giao',
      ENDED: 'Đã kết thúc',
      CANCELLED: 'Đã hủy',
    }[s] ?? s
  );
}

export function invoiceStatusLabel(s: string): string {
  return ({ DRAFT: 'Nháp', ISSUED: 'Đã phát hành', PAID: 'Đã thanh toán', VOID: 'Đã hủy' }[s] ?? s);
}

export function isOverdue(status: string, dueDate: string): boolean {
  if (status !== 'ISSUED') return false;
  const today = new Date();
  const d = new Date(dueDate + 'T23:59:59');
  return d < today;
}