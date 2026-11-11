# 21. API & EVENT CONTRACTS V1.1
Trạng thái: Hợp đồng thiết kế đã chốt; hiện mới có ORM, migration và hạ tầng local, chưa triển khai API/nghiệp vụ.
Tiêu chuẩn: OpenAPI 3.1 cho REST API; AsyncAPI 3.0 cho RabbitMQ và MQTT.
Database: Database Design V3, gồm 26 bảng trong 6 database logic.
Phạm vi: 5 microservices nghiệp vụ, FastAPI Auth và Nginx API Gateway.
Nguyên tắc: Không thay đổi kiến trúc đã thống nhất. Mỗi service chỉ truy cập database mình sở hữu. Giao tiếp giữa các service thông qua REST hoặc RabbitMQ.

21.1. QUY ƯỚC TOÀN HỆ THỐNG
21.1.1. Phân loại API
Admin API: /api/v1/...
Dành cho chủ trọ, yêu cầu JWT, truy cập thông qua API Gateway.
Public API: /public/v1/...
Dành cho người thuê xem và thanh toán hóa đơn bằng liên kết chứa token.
Internal API: /internal/v1/...
Dành cho service-to-service, sử dụng X-Service-Token, không công khai ra Internet.
Webhook: /webhooks/momo/ipn
Nhận kết quả thanh toán từ MoMo, bắt buộc xác minh chữ ký.
Health: /health
Kiểm tra tiến trình còn hoạt động, không phụ thuộc việc PostgreSQL hoặc RabbitMQ có đang sẵn sàng hay không.
Readiness: /ready
Kiểm tra khả năng phục vụ dựa trên các dependency cần thiết.
21.1.2. Định dạng dữ liệu
Request/Response: JSON.
Khóa định danh: UUID.
Thời điểm: ISO 8601 có timezone.
Múi giờ nghiệp vụ: Asia/Ho_Chi_Minh.
Tiền VNĐ: Số nguyên, backend sử dụng Decimal khi tính toán.
Chỉ số điện nước: Decimal, không sử dụng float để tính tiền.
API phân trang: Trả items và meta, trong đó meta chứa page, page_size, total.
API billable: Hỗ trợ phân trang cursor để Billing quét nhiều hợp đồng.
21.1.3. Quy ước thời gian
contracts.start_date: Ngày bắt đầu thuê, được tính vào thời gian thuê.
contracts.end_date: Ngày kết thúc theo hợp đồng, được tính vào thời gian thuê.
contracts.actual_end_date: Ngày kết thúc thực tế đã xác nhận, cũng được tính vào thời gian thuê.
invoices.period_start: Ngày bắt đầu kỳ tính tiền, bao gồm.
invoices.period_end: Mốc kết thúc kỳ tính tiền, không bao gồm.
API period_end_exclusive: Cùng ý nghĩa với invoices.period_end.
Ví dụ kỳ tháng 11/2026:
[2026-11-01, 2026-12-01)
Mốc chốt đồng hồ cuối kỳ:
2026-12-01T00:00:00+07:00
Nếu hợp đồng kết thúc ngày 30/11/2026:
ContractEnded.effective_at = 2026-12-01T00:00:00+07:00
Không tính thêm tiền sau ngày kết thúc hợp đồng nếu chủ trọ chưa gia hạn.
21.1.4. Bảo mật
Admin: JWT.
Internal: Service token, chỉ sử dụng trong mạng nội bộ.
Public invoice: Token ngẫu nhiên, chỉ lưu hash trong Billing.
MoMo: Xác minh HMAC và đối chiếu thông tin thanh toán.
Rate limiting: Áp dụng cho Public API.
Logging: Không ghi token gốc, URL bí mật, mật khẩu hoặc khóa thanh toán.
HTTP headers: Referrer-Policy: no-referrer và Cache-Control: no-store cho trang hóa đơn.
Correlation: Truyền X-Correlation-ID qua REST và correlation_id qua RabbitMQ.
Error response: Thống nhất các trường code, message, correlation_id, details.
21.1.5. Quy ước HTTP
200: Thành công.
201: Tạo tài nguyên thành công.
202: Đã tiếp nhận công việc chạy nền.
400: Request không hợp lệ.
401: Chưa xác thực.
403: Không đủ quyền.
404: Không tìm thấy tài nguyên.
409: Xung đột nghiệp vụ hoặc trạng thái.
422: Dữ liệu không thỏa mãn ràng buộc.
503: Service phụ thuộc không sẵn sàng.
Các POST quan trọng phải được bảo vệ bằng unique constraints, idempotency hoặc kiểm tra trạng thái để tránh tạo dữ liệu trùng khi client retry.

