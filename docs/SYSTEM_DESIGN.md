# THIẾT KẾ KIẾN TRÚC HỆ THỐNG (SYSTEM DESIGN V2.1)
1. Kiến trúc tổng thể
Hệ thống quản lý nhà trọ sử dụng Microservices Architecture, kết hợp REST API và Event-Driven Architecture.
Microservices nghiệp vụ: Room Service, Tenant Service, Metering Service, Billing Service và Notification Service.
API Gateway: Nginx đóng vai trò điểm truy cập HTTP tập trung, thực hiện định tuyến, kiểm soát truy cập, HTTPS và reverse proxy.
Authentication: Một ứng dụng FastAPI Auth riêng, quản lý đăng nhập, JWT và tài khoản chủ trọ. Đây là thành phần hỗ trợ Gateway, không tính vào 5 microservices nghiệp vụ.
Frontend: React + TypeScript + Vite. Trong môi trường production, Nginx phục vụ các file tĩnh của React sau khi build.
Database: Một PostgreSQL instance chứa 6 database logic, gồm 5 database nghiệp vụ và auth_db. Mỗi service chỉ truy cập database mình sở hữu.
Message Broker: RabbitMQ xử lý sự kiện bất đồng bộ giữa các service và tiếp nhận dữ liệu MQTT từ IoT Simulator.
Mỗi microservice chạy độc lập trong Docker container, có source code, dependencies, Dockerfile và cấu hình riêng.

2. API Gateway và định tuyến
2.1. Vai trò Nginx
Nginx là điểm vào HTTP/HTTPS công khai của hệ thống.
Định tuyến: Chuyển request từ trình duyệt đến đúng microservice dựa trên URL.
Xác thực: Sử dụng cơ chế auth_request để gọi FastAPI Auth kiểm tra JWT trước khi cho phép truy cập Admin API.
Bảo mật: HTTPS, rate limiting, timeout, giới hạn request và cấu hình access logs.
Frontend: Phục vụ HTML, CSS, JavaScript đã build của React.
Nginx không chứa nghiệp vụ quản lý phòng, hợp đồng, hóa đơn hoặc thanh toán.
2.2. Phân loại API
Admin API: /api/v1/...
Chủ trọ đăng nhập bằng JWT. Nginx kiểm tra xác thực trước khi chuyển request đến service.
Public API: /public/v1/...
Người thuê xem và thanh toán hóa đơn qua token bảo mật. Billing chịu trách nhiệm xác minh token.
Webhook: /webhooks/momo/ipn
Nhận kết quả thanh toán MoMo. Billing xác minh chữ ký và dữ liệu giao dịch.
Internal API: /internal/v1/...
Dành cho giao tiếp trực tiếp giữa microservices qua Docker network. Không định tuyến công khai qua Nginx.
2.3. Nguyên tắc trách nhiệm
Nginx: Routing, kiểm soát HTTP và bảo vệ cổng vào.
FastAPI Auth: Đăng nhập, hash mật khẩu, cấp và xác minh JWT.
Microservices: Xử lý nghiệp vụ và kiểm tra quyền đối với tài nguyên thuộc service.
RabbitMQ: Truyền thông điệp bất đồng bộ.
Không sử dụng một FastAPI Gateway riêng chỉ để chuyển tiếp request.

3. Giao tiếp giữa các thành phần
3.1. REST/HTTP
Dùng khi nghiệp vụ cần phản hồi trực tiếp.
Frontend → Nginx → Microservices: Người dùng thao tác với hệ thống.
Tenant → Room: Kiểm tra thông tin và trạng thái hoạt động của phòng.
Billing → Tenant: Lấy hợp đồng và các điều khoản giá.
Billing → Metering: Lấy chỉ số điện nước đã chốt và lượng tiêu thụ.
Notification → Billing: Kiểm tra điều kiện nhắc nợ và lấy liên kết truy cập hóa đơn.
IoT Simulator → Metering: Lấy danh sách đồng hồ đang hoạt động.
Giao tiếp REST giữa các service được thực hiện trực tiếp qua mạng nội bộ, không đi vòng qua Nginx.
REST nội bộ sử dụng service token, timeout và cơ chế xử lý lỗi phù hợp.
3.2. RabbitMQ/AMQP
Sử dụng để truyền sự kiện bất đồng bộ.
RoomCreated: Room phát sự kiện khi tạo phòng, Metering nhận và tạo đồng hồ.
ContractStarted: Tenant phát khi hợp đồng bắt đầu có hiệu lực, Room và Metering cập nhật trạng thái tương ứng.
ContractEnded: Tenant phát khi hợp đồng kết thúc có hiệu lực, Room và Metering xử lý kết thúc.
ContractExpiring: Tenant phát thông báo hợp đồng sắp hết hạn.
InvoiceIssued: Billing phát khi hóa đơn được phát hành.
InvoiceReminderRequested: Billing phát yêu cầu nhắc nợ.
PaymentSucceeded: Billing phát sau khi xác nhận thanh toán thành công.
Các consumer phải xử lý an toàn khi nhận trùng hoặc nhận sự kiện không đúng thứ tự.
3.3. MQTT
Dùng để mô phỏng dữ liệu điện nước.
IoT Simulator viết bằng Python, sử dụng Paho MQTT.
Simulator gửi chỉ số điện nước tích lũy theo MQTT QoS 1 tới RabbitMQ MQTT Plugin.
RabbitMQ định tuyến dữ liệu vào queue tương ứng để Metering Service nhận qua AMQP.
Chu kỳ mặc định là 5 phút, hỗ trợ tăng tốc thời gian mô phỏng để demo.
Nginx không tham gia luồng MQTT.

