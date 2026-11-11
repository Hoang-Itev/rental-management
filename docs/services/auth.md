# Auth Service — P01 Contract and Code Map

**Sở hữu:** `auth_db.users` (PostgreSQL); không truy cập DB các service khác. **Cổng nội bộ:** 8000, gateway Nginx :8080. **Cấp quyền:** hiện chỉ một owner; không có đăng ký tài khoản công khai, không giả định có role column.

## HTTP routes

| Route | Caller | Trả về / Lỗi |
|---|---|---|
| `POST /api/v1/auth/login` | Guest → Nginx → Auth | `200 {access_token,token_type,expires_in,user}`, `401` sai thông tin, `422` dữ liệu sai; không gửi hash |
| `GET /api/v1/auth/me` | Owner → Nginx → Auth | `200 UserPublic`, `401` JWT không hợp lệ/hết hạn hoặc user bị vô hiệu hóa |
| `GET /internal/v1/auth/verify` | **Chỉ** Nginx `_auth` | `204` + header `X-Auth-User-Id`, `401` JWT sai, `403` service token sai |
| `GET /health` | Docker liveness | `200` khi tiến trình sống |
| `GET /ready` | Docker readiness | `200` nếu DB có Alembic marker, `503` nếu chưa sẵn sàng |

Hai public routes được định nghĩa trong `contracts/openapi.yaml`; internal route chỉ dành cho Gateway, không công khai qua Nginx hoặc trong FastAPI Swagger.

## Mô tả từng file và các API nội bộ

| File | Hàm / class và vai trò |
|---|---|
| `app/config.py` | `AuthSettings`: cấu hình JWT, Service Token có kiểm tra độ dài; `get_settings()` có cache |
| `app/security.py` | `hash_password()`, `verify_password()` (Argon2id); `reject_unknown_user()` chống lộ sự tồn tại email qua timing ở mức cơ bản; `create_access_token()` và `decode_access_token()` (HS256, sub/iss/aud/iat/nbf/exp/jti/type); `bearer_token()`; `valid_service_token()` |
| `app/schemas.py` | `LoginRequest`, `LoginResponse`, `UserPublic`, `ApiError`; chuẩn hóa email; loại hash khỏi DTO |
| `app/repository.py` | `get_user_by_email()`, `get_user_by_id()`, `record_successful_login()`; truy vấn và ghi `last_login_at` |
| `app/service.py` | `login()` xử lý xác thực và cấp token; `current_user()` xác minh chữ ký và kiểm tra user đang hoạt động; `AuthenticationRejected` thống nhất lỗi |
| `app/api.py` | 2 public routes; khai báo `BearerAuth` trong OpenAPI; `unauthorized()` |
| `app/api_internal.py` | Verify route cho Nginx; phải có service token và JWT; chỉ trả identity header khi hợp lệ |
| `app/main.py` | Đăng ký routers, error handlers trả `{code,message,correlation_id}`, `/health`, `/ready`; tuyệt đối không phản chiếu password trong validation error |
| `app/db.py`, `app/models.py` | **Giữ nguyên** ở P01; dùng session và bảng `users` từ Database V3 |
| `tests/conftest.py` | `FakeSession`, fixtures AuthSettings/user/TestClient; không cần DB thật |
| `tests/test_security.py` | Hash, bearer parsing, JWT tamper, expiry, algorithm, issuer/audience, required claims |
| `tests/test_service.py` | Success/failure/disable/deleted user, DB write only on success |
| `tests/test_api.py` | Public/Internal API, DTO, invalid data, privacy, OpenAPI security |
| `tests/test_repository.py` | SQL lookup normalization, lookup UUID, commit |
| `tests/test_config.py` | Required secrets, token TTL bounds, env parsing |
| `tests/test_main.py` | Readiness DB up/down, no migration, error responses |
| `infra/nginx/default.conf` | `auth_request /_auth`, propagate verified user ID (never client-supplied), throttle login 10/min with burst 8 |
| `scripts/auth/gateway_check.py` | E2E thực qua `127.0.0.1:8080`, **không mock**; kiểm tra login/me/đường nội bộ |
| `scripts/test_auth_unit.ps1`, `scripts/test_auth_gateway.ps1` | Một lệnh test trong Docker, một lệnh E2E qua gateway trên Windows |
| `compose.auth-test.yaml` | Overlay chỉ mount test và requirements-test, không được dùng cho production |

## Chính sách bảo mật và giới hạn P01

Tài khoản owner tạo qua seed (`scripts/run_seed_demo.ps1`, nhập mật khẩu tương tác). Seed chỉ insert khi chưa có, không đặt lại password đã tồn tại. Mật khẩu được hash bằng `pwdlib[argon2]` trong seed, tương thích `argon2-cffi` lúc login. `JWT_SECRET` tối thiểu 32 ký tự; `SERVICE_TOKEN` tối thiểu 24 ký tự; `JWT_TTL_SECONDS` mặc định 3600 giây. Không ghi password/JWT vào logs. Login response có `Cache-Control: no-store`. Nginx throttles login; chưa triển khai distributed lockout hoặc MFA.

`GET /me` cố ý xác minh JWT lần hai trong Auth dù Nginx đã check, để không tin header giả từ client hoặc cổng dev. Các service nghiệp vụ về sau phải chỉ tin `X-Auth-User-Id` từ gateway/network đáng tin cậy, không tin header gửi trực tiếp từ Internet. Trạng thái `is_active` được truy vấn ở mỗi request, nên khóa tài khoản có hiệu lực ngay. JWT đã cấp không thể thu hồi riêng lẻ cho tới khi hết hạn, trừ khi đổi JWT secret làm vô hiệu tất cả.

## Definition of Done

Local: `scripts/test_auth_unit.ps1` đạt **>=95%** coverage và `scripts/test_auth_gateway.ps1` hoàn tất sau khi seed owner. Kiểm tra `docker compose exec -T nginx nginx -t`. Github CI: `service-unit-tests (auth)` + `compose-startup-smoke` (sẽ seed owner tạm riêng, chạy `gateway_check.py`) đạt. Mọi thay đổi qua feature branch, Pull Request, CI trước merge.

**Không cần sửa migration hay bảng Auth.** P01 không thêm API đăng ký, refresh token, logout server-side, MFA, đổi mật khẩu, hoặc RBAC nhiều vai trò.
