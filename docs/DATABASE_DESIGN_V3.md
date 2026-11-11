# DATABASE DESIGN V3 — cập nhật thực thi V3.1

12.1. Nguyên tắc thiết kế
Hệ thống sử dụng PostgreSQL, gồm 6 database logic chạy trên một PostgreSQL instance: room_db, tenant_db, metering_db, billing_db, notification_db và auth_db.
Năm database đầu thuộc năm microservices nghiệp vụ. auth_db thuộc FastAPI Auth, thành phần xác thực hỗ trợ Nginx API Gateway.
Mỗi service chỉ được truy cập database do mình sở hữu. Các database không truy vấn trực tiếp lẫn nhau, không sử dụng Foreign Key xuyên database. Thông tin liên service được trao đổi thông qua REST API hoặc RabbitMQ.
Quy ước dữ liệu:
Khóa chính sử dụng UUID, ngoại trừ meter_readings dùng khóa chính kết hợp.
Tiền VNĐ sử dụng BIGINT; đơn giá cần độ chính xác thập phân sử dụng NUMERIC(18,4); chỉ số điện nước sử dụng NUMERIC(16,3).
Ngày nghiệp vụ dùng DATE. Thời điểm sự kiện dùng TIMESTAMPTZ, thống nhất lưu thời điểm theo UTC và xác định kỳ thanh toán theo Asia/Ho_Chi_Minh.
Các trạng thái dùng VARCHAR kết hợp CHECK, không bắt buộc sử dụng PostgreSQL native ENUM.
Dữ liệu ưu tiên chuẩn hóa 3NF. Những snapshot phục vụ lịch sử hóa đơn được lưu lặp có chủ đích.
Các bảng nghiệp vụ có created_at và updated_at khi thích hợp. Bảng lịch sử chỉ ghi thêm có thể không cần updated_at.
Chỉ sử dụng Foreign Key giữa các bảng trong cùng database. Các trường liên kết sang service khác là tham chiếu logic.

13. ROOM DATABASE – room_db
Số bảng: 6
13.1. properties
Mục đích: Quản lý các khu trọ.
Thuộc tính: id UUID PK; name VARCHAR; address TEXT; description TEXT nullable; status VARCHAR (ACTIVE/INACTIVE); created_at TIMESTAMPTZ; updated_at TIMESTAMPTZ.
Quan hệ: Một property có nhiều building.
13.2. buildings
Mục đích: Quản lý các dãy nhà trong khu trọ.
Thuộc tính: id UUID PK; property_id UUID FK → properties; name VARCHAR; status VARCHAR (ACTIVE/INACTIVE); created_at; updated_at.
Ràng buộc: UNIQUE(property_id, name).
Quan hệ: Một building thuộc một property và có nhiều floor.
13.3. floors
Mục đích: Quản lý tầng của từng dãy.
Thuộc tính: id UUID PK; building_id UUID FK → buildings; floor_number INTEGER; name VARCHAR nullable; status VARCHAR (ACTIVE/INACTIVE); created_at; updated_at.
Ràng buộc: UNIQUE(building_id, floor_number).
Quan hệ: Một floor có nhiều room.
13.4. rooms
Mục đích: Quản lý thông tin phòng và trạng thái sử dụng.
Thuộc tính: id UUID PK; property_id UUID FK → properties; floor_id UUID FK → floors; room_code VARCHAR; area_m2 NUMERIC(8,2); listed_rent BIGINT; status VARCHAR (ACTIVE/INACTIVE); occupancy_contract_id UUID nullable (logic → Tenant); occupancy_updated_at TIMESTAMPTZ nullable; created_at; updated_at.
Ràng buộc: UNIQUE(property_id, room_code); area_m2 > 0; listed_rent >= 0.
Phải bảo đảm property_id khớp với khu trọ thực sự chứa floor_id.
Trạng thái hiển thị Trống/Đang thuê được suy ra từ trạng thái hoạt động và thông tin hợp đồng hiện hành.
Room nhận ContractStarted và ContractEnded từ Tenant. Chỉ cập nhật trạng thái với sự kiện hợp lệ, không cho sự kiện cũ ghi đè dữ liệu mới. ContractEnded chỉ xóa thông tin chiếm dụng nếu đúng hợp đồng tương ứng.
13.5. outbox_events
Mục đích: Lưu sự kiện Room trước khi phát lên RabbitMQ.
Thuộc tính: id UUID PK; aggregate_type VARCHAR; aggregate_id UUID; event_type VARCHAR; event_version INTEGER; payload JSONB; correlation_id UUID nullable; dedupe_key VARCHAR nullable UNIQUE; created_at; published_at TIMESTAMPTZ nullable; attempts INTEGER; last_error TEXT nullable.
Sự kiện: RoomCreated.
13.6. processed_events
Mục đích: Chống xử lý lặp sự kiện nhận từ RabbitMQ.
Thuộc tính: event_id UUID PK; event_type VARCHAR; processed_at TIMESTAMPTZ.
Sự kiện nhận: ContractStarted, ContractEnded.