4. Nguyên tắc thiết kế phân tán
4.1. Database per Service
Mỗi microservice sở hữu database logic riêng.
Không sử dụng Foreign Key xuyên database hoặc truy vấn trực tiếp dữ liệu của service khác.
PostgreSQL được chia sẻ ở mức hạ tầng nhằm tiết kiệm tài nguyên, không chia sẻ quyền sở hữu dữ liệu.
4.2. Transactional Outbox
Áp dụng cho Room, Tenant và Billing đối với những sự kiện nghiệp vụ quan trọng.
Thay đổi dữ liệu nghiệp vụ và bản ghi outbox được lưu trong cùng database transaction.
Outbox worker gửi sự kiện lên RabbitMQ, hỗ trợ retry khi publish thất bại.
4.3. Idempotency
Các tình huống cần chống xử lý trùng gồm:
Dữ liệu MQTT được gửi lại.
RabbitMQ gửi lại domain event.
Nhiều job lập hóa đơn cùng chạy.
MoMo gửi callback thanh toán nhiều lần.
Việc chống trùng dựa trên database constraints, transaction, event ID và các khóa nghiệp vụ phù hợp.
4.4. Retry và Dead Letter Queue
Thông điệp xử lý thất bại tạm thời được retry với backoff và giới hạn số lần thử.
Thông điệp không thể xử lý sau số lần retry quy định được chuyển vào Dead Letter Queue để kiểm tra.
Không retry vô hạn.
4.5. Consistency và xử lý thời gian
Hợp đồng và hóa đơn sử dụng quy tắc ngày tháng thống nhất theo Asia/Ho_Chi_Minh.
Không có quy trình bàn giao phòng riêng.
ContractStarted và ContractEnded mang effective_at để xác định thời điểm nghiệp vụ có hiệu lực.
Consumer không áp dụng thay đổi trước effective_at.
Khi sự kiện kết thúc hợp đồng cũ và bắt đầu hợp đồng mới có cùng thời điểm hiệu lực, hệ thống phải xử lý đúng trạng thái cuối cùng, không phụ thuộc thứ tự message đến.
Hóa đơn lưu snapshot giá và dữ liệu đã dùng để tính tiền, tránh thay đổi lịch sử khi hợp đồng được cập nhật.
4.6. Phạm vi nhất quán phân tán
Sử dụng transaction trong từng service.
Không triển khai distributed transaction giữa các database.
Không dùng Saga cho quy trình tạo hợp đồng.
Ràng buộc hợp đồng chồng lấn được giải quyết trong Tenant Service bằng transaction và database constraints.

5. Xác thực và bảo mật
Authentication: FastAPI Auth quản lý tài khoản chủ trọ trong auth_db.
JWT: Được xác minh thông qua Nginx auth_request đối với Admin API.
Authorization: Mỗi service kiểm tra quyền nghiệp vụ khi cần, không chỉ dựa vào việc request đã đi qua Gateway.
Public invoice: Người thuê truy cập hóa đơn bằng token ngẫu nhiên có thời hạn và có thể thu hồi; Billing chỉ lưu hash của token.
MoMo: Billing xác minh chữ ký và đối chiếu mã giao dịch, số tiền và trạng thái trước khi cập nhật thanh toán.
Internal REST: Giao tiếp trong Docker network, sử dụng xác thực service-to-service.
Secrets: Quản lý bằng biến môi trường hoặc GitHub Secrets phù hợp, không commit mật khẩu và API key.
Network: Chỉ Nginx mở cổng HTTP/HTTPS công khai. PostgreSQL, RabbitMQ, MQTT, Auth verification endpoint và Internal APIs không được công khai trực tiếp.
Logging: Che token hóa đơn và dữ liệu nhạy cảm trong access logs và application logs.

