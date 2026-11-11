# CONTEXT MASTER V3.1 — HỆ THỐNG QUẢN LÝ NHÀ TRỌ

Phiên bản 11/11/2026. Tài liệu này gộp ngữ cảnh để dùng trong một cuộc trò chuyện AI; source-of-truth theo từng lĩnh vực vẫn là các file bên dưới. Không chép những mật khẩu trong `.env` vào chat.

## Thứ tự ưu tiên khi có mâu thuẫn
1. Quyết định nghiệp vụ đã thống nhất trong docs và contracts sau đợt đối chiếu V3.1.
2. OpenAPI/AsyncAPI mô tả giao tiếp mong muốn (không đồng nghĩa đã triển khai).
3. Models và các Alembic revisions đang áp dụng mô tả schema hiện hữu.
4. Code runtime và tests chứng minh hành vi đã chạy; file TODO/empty không phải implementation.

---



---

# PROJECT CONTEXT: HỆ THỐNG QUẢN LÝ NHÀ TRỌ TRÊN NỀN TẢNG ĐÁM MÂY
Trạng thái dự án (11/11/2026): Database Design V3 có 26 bảng trong 6 database, ORM + Alembic V3 đã được chạy thành công trên PostgreSQL. Hạ tầng local có Docker Compose, RabbitMQ, Nginx. OpenAPI V1.1 và AsyncAPI V1.1 là tài liệu hợp đồng; nghiệp vụ các service chưa được triển khai. CI trên repository cần được thiết lập (file ci.yml ở commit được kiểm tra đang rỗng).
Mục đích: Tài liệu giới thiệu cho chat AI và nhóm. Các phần chi tiết nằm trong SYSTEM_DESIGN.md, DATABASE_DESIGN_V3.md và API_EVENT_CONTRACTS_CONTEXT.md. Mô tả kết quả đã kiểm thử khác với chức năng dự định làm.

1. BỐI CẢNH VÀ MỤC TIÊU ĐỒ ÁN
Đây là đồ án cuối kỳ môn Điện toán đám mây (Cloud Computing), thực hiện bởi nhóm 3 sinh viên,
Môn học tập trung vào Cloud Computing, Virtualization, Docker, Microservices
Mục tiêu chính của đồ án không phải xây dựng phần mềm quản lý nhà trọ có thật nhiều tính năng, mà là xây dựng một hệ thống có nghiệp vụ đủ rõ để chứng minh năng lực thiết kế, triển khai và vận hành ứng dụng phân tán trên cloud.
Các kỹ năng trọng tâm cần thể hiện gồm microservices, containerization, giao tiếp đồng bộ và bất đồng bộ, xử lý lỗi, tính nhất quán dữ liệu, CI/CD, Infrastructure as Code và triển khai thực tế lên cloud.
Ưu tiên một hệ thống hoạt động ổn định, có thể trình diễn các kịch bản kỹ thuật và giải thích được những quyết định kiến trúc.
2. PHẠM VI NGHIỆP VỤ
2.1. Bản chất hệ thống
Đây là hệ thống số hóa hoạt động quản lý nhà trọ đã tồn tại ngoài đời thực.
Không phải website tìm kiếm, đặt phòng hoặc môi giới thuê trọ.
Chủ trọ và người thuê thỏa thuận trực tiếp bên ngoài. Sau đó chủ trọ nhập thông tin vào hệ thống để quản lý lâu dài.
Hệ thống phục vụ một chủ trọ có thể sở hữu nhiều khu trọ. Chưa phát triển theo mô hình SaaS nhiều chủ trọ độc lập.
2.2. Tác nhân
Chủ trọ: Đăng nhập website để quản lý phòng, người thuê, hợp đồng, điện nước, hóa đơn, công nợ và theo dõi hệ thống.
Người thuê: Không cần đăng ký tài khoản hoặc đăng nhập. Nhận hóa đơn qua email, mở liên kết bảo mật để xem và thanh toán hóa đơn.
IoT Simulator: Chương trình giả lập các đồng hồ điện nước, chủ động gửi dữ liệu đo qua giao thức MQTT.
MoMo Sandbox: Dịch vụ bên ngoài phục vụ kiểm thử thanh toán trực tuyến.
Brevo: Dịch vụ gửi email hóa đơn, nhắc hạn và xác nhận thanh toán.
2.3. Quản lý khu trọ và phòng
Cấu trúc quản lý gồm:
Khu trọ → Dãy nhà → Tầng → Phòng.
Một chủ trọ có thể quản lý nhiều khu trọ. Mỗi phòng có mã phòng, diện tích, giá niêm yết và trạng thái.
Hỗ trợ tạo phòng hàng loạt bằng cách nhập dãy, số tầng, số phòng mỗi tầng và quy tắc đánh số.
Trạng thái phòng gồm Trống, Đang thuê và Ngừng sử dụng.
Không cho phép có hai hợp đồng thuê hiệu lực chồng lấn trên cùng phòng. Phòng đã có lịch sử nghiệp vụ không bị xóa cứng.
2.4. Người thuê và hợp đồng
Hệ thống lưu hồ sơ người thuê và thông tin hợp đồng đã thỏa thuận ngoài đời thực.
Mỗi hợp đồng gồm người đại diện, phòng thuê, ngày bắt đầu, ngày kết thúc, giá thuê, đơn giá điện nước và các điều khoản cần phục vụ việc tính tiền.
Hợp đồng có thể bắt đầu vào ngày bất kỳ trong tháng.
Nghiệp vụ hợp đồng gồm tạo, xem, gia hạn và kết thúc. Có thể ghi nhận kết thúc trước hạn, nhưng không xây dựng quy trình xử lý tranh chấp pháp lý phức tạp.
Hợp đồng hết hạn không được tự động gia hạn. 
Không triển khai ký số, phê duyệt hợp đồng điện tử hay quản lý tài liệu pháp lý phức tạp.
Tiền cọc: Chỉ lưu số tiền cọc thỏa thuận như một thuộc tính tùy chọn của hợp đồng. Không xây dựng nghiệp vụ thu cọc, hoàn cọc, khấu trừ, đối soát hoặc quản lý giao dịch tiền cọc. Billing Service không tham gia xử lý tiền cọc.
2.5. Điện nước và IoT giả lập
Mỗi phòng có một đồng hồ điện và một đồng hồ nước giả lập.
Simulator tạo chỉ số tích lũy tương tự đồng hồ thực tế, gửi qua MQTT đến RabbitMQ, sau đó được Metering Service tiếp nhận và xử lý.
Chu kỳ gửi dữ liệu mặc định là 5 phút. Có chế độ tăng tốc thời gian mô phỏng để tạo dữ liệu nhiều ngày hoặc nhiều tháng phục vụ demo.
Hệ thống lưu lịch sử đo, phát hiện dữ liệu trùng, dữ liệu đến trễ, chỉ số giảm bất thường và mất kết nối.
Tại mốc bắt đầu/kết thúc hợp đồng có hiệu lực, Metering lập mốc chốt chỉ số; không có quy trình bàn giao phòng độc lập.
Cuối kỳ, Metering Service xác nhận chỉ số đầu và cuối kỳ để tính mức tiêu thụ. Nếu thiếu dữ liệu, chủ trọ được phép nhập và xác nhận thủ công.
Chỉ số đã dùng để phát hành hóa đơn không được tự động thay đổi do dữ liệu đến muộn.
Không sử dụng phần cứng IoT thật. Không cần mô phỏng lỗi hỏng cảm biến vật lý hay thay thiết bị.
2.6. Hóa đơn và thanh toán
Kỳ hóa đơn thông thường tính theo tháng dương lịch, sử dụng múi giờ Việt Nam.
Đề xuất phát hành hóa đơn ngày 1 tháng tiếp theo, hạn thanh toán hết ngày 5.
Hóa đơn gồm tiền phòng, tiền điện, tiền nước và phí dịch vụ đã thỏa thuận nếu có.
Tiền phòng trong tháng không trọn kỳ được tính theo số ngày thuê thực tế.
Mỗi hợp đồng có tối đa một hóa đơn định kỳ hợp lệ cho mỗi tháng. Có thể phát sinh hóa đơn quyết toán cuối kỳ khi trả phòng, nhưng tuyệt đối không tính trùng khoản đã lập.
Hóa đơn chỉ được phát hành khi dữ liệu cần thiết đã được xác nhận.
Người thuê thanh toán trực tuyến bằng MoMo Sandbox qua liên kết email.
Mỗi hóa đơn chỉ được thanh toán toàn bộ một lần. Không hỗ trợ thanh toán một phần.
Nếu thanh toán thất bại, người thuê có thể thử lại. Nếu giao dịch đang chờ xác minh, không tạo giao dịch mới có nguy cơ thu tiền trùng.
Hệ thống phải chống callback lặp, xử lý phản hồi chậm và đối soát giao dịch chưa rõ trạng thái.
Hóa đơn quá hạn vẫn được phép thanh toán. Hệ thống gửi email nhắc nợ, không tự động phạt hoặc chấm dứt hợp đồng.
Hóa đơn đã thanh toán không được sửa trực tiếp số tiền. Sai sót được xử lý bằng quy trình điều chỉnh riêng.
2.7. Email và liên kết thanh toán
Notification Service gửi email khi phát hành hóa đơn, nhắc hạn, quá hạn và xác nhận thanh toán thành công.
Người thuê có thể mở liên kết để xem hóa đơn và thanh toán mà không cần đăng nhập.
Liên kết được bảo vệ bằng token ngẫu nhiên, có thời hạn và có thể thu hồi.
Email gửi lỗi không được làm mất hóa đơn hoặc thay đổi kết quả thanh toán.
Không triển khai SMS hoặc website dành riêng cho người thuê.
3. KIẾN TRÚC MICROSERVICES
Hệ thống được thiết kế theo Microservices Architecture kết hợp REST API và Event-Driven Architecture.
Chốt 5 microservices nghiệp vụ, không tăng thêm nếu chưa có lý do rõ ràng.
3.1. Room Service
Quản lý khu trọ, dãy, tầng, phòng, giá niêm yết và trạng thái phòng.
Cung cấp thông tin phòng cho Tenant Service.
Phát sự kiện RoomCreated khi phòng được tạo.
Nhận ContractStarted/ContractEnded từ Tenant, cập nhật chiếm dụng theo effective_at và chống event trùng hoặc đến sai thứ tự.
Trạng thái phòng ở Room là dữ liệu phục vụ quản lý và hiển thị; nguồn kiểm soát hợp đồng chồng lấn nằm ở Tenant Service.
3.2. Tenant Service
Quản lý hồ sơ người thuê, hợp đồng và lịch sử thuê.
Kiểm tra thông tin phòng thông qua Room Service khi lập hợp đồng.
Sở hữu thời gian hiệu lực hợp đồng và ràng buộc không chồng lấn hợp đồng trên cùng phòng.
Quản lý giá thuê và điều khoản điện nước có hiệu lực theo thời gian.
Phát ContractStarted, ContractEnded và ContractExpiring. Không sử dụng RoomOccupied hoặc RoomVacated.
Không sử dụng Saga cho việc lập hợp đồng. Áp dụng transaction và ràng buộc dữ liệu cục bộ để bảo đảm tính hợp lệ.
3.3. Metering Service
Quản lý đồng hồ giả lập, dữ liệu điện nước và chỉ số chốt theo kỳ.
Tự tạo hai đồng hồ giả lập khi nhận sự kiện RoomCreated.
Tiếp nhận dữ liệu IoT từ RabbitMQ, kiểm tra tính hợp lệ, chống trùng và ghi nhận lịch sử.
Cung cấp chỉ số đã chốt cho Billing Service.
Không quyết định số tiền hóa đơn.
3.4. Billing Service
Quản lý hóa đơn, công nợ, trạng thái thanh toán và tích hợp MoMo Sandbox.
Điều phối tác vụ lập hóa đơn theo kỳ.
Lấy điều khoản hợp đồng từ Tenant Service và dữ liệu chốt điện nước từ Metering Service.
Lưu snapshot giá và lượng tiêu thụ trong hóa đơn để dữ liệu lịch sử không bị thay đổi khi thông tin gốc thay đổi.
Phát sự kiện InvoiceIssued, InvoiceReminderRequested và PaymentSucceeded.
Billing là nguồn dữ liệu chính thức quyết định trạng thái hóa đơn và thanh toán.
3.5. Notification Service
Nhận các sự kiện liên quan đến hợp đồng, hóa đơn và thanh toán.
Tạo yêu cầu gửi email, xử lý lỗi, retry và ghi nhận trạng thái gửi.
Không sở hữu dữ liệu hóa đơn hay quyết định công nợ.
Đối với email nhắc nợ, phải xác minh trạng thái hóa đơn còn hiệu lực trước khi gửi để hạn chế nhắc nhầm người đã thanh toán.


