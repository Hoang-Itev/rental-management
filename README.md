# Rental Management

Hệ thống FastAPI gồm Auth, Room, Tenant, Metering, Billing và Notification. Nginx là gateway. PostgreSQL chứa sáu database, RabbitMQ truyền sự kiện và telemetry, Mailpit nhận email thử. Frontend là phần việc riêng.

## Chạy local từ đầu

Mở Docker Desktop ở chế độ Linux containers. Trong thư mục dự án, tạo `.env` nếu chưa có:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose version
```

### Reset Docker cũ nếu cần dữ liệu trắng

**Lệnh sau xóa dữ liệu PostgreSQL, RabbitMQ và Mailpit của project local `rental-management`.** Sao lưu trước nếu cần giữ dữ liệu. Nếu trước đây dùng tên project khác, xem tên bằng `docker compose ls -a` rồi chọn đúng project của đồ án. Chạy lệnh từ máy local với Docker context của Docker Desktop.

```powershell
docker context show
docker compose -p rental-management -f compose.yaml -f compose.runtime.yaml down --volumes --remove-orphans
```

### Khởi động

Dùng hai file cho môi trường local đầy đủ:

```powershell
$stack = @('-f', 'compose.yaml', '-f', 'compose.runtime.yaml')
docker compose @stack config --quiet
docker compose @stack up -d --build --wait
docker compose @stack ps -a
```

Gateway dùng `http://localhost:8080`, Mailpit dùng `http://localhost:8025` và RabbitMQ Management dùng `http://localhost:15672`. Sáu container migration và `rabbitmq-init` chạy một lần rồi thoát mã 0. Các API, worker và scheduler tiếp tục chạy. Để bật thêm simulator hoặc dừng stack:

```powershell
docker compose @stack --profile simulator up -d --build --wait
docker compose @stack --profile simulator stop
```

`compose.runtime.yaml` thay chuỗi overlay P03, P05, P06, P07, P09, P10, P11 và P12. Các file Compose dành cho test chỉ được script của chúng dùng. `compose.dev.yaml` là tùy chọn khi cần hot reload.

### Seed dữ liệu demo tùy chọn

Nếu cần số liệu seed đúng như fixture ngay từ đầu, khởi động hạ tầng và API, seed, rồi mới bật các job nghiệp vụ. Sau khi reset, dùng các lệnh này thay cho bước khởi động đầy đủ phía trên:

```powershell
$stack = @('-f', 'compose.yaml', '-f', 'compose.runtime.yaml')
docker compose -f compose.yaml up -d --build --wait
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_seed_demo.ps1
docker compose @stack up -d --build --wait
```

Script sẽ hỏi mật khẩu demo. Đăng nhập bằng `OWNER_EMAIL` trong `.env`. Seed ghi snapshot mẫu trực tiếp và kiểm tra schema trước khi ghi. Sau khi bật scheduler, dữ liệu mẫu có thể thay đổi theo nghiệp vụ.

## Test local

Kiểm tra stack đang chạy. Các lệnh này đọc trạng thái migration, healthcheck, worker và gateway:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1 -Runtime -TimeoutSeconds 240
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_schema_v3.ps1
```

Chạy unit và các integration test cô lập. Mỗi integration script tạo project và volume test riêng rồi tự dọn. Có thể thêm `-UnitOnly` để chạy nhanh unit test:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_local.ps1
```

Sau khi seed tài khoản demo, có thể kiểm tra đăng nhập và JWT qua gateway:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_auth_gateway.ps1
```

Bài test MoMo tự động mô phỏng provider. Demo MoMo Sandbox cần tài khoản Sandbox và URL IPN HTTPS mà MoMo truy cập được. CI chạy thêm smoke trên stack đầy đủ, kiểm tra cấu hình Nginx và các integration theo từng luồng nghiệp vụ.

## Chuẩn bị chạy cloud sau này

Khi triển khai thủ công, dùng `compose.yaml`, `compose.runtime.yaml` và thêm `compose.prod.yaml`. Cấu hình này bỏ port quản trị RabbitMQ và chỉ bật Mailpit nếu chọn profile `local-mail`. Gateway lắng nghe ở loopback `127.0.0.1:8080` để reverse proxy trên máy chủ nhận HTTPS và chuyển tiếp vào gateway. PostgreSQL và API nội bộ vẫn chạy trong mạng Docker.

Tạo file môi trường riêng trên máy chủ với password DB/broker, JWT secret và service token mới. Đặt `PUBLIC_BASE_URL` thành origin HTTPS và cấu hình SMTP thật qua `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_FROM`, `SMTP_USERNAME`, `SMTP_PASSWORD`. `compose.prod.yaml` mặc định dùng SMTP STARTTLS cổng 587. Nếu dùng MoMo, cấu hình `MOMO_IPN_URL` bằng HTTPS của gateway. Giữ thông tin này ngoài Git. Dữ liệu demo chỉ dùng ở local.
