# CONTEXT BÀN GIAO DỰ ÁN RENTAL MANAGEMENT CHO FRONTEND VÀ AI

**Phiên bản:** 1.0, đối chiếu mã nguồn ngày 13/11/2026  
**Repository:** https://github.com/Hoang-Itev/rental-management  
**Nhánh:** `main`  
**Commit nguồn đã đối chiếu:** `7a3ec7f3d65230974cec6875d4b5e8bf479de8f7` (sau khi merge PR #19)  
**Đối tượng đọc:** Thành viên mới của nhóm, người xây dựng React FE và AI hỗ trợ viết frontend.  
**Nguồn sự thật:** Mã Python thực thi trong `backend/**/app`, Pydantic schemas, ORM models, migration, worker/scheduler, `infra/nginx/default.conf`, Compose và script test. **Không sử dụng README/docs làm căn cứ suy đoán tính năng.** Tài liệu này là bản tóm lược từ việc đọc code, không thay thế source và không phải biên bản chạy kiểm thử thực tế ở thời điểm tạo file.

---

## 0. HƯỚNG DẪN SỬ DỤNG CONTEXT VỚI AI

Đọc toàn bộ file theo thứ tự. Khi yêu cầu AI tạo code frontend, cung cấp **file này cùng bản source ở commit nêu trên** (hoặc checkout commit mới nhất và yêu cầu AI đối chiếu lại). Mọi tên field, enum, tham số, phương thức HTTP, điều kiện ẩn/hiện nút phải dựa vào route và Pydantic schema đang tồn tại. Nếu context và source khác nhau, **source thắng**.

**Ba nhãn cần phân biệt:** **ĐÃ CODE** là hành vi tìm thấy trong code, không đồng nghĩa đã được nghiệm thu trực tiếp trên máy bạn. **CHƯA CODE** là phần FE/hạ tầng chưa có trong snapshot. **CHƯA NGHIỆM THU** là đã có code/test giả lập nhưng chưa xác nhận thành công với dịch vụ bên ngoài như MoMo thực tế.

**Mục tiêu AI FE:** Tạo React + TypeScript + Vite, hoạt động với API Nginx hiện tại, không tự sửa logic tiền/phòng/hợp đồng, không tự tạo API hay database, không hardcode hostname, không đánh dấu thanh toán thành công từ return URL, không đưa secret backend vào bundle. Nếu cần backend bổ sung chức năng, đánh dấu thành yêu cầu riêng, **không lén viết endpoint tưởng tượng**.

---

## 1. DỰ ÁN NÀY GIẢI QUYẾT BÀI TOÁN GÌ?

Đây là hệ thống quản lý nhà trọ phục vụ đồ án Điện toán đám mây. Chủ trọ đã có nhà/phòng và đã thỏa thuận với khách thuê bên ngoài; ứng dụng dùng để lưu cơ cấu nhà trọ, quản lý người thuê và hợp đồng, ghi nhận điện nước, lập hóa đơn, gửi email và hỗ trợ thanh toán. Đây **không phải** trang tìm nhà, ứng dụng đặt phòng công khai hay nền tảng SaaS nhiều chủ trọ.

Hiện hệ thống chỉ có **một vai trò đăng nhập: chủ trọ (admin/owner)**. Người thuê **không có tài khoản**, không đăng nhập và không có dashboard riêng. Người thuê nhận liên kết có token qua email để xem một hóa đơn và bắt đầu thanh toán. Phần tương tác của khách thuê là trang hóa đơn công khai, không phải portal quản lý tài khoản.

Phạm vi kỹ thuật nhằm chứng minh Docker, microservices, database-per-service, REST giữa các service, RabbitMQ, MQTT giả lập, idempotency, outbox, xử lý lỗi, CI và triển khai cloud. Backend đang dùng Python/FastAPI và PostgreSQL. Chưa có module SMS, thiết bị đồng hồ vật lý, gateway thanh toán thực nghiệm thu thành công hay hệ thống hoàn tiền tự động.

## 2. KIẾN TRÚC THỰC TẾ TRONG CODE

```text
LOCAL DEVELOPMENT
Browser ──> React/Vite :5173 ──[Vite proxy /api, /public]──> Nginx :8080
                                                           │
                                    ┌──────────────────────┼────────────────────────┐
                                    │                      │                        │
                          FastAPI Auth                5 FastAPI services      Public invoice / MoMo IPN
                          (JWT validation)           Room, Tenant, Metering,
                                                     Billing, Notification
                                    │                      │
                                    └──── Docker internal network ────────────────┐
                                                            │                      │
                                                    PostgreSQL (6 DB)           RabbitMQ
                                                                                   │
                                                    Notification worker        MQTT Simulator
                                                           │
                                                        Mailpit

TARGET PRODUCTION (CHƯA HOÀN THIỆN)
Browser ── HTTPS reverse proxy ──> Nginx phục vụ React đã build + định tuyến API
                                               └──> microservices trong Docker
```

**Nginx là HTTP gateway, không phải bộ điều khiển mọi microservice.** API quản trị đi qua `auth_request`: Nginx gọi `GET /internal/v1/auth/verify`, Auth xác minh JWT rồi gateway gắn `X-Auth-User-Id` cho request đi tiếp. Các service trao đổi REST nội bộ trực tiếp bằng Docker hostname và `X-Service-Token`; các sự kiện đi RabbitMQ; Simulator phát MQTT. Trình duyệt không được truy cập PostgreSQL, RabbitMQ hay internal REST.

**Backend có 5 service nghiệp vụ và 1 Auth service hỗ trợ**, không phải 6 nghiệp vụ độc lập: Room, Tenant, Metering, Billing, Notification và Auth. Một PostgreSQL instance có 6 database. Không có foreign key xuyên database/service; UUID ngoài phạm vi service chỉ là logical reference.

**Mô hình vận hành:** `compose.yaml` chứa database, broker, Mailpit, API, migration và Nginx; `compose.workers.yaml` bổ sung 10 worker/scheduler; profile `simulator` bật giả lập điện nước. `compose.prod.yaml` chỉ là overlay cấu hình, **chưa tự tạo HTTPS/certificate**.

## 3. RANH GIỚI TRÁCH NHIỆM SERVICE, CƠ SỞ DỮ LIỆU

| Service | Database | Bảng ORM thực tế | Sở hữu nghiệp vụ |
|---|---|---|---|
| Auth | `auth_db` | `users` | Người dùng chủ trọ, hash mật khẩu, JWT |
| Room | `room_db` | `properties`, `buildings`, `floors`, `rooms`, `outbox_events`, `processed_events` | Cây khu trọ, trạng thái hoạt động và trạng thái phòng |
| Tenant | `tenant_db` | `tenants`, `contracts`, `contract_terms`, `contract_events`, `outbox_events` | Người thuê, vòng đời hợp đồng, điều khoản giá, chống chồng lấn |
| Metering | `metering_db` | `meters`, `meter_readings`, `meter_cutoffs`, `meter_cutoff_reasons`, `meter_alerts`, `processed_events` | Đồng hồ, reading, cutoff, cảnh báo |
| Billing | `billing_db` | `invoices`, `invoice_items`, `invoice_adjustments`, `invoice_access_tokens`, `payment_attempts`, `payment_webhook_receipts`, `billing_runs`, `outbox_events` | Tiền hóa đơn, công nợ, link, MoMo |
| Notification | `notification_db` | `email_jobs` | Việc gửi email, retry và trạng thái gửi |

**Tổng:** 27 bảng ứng dụng theo `__tablename__` của 6 ORM; không tính 6 bảng Alembic migration. Việc có 27 bảng trong source không chứng minh database local đang đúng schema; phải chạy `scripts/verify_schema_v3.ps1`.

Một số mối liên hệ FE cần hiểu: `room_id` trong Contract trỏ đến UUID Room nhưng không phải quan hệ SQL cross-service. `room_code_snapshot` được chụp lúc xác nhận hợp đồng; `tenant_name_snapshot` và `room_code_snapshot` của Invoice là ảnh chụp lịch sử tại thời điểm lập hóa đơn. **Không cập nhật tên trên hóa đơn đã phát hành chỉ vì tên người thuê/phòng đã đổi ở service khác.**

---

## 4. NGHIỆP VỤ AUTH: MỘT CHỦ TRỌ ĐĂNG NHẬP

**ĐÃ CODE:** `POST /api/v1/auth/login` nhận JSON `{"email":"...","password":"..."}`; thành công trả `access_token`, `token_type: "bearer"`, `expires_in`, và `user` gồm `id`, `email`, `full_name`, `is_active`. `GET /api/v1/auth/me` trả user hiện tại nếu có Bearer token hợp lệ. Không có endpoint đăng ký, refresh token, quên mật khẩu hoặc đổi mật khẩu trong snapshot hiện tại. Tài khoản chủ trọ do seed/database tạo trước.

Mật khẩu xác minh bằng Argon2id; JWT HS256 với issuer/audience; TTL mặc định 3.600 giây. Sau 401, FE phải coi token hết hạn hoặc không hợp lệ và cho đăng nhập lại. Logout ở FE hiện chỉ là xóa token/phiên phía client, **không có endpoint logout server**.

Phía trình duyệt chỉ truyền `Authorization: Bearer <access_token>` cho các `/api/v1/...` bảo vệ. **Không gửi `X-Service-Token`, không gắn `X-Auth-User-Id`**. Gateway đã phụ trách việc này. Không sử dụng tài khoản demo hay mật khẩu demo trong production.

**Màn hình FE tối thiểu:** Login, hiển thị thông tin chủ trọ, trạng thái hết phiên, logout client. Không làm đăng ký tài khoản/đăng nhập người thuê.

Nguồn code: `backend/auth/app/api.py`, `schemas.py`, `security.py`, `api_internal.py`; `infra/nginx/default.conf`.

---

## 5. NGHIỆP VỤ ROOM: KHU TRỌ → DÃY NHÀ → TẦNG → PHÒNG

**ĐÃ CODE:** Một `Property` (khu trọ) chứa nhiều `Building` (dãy/tòa), mỗi Building chứa Floor (tầng), mỗi Floor chứa nhiều Room (phòng). Dãy nhà không đổi sang khu khác và tầng không đổi sang dãy khác sau tạo. Phòng lưu `room_code`, `area_m2`, `listed_rent`, `status`, `occupancy_contract_id` và `display_occupancy`. `room_code` được chuyển thành chữ hoa, unique theo `(property_id, room_code)` chứ **không unique toàn hệ thống**.

Room có hai khái niệm độc lập: `status: ACTIVE | INACTIVE` là tình trạng vận hành; `display_occupancy: VACANT | OCCUPIED | INACTIVE` là trạng thái hiển thị. Không được dùng `ACTIVE` để suy ra đang có người. `occupancy_contract_id` đến từ sự kiện hợp đồng; FE không được chỉnh trường này.

Các API tạo/sửa khu trọ, dãy, tầng, phòng có validation rõ. `DELETE` chuyển sang `INACTIVE`, không xóa lịch sử. Không thể vô hiệu hóa tầng khi còn phòng ACTIVE, dãy khi còn tầng ACTIVE, khu khi còn dãy ACTIVE. Phòng đang chiếm dụng không thể chuyển INACTIVE. Thao tác mở lại cần qua `PATCH ... {"status":"ACTIVE"}` nếu trạng thái và ràng buộc cho phép.

**Tạo phòng hàng loạt:** `POST /api/v1/floors/{floor_id}/rooms/bulk` nhận `{ "rooms": [{ "room_code": "A101", "area_m2": "20.00", "listed_rent": 2000000 }] }`; 1–100 phòng/lần; toàn bộ lô rollback nếu lỗi; có thể gắn `Idempotency-Key`. Ngoài ra có `POST /api/v1/floors/{floor_id}/rooms` để tạo một phòng. `property_id` trên item tạo phòng chỉ là kiểm tra tùy chọn, thực tế suy ra từ floor; FE không nên cho người dùng tự chọn cha khác với tầng.

`listed_rent` chỉ là giá niêm yết để tham khảo/hiển thị. **Billing lấy `monthly_rent` từ `contract_terms`, không lấy `listed_rent` của Room.** UI không được mặc định sửa giá phòng sẽ đổi tiền các hợp đồng đang chạy.

**Bất đồng bộ:** Tạo phòng sẽ ghi `RoomCreated` vào outbox. Worker publish lên RabbitMQ, Metering nhận và tạo 2 đồng hồ ELECTRICITY/WATER. Vì vậy phòng vừa tạo có thể hiển thị `GET /api/v1/rooms/{room_id}/meters` trả rỗng trong chốc lát. FE nên hiển thị “Đang khởi tạo đồng hồ”/refresh hoặc polling vừa phải, thay vì báo tạo phòng thất bại.

**Màn hình FE:** Trang danh sách khu trọ; cây điều hướng khu → dãy → tầng → phòng; form CRUD tương ứng; danh sách phòng có lọc `property_id`, `status`, `occupancy`; chi tiết phòng và đồng hồ. Không làm thao tác xóa vật lý hay nút “đánh dấu có người” độc lập.

**Nguồn:** `backend/services/room/app/api.py`, `schemas.py`, `service.py`, `models.py`, `messaging.py`, `lifecycle.py`.

---

## 6. NGHIỆP VỤ TENANT: NGƯỜI THUÊ VÀ VÒNG ĐỜI HỢP ĐỒNG

### 6.1. Hồ sơ người thuê

`TenantCreate` yêu cầu `full_name`; có `phone`, `email`, `note` tùy chọn. Người thuê **không** có password và không đăng nhập. Một `Contract` chỉ lưu một `representative_tenant_id` là người đại diện chịu trách nhiệm thanh toán; hiện không có danh sách nhiều thành viên cùng phòng theo hợp đồng. Email của người đại diện **phải có trước khi xác nhận hợp đồng** để nhận hóa đơn; form tạo hồ sơ có thể để email trống nhưng đến bước confirm sẽ bị chặn.

### 6.2. Tạo hợp đồng và điều khoản giá

`POST /api/v1/contracts` nhận `contract_code`, `room_id`, `representative_tenant_id`, `start_date`, `end_date`, `initial_terms` và `deposit_amount` tùy chọn. `initial_terms` có `effective_from`, `effective_to`, `monthly_rent`, `electricity_unit_price`, `water_unit_price`, `monthly_service_fee`. Có thể lưu một hợp đồng DRAFT cho phòng hiện INACTIVE, nhưng không được xác nhận nếu cây phòng không ACTIVE.

`end_date` là **ngày cuối được thuê, tính cả ngày**. Ví dụ 01/10–31/10 là 31 ngày. Khoảng hiệu lực của `contract_terms` dùng `[effective_from, effective_to)`, **không tính `effective_to`**; `effective_to = null` là không có mốc kết thúc giá trong phiên bản đó. Điều khoản giá phải nối tiếp, không hở ngày và không chồng nhau; chỉ được thêm/sửa khi hợp đồng còn DRAFT (sửa dữ liệu hợp đồng bằng PATCH và thêm term bằng POST).

**Tiền cọc:** Code hiện tại có `deposit_amount` tùy chọn trong Contract. Đó là trường ghi nhận thỏa thuận, **không** được Billing cộng vào hóa đơn, khấu trừ hay tự hoàn cọc. FE có thể cho nhập và hiển thị nhưng không tạo các luồng thu/hoàn cọc chưa tồn tại.

### 6.3. Trạng thái và thao tác được phép

| Trạng thái | Ý nghĩa và khả năng thao tác FE |
|---|---|
| `DRAFT` | Nháp, chưa giữ lịch; cho PATCH hợp đồng, thêm term, xác nhận, hủy |
| `SCHEDULED` | Đã xác nhận, giữ khoảng thuê dự kiến; chưa chiếm dụng; có thể gia hạn hoặc hủy trước kích hoạt |
| `ACTIVE` | Hợp đồng đã có hiệu lực; phòng được chiếm dụng; có thể gia hạn hoặc ghi bàn giao/kết thúc |
| `EXPIRED_PENDING` | Qua hết `end_date` nhưng chưa bàn giao; **vẫn chiếm dụng phòng**, có thể gia hạn hoặc kết thúc |
| `ENDED` | Đã hoàn tất bàn giao theo mốc hiệu lực; không cho sửa như DRAFT |
| `CANCELLED` | Hủy hợp đồng chưa kích hoạt; lịch giữ chỗ được giải phóng |

Luồng thông thường: `DRAFT → SCHEDULED → ACTIVE → EXPIRED_PENDING → ENDED`, có nhánh `ACTIVE → ENDED` khi kết thúc trước hạn và `DRAFT/SCHEDULED → CANCELLED`. Không có nút UI để tự chuyển trạng thái tùy ý. Trạng thái đổi qua API nghiệp vụ hoặc scheduler.

**Confirm:** `POST /api/v1/contracts/{id}/confirm`, chỉ áp dụng DRAFT (gọi lại khi đã SCHEDULED được coi là retry). Tenant kiểm tra email đại diện, hợp đồng/term, phòng hoạt động và lịch thuê không chồng lấn. PostgreSQL GiST exclusion constraint chặn hai hợp đồng đã xác nhận chiếm cùng phòng trong khoảng lịch chồng nhau kể cả khi có request đồng thời. Không khẳng định DRAFT đã giữ chỗ.

**Kích hoạt:** Scheduler chạy nền kiểm tra thời điểm đầu ngày `start_date` theo giờ Việt Nam; không kích hoạt sớm. Khi trở thành ACTIVE, Tenant publish `ContractStarted`. Room/Metering áp dụng sự kiện bất đồng bộ, không đồng nhất tức thì.

**Hết hạn:** Sau 00:00 ngày tiếp theo `end_date`, ACTIVE chưa bàn giao thành `EXPIRED_PENDING` nhưng phòng chưa VACANT. Chủ trọ cần thực hiện bàn giao thực tế.

**End:** `POST /api/v1/contracts/{id}/end` với `{ "actual_end_date": "YYYY-MM-DD", "reason": "..." }`. Ngày bàn giao không được trước ngày bắt đầu hoặc sau ngày hiện tại theo giờ Việt Nam. Nếu ghi nhận trong chính ngày bàn giao, `actual_end_date` đã được lưu nhưng Room vẫn bị OCCUPIED cho đến 00:00 hôm sau. Scheduler hoàn tất ENDED và phát `ContractEnded` ở mốc hiệu lực. **FE phải tách “Đã ghi nhận bàn giao” với “Phòng đã trống”.**

**Renew:** `POST /api/v1/contracts/{id}/renew` nhận `new_end_date` lớn hơn cuối cũ, `reason` tùy chọn và `new_terms` tùy chọn. Có thể gia hạn SCHEDULED, ACTIVE, EXPIRED_PENDING khi chưa ghi bàn giao; gia hạn có thể nối tiếp giá cũ hoặc tạo giá mới cho phần kéo dài theo ràng buộc.

**Cancel:** `POST /api/v1/contracts/{id}/cancel` với `{ "reason": "..." }`, chỉ cho DRAFT/SCHEDULED chưa kích hoạt. Không dùng Cancel để kết thúc hợp đồng có người ở. Gọi lại hợp đồng đã CANCELLED là idempotent.

**Sắp hết hạn:** `GET /api/v1/contracts/expiring?within_days=7&page=1&page_size=20`, chỉ trả ACTIVE chưa ghi bàn giao với `end_date` từ hôm nay đến tối đa 7 ngày tới (có thể chọn 1–90 ngày). Đây là truy vấn danh sách, khác email ContractExpiring của scheduler.

**Màn hình FE:** Danh sách và chi tiết người thuê; danh sách hợp đồng lọc `room_id`, `status`; tạo hợp đồng theo wizard “chọn phòng → người đại diện → kỳ thuê → giá”; xem terms và history; nút thao tác phụ thuộc status; mục sắp hết hạn và bàn giao. Hiển thị message khi trùng lịch/room đang OCCUPIED, không cho người dùng nghĩ cứ DRAFT là đang giữ phòng.

**Nguồn:** `backend/services/tenant/app/api.py`, `schemas.py`, `service.py`, `repository.py`, `scheduler.py`, `models.py`.

---

## 7. NGHIỆP VỤ METERING: ĐỒNG HỒ, CHỈ SỐ, CUTOFF

Đây là điện nước giả lập, không có ESP32/thiết bị vật lý. Khi RoomCreated tới Metering, mỗi phòng có **một đồng hồ ELECTRICITY (KWH)** và **một đồng hồ WATER (M3)**. Simulator lấy danh sách meter ACTIVE qua REST nội bộ, gửi **chỉ số tích lũy**, không phải số tiêu thụ của lần đo, mặc định 300 giây/lần qua MQTT QoS 1. Ví dụ chỉ số 1.255 rồi 1.258 nghĩa là tăng 3 đơn vị, không phải 1.258 đơn vị đã sử dụng trong một lần đọc.

`MeterReading` có `meter_id`, `measured_at`, `reading_value`, `received_at`, `validation_status: VALID | SUSPECT | REJECTED`, `anomaly_reason`. Khóa định danh mẫu là `(meter_id, measured_at)`; mẫu trùng đúng giá trị được chống trùng, trùng timestamp mà giá trị khác sinh cảnh báo. Mẫu giảm bất thường, đến muộn liên quan mốc chốt hoặc OFFLINE có cơ chế phát hiện. FE **chỉ hiển thị** số đã ghi nhận; không có API admin để tự tạo reading bằng giao diện.

**Cutoff** là mốc chốt chỉ số được dùng khi tính tiền. Có cutoff tháng và mốc bắt đầu/kết thúc hợp đồng. Với một meter và một thời điểm, code dùng **một cutoff vật lý** cho nhiều ngữ cảnh, lưu nguyên nhân trong `meter_cutoff_reasons`. Trạng thái cutoff là `PENDING`, `CONFIRMED`, `SUPERSEDED`. Ngày đầu tháng tính theo 00:00 giờ Việt Nam. Hệ thống chờ qua 15 phút, rồi với cutoff cần xử lý chọn **mẫu VALID mới nhất ở hoặc trước mốc cutoff, nằm trong 15 phút trước mốc**. Không tự cộng dồn hay nội suy thiếu mẫu.

**Thao tác FE:** Chủ trọ thấy cutoff PENDING thì có thể nhập chỉ số thật và lý do (`manual_reason` ít nhất 8 ký tự) qua `POST /api/v1/meter-cutoffs/{id}/confirm`. Với cutoff đã CONFIRMED, không sửa đè; gọi `POST /api/v1/meter-cutoffs/{id}/corrections` tạo phiên bản mới CONFIRMED, bản cũ SUPERSEDED. `/revise` là alias tồn tại nhưng FE nên dùng `/corrections`. Backend chặn giá trị mới trái với các mốc CONFIRMED lân cận.

`MeterAlert` có trạng thái OPEN/RESOLVED, có thể lọc `alert_type: OFFLINE | READING_DECREASE | LATE_AFTER_CUTOFF | CONFLICTING_DUPLICATE`; resolve bằng `POST /api/v1/meter-alerts/{id}/resolve` với `resolution_note` tối thiểu 8 ký tự. Ngưỡng OFFLINE mặc định 20 phút, scheduler meter mặc định poll 60 giây.

**Màn hình FE:** Đồng hồ theo phòng; lịch sử reading, cutoff và trang chốt pending; xác nhận thủ công, xem lịch sử sửa mốc; danh sách cảnh báo và giải quyết cảnh báo. Sau khi tạo phòng, nếu chưa có meter thì đợi event xử lý, không yêu cầu FE gọi internal route.

**Đặc điểm response:** `GET /api/v1/rooms/{room_id}/meters` trả `{ "items": [MeterOut...] }` **không có `meta`**. Nhiều danh sách khác trả `{ "items": [...], "meta": {"page", "page_size", "total"} }`. Viết type tương ứng, không mặc định mọi list có `meta`.

**Nguồn:** `backend/services/metering/app/api.py`, `schemas.py`, `service.py`, `repository.py`, `api_internal.py`, `scheduler.py`; `simulator/app/main.py`, `config.py`.

---

## 8. NGHIỆP VỤ BILLING: TÍNH TIỀN, LẬP HÓA ĐƠN, QUÁ HẠN

### 8.1. Hai loại hóa đơn và bốn trạng thái

`invoice_type: PERIODIC | FINAL`. Hóa đơn PERIODIC tính kỳ tháng dương lịch, giao với ngày tính phí của hợp đồng; FINAL lập cho khoảng chưa được hóa đơn khác bao phủ khi hợp đồng đã ENDED. Một hợp đồng không có hai hóa đơn còn hiệu lực chồng kỳ; database có exclusion constraint. FINAL không tạo nếu đã được tính đủ hoặc khoảng thiếu rời rạc không thể gộp an toàn.

`status: DRAFT | ISSUED | PAID | VOID`. `DRAFT` có thể thiếu chỉ số/điều kiện, `total_amount` ban đầu 0 và `blocked_reason` cho biết vì sao chưa phát hành. `ISSUED` là đã chốt nội dung hóa đơn. `PAID` chỉ khi backend xác nhận thanh toán thật qua IPN/đối soát. `VOID` là hóa đơn đã hủy hiệu lực, không xóa lịch sử. **Không có `OVERDUE` như một trạng thái hóa đơn riêng**: quá hạn là `ISSUED` và `due_date` nhỏ hơn ngày hiện tại. FE tính nhãn “Quá hạn” ở lớp hiển thị từ trạng thái + hạn.

### 8.2. Cách tính tiền thực tế

`period_start` **bao gồm**, `period_end` **không bao gồm**. Hợp đồng `end_date` lại **bao gồm** nên kỳ có thể kết thúc tại `end_date + 1 ngày`. Phí thuê + phí dịch vụ theo số ngày thuê trong tháng; điện/nước theo hiệu chỉ số tích lũy của hai cutoff đã CONFIRMED và đơn giá trong `contract_terms`. Nếu giá giữa kỳ thay đổi, hệ thống cần cutoff xác nhận ngay mốc đổi giá để tính đúng từng đoạn; **không tự nội suy số điện/nước**.

Tiền tính bằng `Decimal`, làm tròn **ROUND_HALF_UP cho từng dòng hóa đơn**, rồi cộng dòng đã làm tròn ra `total_amount`. Đơn giá ngày/quantity có độ chính xác để hiển thị; không lấy `quantity * unit_price` (đã bị làm tròn hiển thị) làm nguồn sự thật để tính lại tổng. FE phải lấy `items[].amount` và `total_amount` từ Backend.

Giới hạn ngày tính phí lấy theo `min(end_date, actual_end_date nếu có)`; nếu bàn giao sau ngày hết hạn, code hiện tại không tự tính thêm ngày thuê quá hạn. Không tự bịa phí phạt/ngày lưu trú phát sinh ngoài hợp đồng.

Các `blocked_reason` có thể gặp trong code là `MISSING_RECIPIENT_EMAIL`, `PENDING_CUTOFF`, `DEPENDENCY_UNAVAILABLE`, `INVALID_BILLING_DATA`, mã lỗi của calculator và `CONTRACT_NOT_BILLABLE`, `PERIOD_ALREADY_COVERED`. Nếu có blocked_reason, FE hiển thị nguyên nhân và hướng xử lý, **không cho thanh toán DRAFT**.

### 8.3. Phát hành và hạn thanh toán

`POST /api/v1/billing-runs` tạo job tháng đã đóng, yêu cầu `{"billing_month":"YYYY-MM-01"}`; có thể thêm `Idempotency-Key`. Scheduler chạy mặc định 300 giây/lần, tự lên lịch lập hóa đơn cho tháng trước sau mốc 02:00 ngày 1 giờ Việt Nam; thử lại hóa đơn DRAFT khi đủ cutoff. `GET /api/v1/billing-runs` hiển thị progress và `issued_count`, `waiting_count`, `skipped_count`, `failed_count`.

`POST /api/v1/invoices/{id}/issue` cố phát hành lại DRAFT bằng dữ liệu hiện tại, có thể trả 422/503 khi thiếu cutoff/nguồn khác. Phát hành ISSUED ghi snapshot item và event `InvoiceIssued` để gửi email.

**Lưu ý quan trọng từ code:** `due_date` được đặt là **ngày 5 của tháng thực tế phát hành**, không cố định “ngày 5 của tháng ngay sau kỳ hóa đơn”. Hóa đơn được phát hành muộn sau ngày 5 có thể mang hạn thanh toán đã ở quá khứ. Đây là hành vi hiện hữu, không phải lời khuyên nghiệp vụ; FE nên hiển thị theo dữ liệu server và đánh dấu cần chủ BE xác nhận nếu muốn đổi chính sách.

### 8.4. Hủy, phát hành lại và điều chỉnh

`POST /api/v1/invoices/{id}/void` nhận `{"reason":"..."}`, áp dụng hóa đơn chưa PAID và **không có PaymentAttempt PENDING**. VOID thu hồi liên kết cũ. `POST /api/v1/invoices/{id}/reissue` tạo bản thay thế có `revision` tăng, `replaces_invoice_id` tham chiếu bản gốc; không sửa dữ liệu hóa đơn cũ. Nếu nguyên bản ISSUED mà việc tính lại thất bại thì bản cũ được giữ nguyên, chưa VOID.

Invoice PAID không được sửa tiền trực tiếp. Nếu cần phản ánh sai lệch, `POST /api/v1/invoices/{id}/adjustments` tạo `InvoiceAdjustment` với `reason`, `amount_delta` khác 0; `POST /api/v1/invoice-adjustments/{adjustment_id}/resolve` đóng hồ sơ bằng `RESOLVED` hoặc `REJECTED`. **Đóng adjustment không tự hoàn tiền, không tự tạo hóa đơn bù**. FE không làm nút “Refund” hoặc tự sửa tổng đã PAID.

**Màn hình FE:** Danh sách hóa đơn lọc `contract_id`, `billing_month`, `status`; chi tiết có item, cutoff và kỳ; danh sách billing runs; trạng thái chờ dữ liệu; phát hành, nhắc nợ, void/reissue; payment attempts; adjustment cho PAID. Các thao tác cập nhật phải được ẩn/disable theo trạng thái nhưng vẫn xử lý lỗi 409 từ BE vì dữ liệu có thể đổi trong lúc người dùng thao tác.

**Nguồn:** `backend/services/billing/app/api.py`, `schemas.py`, `service.py`, `calculator.py`, `models.py`, `scheduler.py`, `reminders.py`.

---

## 9. LINK HÓA ĐƠN CÔNG KHAI VÀ MOMO

### 9.1. Link email là token, không phải account người thuê

Notification xin Billing cấp URL sau event InvoiceIssued hoặc nhắc nợ. Billing sinh token ngẫu nhiên, **chỉ lưu SHA-256 hash** trong `invoice_access_tokens`, thời hạn mặc định 259.200 giây (72 giờ), có thể bị thu hồi. Token đặt trong đường dẫn URL và là **bearer capability**: ai có URL còn hiệu lực có thể xem dữ liệu hóa đơn tương ứng; không yêu cầu JWT quản trị.

**HIỆN TẠI** `create_access_link` tạo URL `${PUBLIC_BASE_URL}/public/v1/invoices/{token}`. URL đó trả **JSON API**, chưa phải giao diện React. API `GET /public/v1/invoices/{token}` trả `invoice_code`, `room_code`, `tenant_name`, `period_start`, `period_end`, `status: ISSUED | PAID`, `total_amount`, `due_date`, `items`. Link VOID/hết hạn/bị thu hồi bị từ chối. FE phải tạo màn hình `/hoa-don/:token` để hiển thị đẹp, **và BE cần được sửa cách tạo link email** để dẫn đến trang React đó (hoặc giải pháp redirect được thống nhất). **Chưa có `FRONTEND_BASE_URL` trong Billing Settings hiện tại; đó là đề xuất tương lai, không phải cấu hình đã code.**

**Bảo vệ token:** Không in vào log, không gửi analytics/referrer, không gắn vào request không liên quan, không lưu token trong state dài hạn không cần thiết. Backend đang đặt `Referrer-Policy: no-referrer`, `Cache-Control: no-store` cho response công khai và Nginx tắt access log ở route public invoice. Dùng link trong browser cần chú ý lịch sử/clipboard vì token cấp quyền xem hóa đơn.

### 9.2. MoMo: phân biệt checkout với hoàn tất thanh toán

`POST /public/v1/invoices/{token}/payments/momo` là public API, nhận optional header `Idempotency-Key` và dùng số tiền trên **Invoice backend**, không nhận tiền do browser gửi. Khoảng được phép là **10.000–50.000.000 VND**, không hỗ trợ trả một phần. Một hóa đơn chưa PAID có tối đa một PaymentAttempt PENDING; retry thường dùng lại attempt này. PaymentAttempt có `PENDING | SUCCESS | FAILED | EXPIRED`.

Sau PR #19, response checkout có `checkout_status` rõ ràng:

| `checkout_status` | Hành vi FE phải làm |
|---|---|
| `READY` | Có `pay_url`; cho người dùng mở URL MoMo. `status` thường `PENDING`. |
| `RECONCILING` | Chưa có URL khả dụng, backend đang cần đối soát; HTTP có thể là **202** cùng `retry_after_seconds`/`Retry-After`; hiển thị thông báo chờ, không tự sinh order mới hoặc loop liên tục. |
| `PAID` | Backend đã xác nhận payment SUCCESS; thông báo đã trả. `pay_url` không còn. |

MoMo gửi **IPN server-to-server** đến `POST /webhooks/momo/ipn`. Billing xác minh HMAC, partner, order/request ID, số tiền, chống trùng rồi chuyển Invoice sang PAID và phát event `PaymentSucceeded`. Browser quay về `GET /public/v1/payments/momo/return` **chỉ nhận plain text hướng dẫn mở lại link email**, không phải giao diện xác nhận. **Không lấy query parameter `resultCode=0` trên return URL để tự đánh dấu đã trả tiền.**

**Trạng thái kiểm thử bên ngoài:** Đã tạo checkout Sandbox MoMo và có URL thanh toán nhưng giao dịch ATM test bị endpoint `napas` từ chối `resultCode=1002`; trang thanh toán cũng hiển thị lỗi reCAPTCHA site key. Test integration trong repo dùng HTTP mock provider, **không chứng minh giao dịch thật thành công trên Sandbox**. **Không được giả giao dịch đã PAID trong UI demo**. Các màn quản lý phòng, hợp đồng, điện nước, hóa đơn và Mailpit vẫn có thể hoàn thiện độc lập.

**Màn hình FE:** Trang hóa đơn công khai nhận URL token; hiển thị các dòng chi tiết, tổng, hạn và trạng thái; nút “Thanh toán qua MoMo” khi `ISSUED`, amount đủ điều kiện và provider sẵn sàng; xử lý READY/RECONCILING/PAID cùng lỗi 503 `MOMO_UNAVAILABLE`; cho người dùng refresh hóa đơn sau khi quay lại từ cổng thanh toán. Không hiển thị nút khi `PAID`.

**Nguồn:** `backend/services/billing/app/api_public.py`, `api_webhook.py`, `payment.py`, `momo.py`, `service.py`, `schemas.py`.

---

## 10. NOTIFICATION: EMAIL VÀ TRẠNG THÁI JOB

Notification nhận sự kiện `InvoiceIssued` (email hóa đơn), `InvoiceReminderRequested` (nhắc nợ), `PaymentSucceeded` (biên nhận), `ContractExpiring` (nhắc chủ trọ `OWNER_EMAIL`). Không có API “soạn email rồi gửi” tùy ý trên UI; email phát theo nghiệp vụ event/scheduler. Worker ghi email job theo event ID để hạn chế trùng, gọi Billing xin token/hỏi điều kiện và Tenant kiểm tra điều kiện nhắc, sau đó SMTP gửi.

`email_jobs.status: PENDING | SENDING | SENT | FAILED | SKIPPED`. Thất bại tạm thời retry theo backoff, mặc định tối đa 5 lần; `POST /api/v1/email-jobs/{job_id}/retry` **chỉ cho `FAILED`**. `SKIPPED` thường là thông báo đã không còn hợp lệ về nghiệp vụ, không nên coi là lỗi SMTP. Event PaymentSucceeded giúp bỏ qua nhắc nợ còn chờ.

Local dùng Mailpit ở `http://127.0.0.1:8025`; email không gửi ra Internet. Container gửi thư thật là **`notification-worker`**, đọc `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_FROM`, `SMTP_USERNAME`, `SMTP_PASSWORD` từ Compose. Cloud dự kiến dùng SMTP đã xác minh như Brevo; cấu hình thay qua `.env` + `compose.prod.yaml`, không sửa React.

**Màn hình FE:** Danh sách và chi tiết email job, lọc status/email_type, xem lần gửi/lỗi và nút retry khi FAILED. **Không hiển thị địa chỉ Mailpit như tính năng cloud**; nó chỉ là công cụ local cho nhóm dev. Email thất bại không rollback trạng thái hóa đơn hoặc PaymentSucceeded đã xác nhận.

**Nguồn:** `backend/services/notification/app/api.py`, `schemas.py`, `service.py`, `messaging.py`, `worker.py`, `clients.py`, `config.py`.

---

## 11. HỆ THỐNG EVENT/WORKER: VÌ SAO UI CÓ THỂ CẬP NHẬT CHẬM?

| Event | Producer | Consumer và tác động |
|---|---|---|
| `RoomCreated` | Room outbox | Metering tạo hai meter |
| `ContractStarted` | Tenant outbox | Room cập nhật OCCUPIED; Metering sinh cutoff đầu hợp đồng |
| `ContractEnded` | Tenant outbox | Room giải phóng occupancy; Metering sinh cutoff cuối hợp đồng |
| `ContractExpiring` | Tenant scheduler/outbox | Notification gửi email nhắc chủ trọ |
| `InvoiceIssued` | Billing outbox | Notification tạo/gửi email hóa đơn |
| `InvoiceReminderRequested` | Billing | Notification tạo email nhắc nợ |
| `PaymentSucceeded` | Billing | Notification gửi biên nhận, bỏ qua các nhắc nợ phù hợp |

Sự kiện ghi outbox cùng giao dịch dữ liệu gốc, rồi worker gửi lên RabbitMQ `rental.domain.v1` theo routing key. Truyền tin có thể lặp hoặc trễ; các consumer dùng các cơ chế chống trùng/retry khác nhau. MQTT dùng `amq.topic` để đưa `meters.*.reading` vào `metering.telemetry.q`. Đừng ghi “mọi sự kiện được xử lý đúng một lần” vì hệ thống cố tình triển khai theo hướng at-least-once và idempotency.

**Đối với FE:** Khi tạo phòng xong mà meter chưa có, hay khi contract ACTIVE nhưng occupancy Room chưa đồng bộ, UI nên làm mới sau thao tác, cho hiển thị trạng thái đang xử lý, không ép sự kiện xuất hiện tức thì. Không cho FE tự sửa database/nhét thông điệp RabbitMQ để “đồng bộ nhanh”.

10 tiến trình nền theo Compose: `room-outbox`, `room-consumer`, `tenant-outbox`, `tenant-scheduler`, `metering-consumer`, `metering-telemetry-consumer`, `metering-cutoff-scheduler`, `billing-outbox`, `billing-scheduler`, `notification-worker`. Có thêm `simulator` nếu bật profile.

**Nguồn:** `infra/rabbitmq/definitions.json`, `backend/services/*/app/{messaging,worker,scheduler,lifecycle}.py` khi có, `compose.workers.yaml`.

---

## 12. HỢP ĐỒNG HTTP DÀNH CHO FRONTEND

Theo cách đăng ký route ở code hiện tại có **87 operation** ở sáu ứng dụng, chưa tính health/readiness: khoảng **70 admin operation `/api/v1` (bao gồm login), 13 internal, 3 public và 1 webhook**. Các route không công khai qua gateway ở `/internal/v1` chỉ phục vụ service-to-service; FE không được gọi.

### 12.1. Auth và Room, đường dẫn FE được gọi

```http
POST   /api/v1/auth/login
GET    /api/v1/auth/me

GET    /api/v1/properties
POST   /api/v1/properties
GET    /api/v1/properties/{property_id}
PATCH  /api/v1/properties/{property_id}
DELETE /api/v1/properties/{property_id}
GET    /api/v1/properties/{property_id}/buildings
POST   /api/v1/properties/{property_id}/buildings
GET    /api/v1/buildings/{building_id}
PATCH  /api/v1/buildings/{building_id}
DELETE /api/v1/buildings/{building_id}
GET    /api/v1/buildings/{building_id}/floors
POST   /api/v1/buildings/{building_id}/floors
GET    /api/v1/floors/{floor_id}
PATCH  /api/v1/floors/{floor_id}
DELETE /api/v1/floors/{floor_id}
POST   /api/v1/floors/{floor_id}/rooms
POST   /api/v1/floors/{floor_id}/rooms/bulk
GET    /api/v1/rooms
GET    /api/v1/rooms/{room_id}
PATCH  /api/v1/rooms/{room_id}
DELETE /api/v1/rooms/{room_id}
```

### 12.2. Tenant và Contract

```http
GET    /api/v1/tenants
POST   /api/v1/tenants
GET    /api/v1/tenants/{tenant_id}
PATCH  /api/v1/tenants/{tenant_id}
GET    /api/v1/contracts
POST   /api/v1/contracts
GET    /api/v1/contracts/expiring
GET    /api/v1/contracts/{contract_id}
PATCH  /api/v1/contracts/{contract_id}
GET    /api/v1/contracts/{contract_id}/terms
POST   /api/v1/contracts/{contract_id}/terms
GET    /api/v1/contracts/{contract_id}/events
POST   /api/v1/contracts/{contract_id}/confirm
POST   /api/v1/contracts/{contract_id}/renew
POST   /api/v1/contracts/{contract_id}/end
POST   /api/v1/contracts/{contract_id}/cancel
POST   /api/v1/jobs/contracts/lifecycle/run
```

Endpoint `/api/v1/jobs/contracts/lifecycle/run` dành cho vận hành/demo và có thể thay đổi trạng thái nhiều hợp đồng. FE có thể để ở trang công cụ quản trị thử nghiệm, không đặt ở luồng sử dụng bình thường.

### 12.3. Metering

```http
GET    /api/v1/rooms/{room_id}/meters
GET    /api/v1/meters/{meter_id}/readings
GET    /api/v1/meters/{meter_id}/cutoffs
GET    /api/v1/meters/{meter_id}/alerts
GET    /api/v1/meter-cutoffs
GET    /api/v1/meter-cutoffs/{cutoff_id}
POST   /api/v1/meter-cutoffs/{cutoff_id}/confirm
POST   /api/v1/meter-cutoffs/{cutoff_id}/corrections
POST   /api/v1/meter-cutoffs/{cutoff_id}/revise        # alias cũ, FE không ưu tiên
GET    /api/v1/meter-alerts
POST   /api/v1/meter-alerts/{alert_id}/resolve
POST   /api/v1/jobs/meters/cutoffs
POST   /api/v1/jobs/meters/monthly-cutoffs/run
```

### 12.4. Billing và Notification

```http
GET    /api/v1/invoices
GET    /api/v1/invoices/{invoice_id}
POST   /api/v1/invoices/{invoice_id}/issue
POST   /api/v1/invoices/{invoice_id}/void
POST   /api/v1/invoices/{invoice_id}/reissue
POST   /api/v1/invoices/{invoice_id}/reminders
GET    /api/v1/invoices/{invoice_id}/payment-attempts
GET    /api/v1/invoices/{invoice_id}/adjustments
POST   /api/v1/invoices/{invoice_id}/adjustments
POST   /api/v1/invoice-adjustments/{adjustment_id}/resolve
GET    /api/v1/billing-runs
POST   /api/v1/billing-runs
POST   /api/v1/final-invoices
POST   /api/v1/jobs/payments/reconcile/run

GET    /api/v1/email-jobs
GET    /api/v1/email-jobs/{job_id}
POST   /api/v1/email-jobs/{job_id}/retry
```

### 12.5. Public và webhook

```http
GET    /public/v1/invoices/{token}
POST   /public/v1/invoices/{token}/payments/momo
GET    /public/v1/payments/momo/return
POST   /webhooks/momo/ipn                  # MoMo server gọi; FE không gọi
```

### 12.6. Internal endpoints chỉ để AI hiểu luồng, KHÔNG gọi từ FE

```http
GET  /internal/v1/auth/verify
GET  /internal/v1/rooms/{room_id}/validation
GET  /internal/v1/contracts/billable
GET  /internal/v1/contracts/{contract_id}
GET  /internal/v1/contracts/{contract_id}/billing-context
GET  /internal/v1/contracts/{contract_id}/expiry-notification-eligibility
GET  /internal/v1/meters
GET  /internal/v1/rooms/{room_id}/meters
GET  /internal/v1/meters/{meter_id}/baseline
GET  /internal/v1/rooms/{room_id}/cutoffs
GET  /internal/v1/rooms/{room_id}/usage
POST /internal/v1/invoices/{invoice_id}/access-links
GET  /internal/v1/invoices/{invoice_id}/reminder-eligibility
```

**Không tự suy ra JSON từ bảng endpoint này.** Kiểu dữ liệu chính xác nằm trong Pydantic `schemas.py` và route signature. `contracts/openapi.yaml` có thể dùng để import/nhập type sau khi đối chiếu code, nhưng **không phải căn cứ duy nhất của bản context**.

---

## 13. QUY ƯỚC DATA VÀ XỬ LÝ LỖI FE PHẢI TUÂN THỦ

**Dạng list thông dụng:** `{ "items": [...], "meta": { "page": 1, "page_size": 20, "total": 100 } }`. Phần lớn admin list có pagination; Room meters là ngoại lệ trả `items` không `meta`.

**Ngày:** JSON `YYYY-MM-DD` cho ngày dân sự; timestamp ISO 8601 timezone-aware (thường UTC) cho event/cutoff. FE hiển thị lịch theo Asia/Ho_Chi_Minh cho nghiệp vụ hợp đồng, tháng và nhắc nợ. Không dùng JavaScript `new Date('YYYY-MM-DD')` rồi vô tình đổi ngày do timezone. `period_end` của hóa đơn là exclusive, phải dùng khi hiển thị “đến hết ngày nào” một cách có chủ ý.

**Tiền:** Các trường tổng tiền và đơn giá của hợp đồng thường là số nguyên VND. Dòng hóa đơn có `quantity`, `unit_price` dạng decimal và có thể được Pydantic serialize thành số JSON float phục vụ hiển thị. **Backend là nguồn sự thật về số tiền**; FE chỉ format VND (`Intl.NumberFormat('vi-VN')`), không tự tính lại hoặc chấp nhận `total_amount` nhập tay từ form thanh toán.

**Lỗi HTTP:** Nhiều service chuẩn hóa `{code, message, correlation_id}`, nhưng code hiện có **không đồng nhất 100%**: Nginx có thể trả `{detail: 'Not authenticated'}`, FastAPI Metering đôi lúc trả `{detail: ...}` và Notification trả lỗi detail trực tiếp. FE cần handler chấp nhận cả `message`, `detail` dạng chuỗi và `detail` dạng object; tuyệt đối không giả định chỉ một shape.

**HTTP 401:** token thiếu/hết hạn, chuyển đăng nhập. **403:** không đủ quyền/service từ chối. **409:** xung đột nghiệp vụ (sửa trạng thái lỗi, chồng lịch, pending payment). **422:** payload sai/điều kiện dữ liệu chưa đủ. **503:** dependency/provider không có, cần thông báo và có thể thử lại sau. Trường hợp 202 ở checkout là `RECONCILING`, **không phải lỗi**. Handler cũng phải chấp nhận response thành công HTTP **204 không có JSON body** cho DELETE và webhook (webhook không dành cho FE).

**Tính bất đồng bộ:** Sau mutation tạo phòng, confirm hợp đồng, phát hành hóa đơn, gửi mail, UI nên refetch/poll hợp lý theo luồng liên quan. Không dùng vòng lặp query quá dày. Với mutation nhạy cảm/không an toàn retry, dùng `Idempotency-Key` khi API hỗ trợ và tránh double click.

---

## 14. HƯỚNG DẪN THIẾT KẾ VÀ CODE FRONTEND

### 14.1. Công nghệ và cách tổ chức

Chốt **React + TypeScript + Vite**, React Router, một API client tập trung, typed DTO, trạng thái loading/error/empty rõ ràng. Có thể dùng TanStack Query để quản lý fetch/cache/invalidation nếu nhóm biết sử dụng; đó là **đề xuất FE, không phải thư viện đã tồn tại trong backend**. Tạo source trong thư mục `frontend/` cùng cấp `backend/` và `infra/`, **không di chuyển source React vào `infra/nginx/`**.

Gợi ý cấu trúc:

```text
frontend/
  src/
    app/           # Router, providers, layouts
    features/
      auth/
      properties/
      rooms/
      tenants/
      contracts/
      meters/
      invoices/
      notifications/
      public-invoice/
    lib/api/       # API client, error parser, shared types
    components/    # UI tái sử dụng
  vite.config.ts
  package.json
```

### 14.2. Cách gọi API không phải sửa React khi đưa lên cloud

**Quy tắc bắt buộc:** FE gọi đường dẫn **tương đối** `/api/v1/...` hoặc `/public/v1/...`, không hardcode `http://localhost:8080` hay domain EC2 trong các component. FE local `npm run dev` thường ở `http://localhost:5173`; `vite.config.ts` cấu hình proxy `/api`, `/public` về Nginx BE `http://127.0.0.1:8080`. Cloud sẽ phục vụ React build cùng origin với API qua Nginx, HTTPS proxy phía ngoài. Khi đúng kiến trúc này không cần cấu hình CORS giữa FE và BE.

```ts
// frontend/vite.config.ts, ví dụ cấu hình mới phải tạo
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8080', changeOrigin: true },
      '/public': { target: 'http://127.0.0.1:8080', changeOrigin: true },
    },
  },
});
```

```ts
// Ví dụ: dùng chung origin; accessToken do login trả về
const response = await fetch('/api/v1/rooms?page=1&page_size=20', {
  headers: { Authorization: `Bearer ${accessToken}` },
});
```

Nếu FE chạy **trên máy khác máy chạy BE**, `127.0.0.1` trỏ đến máy của FE; cần thỏa thuận backend/proxy target truy cập được (VPN, tunnel riêng, hoặc cài BE trên máy FE). **Compose hiện chỉ publish Nginx trên 127.0.0.1:8080**, không tự mở LAN. Không sửa thành cổng công khai tùy tiện chỉ để tiện test.

### 14.3. Đề xuất navigation/screen, bám đúng API đã có

| Nhóm màn hình | Dữ liệu và thao tác từ BE | Lưu ý |
|---|---|---|
| Đăng nhập | Auth login, me | Không có sign-up/refresh |
| Dashboard | Tổng hợp client từ các list có sẵn | Chưa có dashboard aggregate API; cần cân nhắc nhiều request/pagination, không tự bịa `/dashboard` |
| Khu trọ / Dãy / Tầng | CRUD property/building/floor | DELETE là vô hiệu hóa |
| Phòng | List/filter, tạo đơn/lô, cập nhật, xem meter | `ACTIVE` khác `OCCUPIED` |
| Người thuê | CRUD hồ sơ (không có DELETE tenant) | Người đại diện phải có email khi confirm |
| Hợp đồng | List/detail, terms, events, confirm, renew, end, cancel, expiring | Hiển thị nút theo status; lưu ý mốc hiệu lực |
| Điện nước | Room meters, readings, cutoff, alerts | Có thể phải đợi event RoomCreated; không có REST ghi reading admin |
| Hóa đơn | List/detail, run, issue, reminders, void, reissue, adjustment | DRAFT chưa trả tiền; PAID bất biến |
| Email jobs | List/detail/retry | SENT không đồng nghĩa mở email; chỉ FAILED retry |
| Hóa đơn công khai | GET token và checkout MoMo | Không yêu cầu JWT; phải bảo vệ token; Sandbox chưa nghiệm thu |

### 14.4. Các rule UX dễ sai

Khi hợp đồng DRAFT, có thể cho chỉnh giá; sau SCHEDULED/ACTIVE không dùng form PATCH giá nháp, mà thao tác gia hạn nếu phù hợp. Khi EXPIRED_PENDING, **vẫn hiển thị phòng đang chiếm dụng**. Khi tạo phòng, meter có thể chưa kịp xuất hiện. Khi invoice DRAFT, phải hiển thị `blocked_reason` và không thanh toán. Hóa đơn quá hạn không có status `OVERDUE` độc lập. Khi payment `RECONCILING`, không mở pay URL rỗng. Khi một thao tác bị 409, refetch detail vì trạng thái có thể đã thay đổi từ worker hoặc tab khác.

Không lưu bearer token trong secret `VITE_*`; mọi biến `VITE_*` sẽ được đưa vào bundle JS khi build. Chỉ cần JWT client, tuyệt đối không đưa MoMo secret, SMTP password, JWT signing secret, `SERVICE_TOKEN`, DB password vào FE. Không dùng `X-Auth-User-Id` tự điền trong request.

### 14.5. Tích hợp React với Nginx: CHƯA CODE

`infra/nginx/Dockerfile` hiện copy `infra/nginx/index.html` placeholder vào Nginx, **chưa có build Vite multi-stage**. Sau khi FE có bản chạy được, cần cập nhật Dockerfile để build React và copy `frontend/dist` vào `/usr/share/nginx/html`, giữ nguyên định tuyến `/api/v1`, `/public/v1`, `/webhooks`, và SPA fallback. Nên thử integration trước khi FE hoàn thành 100% để phát hiện lỗi routing và asset path; sau đó cloud chỉ thay cấu hình domain/HTTPS, không thay code gọi API.

Cần chốt **route giao diện hóa đơn công khai** (đề xuất `/hoa-don/:token`) và sửa **code Billing** cấp link email sang route đó. Đây là **việc chưa triển khai**, cần BE/FE làm chung; đừng mặc định email đã trỏ vào React. `GET /public/v1/payments/momo/return` hiện chỉ trả plain text; nếu muốn trải nghiệm quay lại trang React, cần thiết kế và điều chỉnh có kiểm thử, không đổi bừa hợp đồng IPN.

---

## 15. CHẠY LOCAL VÀ KIỂM TRA MÔI TRƯỜNG BÀN GIAO

Yêu cầu: Docker Desktop/Linux containers, PowerShell ở gốc repository và `.env` local có các secret cần thiết. `compose.yaml` phục vụ backend, migration và hạ tầng; không khởi tạo app FE Vite.

### 15.1. Lần đầu hoặc khi DB mới hoàn toàn

```powershell
# 1. Hạ tầng
docker compose -f compose.yaml up -d --wait postgres rabbitmq mailpit

# 2. Build backend và Nginx
docker compose -f compose.yaml build auth room tenant metering billing notification nginx
docker compose -f compose.yaml up -d --wait

# 3. Chỉ trên database demo mới/chuẩn, không phải DB đã sửa dữ liệu
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_seed_demo.ps1 -UseDemoPassword

# 4. Worker/scheduler và simulator
docker compose -f compose.yaml -f compose.workers.yaml up -d --wait
docker compose -f compose.yaml -f compose.workers.yaml --profile simulator up -d --build --wait simulator
```

Seed demo từ `scripts/seed/demo_data.json`: 1 khu trọ, 2 dãy, 4 tầng, 12 phòng, 8 người thuê, 6 hợp đồng ACTIVE, 24 meter, một số cutoff PENDING, có hóa đơn demo ISSUED/DRAFT. Bộ seed **ghi dữ liệu trực tiếp vào các database**, không phải người dùng đi qua tất cả API; bởi vậy hình ảnh demo seed chưa chứng minh mọi workflow HTTP đã hoạt động. Nếu database đã được sửa sau seed (thử MoMo, reissue, v.v.), không chạy `verify_seed_demo.ps1` và kỳ vọng mọi snapshot còn nguyên.

### 15.2. Những lần bật máy sau

```powershell
# Bật lại, giữ volume
docker compose -f compose.yaml -f compose.workers.yaml --profile simulator up -d --wait

# Dừng nhưng không xóa DB
docker compose -f compose.yaml -f compose.workers.yaml --profile simulator stop
```

Địa chỉ kiểm tra local: `http://127.0.0.1:8080/gateway-health` là Nginx; `http://127.0.0.1:8025` là Mailpit; `http://127.0.0.1:15672` là RabbitMQ UI. Frontend Vite chạy riêng ở `http://localhost:5173` theo cấu hình của nhóm FE.

### 15.3. Bộ test đã có trong SOURCE (không đồng nghĩa vừa chạy trong lần tạo context này)

```powershell
# Bảng và Alembic migration có khớp schema không?
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_schema_v3.ps1

# Runtime + Gateway + 10 background processes đang chạy không?
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1 -Runtime

# Unit/API contract + integration, dùng Docker test project cô lập
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_local.ps1
```

Còn có test gateway login `scripts/tests/auth-gateway.ps1`, kiểm tra Room/Tenant/Contract khác ở `scripts/tests/`. Integration MoMo dùng provider mô phỏng bằng mock HTTP; phải phân biệt với Sandbox thật. **Không xóa volume** chỉ để sửa lỗi FE hoặc “test lại cho sạch”; thao tác reset có thể làm mất dữ liệu demo đã chỉnh.

### 15.4. Cloud: phần đã chuẩn bị và phần chưa hoàn thành

`compose.prod.yaml` chứa overlay giới hạn hạ tầng và yêu cầu `PUBLIC_BASE_URL` HTTPS + SMTP thật. Nginx ứng dụng hiện chỉ listen HTTP 80 trong container; `compose.yaml` bind cổng 8080 **chỉ vào loopback**. Bước Cloud cần một HTTPS reverse proxy trước gateway, chứng chỉ/domain, mapping frontend bundle vào Nginx, secret production, thay Mailpit bằng SMTP thật và kiểm thử kết nối thực tế. Đây là công việc **sau FE**, không phải “chỉ đổi `.env` là EC2 có HTTPS ngay”. Không seed demo/mật khẩu test trên môi trường public.

---

## 16. NHỮNG ĐIỂM CHƯA HOÀN TẤT / DỄ GÂY HIỂU NHẦM

| Vấn đề | Tình trạng ở commit nguồn | Hướng xử lý |
|---|---|---|
| React FE | **CHƯA CODE trong snapshot** | Nhóm FE tạo `frontend/` |
| Vite Proxy/CORS | Nginx chưa chủ động hỗ trợ CORS cross-origin | FE dùng Vite Proxy local và relative path |
| React build trong Nginx | Nginx chỉ có HTML placeholder | Thêm multi-stage Dockerfile và build sau khi có FE |
| Email link đến trang hóa đơn React | Hiện link đến JSON API `/public/v1/invoices/{token}` | Cần phối hợp đổi URL/link hoặc tạo redirect; chưa có `FRONTEND_BASE_URL` |
| MoMo payment completion thực tế | Có code checkout/IPN/query và test mock; ATM Sandbox đã trả `1002` trong thử nghiệm | Chưa nghiệm thu; không giả PAID |
| UI return MoMo | Hiện chỉ plain text | FE/BE thống nhất sau, không dựa return để xác nhận PAID |
| HTTPS EC2 | Production overlay dự kiến HTTPS ngoài container; chưa thấy cấu hình TLS hoàn chỉnh | Làm khi triển khai cloud |
| Refresh token/password reset | Không có route | FE không làm tính năng backend chưa có |
| Dashboard aggregate API | Không có endpoint tổng hợp | FE tổng hợp từ API sẵn có có giới hạn; nếu cần hiệu năng thì đề xuất backend riêng |
| CSV/Excel/PDF export | Chưa thấy endpoint xuất báo cáo trong API hiện tại | Không thiết kế là chức năng đã triển khai |
| Refund/cọc điện tử | Không có | Chỉ hiển thị deposit và hồ sơ điều chỉnh |

**Sai khác so với tài liệu nghiệp vụ đính kèm:** File cũ chốt ở commit `23420d9`, trong khi code `main` hiện là `7a3ec7f` sau PR #19. Phần lớn nội dung nghiệp vụ chính của file cũ phù hợp code, nhưng cần cập nhật phản hồi checkout có `checkout_status: READY | RECONCILING | PAID`, HTTP 202 + `Retry-After` khi đang đối soát, và phân biệt rõ phần FE/HTTPS chưa code. File cũ ghi “CI PR #18 đã pass” là kết quả của một lần chạy ở commit trước, **không được tự suy ra mọi CI ở HEAD hoặc Sandbox ngoài Internet đều pass**. Về cutoffs, code `repo.closest_valid` thực sự chọn reading ở/trước mốc trong 15 phút; một docstring khác nói chọn gần nhất ±15 phút nhưng query thực tế là **chỉ nhìn quá khứ**, nên khi có mâu thuẫn hãy theo query runtime.

---

## 17. CÁCH AI PHẢI TRIỂN KHAI FE VỚI CONTEXT NÀY

Khi AI được giao phát triển một trang, trước tiên xác định user role, endpoint admin/public, trường request/response trong source schema, enum và điều kiện thao tác từ service. Tạo type TypeScript tương ứng; không dùng `any` cho DTO quan trọng. Sau đó tạo API client/hook, màn hình và trạng thái loading/empty/error, rồi kiểm thử với Nginx local. Không tạo mock data cho luồng thực tế trừ khi đánh dấu rõ là chế độ demo/storybook. Mỗi chức năng hoàn thành phải chạy `npm run build` của FE và kiểm thử request thật với backend nếu môi trường sẵn có.

Cần ưu tiên thứ tự màn hình dễ kiểm thử xuyên nghiệp vụ: Login → cây quản lý khu trọ/phòng → người thuê → hợp đồng (confirm, renew, end, cancel) → meter/cutoff → hóa đơn/run → email jobs → trang hóa đơn công khai. Cổng thanh toán real Sandbox được đánh dấu blocked cho đến khi kiểm tra provider thành công, nhưng không được cản những màn hình khác.

Đối với bất kỳ thao tác có tiền, trạng thái hoặc ngày tháng, AI phải thể hiện được `POST/PATCH` hợp lệ, điều kiện được phép, response và thông báo khi bị `409/422/503`. Không thực hiện tính tiền/hợp đồng ở FE để “khớp giao diện” nếu backend không làm vậy. Cần đề xuất diff nhỏ phía BE **riêng** khi gặp thiếu endpoint hoặc thiếu link route, thay vì âm thầm thay đổi source BE và làm hỏng API đã bàn giao.

**Ví dụ prompt giao cho AI FE sau khi đính kèm file này:**

> Bạn là kỹ sư frontend phụ trách dự án Rental Management. Đọc toàn bộ `RENTAL_MANAGEMENT_CONTEXT_FOR_FE_AI.md` và source tại commit được ghi trong file. Hãy thiết kế frontend React + TypeScript + Vite theo API và trạng thái đã triển khai, không suy ra thêm chức năng từ tên gọi. Khởi tạo Vite Proxy cho `/api` và `/public`, dùng URL tương đối ở mọi request, bảo vệ trang admin bằng JWT và tạo trang public invoice từ token. Trước khi code từng module, trích tên file backend có route + Pydantic schema để đối chiếu; nếu thiếu field/route hãy báo cụ thể. Không sửa backend ngoài phạm vi được đồng ý. Ưu tiên code module nhỏ, có test/build, có thể mở được với Docker backend local và sau đó đóng gói React vào Nginx mà không phải thay logic API.

---

## 18. BẢN ĐỒ MÃ NGUỒN ĐỂ AI TỰ KIỂM TRA LẠI

| Cần xác minh | Mã nguồn ưu tiên |
|---|---|
| Route HTTP và field request | `backend/{auth,services/*}/app/api*.py`, `schemas.py` |
| Quy tắc nghiệp vụ | `backend/services/{room,tenant,metering,billing,notification}/app/service.py` |
| Trạng thái và tính hợp lệ database | `backend/**/app/models.py`, `backend/**/migrations/versions/*.py` |
| Auth / JWT / user | `backend/auth/app/api.py`, `api_internal.py`, `security.py`, `config.py` |
| Thời gian hợp đồng | `backend/services/tenant/app/service.py`, `scheduler.py` |
| Event và worker | `messaging.py`, `worker.py`, `scheduler.py`, `lifecycle.py` tương ứng |
| Điện nước | `backend/services/metering/app/{service,repository,api_internal,cutoffs}.py`, `simulator/app/*.py` |
| Công thức hóa đơn | `backend/services/billing/app/{calculator,service,clients,schemas}.py` |
| MoMo trạng thái thực | `backend/services/billing/app/{payment,momo,api_public,api_webhook}.py` |
| SMTP | `backend/services/notification/app/{clients,service,worker,config}.py` |
| Gateway | `infra/nginx/default.conf`, `infra/nginx/Dockerfile` |
| Cấu hình container | `compose.yaml`, `compose.workers.yaml`, `compose.prod.yaml` |
| Dữ liệu demo | `scripts/seed/demo_data.json`, `scripts/seed/seed_service.py` |
| Kiểm thử nguồn | `scripts/test_local.ps1`, `scripts/smoke_test.ps1`, `scripts/verify_schema_v3.ps1`, `tests/integration/`, service `tests/` |

**GitHub tree cố định của bản đối chiếu:** https://github.com/Hoang-Itev/rental-management/tree/7a3ec7f3d65230974cec6875d4b5e8bf479de8f7

**Phạm vi xác minh:** Nội dung tài liệu được dựng từ việc đọc source hiện hành qua GitHub connector và đối chiếu file nghiệp vụ được cung cấp; **không** chạy Docker, API E2E hay tái kiểm thử MoMo/SMTP ở lượt lập tài liệu này. Mọi tuyên bố “đã code” là có đường code tương ứng, không phải chứng nhận không tồn tại bug hoặc mọi nhánh nghiệp vụ đều đã pass.