14. TENANT DATABASE – tenant_db
Số bảng: 5
14.1. tenants
Mục đích: Quản lý hồ sơ người thuê.
Thuộc tính: id UUID PK; full_name VARCHAR; phone VARCHAR nullable; email VARCHAR nullable; note TEXT nullable; created_at; updated_at.
Email bắt buộc đối với người đại diện hợp đồng sử dụng hình thức nhận hóa đơn qua email.
Không lưu CCCD hoặc thông tin nhạy cảm không cần thiết.
14.2. contracts
Mục đích: Quản lý quan hệ thuê phòng.
Thuộc tính: id UUID PK; contract_code VARCHAR UNIQUE; room_id UUID (logic → Room); room_code_snapshot VARCHAR; representative_tenant_id UUID FK → tenants; start_date DATE; end_date DATE; actual_end_date DATE nullable; status VARCHAR; deposit_amount BIGINT nullable; end_reason TEXT nullable; created_at; updated_at.
Trạng thái: DRAFT, SCHEDULED, ACTIVE, EXPIRED_PENDING, ENDED, CANCELLED.
deposit_amount chỉ lưu số tiền cọc thỏa thuận. Không phát sinh nghiệp vụ quản lý giao dịch tiền cọc.
Ràng buộc: Ngày kết thúc hợp lệ so với ngày bắt đầu. Không cho phép hai hợp đồng cùng phòng có thời gian chiếm dụng hiệu lực chồng lấn.
Dùng PostgreSQL EXCLUDE constraint trên khoảng thời gian hợp đồng đối với các trạng thái cần kiểm soát.
Ngày kết thúc trên giao diện được hiểu là ngày thuê cuối cùng, còn range kỹ thuật dùng quy ước [start, end) sau khi chuyển đổi mốc cuối phù hợp.
EXPIRED_PENDING tiếp tục ngăn tạo hợp đồng mới có thời gian chiếm dụng trùng cho đến khi chủ trọ xử lý.
14.3. contract_terms
Mục đích: Lưu điều khoản và lịch sử thay đổi giá.
Thuộc tính: id UUID PK; contract_id UUID FK → contracts; effective_from DATE; effective_to DATE nullable; monthly_rent BIGINT; electricity_unit_price BIGINT; water_unit_price BIGINT; monthly_service_fee BIGINT mặc định 0; created_at.
Ràng buộc: Các phiên bản điều khoản trong cùng hợp đồng không được chồng lấn thời gian hiệu lực.
effective_to là mốc bắt đầu hết hiệu lực, không bao gồm ngày đó.
Khi đổi giá hoặc gia hạn, tạo phiên bản điều khoản mới thay vì ghi đè giá cũ.
Thay đổi giá thông thường có hiệu lực từ kỳ tháng tiếp theo.
14.4. contract_events
Mục đích: Lưu lịch sử thay đổi hợp đồng.
Thuộc tính: id UUID PK; contract_id UUID FK → contracts; event_type VARCHAR; occurred_at TIMESTAMPTZ; actor_id UUID nullable (logic → Auth); reason TEXT nullable; details JSONB; created_at.
Loại sự kiện lịch sử: CREATED, CONFIRMED, STARTED, EXTENDED, TERMINATION_RECORDED, ENDED, CANCELLED.
Lưu dữ liệu trước và sau khi thay đổi vào details khi cần phục vụ kiểm tra.
Đây là bảng lịch sử nội bộ, khác với các sự kiện được phát lên RabbitMQ.
14.5. outbox_events
Sử dụng cấu trúc outbox thống nhất như Room Service.
Sự kiện phát: ContractStarted, ContractEnded, ContractExpiring.
Event phải chứa room_id, contract_id, thời điểm hiệu lực và những thông tin cần thiết cho consumer.