---

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


---

# DATABASE DESIGN V3 — cập nhật thực thi V3.1

12.1. Nguyên tắc thiết kế
Hệ thống sử dụng PostgreSQL, gồm 6 database logic chạy trên một PostgreSQL instance: room_db, tenant_db, metering_db, billing_db, notification_db và auth_db.
Năm database đầu thuộc năm microservices nghiệp vụ. auth_db thuộc FastAPI Auth, thành phần xác thực hỗ trợ Nginx API Gateway.
Mỗi service chỉ được truy cập database do mình sở hữu. Các database không truy vấn trực tiếp lẫn nhau, không sử dụng Foreign Key xuyên database. Thông tin liên service được trao đổi thông qua REST API hoặc RabbitMQ.
Quy ước dữ liệu:
Khóa chính sử dụng UUID, ngoại trừ meter_readings dùng khóa chính kết hợp.
Tiền VNĐ sử dụng BIGINT; đơn giá cần độ chính xác thập phân sử dụng NUMERIC(18,4); chỉ số điện nước sử dụng NUMERIC(16,3).
Ngày nghiệp vụ dùng DATE. Thời điểm sự kiện dùng TIMESTAMPTZ, thống nhất lưu thời điểm theo UTC và xác định kỳ thanh toán theo Asia/Ho_Chi_Minh.
Các trạng thái dùng VARCHAR kết hợp CHECK, không bắt buộc sử dụng PostgreSQL native ENUM.
Dữ liệu ưu tiên chuẩn hóa 3NF. Những snapshot phục vụ lịch sử hóa đơn được lưu lặp có chủ đích.
Các bảng nghiệp vụ có created_at và updated_at khi thích hợp. Bảng lịch sử chỉ ghi thêm có thể không cần updated_at.
Chỉ sử dụng Foreign Key giữa các bảng trong cùng database. Các trường liên kết sang service khác là tham chiếu logic.

13. ROOM DATABASE – room_db
Số bảng: 6
13.1. properties
Mục đích: Quản lý các khu trọ.
Thuộc tính: id UUID PK; name VARCHAR; address TEXT; description TEXT nullable; status VARCHAR (ACTIVE/INACTIVE); created_at TIMESTAMPTZ; updated_at TIMESTAMPTZ.
Quan hệ: Một property có nhiều building.
13.2. buildings
Mục đích: Quản lý các dãy nhà trong khu trọ.
Thuộc tính: id UUID PK; property_id UUID FK → properties; name VARCHAR; status VARCHAR (ACTIVE/INACTIVE); created_at; updated_at.
Ràng buộc: UNIQUE(property_id, name).
Quan hệ: Một building thuộc một property và có nhiều floor.
13.3. floors
Mục đích: Quản lý tầng của từng dãy.
Thuộc tính: id UUID PK; building_id UUID FK → buildings; floor_number INTEGER; name VARCHAR nullable; status VARCHAR (ACTIVE/INACTIVE); created_at; updated_at.
Ràng buộc: UNIQUE(building_id, floor_number).
Quan hệ: Một floor có nhiều room.
13.4. rooms
Mục đích: Quản lý thông tin phòng và trạng thái sử dụng.
Thuộc tính: id UUID PK; property_id UUID FK → properties; floor_id UUID FK → floors; room_code VARCHAR; area_m2 NUMERIC(8,2); listed_rent BIGINT; status VARCHAR (ACTIVE/INACTIVE); occupancy_contract_id UUID nullable (logic → Tenant); occupancy_updated_at TIMESTAMPTZ nullable; created_at; updated_at.
Ràng buộc: UNIQUE(property_id, room_code); area_m2 > 0; listed_rent >= 0.
Phải bảo đảm property_id khớp với khu trọ thực sự chứa floor_id.
Trạng thái hiển thị Trống/Đang thuê được suy ra từ trạng thái hoạt động và thông tin hợp đồng hiện hành.
Room nhận ContractStarted và ContractEnded từ Tenant. Chỉ cập nhật trạng thái với sự kiện hợp lệ, không cho sự kiện cũ ghi đè dữ liệu mới. ContractEnded chỉ xóa thông tin chiếm dụng nếu đúng hợp đồng tương ứng.
13.5. outbox_events
Mục đích: Lưu sự kiện Room trước khi phát lên RabbitMQ.
Thuộc tính: id UUID PK; aggregate_type VARCHAR; aggregate_id UUID; event_type VARCHAR; event_version INTEGER; payload JSONB; correlation_id UUID nullable; dedupe_key VARCHAR nullable UNIQUE; created_at; published_at TIMESTAMPTZ nullable; attempts INTEGER; last_error TEXT nullable.
Sự kiện: RoomCreated.
13.6. processed_events
Mục đích: Chống xử lý lặp sự kiện nhận từ RabbitMQ.
Thuộc tính: event_id UUID PK; event_type VARCHAR; processed_at TIMESTAMPTZ.
Sự kiện nhận: ContractStarted, ContractEnded.

14. TENANT DATABASE – tenant_db
Số bảng: 5
14.1. tenants
Mục đích: Quản lý hồ sơ người thuê.
Thuộc tính: id UUID PK; full_name VARCHAR; phone VARCHAR nullable; email VARCHAR nullable; note TEXT nullable; created_at; updated_at.
Email bắt buộc đối với người đại diện hợp đồng sử dụng hình thức nhận hóa đơn qua email.
Không lưu CCCD hoặc thông tin nhạy cảm không cần thiết.
14.2. contracts
Mục đích: Quản lý quan hệ thuê phòng.
Thuộc tính: id UUID PK; contract_code VARCHAR UNIQUE; room_id UUID (logic → Room); room_code_snapshot VARCHAR; representative_tenant_id UUID FK → tenants; start_date DATE; end_date DATE; actual_end_date DATE nullable; status VARCHAR; deposit_amount BIGINT nullable; end_reason TEXT nullable; created_at; updated_at.
Trạng thái: DRAFT, SCHEDULED, ACTIVE, EXPIRED_PENDING, ENDED, CANCELLED.
deposit_amount chỉ lưu số tiền cọc thỏa thuận. Không phát sinh nghiệp vụ quản lý giao dịch tiền cọc.
Ràng buộc: Ngày kết thúc hợp lệ so với ngày bắt đầu. Không cho phép hai hợp đồng cùng phòng có thời gian chiếm dụng hiệu lực chồng lấn.
Dùng PostgreSQL EXCLUDE constraint trên khoảng thời gian hợp đồng đối với các trạng thái cần kiểm soát.
Ngày kết thúc trên giao diện được hiểu là ngày thuê cuối cùng, còn range kỹ thuật dùng quy ước [start, end) sau khi chuyển đổi mốc cuối phù hợp.
EXPIRED_PENDING tiếp tục ngăn tạo hợp đồng mới có thời gian chiếm dụng trùng cho đến khi chủ trọ xử lý.
14.3. contract_terms
Mục đích: Lưu điều khoản và lịch sử thay đổi giá.
Thuộc tính: id UUID PK; contract_id UUID FK → contracts; effective_from DATE; effective_to DATE nullable; monthly_rent BIGINT; electricity_unit_price BIGINT; water_unit_price BIGINT; monthly_service_fee BIGINT mặc định 0; created_at.
Ràng buộc: Các phiên bản điều khoản trong cùng hợp đồng không được chồng lấn thời gian hiệu lực.
effective_to là mốc bắt đầu hết hiệu lực, không bao gồm ngày đó.
Khi đổi giá hoặc gia hạn, tạo phiên bản điều khoản mới thay vì ghi đè giá cũ.
Thay đổi giá thông thường có hiệu lực từ kỳ tháng tiếp theo.
14.4. contract_events
Mục đích: Lưu lịch sử thay đổi hợp đồng.
Thuộc tính: id UUID PK; contract_id UUID FK → contracts; event_type VARCHAR; occurred_at TIMESTAMPTZ; actor_id UUID nullable (logic → Auth); reason TEXT nullable; details JSONB; created_at.
Loại sự kiện lịch sử: CREATED, CONFIRMED, STARTED, EXTENDED, TERMINATION_RECORDED, ENDED, CANCELLED.
Lưu dữ liệu trước và sau khi thay đổi vào details khi cần phục vụ kiểm tra.
Đây là bảng lịch sử nội bộ, khác với các sự kiện được phát lên RabbitMQ.
14.5. outbox_events
Sử dụng cấu trúc outbox thống nhất như Room Service.
Sự kiện phát: ContractStarted, ContractEnded, ContractExpiring.
Event phải chứa room_id, contract_id, thời điểm hiệu lực và những thông tin cần thiết cho consumer.

