# Rental Management

FastAPI Auth, Room, Tenant, Metering, Billing và Notification chạy qua Nginx. PostgreSQL chứa sáu database, RabbitMQ truyền sự kiện và MQTT, Mailpit nhận email thử.

## Chạy local

Xem [hướng dẫn chạy Docker thủ công](RUN_LOCAL.md) để khởi động hạ tầng, API, seed demo và worker theo từng bước, kiểm tra vai trò từng container hoặc làm mới dữ liệu local.

Khi đã quen các bước, có thể dùng lệnh tắt để chạy full stack và seed demo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local.ps1 -SeedDemo
```

## Cấu hình và test

| Vị trí | Mục đích |
| --- | --- |
| `compose.yaml` | Hạ tầng local, API, migration và profile simulator. |
| `compose.workers.yaml` | Worker và scheduler chạy cùng project, áp dụng sau file chính. |
| `compose.prod.yaml` | Cấu hình bổ sung cho lần triển khai cloud sau này. |
| `infra/compose/` | Hot reload, seed và các cấu hình test đặt tên theo chức năng. |

Chạy smoke cho stack đang chạy và chạy các bộ test cô lập:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1 -Runtime
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_local.ps1
```

Thêm `-UnitOnly` khi chỉ cần unit test. Các suite riêng nằm ở `scripts/tests/`, ví dụ `scripts/tests/billing-invoices.ps1`. Các kiểm tra HTTP qua gateway nằm ở `scripts/tests/gateway/`.

GitHub Actions dùng một workflow `.github/workflows/ci.yml` cho kiểm tra tĩnh, unit test, migration, smoke và integration. Các suite nghiệp vụ chạy ở job riêng để nhìn thấy suite nào lỗi ngay trên PR.

## Cloud sau này

Dùng theo thứ tự `compose.yaml`, `compose.workers.yaml`, `compose.prod.yaml`. Chuẩn bị file môi trường riêng với secret mới, `PUBLIC_BASE_URL` là HTTPS của gateway và cấu hình SMTP thật. Khi bật Sandbox, thêm `MOMO_PARTNER_CODE`, `MOMO_ACCESS_KEY`, `MOMO_SECRET_KEY` và `MOMO_IPN_URL` vào môi trường cần chạy. Cấu hình IPN phải cho MoMo gọi được từ bên ngoài. Dữ liệu seed và mật khẩu demo chỉ dùng local.