21.2. REST API CONTRACTS
21.2.1. AUTH — 2 ENDPOINTS
POST /api/v1/auth/login
Mục đích: Đăng nhập quản trị.
GET /api/v1/auth/me
Mục đích: Xem thông tin tài khoản hiện tại.
21.2.2. ROOM SERVICE — 14 ENDPOINTS
GET /api/v1/properties
Mục đích: Danh sách khu trọ.
POST /api/v1/properties
Mục đích: Tạo khu trọ.
GET /api/v1/properties/{property_id}
Mục đích: Chi tiết khu trọ.
PATCH /api/v1/properties/{property_id}
Mục đích: Cập nhật khu trọ.
GET /api/v1/properties/{property_id}/buildings
Mục đích: Danh sách dãy nhà.
POST /api/v1/properties/{property_id}/buildings
Mục đích: Tạo dãy nhà.
GET /api/v1/buildings/{building_id}/floors
Mục đích: Danh sách tầng.
POST /api/v1/buildings/{building_id}/floors
Mục đích: Tạo tầng.
POST /api/v1/floors/{floor_id}/rooms/bulk
Mục đích: Tạo hàng loạt phòng.
GET /api/v1/rooms
Mục đích: Danh sách phòng.
GET /api/v1/rooms/{room_id}
Mục đích: Chi tiết phòng.
PATCH /api/v1/rooms/{room_id}
Mục đích: Cập nhật thông tin phòng.
PATCH /api/v1/buildings/{building_id}
Mục đích: Cập nhật tên hoặc trạng thái dãy nhà.
PATCH /api/v1/floors/{floor_id}
Mục đích: Cập nhật tên hoặc trạng thái tầng.
21.2.3. TENANT SERVICE — 17 ENDPOINTS
GET /api/v1/tenants
Mục đích: Danh sách người thuê.
POST /api/v1/tenants
Mục đích: Tạo hồ sơ người thuê.
GET /api/v1/tenants/{tenant_id}
Mục đích: Chi tiết người thuê.
PATCH /api/v1/tenants/{tenant_id}
Mục đích: Cập nhật người thuê.
GET /api/v1/contracts
Mục đích: Danh sách hợp đồng.
POST /api/v1/contracts
Mục đích: Tạo hợp đồng DRAFT.
GET /api/v1/contracts/expiring
Mục đích: Danh sách hợp đồng gần hết hạn.
GET /api/v1/contracts/{contract_id}
Mục đích: Chi tiết hợp đồng.
PATCH /api/v1/contracts/{contract_id}
Mục đích: Chỉnh sửa hợp đồng DRAFT.
GET /api/v1/contracts/{contract_id}/terms
Mục đích: Danh sách phiên bản điều khoản.
POST /api/v1/contracts/{contract_id}/terms
Mục đích: Thêm phiên bản điều khoản mới.
GET /api/v1/contracts/{contract_id}/events
Mục đích: Lịch sử thay đổi hợp đồng.
POST /api/v1/contracts/{contract_id}/confirm
Mục đích: Xác nhận hợp đồng.
POST /api/v1/contracts/{contract_id}/renew
Mục đích: Gia hạn hợp đồng.
POST /api/v1/contracts/{contract_id}/end
Mục đích: Xác nhận kết thúc hợp đồng.
POST /api/v1/contracts/{contract_id}/cancel
Mục đích: Hủy hợp đồng chưa có hiệu lực.
POST /api/v1/jobs/contracts/lifecycle/run
Mục đích: Chạy thủ công job vòng đời hợp đồng để demo.
21.2.4. METERING SERVICE — 8 ENDPOINTS
GET /api/v1/rooms/{room_id}/meters
Mục đích: Danh sách đồng hồ điện nước của phòng.
GET /api/v1/meters/{meter_id}/readings
Mục đích: Lịch sử số đo.
GET /api/v1/meters/{meter_id}/cutoffs
Mục đích: Danh sách mốc chốt.
POST /api/v1/meter-cutoffs/{cutoff_id}/confirm
Mục đích: Xác nhận chỉ số thủ công.
POST /api/v1/meter-cutoffs/{cutoff_id}/corrections
Mục đích: Tạo phiên bản chốt thay thế.
GET /api/v1/meter-alerts
Mục đích: Danh sách cảnh báo IoT.
POST /api/v1/meter-alerts/{alert_id}/resolve
Mục đích: Xác nhận xử lý cảnh báo.
POST /api/v1/jobs/meters/monthly-cutoffs/run
Mục đích: Chạy chốt chỉ số tháng thủ công.
21.2.5. BILLING SERVICE — 14 ENDPOINTS
GET /api/v1/invoices
Mục đích: Danh sách hóa đơn.
GET /api/v1/invoices/{invoice_id}
Mục đích: Chi tiết hóa đơn.
POST /api/v1/invoices/{invoice_id}/issue
Mục đích: Phát hành hóa đơn DRAFT đủ dữ liệu.
POST /api/v1/invoices/{invoice_id}/void
Mục đích: Hủy hóa đơn chưa thanh toán.
POST /api/v1/invoices/{invoice_id}/reissue
Mục đích: Phát hành phiên bản hóa đơn thay thế.
POST /api/v1/invoices/{invoice_id}/reminders
Mục đích: Yêu cầu gửi nhắc nợ.
GET /api/v1/invoices/{invoice_id}/payment-attempts
Mục đích: Danh sách lần thử thanh toán.
GET /api/v1/invoices/{invoice_id}/adjustments
Mục đích: Danh sách yêu cầu điều chỉnh.
POST /api/v1/invoices/{invoice_id}/adjustments
Mục đích: Ghi nhận yêu cầu điều chỉnh.
POST /api/v1/invoice-adjustments/{adjustment_id}/resolve
Mục đích: Đóng yêu cầu điều chỉnh.
GET /api/v1/billing-runs
Mục đích: Lịch sử chạy job lập hóa đơn.
POST /api/v1/billing-runs
Mục đích: Chạy lập hóa đơn theo tháng.
POST /api/v1/final-invoices
Mục đích: Lập hóa đơn quyết toán cho phần chưa tính tiền.
POST /api/v1/jobs/payments/reconcile/run
Mục đích: Đối soát giao dịch MoMo PENDING thủ công.
21.2.6. NOTIFICATION SERVICE — 3 ENDPOINTS
GET /api/v1/email-jobs
Mục đích: Danh sách tác vụ email.
GET /api/v1/email-jobs/{job_id}
Mục đích: Chi tiết tác vụ email.
POST /api/v1/email-jobs/{job_id}/retry
Mục đích: Thử gửi lại email thất bại.
21.2.7. PUBLIC API — 3 ENDPOINTS
GET /public/v1/invoices/{token}
Mục đích: Xem hóa đơn không cần đăng nhập.
POST /public/v1/invoices/{token}/payments/momo
Mục đích: Tạo hoặc sử dụng lại phiên thanh toán MoMo.
POST /webhooks/momo/ipn
Mục đích: Nhận thông báo kết quả thanh toán từ MoMo.
21.2.8. INTERNAL API — ROOM
GET /internal/v1/rooms/{room_id}/validation
Caller: Tenant Service.
Mục đích: Kiểm tra phòng tồn tại, còn hoạt động và thông tin cần thiết trước khi tạo hợp đồng.
21.2.9. INTERNAL API — TENANT
GET /internal/v1/contracts/{contract_id}/billing-context
Caller: Billing Service.
Mục đích: Lấy thông tin hợp đồng, người thuê và phiên bản giá trong kỳ tính tiền.
GET /internal/v1/contracts/billable
Caller: Billing Service.
Mục đích: Liệt kê các hợp đồng giao với kỳ cần lập hóa đơn, hỗ trợ cursor.
21.2.10. INTERNAL API — METERING
GET /internal/v1/meters
Caller: IoT Simulator.
Mục đích: Lấy danh sách đồng hồ đang hoạt động.
GET /internal/v1/rooms/{room_id}/usage
Caller: Billing Service.
Mục đích: Lấy số điện nước tiêu thụ từ hai mốc chốt.
Query: period_start, period_end_exclusive.
Response chứa chỉ số đầu, chỉ số cuối, lượng tiêu thụ và ID các cutoff liên quan.
21.2.11. INTERNAL API — BILLING
GET /internal/v1/invoices/{invoice_id}/reminder-eligibility
Caller: Notification Service.
Mục đích: Kiểm tra hóa đơn còn đủ điều kiện gửi nhắc nợ.
POST /internal/v1/invoices/{invoice_id}/access-links
Caller: Notification Service.
Mục đích: Xin liên kết truy cập hóa đơn có thời hạn.
Chỉ tạo liên kết khi hóa đơn đang ISSUED. Nếu PAID hoặc VOID, trả HTTP 409.
21.2.12. OPERATIONS
GET /health
Mục đích: Liveness.
GET /ready
Mục đích: Readiness.
Tổng số API operations: 70.