6. Bộ công nghệ đã chốt
Frontend: React + TypeScript + Vite.
Backend: Python + FastAPI cho 5 microservices.
Authentication: FastAPI Auth + JWT.
API Gateway / Reverse Proxy: Nginx.
REST API Specification: OpenAPI 3.1.
Event Specification: AsyncAPI 3.0.
ORM: SQLAlchemy 2.x.
Database Migration: Alembic.
Database: PostgreSQL, 6 database logic trên một instance.
Message Broker: RabbitMQ + MQTT Plugin.
IoT Simulator: Python + Paho MQTT.
Thanh toán: MoMo Sandbox.
Email: Brevo SMTP; Mailpit dùng trong local.
Containerization: Docker + Docker Compose.
Version Control: Git + GitHub, sử dụng Monorepo và Pull Requests.
Automated Testing: pytest, HTTPX và integration tests.
API Testing thủ công: FastAPI Swagger UI; có thể dùng VS Code REST Client để lưu request.
CI/CD: GitHub Actions.
Container Registry: GitHub Container Registry (GHCR).
Infrastructure as Code: Terraform.
Cloud: AWS EC2.
Kubernetes thực hành: kind trên local; không triển khai EKS.
Performance Testing: Locust.

7. Chiến lược phát triển và triển khai
7.1. Cấu trúc dự án
Sử dụng một Monorepo trên GitHub.
Frontend nằm trong thư mục frontend/.
Các microservices và Auth nằm trong backend/.
Nginx, Docker Compose, Terraform và cấu hình triển khai nằm trong các thư mục hạ tầng tương ứng.
OpenAPI và AsyncAPI được lưu trong contracts/, dùng chung cho toàn nhóm.
Mỗi service có ORM models, migration, Dockerfile và tests riêng.
7.2. Môi trường Local
Các thành viên lập trình trên máy cá nhân.
FastAPI và React có thể chạy trực tiếp ở chế độ development.
PostgreSQL, RabbitMQ và Mailpit chạy bằng Docker Compose.
Docker Compose cũng được sử dụng để chạy toàn bộ hệ thống khi kiểm thử tích hợp.
Không cần sử dụng Cloud cho công việc lập trình hằng ngày.
7.3. Quy trình phát triển tính năng
Mỗi task được quản lý bằng Kanban trên Trello.
Thành viên tạo feature branch từ main.
Sau khi viết code, thực hiện migration và chạy unit/API tests trên local.
Kiểm thử tích hợp với các service liên quan.
Push code lên GitHub và tạo Pull Request.
GitHub Actions tự động kiểm tra chất lượng code, chạy tests và build Docker image.
Pull Request chỉ được merge khi các kiểm tra cần thiết đạt yêu cầu và đã review.
7.4. CI/CD
CI được thiết lập từ đầu dự án, không đợi đến lúc hoàn thành code.
GitHub Actions chạy kiểm tra khi có Pull Request hoặc push phù hợp.
Docker images được build, gắn phiên bản và push lên GHCR.
CD sử dụng image đã được kiểm thử để triển khai lên EC2.
Triển khai Cloud có bước phê duyệt thủ công để hạn chế làm hỏng môi trường demo.
Hỗ trợ triển khai lại phiên bản trước khi cần; migration phải được kiểm tra khả năng tương thích.
7.5. Triển khai Cloud
Terraform tạo hạ tầng AWS EC2 và cấu hình mạng cần thiết.
Docker Compose chạy Nginx, Auth, 5 microservices, PostgreSQL, RabbitMQ và các worker cần thiết trên EC2.
Nginx phục vụ React static files, HTTPS và định tuyến HTTP.
Sau triển khai, thực hiện smoke tests kiểm tra health, readiness và các API quan trọng.
Cloud được đưa vào giai đoạn tích hợp khi ứng dụng đã đủ ổn định, nhưng Docker, CI và cấu hình triển khai phải được chuẩn bị từ đầu.
Một EC2 không cung cấp High Availability; đây là giới hạn được chấp nhận trong phạm vi đồ án.
7.6. Kubernetes Local
Sử dụng kind để thực hành các khái niệm Kubernetes.
Triển khai một số service lên Kubernetes local bằng Deployment, Service và cấu hình tương ứng.
Demo khả năng tự tạo lại Pod sau khi Pod bị xóa.
Kubernetes không thay thế Docker Compose trên EC2 trong phiên bản triển khai chính.
Hoàn thành luồng nghiệp vụ và CI/CD chính trước khi mở rộng thực hành Kubernetes.