15. METERING DATABASE – metering_db
Số bảng: 5
15.1. meters
Mục đích: Quản lý đồng hồ điện nước giả lập.
Thuộc tính: id UUID PK; room_id UUID (logic → Room); meter_code VARCHAR UNIQUE; meter_type VARCHAR (ELECTRICITY/WATER); unit VARCHAR (KWH/M3); initial_reading NUMERIC(16,3); status VARCHAR (ACTIVE/INACTIVE); last_received_at TIMESTAMPTZ nullable; created_at; updated_at.
Ràng buộc: UNIQUE(room_id, meter_type).
Mỗi phòng có một đồng hồ điện và một đồng hồ nước.
Simulator gọi REST nội bộ Metering để lấy danh sách đồng hồ cần mô phỏng.
15.2. meter_readings
Mục đích: Lưu dữ liệu đo nhận từ MQTT.
Thuộc tính: meter_id UUID FK → meters; measured_at TIMESTAMPTZ; reading_value NUMERIC(16,3); received_at TIMESTAMPTZ; validation_status VARCHAR (VALID/SUSPECT/REJECTED); anomaly_reason TEXT nullable.
Khóa chính kết hợp: (meter_id, measured_at).
Không lưu trùng phép đo có cùng đồng hồ và thời điểm.
Nếu bản ghi trùng khóa nhưng khác chỉ số, không tự ghi đè mà ghi nhận cảnh báo.
Chỉ số giảm bất thường được phát hiện dựa trên thứ tự thời điểm đo, không phải thứ tự dữ liệu được nhận.
15.3. meter_cutoffs
Mục đích: Lưu chỉ số chốt tại mốc hợp đồng và kỳ hóa đơn.
Thuộc tính: id UUID PK; meter_id UUID FK → meters; contract_id UUID nullable (logic → Tenant); cutoff_type VARCHAR (CONTRACT_START/CONTRACT_END/MONTHLY); cutoff_at TIMESTAMPTZ; reading_value NUMERIC(16,3) nullable; source VARCHAR (AUTOMATIC/MANUAL); source_reading_at TIMESTAMPTZ nullable; manual_reason TEXT nullable; status VARCHAR (PENDING/CONFIRMED/SUPERSEDED); confirmed_at TIMESTAMPTZ nullable; confirmed_by UUID nullable (logic → Auth); supersedes_id UUID nullable FK → meter_cutoffs; created_at.
Ràng buộc: Với mỗi (meter_id, cutoff_at) chỉ có MỘT bản chốt chưa SUPERSEDED, bất kể cutoff_type/contract_id; các mục đích chốt trùng thời điểm dùng lại chính bản chốt này. cutoff_type và contract_id chỉ ghi nguồn gốc/ngữ cảnh tạo bản chốt, không phải khóa xác định một giá trị đo khác. Bản CONFIRMED phải có giá trị chỉ số.
Nếu nhập thủ công, phải có lý do và người xác nhận.
Chỉ số tự động được chọn từ bản ghi VALID gần nhất trước hoặc tại thời điểm chốt trong ngưỡng dung sai.
Ngưỡng đề xuất: 15 phút. Nếu không có dữ liệu hợp lệ thì giữ PENDING để chủ trọ xác nhận thủ công.
Bản chốt đã xác nhận không được sửa trực tiếp giá trị. Khi cần điều chỉnh, tạo phiên bản mới có tham chiếu đến bản cũ.
Nếu bản chốt đã được dùng trong hóa đơn, không được tự động thay thế và thay đổi hóa đơn đã phát hành.
15.4. meter_alerts
Mục đích: Lưu cảnh báo IoT.
Thuộc tính: id UUID PK; meter_id UUID FK → meters; alert_type VARCHAR; status VARCHAR (OPEN/RESOLVED); related_measured_at TIMESTAMPTZ nullable; related_cutoff_id UUID nullable FK → meter_cutoffs; detail JSONB; detected_at TIMESTAMPTZ; resolved_at TIMESTAMPTZ nullable; resolution_note TEXT nullable.
Loại cảnh báo: OFFLINE, READING_DECREASE, LATE_AFTER_CUTOFF, CONFLICTING_DUPLICATE.
Không tạo nhiều cảnh báo OFFLINE đang mở cho cùng một đồng hồ.
Ngưỡng mất kết nối đề xuất: 15 phút không nhận dữ liệu mới, tính theo thời gian thực của hệ thống.
15.5. processed_events
Thuộc tính: event_id UUID PK; event_type VARCHAR; processed_at TIMESTAMPTZ.
Sự kiện nhận: RoomCreated, ContractStarted, ContractEnded.
Đánh dấu đã xử lý trong cùng transaction với thay đổi nghiệp vụ để chống xử lý trùng.

16. BILLING DATABASE – billing_db
Số bảng: 8
16.1. invoices
Mục đích: Quản lý hóa đơn.
Thuộc tính: id UUID PK; invoice_code VARCHAR UNIQUE; contract_id UUID (logic → Tenant); room_id UUID (logic → Room); invoice_type VARCHAR (PERIODIC/FINAL); billing_month DATE nullable; period_start DATE; period_end DATE; status VARCHAR (DRAFT/ISSUED/PAID/VOID); blocked_reason TEXT nullable; revision INTEGER; replaces_invoice_id UUID nullable FK → invoices; void_reason TEXT nullable; total_amount BIGINT; due_date DATE; issued_at TIMESTAMPTZ nullable; paid_at TIMESTAMPTZ nullable; voided_at TIMESTAMPTZ nullable; tenant_name_snapshot VARCHAR; tenant_email_snapshot VARCHAR; room_code_snapshot VARCHAR; created_at; updated_at.
Ràng buộc: Mỗi hợp đồng có tối đa một hóa đơn PERIODIC chưa hủy cho một kỳ tháng và tối đa một hóa đơn FINAL chưa hủy.
Không cho các hóa đơn còn hiệu lực tính trùng cùng khoảng thời gian hoặc cùng khoản phải thu.
Hóa đơn DRAFT có thể có blocked_reason khi thiếu thông tin hợp đồng hoặc chỉ số điện nước.
Hóa đơn ISSUED có thể được thay thế trước thanh toán. Hóa đơn PAID không được sửa trực tiếp.
Quá hạn được suy ra từ trạng thái ISSUED và due_date, không lưu thành trạng thái độc lập.
Chỉ mục quan trọng: (contract_id, billing_month) và (status, due_date).
16.2. invoice_items
Mục đích: Lưu chi tiết các khoản tính tiền.
Thuộc tính: id UUID PK; invoice_id UUID FK → invoices; item_type VARCHAR (RENT/ELECTRICITY/WATER/SERVICE); description VARCHAR; quantity NUMERIC(16,3); unit VARCHAR; unit_price NUMERIC(18,4); amount BIGINT; period_start DATE nullable; period_end DATE nullable; meter_start_value NUMERIC(16,3) nullable; meter_end_value NUMERIC(16,3) nullable; source_term_id UUID nullable (logic → Tenant); source_cutoff_start_id UUID nullable (logic → Metering); source_cutoff_end_id UUID nullable (logic → Metering).
Ràng buộc: Số lượng và đơn giá thông thường không âm. Mỗi dòng tính tiền được làm tròn đến đơn vị đồng theo quy tắc thống nhất.
Tổng tiền hóa đơn phải bằng tổng tiền các dòng chi tiết.
Lưu snapshot đơn giá và chỉ số để hóa đơn cũ không thay đổi khi hợp đồng hoặc dữ liệu IoT được cập nhật.
16.3. invoice_adjustments
Mục đích: Ghi nhận yêu cầu điều chỉnh hóa đơn đã thanh toán.
Thuộc tính: id UUID PK; invoice_id UUID FK → invoices; reason TEXT; amount_delta BIGINT (có thể âm); status VARCHAR (OPEN/RESOLVED/REJECTED); resolution_note TEXT nullable; created_by UUID nullable (logic → Auth); created_at; resolved_at TIMESTAMPTZ nullable.
Không tự động hoàn tiền hoặc sửa hóa đơn PAID. Chỉ ghi nhận và theo dõi yêu cầu xử lý sai lệch.
16.4. payment_attempts
Mục đích: Quản lý các lần thử thanh toán qua MoMo.
Thuộc tính: id UUID PK; invoice_id UUID FK → invoices; provider VARCHAR; order_id VARCHAR UNIQUE; request_id VARCHAR UNIQUE; provider_transaction_id VARCHAR nullable; amount BIGINT; status VARCHAR (PENDING/SUCCESS/FAILED/EXPIRED); pay_url TEXT nullable; expires_at TIMESTAMPTZ nullable; result_code VARCHAR nullable; confirmed_at TIMESTAMPTZ nullable; last_reconciled_at TIMESTAMPTZ nullable; created_at; updated_at.
Ràng buộc: Mỗi hóa đơn chỉ có tối đa một payment attempt SUCCESS.
Không cho nhiều payment attempt PENDING độc lập cho cùng hóa đơn.
Callback trùng không được ghi nhận thanh toán hai lần.
Giao dịch PENDING cần được đối soát với MoMo trước khi xác định kết quả cuối cùng. Kết quả thành công đến muộn không được tự bỏ qua, mà phải đối soát và xử lý nhất quán.
16.5. payment_webhook_receipts
Mục đích: Lưu nhật ký callback MoMo.
Thuộc tính: id UUID PK; payment_attempt_id UUID nullable FK → payment_attempts; order_id VARCHAR; payload_fingerprint VARCHAR; signature_valid BOOLEAN; processing_result VARCHAR; received_at TIMESTAMPTZ; processed_at TIMESTAMPTZ nullable.
Kết quả xử lý: PROCESSED, DUPLICATE, INVALID_SIGNATURE, UNKNOWN_ORDER, AMOUNT_MISMATCH và các trường hợp cần đối soát.
Cho phép lưu nhiều lần callback có cùng nội dung để kiểm tra và demo tình huống callback trùng.
Không lưu thông tin bí mật hoặc khóa thanh toán vào nhật ký.
16.6. invoice_access_tokens
Mục đích: Quản lý quyền truy cập hóa đơn không cần đăng nhập.
Thuộc tính: id UUID PK; invoice_id UUID FK → invoices; token_hash VARCHAR UNIQUE; expires_at TIMESTAMPTZ; revoked_at TIMESTAMPTZ nullable; created_at; last_used_at TIMESTAMPTZ nullable.
Token gốc được tạo ngẫu nhiên và chỉ lưu hash trong database.
Khi hóa đơn bị hủy, thay thế hoặc cần thu hồi quyền truy cập, token tương ứng phải bị vô hiệu hóa.
Notification nhận thông tin hóa đơn qua event. Khi chuẩn bị gửi email, Notification sử dụng API nội bộ được xác thực của Billing để lấy liên kết truy cập có thời hạn.
Không ghi token gốc vào log hoặc payload sự kiện RabbitMQ.
16.7. billing_runs
Mục đích: Theo dõi quá trình tạo hóa đơn định kỳ.
Thuộc tính: id UUID PK; billing_month DATE; trigger_type VARCHAR (SCHEDULED/MANUAL); status VARCHAR (RUNNING/COMPLETED/FAILED); started_at TIMESTAMPTZ; finished_at TIMESTAMPTZ nullable; issued_count INTEGER; waiting_count INTEGER; skipped_count INTEGER; failed_count INTEGER.
Cho phép chạy lại job cùng kỳ.
Ràng buộc tại invoices phải bảo đảm không tạo hóa đơn trùng, kể cả khi nhiều replica cùng chạy.
16.8. outbox_events
Sử dụng cấu trúc outbox thống nhất.
Sự kiện phát: InvoiceIssued, InvoiceReminderRequested, PaymentSucceeded.
Phải lưu sự kiện trong cùng transaction với thay đổi nghiệp vụ tương ứng.