21.3. BUSINESS FLOWS
21.3.1. LUỒNG A — TẠO PHÒNG VÀ ĐỒNG HỒ
Bước 1: Chủ trọ tạo khu trọ, dãy nhà và tầng.
Bước 2: Frontend gọi POST /api/v1/floors/{floor_id}/rooms/bulk.
Bước 3: Room Service tạo các phòng và ghi mỗi RoomCreated vào outbox trong cùng transaction.
Bước 4: Outbox worker gửi sự kiện lên RabbitMQ.
Bước 5: Metering nhận RoomCreated, sử dụng processed_events để chống xử lý trùng.
Bước 6: Metering tạo hai đồng hồ ELECTRICITY và WATER cho mỗi phòng.
Bước 7: Simulator gọi Internal Metering API để lấy danh sách đồng hồ ACTIVE.
Bước 8: Simulator gửi dữ liệu đo lên MQTT, mặc định mỗi 5 phút.
Bước 9: Metering nhận dữ liệu qua RabbitMQ MQTT plugin và lưu vào meter_readings.
Ràng buộc: Nếu một phòng bị trùng mã khi tạo hàng loạt thì rollback toàn bộ lô.
Idempotency: Không tạo trùng đồng hồ khi RabbitMQ gửi lại RoomCreated.
21.3.2. LUỒNG B — QUẢN LÝ HỢP ĐỒNG
Tạo hợp đồng: POST /contracts tạo hợp đồng DRAFT cùng điều khoản giá ban đầu.
Xác nhận: POST /confirm kiểm tra phòng hoạt động, email người đại diện và ràng buộc hợp đồng chồng lấn. Hợp đồng chuyển SCHEDULED.
Kích hoạt: Job vòng đời kiểm tra đến start_date. Nếu phòng không có hợp đồng ACTIVE hoặc EXPIRED_PENDING khác, chuyển ACTIVE và phát ContractStarted.
ContractStarted.effective_at: 00:00 ngày start_date, giờ Việt Nam.
Room xử lý: Cập nhật occupancy_contract_id.
Metering xử lý: Tạo cutoff tại effective_at.
Gia hạn: POST /renew thay đổi ngày kết thúc, cập nhật phiên bản điều khoản nếu cần và lưu contract_events.
Quá hạn: Chuyển EXPIRED_PENDING nếu đã quá hạn nhưng chủ trọ chưa xác nhận kết thúc. Không tự giải phóng phòng.
Kết thúc: POST /end yêu cầu actual_end_date nằm trong khoảng [start_date, end_date].
ContractEnded.effective_at: 00:00 ngày sau actual_end_date, giờ Việt Nam.
Nguyên tắc: Không có quy trình bàn giao phòng độc lập. Mốc chốt đồng hồ được xác định từ ngày hiệu lực hợp đồng.
Nếu thiếu số đo hợp lệ, tạo cutoff PENDING để chủ trọ nhập chỉ số thủ công.
Nếu hợp đồng đã quá hạn và cần tính thêm ngày thuê thực tế, chủ trọ phải gia hạn trước khi kết thúc.

