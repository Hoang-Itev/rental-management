# P09 · Phát hành hóa đơn định kỳ

Billing lấy hợp đồng từ Tenant và đọc cutoff đã xác nhận từ Metering bằng `X-Service-Token`. Kỳ tính tiền là phần giao giữa tháng và thời gian thuê. Ngày kết thúc hợp đồng tính phí, còn `period_end` là ngày đầu tiên nằm ngoài kỳ. Hóa đơn sử dụng bộ tính tiền P08 và lưu giá, chỉ số, ID điều khoản cùng ID cutoff theo từng dòng.

| Thao tác | API |
| --- | --- |
| Tạo job cho một tháng đã kết thúc | `POST /api/v1/billing-runs` với `{"billing_month":"2024-11-01"}`. HTTP 202 và trạng thái `RUNNING` xác nhận đã ghi job vào DB. |
| Xem kết quả job | `GET /api/v1/billing-runs`. Có thể dùng lại `Idempotency-Key` cho cùng tháng. |
| Xem hóa đơn | `GET /api/v1/invoices` hoặc `GET /api/v1/invoices/{invoice_id}`. |
| Thử phát hành ngay một bản nháp | `POST /api/v1/invoices/{invoice_id}/issue`. Thiếu dữ liệu trả 422 và giữ bản nháp. |

Job định kỳ xử lý tháng trước từ 02:00 ngày 1 theo giờ Việt Nam. Nếu dịch vụ khởi động muộn, nó xử lý kỳ đến hạn gần nhất. Các tháng cũ có thể yêu cầu qua API. Scheduler cũng xử lý các job thủ công đã lưu và thử lại hóa đơn DRAFT. Nếu ngày thay đổi điều khoản nằm giữa kỳ, mỗi mốc cần cutoff đã xác nhận. Khi thiếu mốc, hóa đơn chờ với `PENDING_CUTOFF`. Để demo dùng hợp đồng một điều khoản hoặc chuyển giá ở đầu tháng.

Hóa đơn thiếu email người trả tiền giữ `DRAFT` với `MISSING_RECIPIENT_EMAIL`. Khi đủ dữ liệu, các dòng tiền, trạng thái `ISSUED` và Outbox `InvoiceIssued` được ghi cùng transaction. Hạn thanh toán mặc định là ngày 5 của tháng phát hành, theo tài liệu nghiệp vụ. Bản phát hành sau ngày 5 có thể đã quá hạn ngay khi được tạo.

Publisher gửi sự kiện vào RabbitMQ và cập nhật `published_at` sau broker confirm. Notification cần xử lý trùng theo `event_id` ở P10. P09 phát hành hóa đơn `PERIODIC`, gồm cả phần tháng cuối nếu đủ cutoff. Luồng `FINAL`, link hóa đơn, email và thanh toán nằm ngoài phạm vi bản vá.

## Docker Compose

Thêm `-f compose.p09.yaml` sau các overlay bạn đang dùng, rồi chạy `up -d --build`. Billing API, scheduler và publisher dùng chung Dockerfile. Scheduler và publisher chạy thành hai process độc lập. Giữ các overlay cũ nếu demo cần consumer hợp đồng hoặc job tạo cutoff.

Local và cloud dùng cùng cấu hình ứng dụng. Đặt thông tin DB, RabbitMQ và service token theo môi trường. Có thể ghi đè `BILLING_TENANT_URL`, `BILLING_METERING_URL`, `BILLING_HTTP_TIMEOUT_SECONDS` (mặc định 5) và `BILLING_POLL_SECONDS` (mặc định 300). Các URL mặc định là tên service trong mạng Compose.

`scripts/test_p09.ps1` tạo project Compose riêng, chạy test và xóa volume của chính project đó. Test bao gồm cutoff thiếu, phát hành, hai yêu cầu đồng thời, rollback khi lỗi Outbox, chạy lại job, tổng tiền và xác nhận nhận sự kiện qua RabbitMQ.