17. NOTIFICATION DATABASE – notification_db
Số bảng: 1
17.1. email_jobs
Mục đích: Quản lý công việc gửi email và xử lý retry.
Thuộc tính: id UUID PK; source_event_id UUID UNIQUE; email_type VARCHAR (INVOICE/REMINDER/PAYMENT_RECEIPT/CONTRACT_EXPIRING); invoice_id UUID nullable (logic → Billing); recipient_email VARCHAR; subject VARCHAR; template_data JSONB; status VARCHAR (PENDING/SENDING/SENT/FAILED/SKIPPED); attempt_count INTEGER; next_attempt_at TIMESTAMPTZ nullable; locked_until TIMESTAMPTZ nullable; sent_at TIMESTAMPTZ nullable; last_error TEXT nullable; provider_message_id VARCHAR nullable; created_at; updated_at.
Ràng buộc: Không tạo nhiều email job từ cùng một event trong mô hình một event tương ứng một email.
Worker sử dụng cơ chế khóa công việc để nhiều replica không đồng thời xử lý cùng job.
Nếu gửi thất bại, thực hiện retry có giới hạn. Sau khi hết số lần thử, ghi FAILED.
Đối với email nhắc nợ, Notification phải kiểm tra trạng thái hiện hành từ Billing ngay trước khi gửi. Nếu hóa đơn đã thanh toán hoặc Billing không phản hồi, không gửi nhắc nợ; xử lý SKIPPED hoặc retry tương ứng.
Khi nhận PaymentSucceeded, có thể đánh dấu các reminder đang chờ của hóa đơn tương ứng thành SKIPPED.
Email cảnh báo hợp đồng hết hạn được gửi về email chủ trọ cấu hình bằng OWNER_EMAIL.
template_data chỉ lưu thông tin cần gửi, không lưu lâu dài liên kết thanh toán chứa token bí mật.

18. AUTH DATABASE – auth_db
Số bảng: 1
18.1. users
Mục đích: Quản lý tài khoản đăng nhập chủ trọ tại FastAPI Auth.
Thuộc tính: id UUID PK; email VARCHAR UNIQUE; password_hash VARCHAR; full_name VARCHAR; is_active BOOLEAN; last_login_at TIMESTAMPTZ nullable; created_at; updated_at.
Email được chuẩn hóa trước khi lưu và phải duy nhất không phân biệt chữ hoa/thường.
Mật khẩu chỉ lưu dưới dạng hash an toàn.
Phiên bản đầu tiên chỉ cần tài khoản chủ trọ, chưa xây dựng hệ thống vai trò phức tạp hoặc tài khoản người thuê.

19. RÀNG BUỘC VÀ NGUYÊN TẮC TOÀN HỆ THỐNG
19.1. Referential Integrity
Sử dụng Foreign Key thực sự cho các quan hệ trong cùng database.
Các trường tham chiếu sang database khác chỉ lưu UUID và phải được xác minh thông qua service sở hữu dữ liệu.
Không dùng cross-database join cho logic nghiệp vụ.
19.2. Database Constraints
Sử dụng UNIQUE để chống trùng mã phòng, mã hợp đồng, hóa đơn theo kỳ, mã giao dịch và dữ liệu đo.
Sử dụng CHECK để kiểm soát số tiền, chỉ số, trạng thái và các điều kiện dữ liệu cơ bản.
Sử dụng PostgreSQL EXCLUDE constraint với range types để ngăn khoảng thời gian hợp đồng và phiên bản điều khoản chồng lấn.
Dùng partial unique index để bảo đảm hóa đơn hợp lệ và thanh toán thành công không bị tạo trùng.
19.3. Transaction và Idempotency
Mọi thay đổi cần tính nguyên tử trong một service phải sử dụng transaction.
Outbox event phải được ghi cùng transaction với dữ liệu nghiệp vụ.
Processed event phải được ghi cùng transaction với kết quả consumer xử lý.
RabbitMQ có thể gửi lại message, vì vậy mỗi consumer phải xử lý lặp an toàn.
Không giả định hệ thống phân tán có exactly-once delivery.
19.4. Data History
Không ghi đè lịch sử hợp đồng, điều khoản giá và hóa đơn đã thanh toán.
Hóa đơn lưu snapshot của những dữ liệu được sử dụng để tính tiền.
Chỉ số điện nước đã dùng để lập hóa đơn không được tự thay đổi khi có dữ liệu mới đến muộn.
Các thay đổi quan trọng phải có lịch sử và khả năng truy vết.
19.5. ORM và Migration
Sử dụng SQLAlchemy 2.x để định nghĩa models, relationships và truy vấn dữ liệu.
Sử dụng Alembic để quản lý database migrations.
Mỗi microservice quản lý ORM models và migrations của database mình.
Không dùng một bộ migration chung cho cả năm service.
Các migration sinh tự động phải được kiểm tra, đặc biệt với partial indexes, exclusion constraints và những ràng buộc PostgreSQL đặc thù.

20. TỔNG KẾT DATABASE DESIGN V3
room_db: 6 bảng.
tenant_db: 5 bảng.
metering_db: 5 bảng.
billing_db: 8 bảng.
notification_db: 1 bảng.
auth_db: 1 bảng.
Tổng cộng: 26 bảng trong 6 database logic, chạy trên một PostgreSQL instance.
ORM và migration ban đầu của 26 bảng đã được chạy thành công. Các bản vá ràng buộc phát hiện sau nghiệm thu được bổ sung bằng migration mới, không sửa lịch sử V3 đã chạy.
Những việc tiếp theo: Kiểm chứng ràng buộc dữ liệu bằng integration tests, hoàn thiện các API, worker, scheduler và xử lý nghiệp vụ; đồng bộ đặc tả OpenAPI/AsyncAPI. API/Event Contracts; kiểm thử tính toàn vẹn dữ liệu và khả năng chống xử lý trùng.
Không tự ý bổ sung bảng, thay đổi ranh giới service hoặc thay đổi bộ công nghệ khi chưa có lý do nghiệp vụ hay kỹ thuật rõ ràng.
## Ghi chú ràng buộc triển khai
- Room: phòng phải thuộc chính khu trọ chứa floor. Bản vá Room V3.1 kiểm tra điều này bằng trigger ở DB, đồng thời cần kiểm tra tại service khi viết API.
- Database isolation: PostgreSQL PUBLIC có quyền CONNECT mặc định; cần thu hồi khỏi 6 database, kể cả trên volume đã tồn tại.
- Metering: bản vá V3.1 thay index theo cutoff_type/contract_id thành một unique index theo (meter_id, cutoff_at) cho các bản chưa SUPERSEDED. Trước khi migration chạy, phải giải quyết mọi bản chốt còn hiệu lực bị trùng thời điểm.


---

# 21. API & EVENT CONTRACTS V1.1
Trạng thái: Hợp đồng thiết kế đã chốt; hiện mới có ORM, migration và hạ tầng local, chưa triển khai API/nghiệp vụ.
Tiêu chuẩn: OpenAPI 3.1 cho REST API; AsyncAPI 3.0 cho RabbitMQ và MQTT.
Database: Database Design V3, gồm 26 bảng trong 6 database logic.
Phạm vi: 5 microservices nghiệp vụ, FastAPI Auth và Nginx API Gateway.
Nguyên tắc: Không thay đổi kiến trúc đã thống nhất. Mỗi service chỉ truy cập database mình sở hữu. Giao tiếp giữa các service thông qua REST hoặc RabbitMQ.