**Quy tắc hiệu lực và thứ tự event:**

POST /end ghi nhận actual_end_date nhưng không kết thúc hợp đồng trước thời điểm effective_at. Nếu effective_at còn ở tương lai, hợp đồng giữ ACTIVE; lifecycle job chuyển ENDED và phát ContractEnded khi đến hạn. Nếu mốc đã qua, xử lý ngay.

Room và Metering chỉ áp dụng ContractStarted/ContractEnded khi thời gian hiện tại >= effective_at.

Room lưu occupancy_updated_at theo effective_at, không dùng occurred_at hoặc thời điểm nhận message.

Khi ContractEnded(A) và ContractStarted(B) có cùng effective_at, hợp đồng B phải là trạng thái cuối cùng bất kể thứ tự event. ContractEnded(A) chỉ xóa occupancy nếu occupancy_contract_id = A. ContractStarted(B) được chấp nhận khi effective_at >= occupancy_updated_at. Event cũ không được ghi đè trạng thái mới.

Consumer phải xử lý idempotent. Viết integration test cho cả hai thứ tự: End(A) → Start(B) và Start(B) → End(A).

21.3.3. LUỒNG C — CHỐT CHỈ SỐ VÀ LẬP HÓA ĐƠN
00:00 ngày 1: Metering chốt chỉ số cho tất cả đồng hồ ACTIVE, kể cả phòng trống.
Chọn số đo: Lấy reading VALID gần nhất trước hoặc đúng thời điểm cutoff, trong dung sai 15 phút.
Thiếu dữ liệu: Tạo cutoff PENDING và yêu cầu xác nhận thủ công.
02:00 ngày 1: Billing bắt đầu chạy job lập hóa đơn tháng trước.
Lấy hợp đồng: Billing gọi /internal/v1/contracts/billable.
Lấy giá: Billing gọi /internal/v1/contracts/{contract_id}/billing-context.
Lấy điện nước: Billing gọi /internal/v1/rooms/{room_id}/usage.
Tính tiền phòng: monthly_rent × số ngày thuê thực tế trong tháng / số ngày của tháng.
Tính tiền điện: (chỉ số cuối - chỉ số đầu) × đơn giá điện.
Tính tiền nước: (chỉ số cuối - chỉ số đầu) × đơn giá nước.
Phí dịch vụ: Tính theo số ngày thuê theo quy tắc prorate đã chốt.
Làm tròn: Sử dụng Decimal, làm tròn từng khoản đến đơn vị đồng.
Thiếu dữ liệu: Hóa đơn giữ DRAFT và lưu blocked_reason.
Đủ dữ liệu: Hóa đơn chuyển ISSUED, tạo InvoiceIssued trong outbox cùng transaction.
Hạn thanh toán: Mặc định ngày 5 của tháng phát hành.
Retry: Billing định kỳ quét lại hóa đơn DRAFT bị chặn.
Hóa đơn FINAL: Chỉ bao phủ phần thời gian và các khoản tiền chưa được lập hóa đơn trước đó.
Chống trùng: Không có hai hóa đơn hợp lệ tính trùng cùng thời gian hoặc cùng khoản phải thu.
Với tiền thuê prorate, không áp CHECK cứng rằng invoice_items.amount = quantity × unit_price đã làm tròn để hiển thị, vì có thể gây sai lệch một vài đồng.
21.3.4. LUỒNG D — GỬI EMAIL VÀ NHẮC NỢ
Nguồn sự kiện: InvoiceIssued, InvoiceReminderRequested, PaymentSucceeded, ContractExpiring.
InvoiceIssued: Notification tạo email_job, chống trùng bằng source_event_id.
Tạo liên kết: Notification gọi API nội bộ Billing để lấy access link trước khi gửi.
Lưu token: Billing chỉ lưu hash của token.
Gửi email: Notification sử dụng Brevo SMTP, hoặc Mailpit trong môi trường local.
Nhắc nợ: Billing scheduler chạy hằng ngày và phát InvoiceReminderRequested.
Kiểm tra trước gửi: Notification gọi Billing reminder-eligibility.
Nếu PAID/VOID: Chuyển job sang SKIPPED.
Nếu Billing không phản hồi: Retry, không gửi email khi chưa xác minh.
Khi PaymentSucceeded: Tạo email biên nhận và bỏ qua các reminder đang chờ.
ContractExpiring: Gửi email về OWNER_EMAIL được cấu hình trong environment.
Lỗi gửi: Retry có backoff và giới hạn số lần thử.
21.3.5. LUỒNG E — THANH TOÁN MOMO
Bước 1: Người thuê mở /public/v1/invoices/{token}.
Bước 2: Người thuê chọn thanh toán MoMo.
Bước 3: Billing tạo payment_attempt PENDING trước khi gọi MoMo.
Bước 4: Nếu hóa đơn đã có attempt PENDING, không tạo thêm phiên mới. Trả lại pay_url đã có hoặc trạng thái chờ nếu kết quả chưa rõ.
Bước 5: Billing gọi MoMo Sandbox và lưu thông tin phiên thanh toán.
Bước 6: Người thuê hoàn tất thanh toán trên MoMo.
Bước 7: MoMo gửi IPN đến /webhooks/momo/ipn.
Bước 8: Billing xác minh HMAC, order_id, request_id, amount và kết quả thanh toán.
Bước 9: Billing ghi payment_webhook_receipts.
Bước 10: Nếu hợp lệ, chuyển attempt sang SUCCESS, invoice sang PAID và ghi outbox PaymentSucceeded trong cùng transaction.
Callback trùng: Xử lý idempotent, không chuyển trạng thái hoặc phát sự kiện thành công lần hai.
Timeout khi gọi MoMo: Không tự kết luận FAILED nếu kết quả chưa rõ.
Đối soát: Scheduler kiểm tra các attempt PENDING; admin có thể chạy thủ công qua POST /api/v1/jobs/payments/reconcile/run.
Kết quả đến muộn: Đưa vào đối soát thay vì bỏ qua.
Phạm vi thanh toán: Toàn bộ hóa đơn, không hỗ trợ thanh toán một phần.
Ngoài phạm vi: Hoàn tiền tự động và giao dịch tiền cọc.
21.3.6. LUỒNG F — CHỈNH SỬA VÀ LỊCH SỬ
Hóa đơn chưa thanh toán: Có thể VOID và reissue, miễn không có attempt PENDING chưa được xử lý.
Hóa đơn PAID: Không chỉnh sửa trực tiếp.
Sai sót sau thanh toán: Ghi invoice_adjustments, không hoàn tiền tự động.
Cutoff CONFIRMED: Không sửa trực tiếp giá trị.
Điều chỉnh cutoff: Tạo bản thay thế thông qua supersedes_id.
Cutoff đã dùng lập hóa đơn: Không tự động thay đổi hóa đơn đã phát hành.

