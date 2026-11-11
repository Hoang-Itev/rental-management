# Room Service – P02 code map & contract

**Sở hữu:** `room_db` (6 bảng: `properties`, `buildings`, `floors`, `rooms`, `outbox_events`, `processed_events`). Không JOIN DB Tenant/Metering. PostgreSQL schema giữ nguyên Room V3 revision `room_v3_003`; P02 **không cần migration**.

## Quy tắc nghiệp vụ đã triển khai

Phân cấp **Property → Building → Floor → Room**; tên dãy duy nhất trong một khu, số tầng duy nhất trong dãy, mã phòng duy nhất trong một khu (`uq_rooms_property_code`). Client luôn gửi `floor_id`; backend suy ra `property_id` từ Floor → Building, không tin ID khu do client gán. `RoomCreateItem.property_id` là tham số xác nhận tùy chọn, khác property thực tế bị từ chối 409. Mã phòng được trim, uppercase và giới hạn ký tự A-Z, 0-9, `_`, `-`, `.`. `area_m2` Decimal(8,2) dương; `listed_rent` VND nguyên không âm; giới hạn 100 phòng/batch.

Không xóa cứng để bảo vệ dữ liệu lịch sử và tham chiếu sang Tenant. **DELETE là soft-delete (đổi `status=INACTIVE`)**, trả 204 cả khi đã inactive. Vô hiệu hóa Property khi vẫn có Building active, Building khi còn Floor active, Floor khi còn Room active hoặc Room đang `occupancy_contract_id` khác null đều trả 409. Khi kích hoạt lại tầng/dãy/phòng, các cấp cha phải active. Không chuyển Property của Building, Building của Floor, `property_id`/`floor_id` của Room; DB còn có trigger V3.1 bảo vệ.

Tạo phòng hàng loạt và **RoomCreated outbox** trong **cùng transaction**. Mỗi phòng có một event `RoomCreated` version 1, envelope đúng `contracts/asyncapi.yaml`, routing key dự kiến `room.created.v1`. Bất kỳ trùng mã hoặc lỗi DB/outbox nào sẽ rollback cả lô. Header `Idempotency-Key` (tối đa 128 ký tự) cho phép retry trả lại cùng IDs; metadata fingerprint/IDs đặt trong outbox của phòng đầu tiên, không thêm bảng thứ 27. Key cũ với request khác trả 409. Retry đảm bảo trong vòng đời record outbox; **chưa có worker publish RabbitMQ** trong P02, đó là phần triển khai độc lập về sau. Không khẳng định message đã được gửi sau HTTP 201.

`RoomValidation.operational` = Room, Floor, Building, Property đều ACTIVE. Không đồng nghĩa phòng còn trống (`display_occupancy=VACANT`); Tenant cần tự kiểm tra hợp đồng và xử lý concurrency của hợp đồng.

## Các routes

| Method | Path | Mục đích |
|---|---|---|
| GET / POST | `/api/v1/properties` | Danh sách phân trang / thêm khu |
| GET / PATCH / DELETE | `/api/v1/properties/{id}` | Chi tiết / sửa / vô hiệu hóa khu |
| GET / POST | `/api/v1/properties/{id}/buildings` | Danh sách / thêm dãy thuộc khu |
| GET / PATCH / DELETE | `/api/v1/buildings/{id}` | Chi tiết / sửa / vô hiệu hóa dãy |
| GET / POST | `/api/v1/buildings/{id}/floors` | Danh sách / thêm tầng thuộc dãy |
| GET / PATCH / DELETE | `/api/v1/floors/{id}` | Chi tiết / sửa / vô hiệu hóa tầng |
| POST | `/api/v1/floors/{id}/rooms` | Thêm phòng đơn, cùng logic bulk |
| POST | `/api/v1/floors/{id}/rooms/bulk` | Thêm 1..100 phòng, all-or-nothing |
| GET | `/api/v1/rooms` | Lọc `property_id`, `status`, `occupancy`, phân trang |
| GET / PATCH / DELETE | `/api/v1/rooms/{id}` | Chi tiết / sửa / vô hiệu hóa phòng |
| GET (internal) | `/internal/v1/rooms/{id}/validation` | Xác nhận room ID và trạng thái hoạt động, `X-Service-Token` bắt buộc |
| GET | `/health`, `/ready` | Liveness và DB readiness |