15. METERING DATABASE – metering_db
Số bảng: 5
15.1. meters
Mục đích: Quản lý đồng hồ điện nước giả lập.
Thuộc tính: id UUID PK; room_id UUID (logic → Room); meter_code VARCHAR UNIQUE; meter_type VARCHAR (ELECTRICITY/WATER); unit VARCHAR (KWH/M3); initial_reading NUMERIC(16,3); status VARCHAR (ACTIVE/INACTIVE); last_received_at TIMESTAMPTZ nullable; created_at; updated_at.
Ràng buộc: UNIQUE(room_id, meter_type).
Mỗi phòng có một đồng hồ điện và một đồng hồ nước.
Simulator gọi REST nội bộ Metering để lấy danh sách đồng hồ cần mô phỏng.
15.2. meter_readings
Mục đích: Lưu dữ liệu đo nhận từ MQTT.
Thuộc tính: meter_id UUID FK → meters; measured_at TIMESTAMPTZ; reading_value NUMERIC(16,3); received_at TIMESTAMPTZ; validation_status VARCHAR (VALID/SUSPECT/REJECTED); anomaly_reason TEXT nullable.
Khóa chính kết hợp: (meter_id, measured_at).
Không lưu trùng phép đo có cùng đồng hồ và thời điểm.
Nếu bản ghi trùng khóa nhưng khác chỉ số, không tự ghi đè mà ghi nhận cảnh báo.
Chỉ số giảm bất thường được phát hiện dựa trên thứ tự thời điểm đo, không phải thứ tự dữ liệu được nhận.
15.3. meter_cutoffs
Mục đích: Lưu chỉ số chốt tại mốc hợp đồng và kỳ hóa đơn.
Thuộc tính: id UUID PK; meter_id UUID FK → meters; contract_id UUID nullable (logic → Tenant); cutoff_type VARCHAR (CONTRACT_START/CONTRACT_END/MONTHLY); cutoff_at TIMESTAMPTZ; reading_value NUMERIC(16,3) nullable; source VARCHAR (AUTOMATIC/MANUAL); source_reading_at TIMESTAMPTZ nullable; manual_reason TEXT nullable; status VARCHAR (PENDING/CONFIRMED/SUPERSEDED); confirmed_at TIMESTAMPTZ nullable; confirmed_by UUID nullable (logic → Auth); supersedes_id UUID nullable FK → meter_cutoffs; created_at.
Ràng buộc: Với mỗi (meter_id, cutoff_at) chỉ có MỘT bản chốt chưa SUPERSEDED, bất kể cutoff_type/contract_id; các mục đích chốt trùng thời điểm dùng lại chính bản chốt này. cutoff_type và contract_id chỉ ghi nguồn gốc/ngữ cảnh tạo bản chốt, không phải khóa xác định một giá trị đo khác. Bản CONFIRMED phải có giá trị chỉ số.
Nếu nhập thủ công, phải có lý do và người xác nhận.
Chỉ số tự động được chọn từ bản ghi VALID gần nhất trước hoặc tại thời điểm chốt trong ngưỡng dung sai.
Ngưỡng đề xuất: 15 phút. Nếu không có dữ liệu hợp lệ thì giữ PENDING để chủ trọ xác nhận thủ công.
Bản chốt đã xác nhận không được sửa trực tiếp giá trị. Khi cần điều chỉnh, tạo phiên bản mới có tham chiếu đến bản cũ.
Nếu bản chốt đã được dùng trong hóa đơn, không được tự động thay thế và thay đổi hóa đơn đã phát hành.
15.4. meter_alerts
Mục đích: Lưu cảnh báo IoT.
Thuộc tính: id UUID PK; meter_id UUID FK → meters; alert_type VARCHAR; status VARCHAR (OPEN/RESOLVED); related_measured_at TIMESTAMPTZ nullable; related_cutoff_id UUID nullable FK → meter_cutoffs; detail JSONB; detected_at TIMESTAMPTZ; resolved_at TIMESTAMPTZ nullable; resolution_note TEXT nullable.
Loại cảnh báo: OFFLINE, READING_DECREASE, LATE_AFTER_CUTOFF, CONFLICTING_DUPLICATE.
Không tạo nhiều cảnh báo OFFLINE đang mở cho cùng một đồng hồ.
Ngưỡng mất kết nối đề xuất: 15 phút không nhận dữ liệu mới, tính theo thời gian thực của hệ thống.
15.5. processed_events
Thuộc tính: event_id UUID PK; event_type VARCHAR; processed_at TIMESTAMPTZ.
Sự kiện nhận: RoomCreated, ContractStarted, ContractEnded.
Đánh dấu đã xử lý trong cùng transaction với thay đổi nghiệp vụ để chống xử lý trùng.