21.1. QUY ƯỚC TOÀN HỆ THỐNG
21.1.1. Phân loại API
Admin API: /api/v1/...
Dành cho chủ trọ, yêu cầu JWT, truy cập thông qua API Gateway.
Public API: /public/v1/...
Dành cho người thuê xem và thanh toán hóa đơn bằng liên kết chứa token.
Internal API: /internal/v1/...
Dành cho service-to-service, sử dụng X-Service-Token, không công khai ra Internet.
Webhook: /webhooks/momo/ipn
Nhận kết quả thanh toán từ MoMo, bắt buộc xác minh chữ ký.
Health: /health
Kiểm tra tiến trình còn hoạt động, không phụ thuộc việc PostgreSQL hoặc RabbitMQ có đang sẵn sàng hay không.
Readiness: /ready
Kiểm tra khả năng phục vụ dựa trên các dependency cần thiết.
21.1.2. Định dạng dữ liệu
Request/Response: JSON.
Khóa định danh: UUID.
Thời điểm: ISO 8601 có timezone.
Múi giờ nghiệp vụ: Asia/Ho_Chi_Minh.
Tiền VNĐ: Số nguyên, backend sử dụng Decimal khi tính toán.
Chỉ số điện nước: Decimal, không sử dụng float để tính tiền.
API phân trang: Trả items và meta, trong đó meta chứa page, page_size, total.
API billable: Hỗ trợ phân trang cursor để Billing quét nhiều hợp đồng.
21.1.3. Quy ước thời gian
contracts.start_date: Ngày bắt đầu thuê, được tính vào thời gian thuê.
contracts.end_date: Ngày kết thúc theo hợp đồng, được tính vào thời gian thuê.
contracts.actual_end_date: Ngày kết thúc thực tế đã xác nhận, cũng được tính vào thời gian thuê.
invoices.period_start: Ngày bắt đầu kỳ tính tiền, bao gồm.
invoices.period_end: Mốc kết thúc kỳ tính tiền, không bao gồm.
API period_end_exclusive: Cùng ý nghĩa với invoices.period_end.
Ví dụ kỳ tháng 11/2026:
[2026-11-01, 2026-12-01)
Mốc chốt đồng hồ cuối kỳ:
2026-12-01T00:00:00+07:00
Nếu hợp đồng kết thúc ngày 30/11/2026:
ContractEnded.effective_at = 2026-12-01T00:00:00+07:00
Không tính thêm tiền sau ngày kết thúc hợp đồng nếu chủ trọ chưa gia hạn.
21.1.4. Bảo mật
Admin: JWT.
Internal: Service token, chỉ sử dụng trong mạng nội bộ.
Public invoice: Token ngẫu nhiên, chỉ lưu hash trong Billing.
MoMo: Xác minh HMAC và đối chiếu thông tin thanh toán.
Rate limiting: Áp dụng cho Public API.
Logging: Không ghi token gốc, URL bí mật, mật khẩu hoặc khóa thanh toán.
HTTP headers: Referrer-Policy: no-referrer và Cache-Control: no-store cho trang hóa đơn.
Correlation: Truyền X-Correlation-ID qua REST và correlation_id qua RabbitMQ.
Error response: Thống nhất các trường code, message, correlation_id, details.
21.1.5. Quy ước HTTP
200: Thành công.
201: Tạo tài nguyên thành công.
202: Đã tiếp nhận công việc chạy nền.
400: Request không hợp lệ.
401: Chưa xác thực.
403: Không đủ quyền.
404: Không tìm thấy tài nguyên.
409: Xung đột nghiệp vụ hoặc trạng thái.
422: Dữ liệu không thỏa mãn ràng buộc.
503: Service phụ thuộc không sẵn sàng.
Các POST quan trọng phải được bảo vệ bằng unique constraints, idempotency hoặc kiểm tra trạng thái để tránh tạo dữ liệu trùng khi client retry.

21.2. REST API CONTRACTS
21.2.1. AUTH — 2 ENDPOINTS
POST /api/v1/auth/login
Mục đích: Đăng nhập quản trị.
GET /api/v1/auth/me
Mục đích: Xem thông tin tài khoản hiện tại.
21.2.2. ROOM SERVICE — 14 ENDPOINTS
GET /api/v1/properties
Mục đích: Danh sách khu trọ.
POST /api/v1/properties
Mục đích: Tạo khu trọ.
GET /api/v1/properties/{property_id}
Mục đích: Chi tiết khu trọ.
PATCH /api/v1/properties/{property_id}
Mục đích: Cập nhật khu trọ.
GET /api/v1/properties/{property_id}/buildings
Mục đích: Danh sách dãy nhà.
POST /api/v1/properties/{property_id}/buildings
Mục đích: Tạo dãy nhà.
GET /api/v1/buildings/{building_id}/floors
Mục đích: Danh sách tầng.
POST /api/v1/buildings/{building_id}/floors
Mục đích: Tạo tầng.
POST /api/v1/floors/{floor_id}/rooms/bulk
Mục đích: Tạo hàng loạt phòng.
GET /api/v1/rooms
Mục đích: Danh sách phòng.
GET /api/v1/rooms/{room_id}
Mục đích: Chi tiết phòng.
PATCH /api/v1/rooms/{room_id}
Mục đích: Cập nhật thông tin phòng.
PATCH /api/v1/buildings/{building_id}
Mục đích: Cập nhật tên hoặc trạng thái dãy nhà.
PATCH /api/v1/floors/{floor_id}
Mục đích: Cập nhật tên hoặc trạng thái tầng.
21.2.3. TENANT SERVICE — 17 ENDPOINTS
GET /api/v1/tenants
Mục đích: Danh sách người thuê.
POST /api/v1/tenants
Mục đích: Tạo hồ sơ người thuê.
GET /api/v1/tenants/{tenant_id}
Mục đích: Chi tiết người thuê.
PATCH /api/v1/tenants/{tenant_id}
Mục đích: Cập nhật người thuê.
GET /api/v1/contracts
Mục đích: Danh sách hợp đồng.
POST /api/v1/contracts
Mục đích: Tạo hợp đồng DRAFT.
GET /api/v1/contracts/expiring
Mục đích: Danh sách hợp đồng gần hết hạn.
GET /api/v1/contracts/{contract_id}
Mục đích: Chi tiết hợp đồng.
PATCH /api/v1/contracts/{contract_id}
Mục đích: Chỉnh sửa hợp đồng DRAFT.
GET /api/v1/contracts/{contract_id}/terms
Mục đích: Danh sách phiên bản điều khoản.
POST /api/v1/contracts/{contract_id}/terms
Mục đích: Thêm phiên bản điều khoản mới.
GET /api/v1/contracts/{contract_id}/events
Mục đích: Lịch sử thay đổi hợp đồng.
POST /api/v1/contracts/{contract_id}/confirm
Mục đích: Xác nhận hợp đồng.
POST /api/v1/contracts/{contract_id}/renew
Mục đích: Gia hạn hợp đồng.
POST /api/v1/contracts/{contract_id}/end
Mục đích: Xác nhận kết thúc hợp đồng.
POST /api/v1/contracts/{contract_id}/cancel
Mục đích: Hủy hợp đồng chưa có hiệu lực.
POST /api/v1/jobs/contracts/lifecycle/run
Mục đích: Chạy thủ công job vòng đời hợp đồng để demo.
21.2.4. METERING SERVICE — 8 ENDPOINTS
GET /api/v1/rooms/{room_id}/meters
Mục đích: Danh sách đồng hồ điện nước của phòng.
GET /api/v1/meters/{meter_id}/readings
Mục đích: Lịch sử số đo.
GET /api/v1/meters/{meter_id}/cutoffs
Mục đích: Danh sách mốc chốt.
POST /api/v1/meter-cutoffs/{cutoff_id}/confirm
Mục đích: Xác nhận chỉ số thủ công.
POST /api/v1/meter-cutoffs/{cutoff_id}/corrections
Mục đích: Tạo phiên bản chốt thay thế.
GET /api/v1/meter-alerts
Mục đích: Danh sách cảnh báo IoT.
POST /api/v1/meter-alerts/{alert_id}/resolve
Mục đích: Xác nhận xử lý cảnh báo.
POST /api/v1/jobs/meters/monthly-cutoffs/run
Mục đích: Chạy chốt chỉ số tháng thủ công.
21.2.5. BILLING SERVICE — 14 ENDPOINTS
GET /api/v1/invoices
Mục đích: Danh sách hóa đơn.
GET /api/v1/invoices/{invoice_id}
Mục đích: Chi tiết hóa đơn.
POST /api/v1/invoices/{invoice_id}/issue
Mục đích: Phát hành hóa đơn DRAFT đủ dữ liệu.
POST /api/v1/invoices/{invoice_id}/void
Mục đích: Hủy hóa đơn chưa thanh toán.
POST /api/v1/invoices/{invoice_id}/reissue
Mục đích: Phát hành phiên bản hóa đơn thay thế.
POST /api/v1/invoices/{invoice_id}/reminders
Mục đích: Yêu cầu gửi nhắc nợ.
GET /api/v1/invoices/{invoice_id}/payment-attempts
Mục đích: Danh sách lần thử thanh toán.
GET /api/v1/invoices/{invoice_id}/adjustments
Mục đích: Danh sách yêu cầu điều chỉnh.
POST /api/v1/invoices/{invoice_id}/adjustments
Mục đích: Ghi nhận yêu cầu điều chỉnh.
POST /api/v1/invoice-adjustments/{adjustment_id}/resolve
Mục đích: Đóng yêu cầu điều chỉnh.
GET /api/v1/billing-runs
Mục đích: Lịch sử chạy job lập hóa đơn.
POST /api/v1/billing-runs
Mục đích: Chạy lập hóa đơn theo tháng.
POST /api/v1/final-invoices
Mục đích: Lập hóa đơn quyết toán cho phần chưa tính tiền.
POST /api/v1/jobs/payments/reconcile/run
Mục đích: Đối soát giao dịch MoMo PENDING thủ công.
21.2.6. NOTIFICATION SERVICE — 3 ENDPOINTS
GET /api/v1/email-jobs
Mục đích: Danh sách tác vụ email.
GET /api/v1/email-jobs/{job_id}
Mục đích: Chi tiết tác vụ email.
POST /api/v1/email-jobs/{job_id}/retry
Mục đích: Thử gửi lại email thất bại.
21.2.7. PUBLIC API — 3 ENDPOINTS
GET /public/v1/invoices/{token}
Mục đích: Xem hóa đơn không cần đăng nhập.
POST /public/v1/invoices/{token}/payments/momo
Mục đích: Tạo hoặc sử dụng lại phiên thanh toán MoMo.
POST /webhooks/momo/ipn
Mục đích: Nhận thông báo kết quả thanh toán từ MoMo.
21.2.8. INTERNAL API — ROOM
GET /internal/v1/rooms/{room_id}/validation
Caller: Tenant Service.
Mục đích: Kiểm tra phòng tồn tại, còn hoạt động và thông tin cần thiết trước khi tạo hợp đồng.
21.2.9. INTERNAL API — TENANT
GET /internal/v1/contracts/{contract_id}/billing-context
Caller: Billing Service.
Mục đích: Lấy thông tin hợp đồng, người thuê và phiên bản giá trong kỳ tính tiền.
GET /internal/v1/contracts/billable
Caller: Billing Service.
Mục đích: Liệt kê các hợp đồng giao với kỳ cần lập hóa đơn, hỗ trợ cursor.
21.2.10. INTERNAL API — METERING
GET /internal/v1/meters
Caller: IoT Simulator.
Mục đích: Lấy danh sách đồng hồ đang hoạt động.
GET /internal/v1/rooms/{room_id}/usage
Caller: Billing Service.
Mục đích: Lấy số điện nước tiêu thụ từ hai mốc chốt.
Query: period_start, period_end_exclusive.
Response chứa chỉ số đầu, chỉ số cuối, lượng tiêu thụ và ID các cutoff liên quan.
21.2.11. INTERNAL API — BILLING
GET /internal/v1/invoices/{invoice_id}/reminder-eligibility
Caller: Notification Service.
Mục đích: Kiểm tra hóa đơn còn đủ điều kiện gửi nhắc nợ.
POST /internal/v1/invoices/{invoice_id}/access-links
Caller: Notification Service.
Mục đích: Xin liên kết truy cập hóa đơn có thời hạn.
Chỉ tạo liên kết khi hóa đơn đang ISSUED. Nếu PAID hoặc VOID, trả HTTP 409.
21.2.12. OPERATIONS
GET /health
Mục đích: Liveness.
GET /ready
Mục đích: Readiness.
Tổng số API operations: 70.