**21 public Room routes + 1 internal route + 2 health routes.** Public request đến qua Nginx `auth_request`; Nginx giữ cấu hình hiện tại, không sửa file trong P02. Các public ports `18001` của `compose.dev.yaml` chỉ dành localhost developer, không được expose trên cloud. Nội bộ có Service Token, Nginx chặn `/internal/` từ Internet.

Trả 201 khi tạo, 200 khi đọc/sửa, 204 khi disable; 404 missing, 409 conflicting business/constraint, 422 Pydantic, 403 internal token sai. API errors của Room chuẩn `{"code","message","correlation_id"}`. JSON 401 do Nginx sinh có định dạng riêng `{"detail":"Not authenticated"}` theo Gateway hiện tại; frontend phải dựa vào status hoặc chuẩn hóa ở client.

## File map (classes, functions)

| File | Code chính và trách nhiệm |
|---|---|
| `app/config.py` | `RoomSettings`, `get_settings()`: Service Token + dependency injection |
| `app/schemas.py` | Property/Building/Floor/Room Create, Patch, Out; `RoomBulkCreate`, `RoomValidation`, `Page`, `RoomOut.from_room()`; normalize/validate/forbid extra |
| `app/repository.py` | `get()`, `page()`, `any_active()`, `code_exists()`, `outbox_by_dedupe()`, `add()`; chỉ query và flush, không commit |
| `app/service.py` | `RoomService` CRUD, `create_rooms()` atomic + outbox + idempotency, `_floor_lineage()`, `validate_room()`; `RoomError` (404/409) |
| `app/api.py` | REST public route handlers, pagination, `Idempotency-Key`, `trace_id()` |
| `app/api_internal.py` | Private RoomValidation, constant-time check service token |
| `app/main.py` | Register routers; HTTP/validation/domain exception handlers, `/health`, `/ready` |
| `app/db.py`, `app/models.py` | **Không sửa**; ORM V3 PostgreSQL dùng nguyên bản |
| `tests/conftest.py` | SQLite real SQLAlchemy/session TestClient (nhanh, không đụng DB local) |
| `tests/test_service.py` | Hierarchy, CRUD, rollback, outbox, idempotency, occupancy/deactivate |
| `tests/test_api.py` | HTTP contracts, 404/409/422/204, filter, phân trang, token nội bộ |
| `tests/test_schemas.py`, `tests/test_repository.py`, `tests/test_config.py` | Validate DTO và các helper/data settings |
| `integration/test_postgres.py` | Real PostgreSQL UNIQUE, immutable triggers, room property guard, rollback and retries; chạy duy nhất trong disposable Compose |
| `compose.room-test.yaml` | Overlay chỉ mount tests, requirements-test, env marker; không dùng cho runtime bình thường |
| `scripts/test_room_unit.ps1` | Chạy test trong Docker, `--cov=app --cov-fail-under=95` |
| `scripts/test_room_postgres.ps1` | Tạo Compose project ngẫu nhiên `p02test...`, migrate Room DB tạm, test rồi xóa **chỉ volume tạm**; không chạm volume local `rental-management` |
| `scripts/test_room_gateway.ps1`, `scripts/room/gateway_check.py` | Test GET danh sách qua Nginx với JWT owner, hoàn toàn read-only với Room DB |
| `scripts/room/sync_openapi.py` | Thêm method GET/POST/DELETE mới vào OpenAPI hiện tại, tránh ghi đè toàn bộ contracts |
| `.github/workflows/ci.yml` | `service-unit-tests` room coverage 95%; `database-and-seed` PostgreSQL tests; `compose-startup-smoke` Room Gateway E2E |

## Acceptance / Definition of Done

Local: `test_room_unit.ps1` đạt ≥95% coverage và toàn bộ unit/API tests xanh; `test_room_postgres.ps1` đạt 5/5; build Room, `smoke_test.ps1`, `test_room_gateway.ps1` xanh; `sync_openapi.py --check` thành công. CI: 3 nhóm `service-unit-tests`, `database-and-seed`, `compose-startup-smoke` xanh trên GitHub Actions. PR `feat/room-management` merge vào `main` sau khi checks xanh. Không reset seed, không chạy `docker compose down -v` trên project hiện tại.
