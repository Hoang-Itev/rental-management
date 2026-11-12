# P03 — RoomCreated → Metering (Giai đoạn I)

**Branch:** `feat/room-meter-events` · **CSDL:** `room_db` và `metering_db` tách biệt · **Broker:** RabbitMQ durable topic exchange `rental.domain.v1` · **Binding:** `room.created.v1` → `metering.events.q`.

## Luồng nghiệp vụ

Chủ trọ đăng nhập qua `POST /api/v1/auth/login`, JWT đi qua Nginx `auth_request`. Chủ trọ tạo Property → Building → Floor → Room qua API Room P02. `RoomService.create_rooms` ghi một bản ghi phòng và một event `RoomCreated` trong `room_db.outbox_events` **cùng transaction**, trả `201` ngay sau commit, không chờ RabbitMQ. Đây là code P02 có sẵn, **P03 không viết lại**.

Container `room-outbox` dùng `SELECT ... FOR UPDATE SKIP LOCKED` lấy những `RoomCreated` còn `published_at IS NULL`, gửi `aio-pika` với message **persistent**, `mandatory=True`, publisher confirms và exchange durable. Chỉ sau ACK từ broker mới đặt `published_at`. Khi publish lỗi, cập nhật `attempts`, `last_error`, giữ `published_at=NULL` để retry. Nếu process chết sau broker confirm nhưng trước DB commit, message được phát lại: **at-least-once**, không phải exactly-once.

Container `metering-consumer` đọc queue durable `metering.events.q` với manual ACK. Parse và validate `RoomCreatedEnvelope` phiên bản 1, đối chiếu `aggregate_id == data.room_id`. Trong **một transaction của `metering_db`**, dùng `INSERT ... ON CONFLICT DO NOTHING` cho `processed_events.event_id` và cho `meters(room_id,meter_type)`, tạo đúng `ELECTRICITY/KWH` + `WATER/M3` với `initial_reading=0`. Chỉ ACK sau khi transaction commit. Không gọi ngược Room DB hoặc dùng cross-database FK.

Lỗi database tạm thời: publish message sang retry queue có TTL `10s`, `60s`, `300s`, sau 3 lần sang `metering.events.q.dlq`; chỉ ACK bản gốc **sau khi RabbitMQ xác nhận message copy**. Nếu không thể gửi bản retry/DLQ, reject/requeue bản gốc. Envelope sai hoặc loại event chưa hỗ trợ được đưa vào DLQ để điều tra; không âm thầm biến mất.

## File và trách nhiệm

| File | Ý nghĩa |
|---|---|
| `room/app/service.py` | Giữ nguyên logic tạo phòng và Outbox của P02. Không thay thế bản fix idempotency đã merge. |
| `room/app/repository.py` | Thêm `claim_room_created_outbox(session)` dùng `FOR UPDATE SKIP LOCKED`. |
| `room/app/messaging.py` | `publish_pending()`, `contract_payload()`, `RabbitPublisher`: đợi broker confirm trước khi ghi `published_at`. |
| `room/app/worker.py` | Worker riêng, reconnect RabbitMQ, poll pending events, tự retry. |
| `metering/app/config.py` | `MeteringSettings`: kiểm tra service token nội bộ. |
| `metering/app/repository.py` | `mark_processed`, `ensure_meter`, `meters_for_room`, `list_meters`: idempotent ở PostgreSQL. |
| `metering/app/service.py` | `RoomCreatedEnvelope`, `MeteringService.process_room_created()`: validate và transaction atomic. |
| `metering/app/messaging.py` | `process_delivery()` và `transfer()`: manual ACK, TTL retry/DLQ. |
| `metering/app/worker.py` | `aio-pika` robust consumer, `prefetch_count=8`. |
| `metering/app/api_internal.py` | `GET /internal/v1/rooms/{room_id}/meters` cho kiểm thử; `GET /internal/v1/meters` cho Simulator sau này. Cả hai yêu cầu `X-Service-Token`. |
| `metering/app/main.py` | Giữ `/health`, `/ready`, đăng ký router nội bộ. |
| `compose.yaml` | Bật Room outbox và Metering consumer trong stack mặc định. |
| `infra/compose/tests/room-meter-events.yaml` | Xóa port RabbitMQ public trên test project ngẫu nhiên để không đụng stack đang chạy. |
| `tests/integration/test_outbox_and_events.py` | PostgreSQL + RabbitMQ E2E thật, xác minh đúng hai meter, duplicate delivery không sinh thêm. |
| `room/integration/test_outbox_publish.py` | PostgreSQL + RabbitMQ publisher test: publish thất bại vẫn pending, lần sau confirm thành công. |
| `scripts/tests/room-meter-gateway.ps1` | Checkpoint **local** đăng nhập + tạo đủ cây + chờ đúng hai meter; **tạo dữ liệu thật trong DB local**, không xóa. |

## API nội bộ

`GET http://metering:8000/internal/v1/rooms/{room_id}/meters` trả `{"items":[{"id":"...","room_id":"...","meter_code":"E-...","meter_type":"ELECTRICITY","unit":"KWH","status":"ACTIVE"}, ...]}` và yêu cầu `X-Service-Token`. Endpoint này không được mở qua Nginx. `GET /internal/v1/meters?status=ACTIVE&page=1&page_size=100` trả `items + meta` theo `MeterList` có sẵn trong `contracts/openapi.yaml`. Không triển khai `/internal/v1/rooms/{room_id}/usage` của Billing trong P03.

## Test và Definition of Done

Unit local: `scripts/tests/room-meter-unit.ps1` ⇒ Room >=95% (bao gồm P02), Metering service/repository/messaging/api_internal >=90%. `.coveragerc` Room chỉ loại `app/worker.py` khỏi **unit coverage** vì worker được xác nhận bởi integration test, không loại logic gửi message.

Integration thật: `scripts/tests/room-meter-events.ps1` ⇒ khởi tạo một Docker Compose project ngẫu nhiên + PostgreSQL/RabbitMQ tách khỏi stack live, chạy Room/Metering Alembic migrations, kiểm thử broker outage và replay, bật workers, rồi chạy `test_outbox_and_events.py`. Cuối cùng chỉ `down -v` project ngẫu nhiên. Cần Docker Compose v2.24+ (hỗ trợ `!reset`).

Checkpoint người dùng: sau khi khởi động ứng dụng với overlay P03, `scripts/tests/room-meter-gateway.ps1` phải xác minh login, tạo cây trọ/phòng qua Gateway và nhận hai meter. PR CI cần có `service-unit-tests (room)`, `service-unit-tests (metering)` và `room-meter-events-integration` xanh, cùng các job cũ.

## Giới hạn và lưu ý vận hành

Không tạo đồng hồ cho phòng **đã tồn tại từ trước P03** nếu phòng đó chưa có event trong Outbox; cần backfill chủ động nếu muốn đồng bộ dữ liệu lịch sử. `meter_code` được sinh xác định từ UUID phòng, chưa hỗ trợ liên kết thiết bị vật lý. Worker publish ưu tiên event cũ; một event bị lỗi vĩnh viễn có thể trì hoãn các event phía sau, cần dashboard cảnh báo trước production. RabbitMQ queue durable + message persistent + publisher confirm bảo đảm chính sách retry khi lỗi thông thường, không thay cho backup broker hay phân cụm HA.

**P03 chưa triển khai** ghi chỉ số điện nước, cutoff, Billing, tiêu thụ hoặc consumer các event hợp đồng; các event khác nếu đi vào `metering.events.q` ở giai đoạn này sẽ được bảo toàn trong DLQ, cần mở rộng handler sau.
