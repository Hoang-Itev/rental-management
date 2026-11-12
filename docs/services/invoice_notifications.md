# P10 · Email hóa đơn

Billing phát sự kiện `InvoiceIssued` qua RabbitMQ. Notification ghi một job theo `source_event_id` trong PostgreSQL rồi mới ACK. Worker xin link qua Billing bằng service token và đối chiếu hóa đơn, event, email trước khi gửi. Link là token ngẫu nhiên, hiệu lực mặc định 72 giờ. Billing lưu SHA-256 của token. Worker giữ link trong bộ nhớ cho lần gửi hiện tại.

Trang hóa đơn là API đọc JSON tại `/public/v1/invoices/{token}` và mở được trực tiếp trên trình duyệt. Token hết hạn, bị thu hồi hoặc không hợp lệ trả 404. Link còn hiệu lực vẫn xem được khi hóa đơn đã thanh toán. Nginx chặn `/internal/`, đặt `Cache-Control: no-store` và `Referrer-Policy: no-referrer` cho route public. Billing tắt access log vì token xuất hiện trong URL.

Khi SMTP hoặc Billing tạm lỗi, job chờ retry theo cấp số nhân. Mặc định retry sau 30 giây, tối đa 5 lần gửi. Nếu hóa đơn đã rời trạng thái ISSUED trước khi worker xin link, job chuyển SKIPPED. Job FAILED có thể thử lại qua `POST /api/v1/email-jobs/{job_id}/retry`. Dedupe bảo đảm một job cho một event. Nếu SMTP đã nhận mail đúng lúc worker mất kết nối hoặc dừng trước khi commit DB, mail có thể được gửi lại. Các loại event email khác sẽ cần handler riêng.

## Local và cloud

Stack mặc định đã bật Billing và Notification worker cùng Mailpit.

```powershell
docker compose -f compose.yaml -f compose.workers.yaml up -d --build
```

Mailpit UI mặc định ở `http://localhost:8025`. URL trong email mặc định bắt đầu bằng `http://localhost:8080`. Chỉnh `PUBLIC_BASE_URL` nếu trình duyệt truy cập gateway qua host hoặc port khác. Đặt `PUBLIC_BASE_URL` thành origin HTTPS của gateway khi triển khai cloud. Cấu hình `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY` (`starttls` hoặc `tls`), `SMTP_FROM` và credential SMTP theo môi trường. Cùng một image ứng dụng dùng được cho cả hai môi trường.

## Kiểm thử

`scripts/tests/invoice-email-integration.ps1` khởi tạo project Compose tạm với PostgreSQL, RabbitMQ, Billing outbox publisher, Notification, Nginx và Mailpit. Ca integration khởi chạy worker với một cổng SMTP lỗi, kiểm tra lịch retry rồi chạy lại worker với Mailpit. Sau khi nhận email, test mở URL qua Nginx và kiểm tra hết hạn. Script xóa container, mạng và volume của project test.