21.3. BUSINESS FLOWS
21.3.1. LUỒNG A — TẠO PHÒNG VÀ ĐỒNG HỒ
Bước 1: Chủ trọ tạo khu trọ, dãy nhà và tầng.
Bước 2: Frontend gọi POST /api/v1/floors/{floor_id}/rooms/bulk.
Bước 3: Room Service tạo các phòng và ghi mỗi RoomCreated vào outbox trong cùng transaction.
Bước 4: Outbox worker gửi sự kiện lên RabbitMQ.
Bước 5: Metering nhận RoomCreated, sử dụng processed_events để chống xử lý trùng.
Bước 6: Metering tạo hai đồng hồ ELECTRICITY và WATER cho mỗi phòng.
Bước 7: Simulator gọi Internal Metering API để lấy danh sách đồng hồ ACTIVE.
Bước 8: Simulator gửi dữ liệu đo lên MQTT, mặc định mỗi 5 phút.
Bước 9: Metering nhận dữ liệu qua RabbitMQ MQTT plugin và lưu vào meter_readings.
Ràng buộc: Nếu một phòng bị trùng mã khi tạo hàng loạt thì rollback toàn bộ lô.
Idempotency: Không tạo trùng đồng hồ khi RabbitMQ gửi lại RoomCreated.
21.3.2. LUỒNG B — QUẢN LÝ HỢP ĐỒNG
Tạo hợp đồng: POST /contracts tạo hợp đồng DRAFT cùng điều khoản giá ban đầu.
Xác nhận: POST /confirm kiểm tra phòng hoạt động, email người đại diện và ràng buộc hợp đồng chồng lấn. Hợp đồng chuyển SCHEDULED.
Kích hoạt: Job vòng đời kiểm tra đến start_date. Nếu phòng không có hợp đồng ACTIVE hoặc EXPIRED_PENDING khác, chuyển ACTIVE và phát ContractStarted.
ContractStarted.effective_at: 00:00 ngày start_date, giờ Việt Nam.
Room xử lý: Cập nhật occupancy_contract_id.
Metering xử lý: Tạo cutoff tại effective_at.
Gia hạn: POST /renew thay đổi ngày kết thúc, cập nhật phiên bản điều khoản nếu cần và lưu contract_events.
Quá hạn: Chuyển EXPIRED_PENDING nếu đã quá hạn nhưng chủ trọ chưa xác nhận kết thúc. Không tự giải phóng phòng.
Kết thúc: POST /end yêu cầu actual_end_date nằm trong khoảng [start_date, end_date].
ContractEnded.effective_at: 00:00 ngày sau actual_end_date, giờ Việt Nam.
Nguyên tắc: Không có quy trình bàn giao phòng độc lập. Mốc chốt đồng hồ được xác định từ ngày hiệu lực hợp đồng.
Nếu thiếu số đo hợp lệ, tạo cutoff PENDING để chủ trọ nhập chỉ số thủ công.
Nếu hợp đồng đã quá hạn và cần tính thêm ngày thuê thực tế, chủ trọ phải gia hạn trước khi kết thúc.

**Quy tắc hiệu lực và thứ tự event:**

POST /end ghi nhận actual_end_date nhưng không kết thúc hợp đồng trước thời điểm effective_at. Nếu effective_at còn ở tương lai, hợp đồng giữ ACTIVE; lifecycle job chuyển ENDED và phát ContractEnded khi đến hạn. Nếu mốc đã qua, xử lý ngay.

Room và Metering chỉ áp dụng ContractStarted/ContractEnded khi thời gian hiện tại >= effective_at.

Room lưu occupancy_updated_at theo effective_at, không dùng occurred_at hoặc thời điểm nhận message.

Khi ContractEnded(A) và ContractStarted(B) có cùng effective_at, hợp đồng B phải là trạng thái cuối cùng bất kể thứ tự event. ContractEnded(A) chỉ xóa occupancy nếu occupancy_contract_id = A. ContractStarted(B) được chấp nhận khi effective_at >= occupancy_updated_at. Event cũ không được ghi đè trạng thái mới.

Consumer phải xử lý idempotent. Viết integration test cho cả hai thứ tự: End(A) → Start(B) và Start(B) → End(A).

21.3.3. LUỒNG C — CHỐT CHỈ SỐ VÀ LẬP HÓA ĐƠN
00:00 ngày 1: Metering chốt chỉ số cho tất cả đồng hồ ACTIVE, kể cả phòng trống.
Chọn số đo: Lấy reading VALID gần nhất trước hoặc đúng thời điểm cutoff, trong dung sai 15 phút.
Thiếu dữ liệu: Tạo cutoff PENDING và yêu cầu xác nhận thủ công.
02:00 ngày 1: Billing bắt đầu chạy job lập hóa đơn tháng trước.
Lấy hợp đồng: Billing gọi /internal/v1/contracts/billable.
Lấy giá: Billing gọi /internal/v1/contracts/{contract_id}/billing-context.
Lấy điện nước: Billing gọi /internal/v1/rooms/{room_id}/usage.
Tính tiền phòng: monthly_rent × số ngày thuê thực tế trong tháng / số ngày của tháng.
Tính tiền điện: (chỉ số cuối - chỉ số đầu) × đơn giá điện.
Tính tiền nước: (chỉ số cuối - chỉ số đầu) × đơn giá nước.
Phí dịch vụ: Tính theo số ngày thuê theo quy tắc prorate đã chốt.
Làm tròn: Sử dụng Decimal, làm tròn từng khoản đến đơn vị đồng.
Thiếu dữ liệu: Hóa đơn giữ DRAFT và lưu blocked_reason.
Đủ dữ liệu: Hóa đơn chuyển ISSUED, tạo InvoiceIssued trong outbox cùng transaction.
Hạn thanh toán: Mặc định ngày 5 của tháng phát hành.
Retry: Billing định kỳ quét lại hóa đơn DRAFT bị chặn.
Hóa đơn FINAL: Chỉ bao phủ phần thời gian và các khoản tiền chưa được lập hóa đơn trước đó.
Chống trùng: Không có hai hóa đơn hợp lệ tính trùng cùng thời gian hoặc cùng khoản phải thu.
Với tiền thuê prorate, không áp CHECK cứng rằng invoice_items.amount = quantity × unit_price đã làm tròn để hiển thị, vì có thể gây sai lệch một vài đồng.
21.3.4. LUỒNG D — GỬI EMAIL VÀ NHẮC NỢ
Nguồn sự kiện: InvoiceIssued, InvoiceReminderRequested, PaymentSucceeded, ContractExpiring.
InvoiceIssued: Notification tạo email_job, chống trùng bằng source_event_id.
Tạo liên kết: Notification gọi API nội bộ Billing để lấy access link trước khi gửi.
Lưu token: Billing chỉ lưu hash của token.
Gửi email: Notification sử dụng Brevo SMTP, hoặc Mailpit trong môi trường local.
Nhắc nợ: Billing scheduler chạy hằng ngày và phát InvoiceReminderRequested.
Kiểm tra trước gửi: Notification gọi Billing reminder-eligibility.
Nếu PAID/VOID: Chuyển job sang SKIPPED.
Nếu Billing không phản hồi: Retry, không gửi email khi chưa xác minh.
Khi PaymentSucceeded: Tạo email biên nhận và bỏ qua các reminder đang chờ.
ContractExpiring: Gửi email về OWNER_EMAIL được cấu hình trong environment.
Lỗi gửi: Retry có backoff và giới hạn số lần thử.
21.3.5. LUỒNG E — THANH TOÁN MOMO
Bước 1: Người thuê mở /public/v1/invoices/{token}.
Bước 2: Người thuê chọn thanh toán MoMo.
Bước 3: Billing tạo payment_attempt PENDING trước khi gọi MoMo.
Bước 4: Nếu hóa đơn đã có attempt PENDING, không tạo thêm phiên mới. Trả lại pay_url đã có hoặc trạng thái chờ nếu kết quả chưa rõ.
Bước 5: Billing gọi MoMo Sandbox và lưu thông tin phiên thanh toán.
Bước 6: Người thuê hoàn tất thanh toán trên MoMo.
Bước 7: MoMo gửi IPN đến /webhooks/momo/ipn.
Bước 8: Billing xác minh HMAC, order_id, request_id, amount và kết quả thanh toán.
Bước 9: Billing ghi payment_webhook_receipts.
Bước 10: Nếu hợp lệ, chuyển attempt sang SUCCESS, invoice sang PAID và ghi outbox PaymentSucceeded trong cùng transaction.
Callback trùng: Xử lý idempotent, không chuyển trạng thái hoặc phát sự kiện thành công lần hai.
Timeout khi gọi MoMo: Không tự kết luận FAILED nếu kết quả chưa rõ.
Đối soát: Scheduler kiểm tra các attempt PENDING; admin có thể chạy thủ công qua POST /api/v1/jobs/payments/reconcile/run.
Kết quả đến muộn: Đưa vào đối soát thay vì bỏ qua.
Phạm vi thanh toán: Toàn bộ hóa đơn, không hỗ trợ thanh toán một phần.
Ngoài phạm vi: Hoàn tiền tự động và giao dịch tiền cọc.
21.3.6. LUỒNG F — CHỈNH SỬA VÀ LỊCH SỬ
Hóa đơn chưa thanh toán: Có thể VOID và reissue, miễn không có attempt PENDING chưa được xử lý.
Hóa đơn PAID: Không chỉnh sửa trực tiếp.
Sai sót sau thanh toán: Ghi invoice_adjustments, không hoàn tiền tự động.
Cutoff CONFIRMED: Không sửa trực tiếp giá trị.
Điều chỉnh cutoff: Tạo bản thay thế thông qua supersedes_id.
Cutoff đã dùng lập hóa đơn: Không tự động thay đổi hóa đơn đã phát hành.