8. Kiểm thử và quan sát hệ thống
8.1. Các cấp độ kiểm thử
Unit Tests: Kiểm tra logic tính tiền, ngày hợp đồng, trạng thái và các hàm nghiệp vụ độc lập.
API Tests: Kiểm tra endpoint, request/response, HTTP status và xác thực.
Integration Tests: Kiểm tra PostgreSQL, RabbitMQ và giao tiếp giữa microservices.
Contract Tests: Kiểm tra API và event payload phù hợp OpenAPI/AsyncAPI đã thống nhất.
End-to-End Tests: Kiểm tra luồng tạo phòng → hợp đồng → IoT → hóa đơn → email → thanh toán.
Failure Tests: Thử callback trùng, event trùng, service bị tắt, retry và DLQ.
Load Tests: Sử dụng Locust đánh giá throughput, độ trễ và khả năng xử lý khi có nhiều request.
8.2. Observability
Mỗi service cung cấp /health (tiến trình đang chạy) và /ready (PostgreSQL + bảng alembic_version sẵn sàng); cần xác minh /ready trên Docker thật sau khi áp dụng bản vá.
Sử dụng structured JSON logs và correlation ID để theo dõi một request hoặc event xuyên các service.
RabbitMQ Management UI hỗ trợ kiểm tra queue, message và consumer.
Docker logs và docker stats phục vụ theo dõi container và mức tiêu thụ tài nguyên.
Prometheus và Grafana là phần mở rộng nếu còn thời gian và tài nguyên.

9 Các kỹ năng đồ án cần chứng minh
Microservices: Phân chia trách nhiệm, dữ liệu độc lập, API contracts và triển khai service độc lập.
Containerization: Docker image, Dockerfile, Docker Compose và network giữa container.
Database Management: SQLAlchemy, Alembic, PostgreSQL constraints và transaction.
Service Communication: REST, RabbitMQ/AMQP và MQTT.
Distributed Systems: Idempotency, Transactional Outbox, retry, DLQ và phục hồi lỗi.
API Gateway: Nginx routing, HTTPS, xác thực qua Auth Service và bảo vệ các endpoint công khai.
Testing: Unit, API, integration, contract, end-to-end và load tests.
DevOps: GitHub Flow, Pull Requests, CI/CD, GHCR và quản lý phiên bản image.
Cloud: Terraform và triển khai hệ thống bằng Docker Compose trên AWS EC2.
Kubernetes: Deployment, Service và self-healing trên kind local.
Observability: Health checks, readiness checks, structured logging và correlation ID.


10. CÁC QUYẾT ĐỊNH ĐÃ BÁC BỎ
Không xây dựng website tìm phòng hoặc đặt phòng trực tuyến.
Không phát triển SaaS nhiều chủ trọ độc lập.
Không bắt buộc người thuê tạo tài khoản.
Không xây dựng ký hợp đồng điện tử.
Không quản lý các giao dịch tiền cọc.
Không thêm Contract Service, Payment Service hoặc Auth Service nghiệp vụ riêng.
Không dùng Saga cho việc lập hợp đồng.
Không cần năm PostgreSQL server vật lý.
Không dùng Kafka trong phiên bản này.
Không sử dụng phần cứng IoT thật.
Không bắt buộc triển khai Kubernetes lên cloud.
Không triển khai EKS, RDS, Helm hoặc hệ thống Dev/Staging/Production đầy đủ.
Không thêm công nghệ chỉ để tăng độ phức tạp mà không có giá trị kiểm chứng.


## Ghi chú trạng thái triển khai (11/11/2026)
ORM/migration V3 đã chạy trên PostgreSQL. Auth/API/worker/scheduler chủ yếu là khung; không được mô tả là nghiệp vụ đã hoàn tất. Docker Compose cần bảo đảm các job Alembic hoàn thành trước khi khởi động ứng dụng. JWT và Nginx auth_request chưa thể nghiệm thu khi Auth chưa có verify endpoint. CI chưa thể tính coverage nghiệp vụ 80% khi các service chưa triển khai.
