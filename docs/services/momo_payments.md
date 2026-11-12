# P11 · Thanh toán MoMo Sandbox

Người thuê mở link hóa đơn và gọi `POST /public/v1/invoices/{token}/payments/momo`. Billing lấy toàn bộ số tiền từ hóa đơn. Hóa đơn quá hạn vẫn thanh toán được. Billing lưu attempt PENDING trước khi gọi MoMo và dùng lại attempt đang chờ khi gọi lặp. MoMo Sandbox mở trang nhập thẻ ATM nội địa qua `pay_url`.

Billing xác minh chữ ký HMAC của IPN, mã đối tác, order ID, request ID và số tiền. Thành công cập nhật attempt SUCCESS, hóa đơn PAID và ghi Outbox PaymentSucceeded cùng transaction. HTTP 204 xác nhận IPN hợp lệ đã được ghi nhận. URL chuyển về từ trình duyệt chỉ hướng dẫn mở lại link hóa đơn. Notification tạo job biên nhận theo event ID.

Khi MoMo timeout, phiên giữ PENDING. Scheduler đối soát mặc định mỗi 5 phút. Admin có thể POST `/api/v1/jobs/payments/reconcile/run` với `{"payment_attempt_id":"..."}`. IPN thành công đến muộn cho attempt đã đóng sẽ được đối soát. Nếu đã có phiên mới đang chờ hoặc hóa đơn đã được thanh toán bằng giao dịch khác, giữ dấu vết đối soát để xử lý thủ công. P11 không tự hoàn tiền.

## Demo local và cloud

Đặt `MOMO_PARTNER_CODE`, `MOMO_ACCESS_KEY`, `MOMO_SECRET_KEY` bằng thông tin Sandbox trong `.env`. Đặt `MOMO_IPN_URL=https://<gateway>/webhooks/momo/ipn`. Gateway phải truy cập được từ phía MoMo. Nếu chạy local, dùng tunnel HTTPS tới Nginx hoặc chạy thử trên cloud. `PUBLIC_BASE_URL` là địa chỉ người dùng mở từ trình duyệt. Đặt nó thành origin HTTPS trên cloud. Giữ bí mật ngoài Git.

```powershell
docker compose -f compose.yaml -f compose.workers.yaml up -d --build
```

Giữ thêm các overlay Tenant/Metering nếu bạn demo từ đầu quy trình. Mở email P10 trong Mailpit, copy link hóa đơn, rồi dùng PowerShell:

```powershell
$invoiceUrl = Read-Host 'Dán link hóa đơn từ email'
$payment = Invoke-RestMethod -Method Post -Uri "$invoiceUrl/payments/momo"
$payment
if ($payment.pay_url) { Start-Process $payment.pay_url }
```

Dùng thông tin thẻ thử do MoMo Sandbox cung cấp trên trang thanh toán. Sau khi hoàn tất, mở lại link trong email để xem `PAID`. Mailpit sẽ nhận email biên nhận nếu Notification đang chạy.

`scripts/tests/momo-payments-integration.ps1` dùng PostgreSQL và RabbitMQ riêng, thay HTTP MoMo bằng fixture có chữ ký kiểm tra độc lập. Nó kiểm tra sai chữ ký/số tiền, callback trùng đồng thời, timeout, đối soát và routing event. Chạy demo với tài khoản Sandbox thật để xác nhận cấu hình IPN bên ngoài.

[Tài liệu MoMo ATM](https://developers.momo.vn/v3/vi/docs/payment/api/atm/onetime/) · [IPN](https://developers.momo.vn/v3/vi/docs/payment/api/result-handling/notification/) · [Đối soát](https://developers.momo.vn/v3/vi/docs/payment/api/payment-api/query/)