21.4. EVENT CONTRACTS — RABBITMQ
21.4.1. Cấu hình chung
Exchange: rental.domain.v1
Exchange type: topic
Durable: true
Event format: JSON
Event version: 1
Delivery: At-least-once.
Outbox: Room, Tenant và Billing ghi sự kiện trong database transaction.
Consumer idempotency: processed_events hoặc unique constraint phù hợp.
21.4.2. Envelope chuẩn
event_id: UUID, định danh sự kiện.
event_type: Tên sự kiện.
event_version: Phiên bản schema.
occurred_at: Thời điểm sự kiện được tạo.
effective_at: Thời điểm có hiệu lực nghiệp vụ, bắt buộc với ContractStarted và ContractEnded.
correlation_id: UUID liên kết các log và thao tác.
aggregate_id: UUID của thực thể nghiệp vụ.
data: Payload nghiệp vụ.
Phân biệt: occurred_at không nhất thiết trùng effective_at.
Không đưa token hóa đơn, mật khẩu hoặc thông tin bí mật vào event payload.
21.4.3. EVENT 01 — RoomCreated
Routing key: room.created.v1
Publisher: Room Service.
Consumer: Metering Service.
Data bắt buộc:
room_id: UUID phòng.
property_id: UUID khu trọ.
floor_id: UUID tầng.
room_code: Mã phòng.
Xử lý: Metering tạo đồng hồ điện và đồng hồ nước, bảo đảm idempotent.
21.4.4. EVENT 02 — ContractStarted
Routing key: contract.started.v1
Publisher: Tenant Service.
Consumers: Room Service, Metering Service.
Envelope bắt buộc: effective_at.
Data bắt buộc:
contract_id: UUID hợp đồng.
room_id: UUID phòng.
start_date: Ngày bắt đầu hợp đồng.
Room xử lý: Đánh dấu phòng đang có hợp đồng.
Metering xử lý: Tạo cutoff CONTRACT_START tại effective_at.
21.4.5. EVENT 03 — ContractEnded
Routing key: contract.ended.v1
Publisher: Tenant Service.
Consumers: Room Service, Metering Service.
Envelope bắt buộc: effective_at.
Data bắt buộc:
contract_id: UUID hợp đồng.
room_id: UUID phòng.
actual_end_date: Ngày kết thúc thực tế.
Room xử lý: Chỉ xóa occupancy_contract_id nếu đúng hợp đồng tương ứng và event không cũ hơn trạng thái hiện tại.
Metering xử lý: Tạo cutoff CONTRACT_END tại effective_at.
21.4.6. EVENT 04 — ContractExpiring
Routing key: contract.expiring.v1
Publisher: Tenant Service.
Consumer: Notification Service.
Data bắt buộc:
contract_id: UUID hợp đồng.
room_id: UUID phòng.
end_date: Ngày kết thúc.
days_remaining: Số ngày còn lại.
room_code: Mã phòng.
tenant_name: Tên người thuê.
Xử lý: Notification gửi email cảnh báo cho chủ trọ qua OWNER_EMAIL.
21.4.7. EVENT 05 — InvoiceIssued
Routing key: invoice.issued.v1
Publisher: Billing Service.
Consumer: Notification Service.
Data bắt buộc:
invoice_id: UUID hóa đơn.
contract_id: UUID hợp đồng.
recipient_email: Email người thuê.
invoice_code: Mã hóa đơn.
total_amount: Tổng tiền.
due_date: Hạn thanh toán.
tenant_name: Tên người thuê.
room_code: Mã phòng.
period_start: Ngày bắt đầu kỳ.
period_end_exclusive: Ngày kết thúc độc quyền.
Xử lý: Notification tạo email job, xin liên kết truy cập từ Billing và gửi hóa đơn.
21.4.8. EVENT 06 — InvoiceReminderRequested
Routing key: invoice.reminder_requested.v1
Publisher: Billing Service.
Consumer: Notification Service.
Data bắt buộc:
invoice_id: UUID hóa đơn.
recipient_email: Email người thuê.
reminder_date: Ngày nhắc nợ.
due_date: Hạn thanh toán.
invoice_code: Mã hóa đơn.
total_amount: Số tiền.
tenant_name: Tên người thuê.
room_code: Mã phòng.
period_start: Ngày bắt đầu kỳ.
period_end_exclusive: Ngày kết thúc độc quyền.
Xử lý: Kiểm tra trạng thái hóa đơn hiện tại trước khi gửi nhắc nợ.
21.4.9. EVENT 07 — PaymentSucceeded
Routing key: payment.succeeded.v1
Publisher: Billing Service.
Consumer: Notification Service.
Data bắt buộc:
invoice_id: UUID hóa đơn.
payment_attempt_id: UUID phiên thanh toán.
paid_amount: Số tiền đã thanh toán.
recipient_email: Email người thuê.
invoice_code: Mã hóa đơn.
tenant_name: Tên người thuê.
room_code: Mã phòng.
period_start: Ngày bắt đầu kỳ.
period_end_exclusive: Ngày kết thúc độc quyền.
paid_at: Thời điểm thanh toán thành công.
Xử lý: Gửi biên nhận và bỏ qua các reminder đang chờ của hóa đơn.
21.4.10. Queue Bindings
room.events.q
Exchange: rental.domain.v1
Binding: contract.started.v1, contract.ended.v1
Consumer: Room Service.
metering.events.q
Exchange: rental.domain.v1
Binding: room.created.v1, contract.started.v1, contract.ended.v1
Consumer: Metering Service.
notification.events.q
Exchange: rental.domain.v1
Binding: contract.expiring.v1, invoice.issued.v1, invoice.reminder_requested.v1, payment.succeeded.v1
Consumer: Notification Service.
metering.telemetry.q
Exchange: amq.topic
Binding: meters.*.reading
Consumer: Metering Service.
Phải khai báo exchange, queue và binding trước khi Simulator publish MQTT.
21.4.11. Retry và Dead Letter Queue
Delivery semantics: At-least-once.
Số lần retry: Tối đa 3.
Retry lần 1: Sau 10 giây.
Retry lần 2: Sau 60 giây.
Retry lần 3: Sau 300 giây.
Hết retry: Chuyển vào DLQ.
Cơ chế: Dùng retry queue có message TTL và dead-letter exchange đưa message quay về source queue.
ACK: Sau khi đã commit transaction nghiệp vụ hoặc publish thành công sang retry queue với publisher confirms.
Outbox worker: Sử dụng FOR UPDATE SKIP LOCKED để lấy batch.
Publish: Persistent messages, sử dụng publisher confirms.
Tránh trùng: Consumer kiểm tra event_id trong cùng transaction với cập nhật dữ liệu.
Không giả định RabbitMQ bảo đảm exactly-once delivery.

21.5. MQTT CONTRACTS — IOT
21.5.1. Topic và cấu trúc message
MQTT topic: meters/{meterId}/reading
QoS: 1
Publisher: Python IoT Simulator.
Consumer: Metering Service thông qua RabbitMQ MQTT plugin.
Exchange: amq.topic.
AMQP routing key: meters.{meterId}.reading.
Queue: metering.telemetry.q.
Queue binding: meters.*.reading.
Payload:
meter_id: UUID đồng hồ.
measured_at: Thời điểm đo ISO 8601.
reading_value: Chỉ số tích lũy.
reading_value là tổng số điện hoặc nước đã đo, không phải lượng tiêu thụ của riêng chu kỳ 5 phút.
21.5.2. Ví dụ message
{
  "meter_id": "2600cc3a-67fd-4c37-947a-6cc7c1ab5c60",
  "measured_at": "2026-11-10T11:05:00+07:00",
  "reading_value": 1352.125
}
21.5.3. Xử lý dữ liệu bất thường
Duplicate cùng giá trị: Bỏ qua.
Duplicate khác giá trị: Tạo cảnh báo CONFLICTING_DUPLICATE.
Chỉ số giảm: Tạo cảnh báo READING_DECREASE.
Reading đến muộn sau khi chốt: Tạo cảnh báo LATE_AFTER_CUTOFF nếu liên quan mốc đã xác nhận.
Không nhận reading quá 15 phút: Tạo cảnh báo OFFLINE.
Nhận dữ liệu trở lại: Đóng cảnh báo OFFLINE phù hợp.
Khóa chống trùng: (meter_id, measured_at).
Môi trường chạy: Docker network nội bộ.
MQTT port 1883: Không mở công khai ra Internet trong cấu hình triển khai.

