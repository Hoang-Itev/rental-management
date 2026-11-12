# Rental Management — chạy Docker thủ công trên Windows

Mở Docker Desktop ở chế độ Linux containers. Mở PowerShell tại thư mục gốc của repo. Các bước dưới đây dùng Docker Compose trực tiếp.

## 1. Chuẩn bị và làm sạch bản local

```powershell
docker context show
docker compose ls -a
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Xác nhận context là Docker Desktop trên máy bạn. Nếu bạn muốn chạy lại từ database trống, chạy lệnh sau. Nó xóa container, image build tự đặt tên và volume PostgreSQL/RabbitMQ của project local `rental-management`. Nếu trước đó bạn dùng một tên project khác, kiểm tra tên bằng `docker compose ls -a` trước.

```powershell
docker compose -p rental-management -f compose.yaml -f compose.workers.yaml --profile simulator down --volumes --remove-orphans --rmi local
```

Lệnh trên giữ các image hạ tầng dùng chung và các image thuộc project test cũ. Nếu muốn dọn **toàn bộ container và image Docker** như yêu cầu ban đầu, chạy thêm hai lệnh dưới đây. Chúng áp dụng cho mọi project trên Docker context đã chọn. Container và dữ liệu chỉ nằm trong lớp ghi của container sẽ bị mất. Các volume khác vẫn còn. Nếu bước xóa container báo lỗi, xử lý lỗi đó trước khi xóa image.

```powershell
docker ps -aq | ForEach-Object { docker rm -f $_ }
docker image prune -a
```

## 2. Khởi động từng lớp

### Hạ tầng và image

```powershell
docker compose -f compose.yaml up -d --wait postgres rabbitmq mailpit
docker compose -f compose.yaml build auth room tenant metering billing notification nginx
```

Build thường dùng lại cache. Để chạy lại từng bước Dockerfile mà vẫn giữ database, thêm `--no-cache` sau `build`. Lệnh xóa image ở bước 1 và build cache là hai việc riêng.

### Migration, cấu hình RabbitMQ và API

```powershell
docker compose -f compose.yaml up -d --wait
docker compose -f compose.yaml ps -a
Invoke-RestMethod http://127.0.0.1:8080/gateway-health
```

Trong bước này Compose tự chạy sáu migration và `rabbitmq-init` theo quan hệ phụ thuộc trong file. Các API có migration tương ứng. Nginx đợi các API healthy. Dùng `ps -a` để xem cả bảy job `Exited (0)`. Nếu job bị lỗi, xem ví dụ `docker compose -f compose.yaml logs billing-migrate` hoặc `docker compose -f compose.yaml logs rabbitmq-init`.

Migration dùng `alembic upgrade head` để cập nhật schema theo phiên bản đang có. Khi có database mới hoặc migration mới, bạn cần chạy job tương ứng. RabbitMQ init nạp các khai báo từ `infra/rabbitmq/definitions.json` khi broker đã sẵn sàng. Compose có thể chạy lại cả hai loại job khi khởi động. Mỗi lần chạy, chúng hoàn thành rồi thoát.

### Dữ liệu demo, nếu bạn muốn đăng nhập hoặc có dữ liệu mẫu

Sau khi reset volume, chạy bước này trước khi bật worker nếu cần account demo. Đoạn dưới gọi cùng chương trình seed trong repo qua Docker, từng service một.

```powershell
$env:SEED_MODE = 'demo'
$env:SEED_OWNER_PASSWORD = '123456789011'
try {
    foreach ($service in 'auth', 'room', 'tenant', 'metering', 'billing', 'notification') {
        docker compose -f compose.yaml -f infra/compose/seed.yaml run --rm --no-deps $service python /seed/seed_service.py $service
        if ($LASTEXITCODE -ne 0) { throw "Seed failed: $service" }
    }
} finally {
    Remove-Item Env:SEED_MODE, Env:SEED_OWNER_PASSWORD
}
```

Đăng nhập bằng `OWNER_EMAIL` trong `.env` và mật khẩu demo trên. Nếu tài khoản đã tồn tại, seed giữ mật khẩu hiện có. Gateway ở `http://127.0.0.1:8080`, Mailpit ở `http://127.0.0.1:8025` và RabbitMQ Management ở `http://127.0.0.1:15672`.

### Worker và scheduler

```powershell
docker compose -f compose.yaml -f compose.workers.yaml up -d --wait
docker compose -f compose.yaml -f compose.workers.yaml ps -a
docker compose -f compose.yaml -f compose.workers.yaml images
```

Nếu vừa build lại một API sau khi đã bật worker, chạy lại lệnh `up` với **cả hai file** để Compose cập nhật cả API lẫn các worker dùng chung image. Chỉ chạy `up` với file chính có thể để worker tiếp tục dùng image cũ.

Đây là cùng project `rental-management`. Docker Compose đọc file chính rồi bổ sung các tiến trình chạy nền. Dùng cả hai file khi quản lý stack đầy đủ. Để thử MQTT mô phỏng, chạy thêm:

```powershell
docker compose -f compose.yaml -f compose.workers.yaml --profile simulator up -d --build --wait simulator
```

Dừng và giữ dữ liệu:

```powershell
docker compose -f compose.yaml -f compose.workers.yaml --profile simulator stop
```

## 3. Từng container chạy gì