21.4. EVENT CONTRACTS — RABBITMQ
21.4.1. Cấu hình chung
Exchange: rental.domain.v1
Exchange type: topic
Durable: true
Event format: JSON
Event version: 1
Delivery: At-least-once.
Outbox: Room, Tenant và Billing ghi sự kiện trong database transaction.
Consumer idempotency: processed_events hoặc unique constraint phù hợp.
21.4.2. Envelope chuẩn
event_id: UUID, định danh sự kiện.
event_type: Tên sự kiện.
event_version: Phiên bản schema.
occurred_at: Thời điểm sự kiện được tạo.
effective_at: Thời điểm có hiệu lực nghiệp vụ, bắt buộc với ContractStarted và ContractEnded.
correlation_id: UUID liên kết các log và thao tác.
aggregate_id: UUID của thực thể nghiệp vụ.
data: Payload nghiệp vụ.
Phân biệt: occurred_at không nhất thiết trùng effective_at.
Không đưa token hóa đơn, mật khẩu hoặc thông tin bí mật vào event payload.
21.4.3. EVENT 01 — RoomCreated
Routing key: room.created.v1
Publisher: Room Service.
Consumer: Metering Service.
Data bắt buộc:
room_id: UUID phòng.
property_id: UUID khu trọ.
floor_id: UUID tầng.
room_code: Mã phòng.
Xử lý: Metering tạo đồng hồ điện và đồng hồ nước, bảo đảm idempotent.
21.4.4. EVENT 02 — ContractStarted
Routing key: contract.started.v1
Publisher: Tenant Service.
Consumers: Room Service, Metering Service.
Envelope bắt buộc: effective_at.
Data bắt buộc:
contract_id: UUID hợp đồng.
room_id: UUID phòng.
start_date: Ngày bắt đầu hợp đồng.
Room xử lý: Đánh dấu phòng đang có hợp đồng.
Metering xử lý: Tạo cutoff CONTRACT_START tại effective_at.
21.4.5. EVENT 03 — ContractEnded
Routing key: contract.ended.v1
Publisher: Tenant Service.
Consumers: Room Service, Metering Service.
Envelope bắt buộc: effective_at.
Data bắt buộc:
contract_id: UUID hợp đồng.
room_id: UUID phòng.
actual_end_date: Ngày kết thúc thực tế.
Room xử lý: Chỉ xóa occupancy_contract_id nếu đúng hợp đồng tương ứng và event không cũ hơn trạng thái hiện tại.
Metering xử lý: Tạo cutoff CONTRACT_END tại effective_at.
21.4.6. EVENT 04 — ContractExpiring
Routing key: contract.expiring.v1
Publisher: Tenant Service.
Consumer: Notification Service.
Data bắt buộc:
contract_id: UUID hợp đồng.
room_id: UUID phòng.
end_date: Ngày kết thúc.
days_remaining: Số ngày còn lại.
room_code: Mã phòng.
tenant_name: Tên người thuê.
Xử lý: Notification gửi email cảnh báo cho chủ trọ qua OWNER_EMAIL.
21.4.7. EVENT 05 — InvoiceIssued
Routing key: invoice.issued.v1
Publisher: Billing Service.
Consumer: Notification Service.
Data bắt buộc:
invoice_id: UUID hóa đơn.
contract_id: UUID hợp đồng.
recipient_email: Email người thuê.
invoice_code: Mã hóa đơn.
total_amount: Tổng tiền.
due_date: Hạn thanh toán.
tenant_name: Tên người thuê.
room_code: Mã phòng.
period_start: Ngày bắt đầu kỳ.
period_end_exclusive: Ngày kết thúc độc quyền.
Xử lý: Notification tạo email job, xin liên kết truy cập từ Billing và gửi hóa đơn.
21.4.8. EVENT 06 — InvoiceReminderRequested
Routing key: invoice.reminder_requested.v1
Publisher: Billing Service.
Consumer: Notification Service.
Data bắt buộc:
invoice_id: UUID hóa đơn.
recipient_email: Email người thuê.
reminder_date: Ngày nhắc nợ.
due_date: Hạn thanh toán.
invoice_code: Mã hóa đơn.
total_amount: Số tiền.
tenant_name: Tên người thuê.
room_code: Mã phòng.
period_start: Ngày bắt đầu kỳ.
period_end_exclusive: Ngày kết thúc độc quyền.
Xử lý: Kiểm tra trạng thái hóa đơn hiện tại trước khi gửi nhắc nợ.
21.4.9. EVENT 07 — PaymentSucceeded
Routing key: payment.succeeded.v1
Publisher: Billing Service.
Consumer: Notification Service.
Data bắt buộc:
invoice_id: UUID hóa đơn.
payment_attempt_id: UUID phiên thanh toán.
paid_amount: Số tiền đã thanh toán.
recipient_email: Email người thuê.
invoice_code: Mã hóa đơn.
tenant_name: Tên người thuê.
room_code: Mã phòng.
period_start: Ngày bắt đầu kỳ.
period_end_exclusive: Ngày kết thúc độc quyền.
paid_at: Thời điểm thanh toán thành công.
Xử lý: Gửi biên nhận và bỏ qua các reminder đang chờ của hóa đơn.
21.4.10. Queue Bindings
room.events.q
Exchange: rental.domain.v1
Binding: contract.started.v1, contract.ended.v1
Consumer: Room Service.
metering.events.q
Exchange: rental.domain.v1
Binding: room.created.v1, contract.started.v1, contract.ended.v1
Consumer: Metering Service.
notification.events.q
Exchange: rental.domain.v1
Binding: contract.expiring.v1, invoice.issued.v1, invoice.reminder_requested.v1, payment.succeeded.v1
Consumer: Notification Service.
metering.telemetry.q
Exchange: amq.topic
Binding: meters.*.reading
Consumer: Metering Service.
Phải khai báo exchange, queue và binding trước khi Simulator publish MQTT.
21.4.11. Retry và Dead Letter Queue
Delivery semantics: At-least-once.
Số lần retry: Tối đa 3.
Retry lần 1: Sau 10 giây.
Retry lần 2: Sau 60 giây.
Retry lần 3: Sau 300 giây.
Hết retry: Chuyển vào DLQ.
Cơ chế: Dùng retry queue có message TTL và dead-letter exchange đưa message quay về source queue.
ACK: Sau khi đã commit transaction nghiệp vụ hoặc publish thành công sang retry queue với publisher confirms.
Outbox worker: Sử dụng FOR UPDATE SKIP LOCKED để lấy batch.
Publish: Persistent messages, sử dụng publisher confirms.
Tránh trùng: Consumer kiểm tra event_id trong cùng transaction với cập nhật dữ liệu.
Không giả định RabbitMQ bảo đảm exactly-once delivery.

