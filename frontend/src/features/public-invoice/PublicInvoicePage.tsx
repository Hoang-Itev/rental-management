import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import type { PublicInvoiceView, SePayCheckoutSession } from '../../lib/api/types';
import { formatVnd, formatDateVi, periodEndInclusive } from '../../lib/utils/format';

export default function PublicInvoicePage() {
  const { token } = useParams<{ token: string }>();
  const [invoice, setInvoice] = useState<PublicInvoiceView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState<string | null>(null);

  async function load() {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<PublicInvoiceView>(
        `/public/v1/invoices/${encodeURIComponent(token)}`,
        { auth: false },
      );
      setInvoice(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError('Liên kết hóa đơn không còn hiệu lực hoặc đã bị thu hồi.');
      } else {
        setError('Không tải được hóa đơn. Vui lòng thử lại sau.');
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function onPayWithSePay() {
    if (!token || !invoice || invoice.status !== 'ISSUED') return;
    setPayError(null);
    setPaying(true);
    try {
      const session = await api.post<SePayCheckoutSession>(
        `/public/v1/invoices/${encodeURIComponent(token)}/payments/sepay`,
        undefined,
        { auth: false },
      );

      if (session.checkout_status === 'PAID') {
        // Backend đã xác nhận thanh toán — reload lại để hiển thị.
        await load();
        return;
      }

      if (!session.action_url || !session.fields) {
        setPayError('Cổng thanh toán chưa sẵn sàng. Vui lòng thử lại sau.');
        return;
      }

      // Tạo HTML form POST thật và submit → chuyển sang SePay Sandbox.
      // KHÔNG dùng GET redirect, KHÔNG tự ký.
      const form = document.createElement('form');
      form.method = session.method; // POST
      form.action = session.action_url;
      form.style.display = 'none';
      for (const [name, value] of Object.entries(session.fields)) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = name;
        input.value = value;
        form.appendChild(input);
      }
      document.body.appendChild(form);
      form.submit();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 'SEPAY_UNAVAILABLE') {
          setPayError('Cổng thanh toán SePay tạm thời không sẵn sàng. Vui lòng thử lại sau.');
        } else if (err.code === 'PAYMENT_PROVIDER_CONFLICT') {
          setPayError('Hóa đơn đang có giao dịch thanh toán khác đang chờ. Vui lòng liên hệ chủ trọ.');
        } else if (err.code === 'INVOICE_NOT_PAYABLE' || err.code === 'INVOICE_ALREADY_PAID') {
          setPayError('Hóa đơn không còn khả dụng để thanh toán.');
          await load();
        } else {
          setPayError('Không tạo được phiên thanh toán. Vui lòng thử lại sau.');
        }
      } else {
        setPayError('Lỗi kết nối. Vui lòng thử lại.');
      }
    } finally {
      setPaying(false);
    }
  }

  if (loading) {
    return <div className="boot-loader">Đang tải hóa đơn…</div>;
  }

  if (error) {
    return (
      <div className="invoice-shell">
        <div className="invoice-card invoice-error">
          <div className="invoice-eyebrow">Hóa đơn</div>
          <h1 className="invoice-title">Không tìm thấy</h1>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!invoice) return null;

  const isPaid = invoice.status === 'PAID';

  return (
    <div className="invoice-shell">
      <div className={`invoice-card ${isPaid ? 'is-paid' : ''}`}>
        <div className="invoice-eyebrow">Nhà trọ Minh An · Hóa đơn</div>
        <h1 className="invoice-title">{invoice.invoice_code}</h1>

        <div className="invoice-meta">
          <div><span>Phòng</span><strong>{invoice.room_code}</strong></div>
          <div><span>Người thuê</span><strong>{invoice.tenant_name}</strong></div>
          <div>
            <span>Kỳ tính phí</span>
            <strong>
              {formatDateVi(invoice.period_start)} — {formatDateVi(periodEndInclusive(invoice.period_end))}
            </strong>
          </div>
          <div><span>Hạn thanh toán</span><strong>{formatDateVi(invoice.due_date)}</strong></div>
        </div>

        <table className="invoice-items">
          <thead>
            <tr>
              <th>Khoản</th>
              <th>SL</th>
              <th>Đơn giá</th>
              <th>Thành tiền</th>
            </tr>
          </thead>
          <tbody>
            {invoice.items.map((it, i) => (
              <tr key={i}>
                <td>{it.description}</td>
                <td>{it.quantity} {it.unit}</td>
                <td>{formatVnd(it.unit_price)}</td>
                <td>{formatVnd(it.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="invoice-total">
          <span>Tổng cộng</span>
          <strong>{formatVnd(invoice.total_amount)}</strong>
        </div>

        {isPaid ? (
          <div className="invoice-paid-badge">Đã thanh toán</div>
        ) : (
          <>
            <button
              className="invoice-pay-btn"
              onClick={onPayWithSePay}
              disabled={paying}
            >
              {paying ? 'Đang tạo phiên thanh toán…' : 'Thanh toán qua SePay'}
            </button>
            {payError && <div className="invoice-error-text">{payError}</div>}
            <div className="invoice-note">
              Sau khi hoàn tất thanh toán trên cổng SePay, hãy quay lại trang này và làm mới
              để kiểm tra trạng thái. Hệ thống xác nhận thanh toán từ phía SePay, không dựa vào
              đường dẫn quay về.
            </div>
          </>
        )}
      </div>
    </div>
  );
}