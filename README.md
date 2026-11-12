# Rental Management

FastAPI Auth, Room, Tenant, Metering, Billing và Notification chạy qua Nginx. PostgreSQL chứa sáu database, RabbitMQ truyền sự kiện và MQTT, Mailpit nhận email thử.

## Chạy local

Mở Docker Desktop ở chế độ Linux containers. Từ PowerShell trong thư mục dự án, chạy một lệnh để tạo `.env` từ mẫu nếu thiếu, khởi động, seed demo và bật worker:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local.ps1 -SeedDemo
```

Đăng nhập bằng `OWNER_EMAIL` trong `.env` và mật khẩu demo `123456789011`. Seed giữ nguyên tài khoản đã có, kể cả mật khẩu. Gateway ở `http://localhost:8080`, Mailpit ở `http://localhost:8025` và RabbitMQ Management ở `http://localhost:15672`.

Nếu đã có `.env` và chỉ cần chạy lại stack, dùng `docker compose up -d --build --wait`. Dùng `docker compose stop` để dừng và giữ dữ liệu. Nếu cần mô phỏng đồng hồ, chạy `docker compose --profile simulator up -d --build --wait`.

### Làm mới dữ liệu và đồng bộ .env

**Lệnh `down --volumes` xóa dữ liệu Docker của project local `rental-management`.** Chạy từ Docker Desktop local. Dùng `docker compose ls -a` để xác nhận tên nếu trước đây bạn đã chọn tên khác với `-p`.

```powershell
docker compose -p rental-management --profile simulator down --volumes --remove-orphans
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local.ps1 -SyncEnv -SeedDemo
```

`-SyncEnv` sao lưu `.env` cũ rồi chép nguyên `.env.example`, nên hai file giống nhau ngay sau khi đồng bộ. Cả `.env` lẫn bản sao lưu đều được Git bỏ qua. Dùng `-SyncEnv` khi làm mới dữ liệu local hoặc khi thông tin kết nối trong template khớp với database hiện tại. Các biến MoMo chỉ cần thêm vào `.env` riêng khi cấu hình Sandbox.

## Cấu hình và test

| Vị trí | Mục đích |
| --- | --- |
| `compose.yaml` | Stack mặc định, gồm API, worker, scheduler và profile simulator. |
| `compose.prod.yaml` | Cấu hình bổ sung cho lần triển khai cloud sau này. |
| `infra/compose/` | Hot reload, seed và các cấu hình test đặt tên theo chức năng. |

Chạy smoke cho stack đang chạy và chạy các bộ test cô lập:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1 -Runtime
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_local.ps1
```

Thêm `-UnitOnly` khi chỉ cần unit test. Các script test cũ vẫn dùng được. Tên workflow và file Compose test theo chức năng để không phụ thuộc thứ tự P01–P13. CI kiểm tra migration, seed, Nginx, worker và các luồng nghiệp vụ.

## Cloud sau này

Dùng `compose.yaml` cùng `compose.prod.yaml`. Chuẩn bị file môi trường riêng với secret mới, `PUBLIC_BASE_URL` là HTTPS của gateway và cấu hình SMTP thật. Khi bật Sandbox, thêm `MOMO_PARTNER_CODE`, `MOMO_ACCESS_KEY`, `MOMO_SECRET_KEY` và `MOMO_IPN_URL` vào môi trường cần chạy. Cấu hình IPN phải cho MoMo gọi được từ bên ngoài. Dữ liệu seed và mật khẩu demo chỉ dùng local.