21.6. RÀNG BUỘC DATABASE VÀ TÍNH NHẤT QUÁN
21.6.1. Hợp đồng
Các hợp đồng cùng phòng không được chồng lấn khoảng ngày hiệu lực theo quy tắc nghiệp vụ.
Sử dụng PostgreSQL EXCLUDE constraint.
Ngày cuối hợp đồng được bao gồm trong thời gian thuê nên chuyển thành mốc cuối độc quyền khi xây dựng daterange.
Không mở rộng khoảng thời gian của EXPIRED_PENDING thành vô hạn trong constraint.
Nếu phòng còn ACTIVE hoặc EXPIRED_PENDING thì không kích hoạt hợp đồng SCHEDULED mới.
21.6.2. Hóa đơn
Khoảng thời gian hóa đơn là [period_start, period_end).
Ràng buộc EXCLUDE không cộng thêm một ngày vào period_end.
Ví dụ:
ALTER TABLE invoices
ADD CONSTRAINT invoices_no_period_overlap
EXCLUDE USING gist (
  contract_id WITH =,
  daterange(period_start, period_end, '[)') WITH &&
)
WHERE (status <> 'VOID');
Hóa đơn PERIODIC không được trùng hợp đồng và kỳ.
Hóa đơn FINAL chỉ chứa phần chưa được lập hóa đơn.
Không tự động thay đổi hóa đơn PAID.
21.6.3. Meter Cutoffs
Mỗi đồng hồ có tối đa một cutoff còn hiệu lực tại một thời điểm.
CREATE UNIQUE INDEX uq_meter_cutoffs_active_time
ON meter_cutoffs (meter_id, cutoff_at)
WHERE status <> 'SUPERSEDED';
cutoff_type và contract_id chỉ là nhãn nguồn gốc/ngữ cảnh khi tạo mốc. Nếu mốc tháng, kết thúc hợp đồng A và bắt đầu B trùng thời điểm thì dùng cùng cutoff.id và cùng reading_value; truy vấn theo (meter_id, cutoff_at), không tạo một cutoff mới theo type/contract_id.
MONTHLY cutoff áp dụng cho tất cả đồng hồ ACTIVE.
Dùng ON CONFLICT DO NOTHING khi nhiều job tạo cùng cutoff.
Bản CONFIRMED không được sửa trực tiếp giá trị.
21.6.4. Thanh toán
Một hóa đơn có tối đa một payment attempt SUCCESS.
Không cho phép nhiều payment attempt PENDING độc lập cùng lúc.
Callback MoMo phải được kiểm tra chữ ký và xử lý idempotent.
Timeout không đồng nghĩa thất bại.
Giao dịch chưa rõ kết quả phải được đối soát.
21.6.5. Outbox và Event Processing
Outbox được ghi cùng transaction với thay đổi nghiệp vụ.
Consumer ghi processed event cùng transaction xử lý dữ liệu.
Outbox worker có thể retry khi publish thất bại.
Không dùng cross-database transaction.
REST nội bộ cần timeout, retry có giới hạn và correlation logging.
Không triển khai Saga hoặc Kafka trong phiên bản đồ án.
21.6.6. Tính tiền và làm tròn
Tiền phòng prorate phải tính bằng Decimal từ giá thuê tháng gốc và tỷ lệ ngày thực tế.
Không dùng float để tính tiền.
Không bắt buộc invoice_items.amount bằng quantity × unit_price đã làm tròn để hiển thị.
Tổng tiền hóa đơn bằng tổng các khoản đã làm tròn đến đơn vị đồng.

21.7. SCHEDULED JOBS
21.7.1. Contract Lifecycle
Service: Tenant.
Lịch: Mỗi 5 phút, có thể cấu hình.
Mục đích: Kích hoạt hợp đồng SCHEDULED đến hạn và đánh dấu hợp đồng quá hạn.
Quy tắc: Chỉ kích hoạt nếu không có hợp đồng ACTIVE hoặc EXPIRED_PENDING khác chiếm dụng phòng.
Không tự giải phóng phòng khi hợp đồng hết hạn.
21.7.2. Monthly Cutoffs
Service: Metering.
Lịch: 00:00 ngày 1 mỗi tháng, giờ Việt Nam.
Mục đích: Chốt chỉ số tất cả đồng hồ ACTIVE.
Thiếu reading: Tạo cutoff PENDING.
Idempotency: Theo (meter_id, cutoff_at).
21.7.3. Offline Detector
Service: Metering.
Lịch: Mỗi 5 phút.
Ngưỡng: 15 phút không nhận dữ liệu.
Mục đích: Tạo và đóng cảnh báo OFFLINE.
21.7.4. Billing Monthly Run
Service: Billing.
Lịch: 02:00 ngày 1 mỗi tháng.
Mục đích: Lập hóa đơn cho kỳ tháng trước.
Quy tắc: Chỉ phát hành khi đủ dữ liệu hợp đồng và điện nước.
21.7.5. Billing DRAFT Retry
Service: Billing.
Lịch: Mỗi 15 phút, có thể cấu hình.
Mục đích: Quét lại hóa đơn DRAFT đang bị chặn.
Quy tắc: Nếu đủ dữ liệu thì phát hành; nếu chưa đủ thì tiếp tục chờ.
21.7.6. Reminder Scheduler
Service: Billing.
Lịch: Hằng ngày, ví dụ 09:00 giờ Việt Nam.
Mục đích: Phát sự kiện nhắc nợ cho các hóa đơn phù hợp.
Quy tắc: Notification kiểm tra lại trạng thái trước khi gửi.
21.7.7. MoMo Reconciliation
Service: Billing.
Lịch: Mỗi 5 phút, có thể cấu hình.
Mục đích: Đối soát payment attempts PENDING với MoMo.
Quy tắc: Không tự kết luận FAILED nếu chưa có kết quả xác định.
Chạy thủ công: POST /api/v1/jobs/payments/reconcile/run.
21.7.8. Email Worker
Service: Notification.
Lịch: Chạy liên tục.
Mục đích: Gửi email, retry và xử lý trạng thái SKIPPED.

21.8. DEPLOYMENT VÀ THỨ TỰ KHỞI ĐỘNG
Giai đoạn 1: PostgreSQL và RabbitMQ sẵn sàng.
Giai đoạn 2: Khai báo exchange, queues, bindings, retry queues và DLQ.
Giai đoạn 3: Khởi động các microservices và workers.
Giai đoạn 4: Khởi động IoT Simulator.
Giai đoạn 5: Kích hoạt các scheduled jobs.
Các job phải sử dụng idempotency hoặc cơ chế khóa phù hợp để tránh thực thi trùng khi nhiều replica cùng chạy.
Không mở PostgreSQL, RabbitMQ Management, MQTT hoặc Internal API trực tiếp ra Internet.
Dùng health/readiness probes, JSON structured logs và correlation ID để theo dõi hệ thống.
Các lịch mặc định có thể được điều chỉnh để trình diễn nhanh trong môi trường demo.

21.9. THỨ TỰ ƯU TIÊN TRIỂN KHAI
P0 — BẮT BUỘC
Auth: Đăng nhập JWT.
Room: Quản lý khu trọ và tạo phòng hàng loạt.
Tenant: Tạo, xác nhận, kích hoạt và kết thúc hợp đồng; chạy lifecycle job.
Metering: Tạo đồng hồ từ event, nhận MQTT, chống trùng dữ liệu, chốt chỉ số tháng và cảnh báo OFFLINE cơ bản.
Billing: Lấy hợp đồng, điều khoản, chỉ số, tính tiền, tạo và phát hành hóa đơn; retry DRAFT.
Notification: Gửi hóa đơn, nhắc nợ và biên nhận; kiểm tra trạng thái trước khi gửi.
MoMo: Thanh toán Sandbox, xử lý IPN, chống callback trùng và đối soát PENDING.
Distributed Systems: Transactional Outbox, idempotent consumer, retry và DLQ.
Cloud: Docker, CI/CD và triển khai lên AWS EC2.
P1 — SAU KHI P0 HOẠT ĐỘNG
Tenant: Gia hạn, thay đổi điều khoản và dashboard hợp đồng gần hết hạn.
Metering: Cảnh báo nâng cao, điều chỉnh cutoff và lịch sử xử lý bất thường.
Billing: Điều chỉnh hóa đơn đã thanh toán, phát hành lại hóa đơn và xử lý các thao tác ít dùng.
Notification: Gửi lại email, thay đổi email nhận hóa đơn và thu hồi liên kết cũ.
Observability: Bổ sung các dashboard và metrics nâng cao nếu còn thời gian.

21.10. TÀI LIỆU KỸ THUẬT VÀ QUY TẮC TRIỂN KHAI
openapi.yaml: Nguồn đặc tả REST API, gồm paths, HTTP methods, request schemas, response schemas, mã lỗi và xác thực.
asyncapi.yaml: Nguồn đặc tả RabbitMQ/MQTT, gồm channels, operations, message schemas và topology.
FastAPI: Sinh OpenAPI runtime từ Pydantic models và endpoints. Phải đối chiếu với hợp đồng API đã chốt để phát hiện sai khác.
SQLAlchemy: Định nghĩa ORM models và các thao tác database.
Alembic: Quản lý migration độc lập cho từng service.
Pydantic: Xác thực request/response và dữ liệu event.
HTTPX: Gọi REST nội bộ giữa các service.
aio-pika: Giao tiếp RabbitMQ AMQP.
Paho MQTT: Simulator publish dữ liệu đo.
PostgreSQL: Một instance, sáu database logic, không có Foreign Key xuyên database.
Nguyên tắc cuối: API/Event Contracts V1.1 là hợp đồng triển khai. Khi phát hiện điểm không phù hợp, nhóm phải cập nhật contract có kiểm soát, thay vì để từng service tự định nghĩa request, response hoặc event khác nhau.
Trạng thái thiết kế: Database V3 + OpenAPI 3.1 + AsyncAPI 3.0 + API/Event Contracts V1.1.
==============================
