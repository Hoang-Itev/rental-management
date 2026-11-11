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
