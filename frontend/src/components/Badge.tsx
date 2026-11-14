const labels: Record<string, string> = {
  DRAFT: 'Nháp', ISSUED: 'Đã phát hành', PAID: 'Đã thanh toán', VOID: 'Đã hủy',
  ACTIVE: 'Hoạt động', INACTIVE: 'Ngừng',
  SCHEDULED: 'Đã lên lịch', EXPIRED_PENDING: 'Chờ bàn giao', ENDED: 'Đã kết thúc', CANCELLED: 'Đã hủy',
  PENDING: 'Chờ xử lý', CONFIRMED: 'Đã xác nhận', SUPERSEDED: 'Bị thay thế',
  SENT: 'Đã gửi', FAILED: 'Thất bại', SKIPPED: 'Bỏ qua', SENDING: 'Đang gửi',
  OPEN: 'Mở', RESOLVED: 'Đã xử lý',
  OCCUPIED: 'Đang thuê', VACANT: 'Trống',
};

const tone: Record<string, 'active' | 'inactive'> = {
  ACTIVE: 'active', PAID: 'active', SENT: 'active', CONFIRMED: 'active', RESOLVED: 'active',
  ENDED: 'inactive', CANCELLED: 'inactive', VOID: 'inactive', INACTIVE: 'inactive', FAILED: 'inactive', EXPIRED: 'inactive',
};

export function Badge({ value }: { value: string }) {
  return (
    <span className={`badge ${tone[value] ?? ''}`}>{labels[value] ?? value}</span>
  );
}