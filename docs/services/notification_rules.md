# P12 · Nhắc nợ, biên nhận và hợp đồng sắp hết hạn

Billing quét từ 09:00 theo giờ Việt Nam và tạo tối đa một event nhắc nợ cho mỗi hóa đơn mỗi ngày. Hóa đơn phải ở trạng thái ISSUED, còn số tiền dương và đã qua ngày đến hạn. Chủ trọ có thể gọi `POST /api/v1/invoices/{invoice_id}/reminders` qua gateway. API dùng cùng khóa chống trùng với scheduler.

Trước khi gửi, Notification hỏi Billing về tình trạng hóa đơn và xin link mới từ event nhắc nợ. Nếu Billing không phản hồi, job retry theo backoff. Nếu hóa đơn đã PAID, VOID hoặc không còn đủ điều kiện, job chuyển SKIPPED. Khi nhận PaymentSucceeded, Notification tạo job biên nhận và bỏ qua các reminder đang chờ. Reminder đến sau PaymentSucceeded cũng chuyển SKIPPED. Trạng thái được kiểm tra trước SMTP. Nếu trạng thái đổi sau khi SMTP đã nhận thư, thư đã gửi vẫn có thể đến hộp thư.

Tenant quét các hợp đồng ACTIVE còn từ 0 đến 7 ngày, theo giờ Việt Nam, từ 09:00. Mỗi hợp đồng có tối đa một cảnh báo cho từng ngày kết thúc đã ghi. Nếu chủ trọ gia hạn, kỳ kết thúc mới có thể phát cảnh báo riêng khi đến gần hạn. Notification hỏi lại Tenant trước khi gửi đến `OWNER_EMAIL`. Nếu hợp đồng đã gia hạn, chấm dứt hoặc đã qua ngày hết hạn, bỏ qua cảnh báo cũ. Nếu Tenant mất kết nối, job chờ retry.

## Chạy demo

Stack mặc định đã bật Tenant, Billing và Notification worker. Đặt `OWNER_EMAIL` theo môi trường.

```powershell
docker compose -f compose.yaml -f compose.workers.yaml up -d --build
```

Nếu demo đồng hồ và cutoff, giữ thêm các overlay P06 và P07 đang dùng. Chạy `scripts/tests/notification-rules.ps1` để kiểm tra bằng PostgreSQL, RabbitMQ và Mailpit trong project Compose riêng. Test chạy lại scheduler, phát lại cùng event, kiểm tra Billing tạm mất kết nối và cả hai thứ tự đến của event thanh toán và reminder.