16. BILLING DATABASE – billing_db
Số bảng: 8
16.1. invoices
Mục đích: Quản lý hóa đơn.
Thuộc tính: id UUID PK; invoice_code VARCHAR UNIQUE; contract_id UUID (logic → Tenant); room_id UUID (logic → Room); invoice_type VARCHAR (PERIODIC/FINAL); billing_month DATE nullable; period_start DATE; period_end DATE; status VARCHAR (DRAFT/ISSUED/PAID/VOID); blocked_reason TEXT nullable; revision INTEGER; replaces_invoice_id UUID nullable FK → invoices; void_reason TEXT nullable; total_amount BIGINT; due_date DATE; issued_at TIMESTAMPTZ nullable; paid_at TIMESTAMPTZ nullable; voided_at TIMESTAMPTZ nullable; tenant_name_snapshot VARCHAR; tenant_email_snapshot VARCHAR; room_code_snapshot VARCHAR; created_at; updated_at.
Ràng buộc: Mỗi hợp đồng có tối đa một hóa đơn PERIODIC chưa hủy cho một kỳ tháng và tối đa một hóa đơn FINAL chưa hủy.
Không cho các hóa đơn còn hiệu lực tính trùng cùng khoảng thời gian hoặc cùng khoản phải thu.
Hóa đơn DRAFT có thể có blocked_reason khi thiếu thông tin hợp đồng hoặc chỉ số điện nước.
Hóa đơn ISSUED có thể được thay thế trước thanh toán. Hóa đơn PAID không được sửa trực tiếp.
Quá hạn được suy ra từ trạng thái ISSUED và due_date, không lưu thành trạng thái độc lập.
Chỉ mục quan trọng: (contract_id, billing_month) và (status, due_date).
16.2. invoice_items
Mục đích: Lưu chi tiết các khoản tính tiền.
Thuộc tính: id UUID PK; invoice_id UUID FK → invoices; item_type VARCHAR (RENT/ELECTRICITY/WATER/SERVICE); description VARCHAR; quantity NUMERIC(16,3); unit VARCHAR; unit_price NUMERIC(18,4); amount BIGINT; period_start DATE nullable; period_end DATE nullable; meter_start_value NUMERIC(16,3) nullable; meter_end_value NUMERIC(16,3) nullable; source_term_id UUID nullable (logic → Tenant); source_cutoff_start_id UUID nullable (logic → Metering); source_cutoff_end_id UUID nullable (logic → Metering).
Ràng buộc: Số lượng và đơn giá thông thường không âm. Mỗi dòng tính tiền được làm tròn đến đơn vị đồng theo quy tắc thống nhất.
Tổng tiền hóa đơn phải bằng tổng tiền các dòng chi tiết.
Lưu snapshot đơn giá và chỉ số để hóa đơn cũ không thay đổi khi hợp đồng hoặc dữ liệu IoT được cập nhật.
16.3. invoice_adjustments
Mục đích: Ghi nhận yêu cầu điều chỉnh hóa đơn đã thanh toán.
Thuộc tính: id UUID PK; invoice_id UUID FK → invoices; reason TEXT; amount_delta BIGINT (có thể âm); status VARCHAR (OPEN/RESOLVED/REJECTED); resolution_note TEXT nullable; created_by UUID nullable (logic → Auth); created_at; resolved_at TIMESTAMPTZ nullable.
Không tự động hoàn tiền hoặc sửa hóa đơn PAID. Chỉ ghi nhận và theo dõi yêu cầu xử lý sai lệch.
16.4. payment_attempts
Mục đích: Quản lý các lần thử thanh toán qua MoMo.
Thuộc tính: id UUID PK; invoice_id UUID FK → invoices; provider VARCHAR; order_id VARCHAR UNIQUE; request_id VARCHAR UNIQUE; provider_transaction_id VARCHAR nullable; amount BIGINT; status VARCHAR (PENDING/SUCCESS/FAILED/EXPIRED); pay_url TEXT nullable; expires_at TIMESTAMPTZ nullable; result_code VARCHAR nullable; confirmed_at TIMESTAMPTZ nullable; last_reconciled_at TIMESTAMPTZ nullable; created_at; updated_at.
Ràng buộc: Mỗi hóa đơn chỉ có tối đa một payment attempt SUCCESS.
Không cho nhiều payment attempt PENDING độc lập cho cùng hóa đơn.
Callback trùng không được ghi nhận thanh toán hai lần.
Giao dịch PENDING cần được đối soát với MoMo trước khi xác định kết quả cuối cùng. Kết quả thành công đến muộn không được tự bỏ qua, mà phải đối soát và xử lý nhất quán.
16.5. payment_webhook_receipts
Mục đích: Lưu nhật ký callback MoMo.
Thuộc tính: id UUID PK; payment_attempt_id UUID nullable FK → payment_attempts; order_id VARCHAR; payload_fingerprint VARCHAR; signature_valid BOOLEAN; processing_result VARCHAR; received_at TIMESTAMPTZ; processed_at TIMESTAMPTZ nullable.
Kết quả xử lý: PROCESSED, DUPLICATE, INVALID_SIGNATURE, UNKNOWN_ORDER, AMOUNT_MISMATCH và các trường hợp cần đối soát.
Cho phép lưu nhiều lần callback có cùng nội dung để kiểm tra và demo tình huống callback trùng.
Không lưu thông tin bí mật hoặc khóa thanh toán vào nhật ký.
16.6. invoice_access_tokens
Mục đích: Quản lý quyền truy cập hóa đơn không cần đăng nhập.
Thuộc tính: id UUID PK; invoice_id UUID FK → invoices; token_hash VARCHAR UNIQUE; expires_at TIMESTAMPTZ; revoked_at TIMESTAMPTZ nullable; created_at; last_used_at TIMESTAMPTZ nullable.
Token gốc được tạo ngẫu nhiên và chỉ lưu hash trong database.
Khi hóa đơn bị hủy, thay thế hoặc cần thu hồi quyền truy cập, token tương ứng phải bị vô hiệu hóa.
Notification nhận thông tin hóa đơn qua event. Khi chuẩn bị gửi email, Notification sử dụng API nội bộ được xác thực của Billing để lấy liên kết truy cập có thời hạn.
Không ghi token gốc vào log hoặc payload sự kiện RabbitMQ.
16.7. billing_runs
Mục đích: Theo dõi quá trình tạo hóa đơn định kỳ.
Thuộc tính: id UUID PK; billing_month DATE; trigger_type VARCHAR (SCHEDULED/MANUAL); status VARCHAR (RUNNING/COMPLETED/FAILED); started_at TIMESTAMPTZ; finished_at TIMESTAMPTZ nullable; issued_count INTEGER; waiting_count INTEGER; skipped_count INTEGER; failed_count INTEGER.
Cho phép chạy lại job cùng kỳ.
Ràng buộc tại invoices phải bảo đảm không tạo hóa đơn trùng, kể cả khi nhiều replica cùng chạy.
16.8. outbox_events
Sử dụng cấu trúc outbox thống nhất.
Sự kiện phát: InvoiceIssued, InvoiceReminderRequested, PaymentSucceeded.
Phải lưu sự kiện trong cùng transaction với thay đổi nghiệp vụ tương ứng.

