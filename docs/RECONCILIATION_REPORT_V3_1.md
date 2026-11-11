# Kiểm tra sai khác trước khi vào nghiệp vụ (11/11/2026)

## Đã xác minh từ file upload + repository GitHub

1. Cao: mâu thuẫn cutoff. ORM V3 unique theo (meter,type,time,contract), OpenAPI/Context quy định một bản chốt cho (meter,time). Bản vá V3.1 dùng 1 cutoff hiệu lực cho (meter,time); loại mốc chỉ mô tả ngữ cảnh tạo.
2. Cao: service chỉ phụ thuộc DB healthy, không phụ thuộc Alembic, /ready đang 404. V3.1 thêm 6 migration jobs trong Compose và /ready tối thiểu.
3. Trung bình: room.property_id có thể khác property của floor. V3.1 thêm guard triggers.
4. Trung bình: PUBLIC CONNECT/TEMPORARY đang mở. V3.1 sửa init và cung cấp SQL cho volume hiện hữu.
5. Trung bình: SERVICE_TOKEN/JWT_SECRET chưa bắt buộc, Compose nối raw password thành URL. V3.1 buộc 2 secret và nêu hạn chế charset. Chưa hỗ trợ password có ký tự URL đặc biệt.
6. Trung bình: hostname internal của OpenAPI đang dùng room-service,... V3.1 đổi thành tên Docker DNS room, tenant, metering, billing.
7. Ngoài danh sách: docs/PROJECT_CONTEXT.md và .github/workflows/ci.yml trên nhánh GitHub được kiểm tra vẫn rỗng. Bản vá chỉ bổ sung tài liệu; CI phải được cài bằng gói CI/Seed đã tạo hoặc hoàn thiện riêng.

## Kiểm thử chưa xác nhận
Không có Docker/PostgreSQL Engine trong môi trường xây dựng bản vá, nên chưa chạy các migrations V3.1 trên DB thật, chưa kiểm tra Compose trên Docker Desktop Windows, chưa kiểm chứng hành vi trigger bằng INSERT thực. Cần xác minh trên bản sao DB local/CI, sau khi đã backup.

## Không thay đổi
Giữ 26 bảng, 6 database logic, source business, seed, giao thức RabbitMQ/MQTT và các file migration 001 đã chạy. Không cung cấp hoặc ghi đè .env.