21.5. MQTT CONTRACTS — IOT
21.5.1. Topic và cấu trúc message
MQTT topic: meters/{meterId}/reading
QoS: 1
Publisher: Python IoT Simulator.
Consumer: Metering Service thông qua RabbitMQ MQTT plugin.
Exchange: amq.topic.
AMQP routing key: meters.{meterId}.reading.
Queue: metering.telemetry.q.
Queue binding: meters.*.reading.
Payload:
meter_id: UUID đồng hồ.
measured_at: Thời điểm đo ISO 8601.
reading_value: Chỉ số tích lũy.
reading_value là tổng số điện hoặc nước đã đo, không phải lượng tiêu thụ của riêng chu kỳ 5 phút.
21.5.2. Ví dụ message
{
  "meter_id": "2600cc3a-67fd-4c37-947a-6cc7c1ab5c60",
  "measured_at": "2026-11-10T11:05:00+07:00",
  "reading_value": 1352.125
}
21.5.3. Xử lý dữ liệu bất thường
Duplicate cùng giá trị: Bỏ qua.
Duplicate khác giá trị: Tạo cảnh báo CONFLICTING_DUPLICATE.
Chỉ số giảm: Tạo cảnh báo READING_DECREASE.
Reading đến muộn sau khi chốt: Tạo cảnh báo LATE_AFTER_CUTOFF nếu liên quan mốc đã xác nhận.
Không nhận reading quá 15 phút: Tạo cảnh báo OFFLINE.
Nhận dữ liệu trở lại: Đóng cảnh báo OFFLINE phù hợp.
Khóa chống trùng: (meter_id, measured_at).
Môi trường chạy: Docker network nội bộ.
MQTT port 1883: Không mở công khai ra Internet trong cấu hình triển khai.

