# P11 · Thanh toán MoMo Sandbox

Người thuê mở link hóa đơn và gọi `POST /public/v1/invoices/{token}/payments/momo`. Billing lấy toàn bộ số tiền từ hóa đơn. Hóa đơn quá hạn vẫn thanh toán được. Billing lưu attempt PENDING trước khi gọi MoMo và dùng lại attempt đang chờ khi gọi lặp. MoMo Sandbox mở trang nhập thẻ ATM nội địa qua `pay_url`.

Billing xác minh chữ ký HMAC của IPN, mã đối tác, order ID, request ID và số tiền. Thành công cập nhật attempt SUCCESS, hóa đơn PAID và ghi Outbox PaymentSucceeded cùng transaction. HTTP 204 xác nhận IPN hợp lệ đã được ghi nhận. URL chuyển về từ trình duyệt chỉ hướng dẫn mở lại link hóa đơn. Notification tạo job biên nhận theo event ID.

Khi MoMo timeout, phiên giữ PENDING. Scheduler đối soát mặc định mỗi 5 phút. Admin có thể POST `/api/v1/jobs/payments/reconcile/run` với `{"payment_attempt_id":"..."}`. IPN thành công đến muộn cho attempt đã đóng sẽ được đối soát. Nếu đã có phiên mới đang chờ hoặc hóa đơn đã được thanh toán bằng giao dịch khác, giữ dấu vết đối soát để xử lý thủ công. P11 không tự hoàn tiền.

## Demo local và cloud

Đặt `MOMO_PARTNER_CODE`, `MOMO_ACCESS_KEY`, `MOMO_SECRET_KEY` bằng thông tin Sandbox trong `.env`. Đặt `MOMO_IPN_URL=https://<gateway>/webhooks/momo/ipn`. Gateway phải truy cập được từ phía MoMo. Nếu chạy local, dùng tunnel HTTPS tới Nginx hoặc chạy thử trên cloud. `PUBLIC_BASE_URL` là địa chỉ người dùng mở từ trình duyệt. Đặt nó thành origin HTTPS trên cloud. Giữ bí mật ngoài Git.

```powershell
docker compose -f compose.yaml -f compose.workers.yaml up -d --build
```

Compose chính và compose.workers.yaml đã bao gồm các service và worker cần cho luồng này. Mở email P10 trong Mailpit, copy link hóa đơn, rồi dùng PowerShell:

```powershell
$invoiceUrl = Read-Host 'Dán link hóa đơn từ email'
$payment = Invoke-RestMethod -Method Post -Uri "$invoiceUrl/payments/momo"
$payment
if ($payment.checkout_status -eq 'READY') {
    Start-Process $payment.pay_url
} elseif ($payment.checkout_status -eq 'PAID') {
    Write-Host 'Hóa đơn đã thanh toán.'
} else {
    Write-Host "Đang chờ đối soát; thử lại sau $($payment.retry_after_seconds) giây. Không tạo hóa đơn khác."
}
```

Dùng thông tin thẻ thử do MoMo Sandbox cung cấp trên trang thanh toán. Sau khi hoàn tất, mở lại link trong email để xem `PAID`. Mailpit sẽ nhận email biên nhận nếu Notification đang chạy.

`scripts/tests/momo-payments-integration.ps1` dùng PostgreSQL và RabbitMQ riêng, thay HTTP MoMo bằng fixture có chữ ký kiểm tra độc lập. Nó kiểm tra sai chữ ký/số tiền, callback trùng đồng thời, timeout, đối soát và routing event. Chạy demo với tài khoản Sandbox thật để xác nhận cấu hình IPN bên ngoài.

[Tài liệu MoMo ATM](https://developers.momo.vn/v3/vi/docs/payment/api/atm/onetime/) · [IPN](https://developers.momo.vn/v3/vi/docs/payment/api/result-handling/notification/) · [Đối soát](https://developers.momo.vn/v3/vi/docs/payment/api/payment-api/query/)

## Cấu hình thực sự được đọc ở đâu?

Compose đọc `.env` để thay `${MOMO_*}` rồi truyền các biến vào `environment` của
`billing` và `billing-scheduler`. `app/config.py:Settings` đọc môi trường của
container; nó không tự mở file `.env` trên Windows. `get_payment_service()` tạo
`MomoClient` từ Settings cho API; `reconcile_loop()` làm tương tự cho scheduler.
Không hardcode khóa trong Python. Khi thiếu một trong bốn biến, checkout trả
503 MOMO_UNAVAILABLE và scheduler không chạy đối soát; các chức năng Billing khác
vẫn hoạt động.

Sau khi sửa `.env`, tạo lại hai container (restart đơn thuần không nạp biến mới):

```powershell
docker compose -f compose.yaml -f compose.workers.yaml up -d --force-recreate billing billing-scheduler
```

Tạo thanh toán: `POST /public/v1/invoices/{token}/payments/momo`.
Nhận thông báo từ MoMo: `POST /webhooks/momo/ipn` (không dùng JWT, xác thực bằng chữ ký MoMo).
Chuyển trình duyệt về: `GET /public/v1/payments/momo/return` (không cập nhật PAID).

## Timeout và đối soát

Checkout trả 200 với `checkout_status=READY` và `pay_url` khi đã có trang thanh toán,
hoặc `checkout_status=PAID` nếu đã thanh toán. Khi lượt PENDING chưa có URL, trả
202 với `checkout_status=RECONCILING`, `retry_after_seconds` và header `Retry-After`.
Frontend hiển thị đang đối soát, chờ rồi gọi lại checkout; không điều hướng khi thiếu URL.
HTTP 202 không có nghĩa đã thanh toán thành công.

Lỗi HTTP 504/HTML, timeout, JSON sai định dạng hoặc sai mã đơn đều giữ PENDING.
Log `app.momo` ghi operation, order_id, loại lỗi và HTTP status, không ghi khóa,
chữ ký, body hay link thanh toán. Không tự đổi FAILED hoặc tạo order mới chỉ vì timeout.
Scheduler mặc định hỏi lại mỗi 300 giây. Chỉ khi query xác nhận mã 42 (không tìm thấy
đơn) và đã qua khoảng chờ, hệ thống mới thử create lại bằng cùng orderId/requestId.
Nếu MoMo vẫn trả 504, hệ thống tiếp tục chờ; sửa log không thể khắc phục sự cố gateway bên ngoài.

CI dùng HTTP MoMo giả lập có kiểm tra chữ ký, cùng PostgreSQL/RabbitMQ thật trong
project test riêng. Nó không chứng nhận bộ khóa Sandbox hay đường IPN Internet đang
hoạt động. Nghiệm thu Sandbox thật cần mở checkout, thanh toán bằng thẻ test,
kiểm tra hóa đơn PAID và biên nhận; không dùng thẻ thật.
