# P07: Chốt chỉ số điện/nước (Metering)

## Phạm vi và quyết định nghiệp vụ

P05 đã tạo một `meter_cutoffs` dạng `PENDING` khi nhận `ContractStarted` / `ContractEnded`, sử dụng một mốc vật lý chung nếu kết thúc hợp đồng A và bắt đầu hợp đồng B cùng một thời điểm. P07 hoàn tất việc chốt mốc đã được tạo, bổ sung cutoff theo tháng lúc **00:00 ngày 1 theo giờ Việt Nam** (`Asia/Ho_Chi_Minh`, UTC+7; `period_end` exclusive), và cảnh báo đồng hồ offline. Billing P08 chỉ được lấy **bản `CONFIRMED` chưa bị thay thế**.

**Chính sách chọn chỉ số:** Hệ thống tự động chọn reading `VALID` mới nhất được đo trong khoảng `[cutoff_at - 15 phút, cutoff_at]`, bao gồm hai đầu. Không sử dụng reading đo sau thời điểm chốt, `SUSPECT` hoặc `REJECTED`.

Job chờ 15 phút sau thời điểm chốt để tiếp nhận các reading truyền đến muộn. Nếu không có reading phù hợp, cutoff giữ trạng thái `PENDING` để chủ trọ xác nhận thủ công.

Cutoff đã `CONFIRMED` không được tự động thay đổi. Nếu một reading hợp lệ được đo trước hoặc đúng mốc nhưng đến sau khi chốt và có thời điểm đo gần mốc hơn reading đã chọn, hệ thống tạo cảnh báo `LATE_AFTER_CUTOFF` để người quản lý kiểm tra. Việc hiệu chỉnh phải tạo phiên bản cutoff mới.

Cutoff theo tháng được tạo cho mọi đồng hồ `ACTIVE` từ sau thời điểm tạo đồng hồ (`created_at`); bao gồm phòng chưa có hợp đồng. Job backfill tối đa 24 tháng (cấu hình `P07_MONTHS_BACK`, giới hạn 1..120); dữ liệu cũ hơn cần thao tác backfill có chủ đích. Nếu một mốc tháng trùng một cutoff bàn giao chưa `SUPERSEDED`, **tái sử dụng cutoff đó**, không tạo mốc vật lý thứ hai; lý do hợp đồng nằm ở `meter_cutoff_reasons`. Nếu hợp đồng đến muộn khi cutoff đã xác nhận, chỉ thêm lý do, không đổi loại/chỉ số của cutoff đã xác nhận.

`CONFIRMED` không bị job cập nhật lại. Chủ trọ có thể `POST /api/v1/meter-cutoffs/{id}/corrections` với `reading_value` và `manual_reason` để tạo hàng mới `CONFIRMED`, đặt `supersedes_id` trỏ về bản cũ; bản cũ chỉ chuyển trạng thái `SUPERSEDED`. Toàn bộ `MeterCutoffReason` được sao chép sang bản mới để P08 truy vấn đúng hợp đồng. Không cho sửa bản `SUPERSEDED` hoặc cập nhật một bản `CONFIRMED` qua endpoint `confirm`. Số đo nhập tay không thể giảm so với cutoff xác nhận trước hoặc vượt cutoff xác nhận sau. Header `X-Auth-User-Id` phải do Nginx lấy từ JWT được Auth kiểm chứng, không nhận actor trong JSON.

Nếu một mẫu `VALID` đến sau khi cutoff tự động đã `CONFIRMED`, và gần mốc hơn nguồn đã chốt, hệ thống ghi `LATE_AFTER_CUTOFF` cho rà soát thủ công; không thay thế số đã chốt. Cảnh báo `OFFLINE` tạo khi `last_received_at` hoặc (nếu chưa có mẫu) `created_at` quá `P07_OFFLINE_MINUTES` (mặc định 20 phút). Mỗi đồng hồ chỉ có một cảnh báo offline `OPEN` đang hiệu lực. Khi nhận telemetry hợp lệ kể cả bản QoS 1 trùng, tự đóng cảnh báo offline; chủ trọ có thể xác nhận xử lý cảnh báo khác qua API.

## API chính

`GET /api/v1/meters/{meter_id}/cutoffs`: danh sách các phiên bản cutoff của đồng hồ. `GET /api/v1/meter-cutoffs` hỗ trợ `meter_id`, `room_id`, `status`, `cutoff_type`, `from`, `to` (đầu bao gồm/cuối không bao gồm), `page`, `page_size`. `GET /api/v1/meter-cutoffs/{cutoff_id}` truy vấn từng bản. `POST /api/v1/meter-cutoffs/{cutoff_id}/confirm` chỉ cho `PENDING` và bắt buộc `{ "reading_value": "123.000", "manual_reason": "Đọc trực tiếp tại đồng hồ" }`; `POST .../{cutoff_id}/corrections` tạo bản thay thế, HTTP 201. `POST /api/v1/meter-alerts/{alert_id}/resolve` nhận `resolution_note`.

`POST /api/v1/jobs/meters/monthly-cutoffs/run` nhận `{ "cutoff_at": "2026-11-30T17:00:00Z" }` để chạy thủ công mốc tháng 12. Job thực tế tự chạy bằng container `metering-cutoff-scheduler` (không cần REST trigger), mặc định mỗi 60 giây. `GET /internal/v1/rooms/{room_id}/cutoffs` yêu cầu `X-Service-Token` và **chỉ trả bản CONFIRMED hiện hành**, với danh sách `reasons` và dữ liệu audit, dành cho Billing tương lai. Nginx chặn `/internal/` từ Internet.

## Chạy và nghiệm thu

Tạo branch `feat/meter-cutoffs` từ `main` đã merge P06. Chạy `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\tests\meter-cutoffs-unit.ps1`. Chạy `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\tests\meter-cutoffs.ps1`. Integration dùng Compose project UUID ngẫu nhiên `p07test...`, DB và broker mới; sau test xóa **duy nhất** project này. Không dùng `docker compose down -v` với project chính.

Chạy stack chính với `docker compose -f compose.yaml -f compose.workers.yaml up -d --build metering metering-cutoff-scheduler metering-consumer metering-telemetry-consumer` sau khi migration `metering` từ P06 đã đạt. Không cần migration mới cho P07; P07 tận dụng `meter_cutoffs`, `meter_cutoff_reasons`, `meter_readings`, `meter_alerts` đã có từ thiết kế V3.

Kiểm thử unit xác nhận 15 phút, mẫu `SUSPECT`, chọn tie, `PENDING`, chốt tay, phiên bản, đồng hồ offline, cảnh báo mẫu đến muộn, mốc tháng 00:00 VN, chạy hai lần, lý do bàn giao chung. Integration P07 chạy RabbitMQ thật với `RoomCreated` và `ContractStarted` ở Metering consumer, phát MQTT QoS1 và kiểm tra reading VALID tại PostgreSQL, chốt tự động và phiên bản, cảnh báo offline. Integration này **không khởi động Auth/Room/Tenant để tạo hợp đồng ACTIVE trong DB Tenant**, vì bước cross-service lifecycle thực tế đã được kiểm tra độc lập bởi P05; tích hợp end-to-end hoàn toàn trên stack chính vẫn cần demo qua Gateway.
