# HTTP API và kiểm thử bàn giao FE

`openapi.yaml` là đặc tả HTTP của code hiện tại. Import file này vào Postman để có danh sách request. Các file `api-requests/*.http` là ví dụ chạy thủ công, không phải bộ kiểm thử tự động và không thay thế CI.

## Phạm vi route

Có 87 operation ứng dụng (đếm theo method + path), cộng 2 đường dẫn probe `/health`, `/ready` chạy riêng ở mỗi service. Không tính Swagger tự sinh hay `/gateway-health` của Nginx.

| Service | Operation ứng dụng |
|---|---:|
| Auth | 3 |
| Room | 22 |
| Tenant | 21 |
| Metering | 18 |
| Billing | 20 |
| Notification | 3 |

FE gọi `http://localhost:8080`. `/api/v1/*` cần JWT, trừ đăng nhập. Nginx tự gắn `X-Auth-User-Id`; FE không tự đặt header này. `/internal/v1/*` chỉ gọi trong Docker network với service token; không đưa token nội bộ vào FE. Link hóa đơn công khai dùng token trong URL. Callback MoMo phải được Billing kiểm chữ ký; browser quay về trang return không có quyền xác nhận đã trả tiền.

## Đối chiếu lần này

Ba operation đã được mô tả nhưng thiếu triển khai được bổ sung: `GET /api/v1/contracts/expiring`, `POST /api/v1/contracts/{contract_id}/cancel`, `GET /api/v1/rooms/{room_id}/meters`.

Hủy chỉ áp dụng DRAFT/SCHEDULED chưa kích hoạt, có khóa row và ghi đúng một lịch sử CANCELLED khi retry. Hợp đồng đã ACTIVE/EXPIRED_PENDING/ENDED bị từ chối 409; phải đi qua kết thúc hợp đồng. Hủy không phát ContractEnded vì chưa từng phát ContractStarted. Lịch đặt phòng được giải phóng bởi trạng thái CANCELLED. Danh sách sắp hết hạn lấy ACTIVE, chưa bàn giao, end_date từ hôm nay đến hôm nay + within_days (bao gồm hai đầu, múi giờ Việt Nam).

12 operation dưới đây đã có trong code trước lần sửa này; được đưa vào đặc tả, không phải thêm 12 chức năng mới:

| Method | Path |
|---|---|
| GET | `/api/v1/meter-cutoffs` |
| GET | `/api/v1/meter-cutoffs/{cutoff_id}` |
| GET | `/api/v1/meters/{meter_id}/alerts` |
| POST | `/api/v1/jobs/meters/cutoffs` |
| POST | `/api/v1/meter-cutoffs/{cutoff_id}/revise` |
| GET | `/internal/v1/auth/verify` |
| GET | `/internal/v1/contracts/{contract_id}` |
| GET | `/internal/v1/contracts/{contract_id}/expiry-notification-eligibility` |
| GET | `/internal/v1/meters/{meter_id}/baseline` |
| GET | `/internal/v1/rooms/{room_id}/cutoffs` |
| GET | `/internal/v1/rooms/{room_id}/meters` |
| GET | `/public/v1/payments/momo/return` |

`/revise` là alias tương thích; code mới dùng `/corrections`. Không xóa alias để tránh phá caller hiện có.

## Quy tắc cập nhật API

Khi sửa route, request hoặc response, chạy bằng môi trường Python đã cài requirements của service tương ứng:

```powershell
python scripts/check_api_contract.py --service tenant --write
python scripts/check_api_contract.py --service tenant
```

Thay `tenant` bằng `auth`, `room`, `metering`, `billing`, `notification` khi cần. Mỗi service chạy trong một process riêng vì các package cùng tên `app`. Chế độ `--write` chỉ cập nhật service đó, từ chối tự xóa route đã công bố. Review diff trước khi commit; exporter không quyết định nghiệp vụ thay người viết. Các schema được gắn tiền tố service để tránh hai DTO cùng tên ghi đè nhau.

CI kiểm tra cả route đang đăng ký (kể cả nội bộ/alias), payload, response schema và security của đặc tả. Đối chiếu contract không gọi DB và không chứng minh kết quả nghiệp vụ; unit/API test, integration PostgreSQL và gateway E2E kiểm tra các phần đó riêng.

## Chạy kiểm thử

Trước khi bàn giao FE, chạy từ gốc repo, Docker Desktop đang mở, `.env` đã có:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_local.ps1
```

Lệnh trên chạy unit/API test và contract check cho sáu backend, unit test simulator, sau đó 10 bộ integration trong các Compose project tạm. Không xóa volume của project local đang dùng. Chỉ muốn test nhanh thì thêm `-UnitOnly`; chế độ này không xác minh PostgreSQL, RabbitMQ hay SMTP thực.

Sau khi backend local đã khởi động và seed đúng tài khoản, kiểm tra qua Nginx:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke_test.ps1 -Runtime
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\tests\auth-gateway.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\tests\tenant-gateway.ps1
```

Gateway tenant tạo dữ liệu demo trong DB local. CI chạy phiên bản Python của gateway test trên DB dùng một lần. Các test đã chạy không đồng nghĩa mọi tổ hợp đầu vào đều được chứng minh đúng.

## Ba nhóm FE kiểm tra thủ công

| Nhóm | Luồng và kết quả cần đối chiếu |
|---|---|
| Đăng nhập, phòng, hợp đồng | JWT đúng/sai; tạo cây phòng; tạo/xác nhận/hủy hợp đồng; trùng kỳ bị chặn; xem hợp đồng sắp hết hạn |
| Đồng hồ và hóa đơn | Chỉ số, cutoff pending/confirmed; thiếu cutoff giữ DRAFT; đủ dữ liệu mới ISSUED; tổng tiền bằng các dòng; chạy lại không trùng hóa đơn |
| Email, thanh toán, điều chỉnh | Xem email trong Mailpit; link hết hạn bị từ chối; MoMo Sandbox khi có credential; VOID/reissue vô hiệu link cũ; PAID không sửa trực tiếp |

Test chữ ký sai, callback trùng, lỗi SMTP, mất kết nối và concurrency nên chạy tự động bằng integration; không cần nhập lại từng trường hợp trong Postman. MoMo thật trong Sandbox cần cấu hình tài khoản và callback có thể truy cập; mock trong CI không chứng minh tài khoản MoMo đã cấu hình đúng.