21.6. RÀNG BUỘC DATABASE VÀ TÍNH NHẤT QUÁN
21.6.1. Hợp đồng
Các hợp đồng cùng phòng không được chồng lấn khoảng ngày hiệu lực theo quy tắc nghiệp vụ.
Sử dụng PostgreSQL EXCLUDE constraint.
Ngày cuối hợp đồng được bao gồm trong thời gian thuê nên chuyển thành mốc cuối độc quyền khi xây dựng daterange.
Không mở rộng khoảng thời gian của EXPIRED_PENDING thành vô hạn trong constraint.
Nếu phòng còn ACTIVE hoặc EXPIRED_PENDING thì không kích hoạt hợp đồng SCHEDULED mới.
21.6.2. Hóa đơn
Khoảng thời gian hóa đơn là [period_start, period_end).
Ràng buộc EXCLUDE không cộng thêm một ngày vào period_end.
Ví dụ:
ALTER TABLE invoices
ADD CONSTRAINT invoices_no_period_overlap
EXCLUDE USING gist (
  contract_id WITH =,
  daterange(period_start, period_end, '[)') WITH &&
)
WHERE (status <> 'VOID');
Hóa đơn PERIODIC không được trùng hợp đồng và kỳ.
Hóa đơn FINAL chỉ chứa phần chưa được lập hóa đơn.
Không tự động thay đổi hóa đơn PAID.
21.6.3. Meter Cutoffs
Mỗi đồng hồ có tối đa một cutoff còn hiệu lực tại một thời điểm.
CREATE UNIQUE INDEX uq_meter_cutoffs_active_time
ON meter_cutoffs (meter_id, cutoff_at)
WHERE status <> 'SUPERSEDED';
cutoff_type và contract_id chỉ là nhãn nguồn gốc/ngữ cảnh khi tạo mốc. Nếu mốc tháng, kết thúc hợp đồng A và bắt đầu B trùng thời điểm thì dùng cùng cutoff.id và cùng reading_value; truy vấn theo (meter_id, cutoff_at), không tạo một cutoff mới theo type/contract_id.
MONTHLY cutoff áp dụng cho tất cả đồng hồ ACTIVE.
Dùng ON CONFLICT DO NOTHING khi nhiều job tạo cùng cutoff.
Bản CONFIRMED không được sửa trực tiếp giá trị.
21.6.4. Thanh toán
Một hóa đơn có tối đa một payment attempt SUCCESS.
Không cho phép nhiều payment attempt PENDING độc lập cùng lúc.
Callback MoMo phải được kiểm tra chữ ký và xử lý idempotent.
Timeout không đồng nghĩa thất bại.
Giao dịch chưa rõ kết quả phải được đối soát.
21.6.5. Outbox và Event Processing
Outbox được ghi cùng transaction với thay đổi nghiệp vụ.
Consumer ghi processed event cùng transaction xử lý dữ liệu.
Outbox worker có thể retry khi publish thất bại.
Không dùng cross-database transaction.
REST nội bộ cần timeout, retry có giới hạn và correlation logging.
Không triển khai Saga hoặc Kafka trong phiên bản đồ án.
21.6.6. Tính tiền và làm tròn
Tiền phòng prorate phải tính bằng Decimal từ giá thuê tháng gốc và tỷ lệ ngày thực tế.
Không dùng float để tính tiền.
Không bắt buộc invoice_items.amount bằng quantity × unit_price đã làm tròn để hiển thị.
Tổng tiền hóa đơn bằng tổng các khoản đã làm tròn đến đơn vị đồng.

21.7. SCHEDULED JOBS
21.7.1. Contract Lifecycle
Service: Tenant.
Lịch: Mỗi 5 phút, có thể cấu hình.
Mục đích: Kích hoạt hợp đồng SCHEDULED đến hạn và đánh dấu hợp đồng quá hạn.
Quy tắc: Chỉ kích hoạt nếu không có hợp đồng ACTIVE hoặc EXPIRED_PENDING khác chiếm dụng phòng.
Không tự giải phóng phòng khi hợp đồng hết hạn.
21.7.2. Monthly Cutoffs
Service: Metering.
Lịch: 00:00 ngày 1 mỗi tháng, giờ Việt Nam.
Mục đích: Chốt chỉ số tất cả đồng hồ ACTIVE.
Thiếu reading: Tạo cutoff PENDING.
Idempotency: Theo (meter_id, cutoff_at).
21.7.3. Offline Detector
Service: Metering.
Lịch: Mỗi 5 phút.
Ngưỡng: 15 phút không nhận dữ liệu.
Mục đích: Tạo và đóng cảnh báo OFFLINE.
21.7.4. Billing Monthly Run
Service: Billing.
Lịch: 02:00 ngày 1 mỗi tháng.
Mục đích: Lập hóa đơn cho kỳ tháng trước.
Quy tắc: Chỉ phát hành khi đủ dữ liệu hợp đồng và điện nước.
21.7.5. Billing DRAFT Retry
Service: Billing.
Lịch: Mỗi 15 phút, có thể cấu hình.
Mục đích: Quét lại hóa đơn DRAFT đang bị chặn.
Quy tắc: Nếu đủ dữ liệu thì phát hành; nếu chưa đủ thì tiếp tục chờ.
21.7.6. Reminder Scheduler
Service: Billing.
Lịch: Hằng ngày, ví dụ 09:00 giờ Việt Nam.
Mục đích: Phát sự kiện nhắc nợ cho các hóa đơn phù hợp.
Quy tắc: Notification kiểm tra lại trạng thái trước khi gửi.
21.7.7. MoMo Reconciliation
Service: Billing.
Lịch: Mỗi 5 phút, có thể cấu hình.
Mục đích: Đối soát payment attempts PENDING với MoMo.
Quy tắc: Không tự kết luận FAILED nếu chưa có kết quả xác định.
Chạy thủ công: POST /api/v1/jobs/payments/reconcile/run.
21.7.8. Email Worker
Service: Notification.
Lịch: Chạy liên tục.
Mục đích: Gửi email, retry và xử lý trạng thái SKIPPED.