17. NOTIFICATION DATABASE – notification_db
Số bảng: 1
17.1. email_jobs
Mục đích: Quản lý công việc gửi email và xử lý retry.
Thuộc tính: id UUID PK; source_event_id UUID UNIQUE; email_type VARCHAR (INVOICE/REMINDER/PAYMENT_RECEIPT/CONTRACT_EXPIRING); invoice_id UUID nullable (logic → Billing); recipient_email VARCHAR; subject VARCHAR; template_data JSONB; status VARCHAR (PENDING/SENDING/SENT/FAILED/SKIPPED); attempt_count INTEGER; next_attempt_at TIMESTAMPTZ nullable; locked_until TIMESTAMPTZ nullable; sent_at TIMESTAMPTZ nullable; last_error TEXT nullable; provider_message_id VARCHAR nullable; created_at; updated_at.
Ràng buộc: Không tạo nhiều email job từ cùng một event trong mô hình một event tương ứng một email.
Worker sử dụng cơ chế khóa công việc để nhiều replica không đồng thời xử lý cùng job.
Nếu gửi thất bại, thực hiện retry có giới hạn. Sau khi hết số lần thử, ghi FAILED.
Đối với email nhắc nợ, Notification phải kiểm tra trạng thái hiện hành từ Billing ngay trước khi gửi. Nếu hóa đơn đã thanh toán hoặc Billing không phản hồi, không gửi nhắc nợ; xử lý SKIPPED hoặc retry tương ứng.
Khi nhận PaymentSucceeded, có thể đánh dấu các reminder đang chờ của hóa đơn tương ứng thành SKIPPED.
Email cảnh báo hợp đồng hết hạn được gửi về email chủ trọ cấu hình bằng OWNER_EMAIL.
template_data chỉ lưu thông tin cần gửi, không lưu lâu dài liên kết thanh toán chứa token bí mật.