| File | Tên trong Compose | Vai trò | Vòng đời |
| --- | --- | --- | --- |
| `compose.yaml` | `postgres` | Một PostgreSQL chứa `auth_db`, `room_db`, `tenant_db`, `metering_db`, `billing_db` và `notification_db`. Script init tạo database và role khi volume trống. | Chạy nền |
| `compose.yaml` | `rabbitmq` | Broker AMQP và MQTT dùng chung cho các sự kiện và telemetry. | Chạy nền |
| `compose.yaml` | `mailpit` | SMTP giả lập, xem email demo trong trình duyệt. | Chạy nền |
| `compose.yaml` | `rabbitmq-init` | Chạy `infra/rabbitmq/bootstrap.py` bằng image Python để nạp cấu hình RabbitMQ. | Chạy xong rồi thoát |
| `compose.yaml` | `auth-migrate` | Alembic của Auth cập nhật `auth_db`. | Chạy xong rồi thoát |
| `compose.yaml` | `room-migrate` | Alembic của Room cập nhật `room_db`. | Chạy xong rồi thoát |
| `compose.yaml` | `tenant-migrate` | Alembic của Tenant cập nhật `tenant_db`. | Chạy xong rồi thoát |
| `compose.yaml` | `metering-migrate` | Alembic của Metering cập nhật `metering_db`. | Chạy xong rồi thoát |
| `compose.yaml` | `billing-migrate` | Alembic của Billing cập nhật `billing_db`. | Chạy xong rồi thoát |
| `compose.yaml` | `notification-migrate` | Alembic của Notification cập nhật `notification_db`. | Chạy xong rồi thoát |
| `compose.yaml` | `auth` | API đăng nhập và JWT, code ở `backend/auth`. | Chạy nền |
| `compose.yaml` | `room` | API nhà, tòa, tầng, phòng, code ở `backend/services/room`. | Chạy nền |
| `compose.yaml` | `tenant` | API người thuê và hợp đồng, code ở `backend/services/tenant`. | Chạy nền |
| `compose.yaml` | `metering` | API đồng hồ, chỉ số và chốt kỳ, code ở `backend/services/metering`. | Chạy nền |
| `compose.yaml` | `billing` | API hóa đơn và thanh toán, code ở `backend/services/billing`. | Chạy nền |
| `compose.yaml` | `notification` | API thông báo, code ở `backend/services/notification`. | Chạy nền |
| `compose.yaml` | `nginx` | Cổng HTTP ở localhost:8080, điều phối request tới các API. | Chạy nền |
| `compose.workers.yaml` | `room-outbox` | Đọc outbox của Room và phát sự kiện lên RabbitMQ. | Chạy nền |
| `compose.workers.yaml` | `room-consumer` | Nhận sự kiện hợp đồng để đồng bộ tình trạng phòng. | Chạy nền |
| `compose.workers.yaml` | `tenant-outbox` | Phát sự kiện đã lưu trong outbox của Tenant. | Chạy nền |
| `compose.workers.yaml` | `tenant-scheduler` | Xử lý các mốc vòng đời hợp đồng và phát nhắc hợp đồng sắp hết hạn. | Chạy nền |
| `compose.workers.yaml` | `metering-consumer` | Xử lý sự kiện Room để đồng bộ đồng hồ. | Chạy nền |
| `compose.workers.yaml` | `metering-telemetry-consumer` | Nhận và lưu dữ liệu chỉ số từ luồng MQTT. | Chạy nền |
| `compose.workers.yaml` | `metering-cutoff-scheduler` | Chạy job chốt chỉ số theo kỳ. | Chạy nền |
| `compose.workers.yaml` | `billing-scheduler` | Chạy lập hóa đơn theo kỳ, nhắc nợ và đối soát MoMo khi được cấu hình. | Chạy nền |
| `compose.workers.yaml` | `billing-outbox` | Phát sự kiện hóa đơn và thanh toán lên RabbitMQ. | Chạy nền |
| `compose.workers.yaml` | `notification-worker` | Nhận sự kiện, xử lý email job và retry khi gửi lỗi. | Chạy nền |
| `compose.yaml` | `simulator` | Phát số đo giả lập qua MQTT. Chỉ bật khi demo IoT. | Chạy nền nếu bật profile |

API, migration và worker của cùng một service dùng chung image. Ví dụ `billing`, `billing-migrate`, `billing-scheduler` và `billing-outbox` có cùng image ID, mỗi container chạy một lệnh khác nhau. Một image có thể tạo nhiều container. Docker Desktop hiển thị `rental-management` như một nhóm, bấm mở để xem các container con.

Bước API + hạ tầng có 10 container chạy và 7 job đã thoát. Khi bật worker, có 20 container chạy và 7 job đã thoát, dùng 11 image riêng biệt. Bật simulator thêm một container và một image. Lệnh seed tạo container tạm và tự xóa khi xong. Các số này giả sử mỗi service có một replica và các job hoàn thành.

## 4. Unit và integration test

Unit test thuần có thể chạy với Python, pytest và dependency đã cài, không cần Docker daemon. Repo cũng có thể chạy unit test trong container Python để đồng nhất môi trường. Chế độ đó chỉ cần image test, không cần khởi động cả stack.

Integration test cần hạ tầng thật mà kịch bản sử dụng, ví dụ PostgreSQL, RabbitMQ hoặc Mailpit. Trong repo, các test này chạy trên các project Compose riêng với database test. Chạy test có thể tạo container và image tạm độc lập với stack chính. Tránh dùng database demo làm database test.

## 5. File Compose còn lại

`infra/compose/seed.yaml` bổ sung dữ liệu demo khi gọi lệnh seed. Các file dưới `infra/compose/tests/` là cấu hình từng bộ test, không thuộc các bước khởi động local. `compose.prod.yaml` dành cho cloud sau này, đi sau `compose.yaml` và `compose.workers.yaml`.