21.8. DEPLOYMENT VÀ THỨ TỰ KHỞI ĐỘNG
Giai đoạn 1: PostgreSQL và RabbitMQ sẵn sàng.
Giai đoạn 2: Khai báo exchange, queues, bindings, retry queues và DLQ.
Giai đoạn 3: Khởi động các microservices và workers.
Giai đoạn 4: Khởi động IoT Simulator.
Giai đoạn 5: Kích hoạt các scheduled jobs.
Các job phải sử dụng idempotency hoặc cơ chế khóa phù hợp để tránh thực thi trùng khi nhiều replica cùng chạy.
Không mở PostgreSQL, RabbitMQ Management, MQTT hoặc Internal API trực tiếp ra Internet.
Dùng health/readiness probes, JSON structured logs và correlation ID để theo dõi hệ thống.
Các lịch mặc định có thể được điều chỉnh để trình diễn nhanh trong môi trường demo.

21.9. THỨ TỰ ƯU TIÊN TRIỂN KHAI
P0 — BẮT BUỘC
Auth: Đăng nhập JWT.
Room: Quản lý khu trọ và tạo phòng hàng loạt.
Tenant: Tạo, xác nhận, kích hoạt và kết thúc hợp đồng; chạy lifecycle job.
Metering: Tạo đồng hồ từ event, nhận MQTT, chống trùng dữ liệu, chốt chỉ số tháng và cảnh báo OFFLINE cơ bản.
Billing: Lấy hợp đồng, điều khoản, chỉ số, tính tiền, tạo và phát hành hóa đơn; retry DRAFT.
Notification: Gửi hóa đơn, nhắc nợ và biên nhận; kiểm tra trạng thái trước khi gửi.
MoMo: Thanh toán Sandbox, xử lý IPN, chống callback trùng và đối soát PENDING.
Distributed Systems: Transactional Outbox, idempotent consumer, retry và DLQ.
Cloud: Docker, CI/CD và triển khai lên AWS EC2.
P1 — SAU KHI P0 HOẠT ĐỘNG
Tenant: Gia hạn, thay đổi điều khoản và dashboard hợp đồng gần hết hạn.
Metering: Cảnh báo nâng cao, điều chỉnh cutoff và lịch sử xử lý bất thường.
Billing: Điều chỉnh hóa đơn đã thanh toán, phát hành lại hóa đơn và xử lý các thao tác ít dùng.
Notification: Gửi lại email, thay đổi email nhận hóa đơn và thu hồi liên kết cũ.
Observability: Bổ sung các dashboard và metrics nâng cao nếu còn thời gian.

21.10. TÀI LIỆU KỸ THUẬT VÀ QUY TẮC TRIỂN KHAI
openapi.yaml: Nguồn đặc tả REST API, gồm paths, HTTP methods, request schemas, response schemas, mã lỗi và xác thực.
asyncapi.yaml: Nguồn đặc tả RabbitMQ/MQTT, gồm channels, operations, message schemas và topology.
FastAPI: Sinh OpenAPI runtime từ Pydantic models và endpoints. Phải đối chiếu với hợp đồng API đã chốt để phát hiện sai khác.
SQLAlchemy: Định nghĩa ORM models và các thao tác database.
Alembic: Quản lý migration độc lập cho từng service.
Pydantic: Xác thực request/response và dữ liệu event.
HTTPX: Gọi REST nội bộ giữa các service.
aio-pika: Giao tiếp RabbitMQ AMQP.
Paho MQTT: Simulator publish dữ liệu đo.
PostgreSQL: Một instance, sáu database logic, không có Foreign Key xuyên database.
Nguyên tắc cuối: API/Event Contracts V1.1 là hợp đồng triển khai. Khi phát hiện điểm không phù hợp, nhóm phải cập nhật contract có kiểm soát, thay vì để từng service tự định nghĩa request, response hoặc event khác nhau.
Trạng thái thiết kế: Database V3 + OpenAPI 3.1 + AsyncAPI 3.0 + API/Event Contracts V1.1.
==============================