18. AUTH DATABASE – auth_db
Số bảng: 1
18.1. users
Mục đích: Quản lý tài khoản đăng nhập chủ trọ tại FastAPI Auth.
Thuộc tính: id UUID PK; email VARCHAR UNIQUE; password_hash VARCHAR; full_name VARCHAR; is_active BOOLEAN; last_login_at TIMESTAMPTZ nullable; created_at; updated_at.
Email được chuẩn hóa trước khi lưu và phải duy nhất không phân biệt chữ hoa/thường.
Mật khẩu chỉ lưu dưới dạng hash an toàn.
Phiên bản đầu tiên chỉ cần tài khoản chủ trọ, chưa xây dựng hệ thống vai trò phức tạp hoặc tài khoản người thuê.

19. RÀNG BUỘC VÀ NGUYÊN TẮC TOÀN HỆ THỐNG
19.1. Referential Integrity
Sử dụng Foreign Key thực sự cho các quan hệ trong cùng database.
Các trường tham chiếu sang database khác chỉ lưu UUID và phải được xác minh thông qua service sở hữu dữ liệu.
Không dùng cross-database join cho logic nghiệp vụ.
19.2. Database Constraints
Sử dụng UNIQUE để chống trùng mã phòng, mã hợp đồng, hóa đơn theo kỳ, mã giao dịch và dữ liệu đo.
Sử dụng CHECK để kiểm soát số tiền, chỉ số, trạng thái và các điều kiện dữ liệu cơ bản.
Sử dụng PostgreSQL EXCLUDE constraint với range types để ngăn khoảng thời gian hợp đồng và phiên bản điều khoản chồng lấn.
Dùng partial unique index để bảo đảm hóa đơn hợp lệ và thanh toán thành công không bị tạo trùng.
19.3. Transaction và Idempotency
Mọi thay đổi cần tính nguyên tử trong một service phải sử dụng transaction.
Outbox event phải được ghi cùng transaction với dữ liệu nghiệp vụ.
Processed event phải được ghi cùng transaction với kết quả consumer xử lý.
RabbitMQ có thể gửi lại message, vì vậy mỗi consumer phải xử lý lặp an toàn.
Không giả định hệ thống phân tán có exactly-once delivery.
19.4. Data History
Không ghi đè lịch sử hợp đồng, điều khoản giá và hóa đơn đã thanh toán.
Hóa đơn lưu snapshot của những dữ liệu được sử dụng để tính tiền.
Chỉ số điện nước đã dùng để lập hóa đơn không được tự thay đổi khi có dữ liệu mới đến muộn.
Các thay đổi quan trọng phải có lịch sử và khả năng truy vết.
19.5. ORM và Migration
Sử dụng SQLAlchemy 2.x để định nghĩa models, relationships và truy vấn dữ liệu.
Sử dụng Alembic để quản lý database migrations.
Mỗi microservice quản lý ORM models và migrations của database mình.
Không dùng một bộ migration chung cho cả năm service.
Các migration sinh tự động phải được kiểm tra, đặc biệt với partial indexes, exclusion constraints và những ràng buộc PostgreSQL đặc thù.

20. TỔNG KẾT DATABASE DESIGN V3
room_db: 6 bảng.
tenant_db: 5 bảng.
metering_db: 5 bảng.
billing_db: 8 bảng.
notification_db: 1 bảng.
auth_db: 1 bảng.
Tổng cộng: 26 bảng trong 6 database logic, chạy trên một PostgreSQL instance.
ORM và migration ban đầu của 26 bảng đã được chạy thành công. Các bản vá ràng buộc phát hiện sau nghiệm thu được bổ sung bằng migration mới, không sửa lịch sử V3 đã chạy.
Những việc tiếp theo: Kiểm chứng ràng buộc dữ liệu bằng integration tests, hoàn thiện các API, worker, scheduler và xử lý nghiệp vụ; đồng bộ đặc tả OpenAPI/AsyncAPI. API/Event Contracts; kiểm thử tính toàn vẹn dữ liệu và khả năng chống xử lý trùng.
Không tự ý bổ sung bảng, thay đổi ranh giới service hoặc thay đổi bộ công nghệ khi chưa có lý do nghiệp vụ hay kỹ thuật rõ ràng.
## Ghi chú ràng buộc triển khai
- Room: phòng phải thuộc chính khu trọ chứa floor. Bản vá Room V3.1 kiểm tra điều này bằng trigger ở DB, đồng thời cần kiểm tra tại service khi viết API.
- Database isolation: PostgreSQL PUBLIC có quyền CONNECT mặc định; cần thu hồi khỏi 6 database, kể cả trên volume đã tồn tại.
- Metering: bản vá V3.1 thay index theo cutoff_type/contract_id thành một unique index theo (meter_id, cutoff_at) cho các bản chưa SUPERSEDED. Trước khi migration chạy, phải giải quyết mọi bản chốt còn hiệu lực bị trùng thời điểm.


## P00.1 — Quy tắc bất biến cấu trúc phòng (room_v3_003, 2026-11-11)

Đã chốt **không có nghiệp vụ chuyển dãy nhà sang khu trọ khác** hay
**chuyển tầng sang dãy nhà khác**. Sau khi INSERT, hai khóa
`buildings.property_id` và `floors.building_id` không được UPDATE sang
ID khác trong mọi trường hợp, kể cả dãy/tầng chưa có phòng. Các field
được phép PATCH trong OpenAPI (ví dụ tên, trạng thái) không bị ảnh hưởng.

Lý do: revision `room_v3_002` chỉ chặn di chuyển nếu thấy phòng tồn tại;
trong hai transaction đồng thời, phép kiểm tra này có thể không nhìn thấy
phòng chưa commit. Revision `room_v3_003` đổi hàm trigger thành chặn
thay đổi khóa cha vô điều kiện; không tạo thêm bảng và không sửa migration
đã áp dụng. Có kiểm thử PostgreSQL dùng savepoint và rollback.

Schema xác thực trên local luôn đối chiếu `alembic_version` với `alembic heads`
của image service tương ứng; không ghi cố định 001/002/003.
