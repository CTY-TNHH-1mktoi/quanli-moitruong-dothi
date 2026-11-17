



BÁO CÁO PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG

Hệ thống thông tin quản lý
và giám sát môi trường đô thị

Dự án demoth1
Trợ lý môi trường Xanh Non









Nhóm 1

Hồ sơ phân tích chức năng  Mô hình hóa hệ thống
Thiết kế dữ liệu  Thiết kế giao diện  Kiểm thử

Tháng 10 năm 2026

MỤC LỤC



DANH MỤC HÌNH



DANH MỤC BẢNG



DANH MỤC TỪ VIẾT TẮT

Bảng 1. Các thuật ngữ sử dụng trong báo cáo



Viết tắt | Ý nghĩa

API | Giao diện lập trình ứng dụng

AQI | Chỉ số chất lượng không khí

BFD | Sơ đồ phân rã chức năng

CAMS | Dịch vụ giám sát khí quyển Copernicus

DFD | Sơ đồ luồng dữ liệu

ERD | Sơ đồ thực thể và quan hệ

FK và PK | Khóa ngoại và khóa chính

GGUF | Định dạng tệp mô hình dùng cho suy luận cục bộ

LoRA | Kỹ thuật tinh chỉnh mô hình bằng các ma trận hạng thấp

PM2.5 và PM10 | Bụi có đường kính khí động học tương ứng không lớn hơn 2,5 và 10 micromet

RF | Random Forest

SRS | Đặc tả yêu cầu phần mềm

SSE | Luồng sự kiện từ máy chủ tới trình duyệt qua HTTP

UML | Ngôn ngữ mô hình hóa thống nhất

UTC+7 | Múi giờ được sử dụng cho dữ liệu tại Việt Nam

# CHƯƠNG 1  TỔNG QUAN ĐỀ TÀI

## 1.1 Bối cảnh và bài toán

Hệ thống quản lý và giám sát môi trường đô thị tập hợp dữ liệu chất lượng không khí, thời tiết và tiếng ồn theo địa điểm. Trên cùng một giao diện, người sử dụng có thể xem chỉ số, theo dõi các lần cập nhật, nhận cảnh báo, lập báo cáo và trao đổi với trợ lý Xanh Non. Bài toán trọng tâm là giữ cho thông tin về địa điểm, thời gian, nguồn và cách diễn giải thống nhất trong toàn bộ các thao tác này.

Các nguồn của dự án không có cùng đặc tính. Nhiệt độ, độ ẩm và chất lượng không khí được lấy qua Open-Meteo; tiếng ồn được tổng hợp từ dữ liệu cộng đồng NoiseCapture. Vì vậy, một màn hình có thể đồng thời chứa dữ liệu mô hình gần thời điểm hiện tại và số liệu tiếng ồn đã được thu thập từ trước. Việc ghi rõ nguồn và thời điểm giúp người sử dụng hiểu đúng ý nghĩa của từng giá trị [T01]–[T03].

## 1.2 Mục tiêu hệ thống

Hệ thống cung cấp khả năng tra cứu môi trường theo danh mục địa điểm, trực quan hóa phân bố AQI trên bản đồ, lưu các bản ghi phục vụ theo dõi và tạo báo cáo. Chatbot giải thích các chỉ số và hỗ trợ tư vấn trong phạm vi môi trường; những câu hỏi về hiện tại và dự báo được gắn với dữ liệu tương ứng, thay vì dùng số liệu đã ghi nhớ trong trọng số mô hình.

## 1.3 Phạm vi phân tích

Báo cáo mô tả phiên bản mã nguồn demoth1 được khảo sát ngày 27/10/2026. Phạm vi bao gồm ứng dụng web, API Flask, sáu bảng SQL Server, hai kho SQLite phục vụ học từ hội thoại và góp ý, mô hình Random Forest, mô hình ngôn ngữ cục bộ và các công cụ chuẩn bị dữ liệu huấn luyện. Các đường dẫn trong phần bằng chứng được tính từ thư mục gốc của dự án.

Phiên bản khảo sát sử dụng danh mục 86 địa điểm tham chiếu. Địa điểm là đơn vị tra cứu, không phải hồ sơ trạm cảm biến. Ứng dụng chưa có đăng nhập, vai trò tài khoản, quản lý thiết bị hay quy trình giao việc xử lý cảnh báo. Các mô hình trong báo cáo giữ đúng phạm vi này; tác nhân người vận hành chỉ thực hiện công việc trên máy và bằng công cụ dòng lệnh.

## 1.4 Công nghệ và tổ chức triển khai

Bảng 2. Thành phần công nghệ của phiên bản khảo sát



Thành phần | Công nghệ và vai trò | Bằng chứng

Giao diện | HTML, CSS, JavaScript; CSS Volt Free 1.4.1; điều hướng theo hash | static/index.html; dashboard.js; vendor/volt/SOURCE.md

Bản đồ | Leaflet 1.9.4; nền OpenStreetMap; lớp màu AQI bằng Canvas | static/map.js; air-overlay.js

Máy chủ | Flask; các blueprint cho báo cáo, bản đồ và góp ý | app.py; environment_reports.py; air_quality_map.py

Lưu trữ | SQL Server qua pyodbc; SQLite cục bộ; tệp JSON | Các tệp schema SQL; chat_feedback.py; chat_learning.py

Phân loại môi trường | Hai bộ phân loại Random Forest nạp từ joblib | environment_predictor.py; environment_rf.joblib

Trợ lý hội thoại | XanhNon-Style-v2; nền Qwen2.5 0.5B; llama.cpp chạy cục bộ | models/xanhnon-active.json; native_chatbot.py

Dữ liệu học | JSONL; Transformers, PEFT LoRA; đánh giá và xuất GGUF riêng | train_xanhnon.py; export_xanhnon.py

## 1.5 Cơ sở lập báo cáo

Nguồn chính của hồ sơ là mã Python, JavaScript, HTML, các lược đồ SQL, danh mục địa điểm, cấu hình bản mô hình và bộ kiểm thử trong repository. Các tài liệu kỹ thuật chính thức được dùng để xác định ký pháp UML, chức năng thư viện và ý nghĩa nguồn dữ liệu. Kết quả kiểm thử đã lưu được ghi kèm ngày và phạm vi; kết quả của một tập tình huống không được quy đổi thành tỷ lệ chính xác chung của chatbot.

# CHƯƠNG 2  KHẢO SÁT HIỆN TRẠNG

## 2.1 Đối tượng sử dụng và nhu cầu thông tin

Người sử dụng truy cập trực tiếp ứng dụng web để xem môi trường tại địa điểm quan tâm. Họ cần biết chỉ số nào đã có dữ liệu, dữ liệu được cập nhật lúc nào, cảnh báo thuộc địa điểm nào và nội dung tư vấn dựa trên thông tin gì. Người vận hành phụ trách khởi chạy dịch vụ, kết nối cơ sở dữ liệu, kiểm tra mô hình và xử lý dữ liệu học bằng công cụ cục bộ. Đây là hai nhóm trách nhiệm nghiệp vụ, không phải hai vai trò đăng nhập trong ứng dụng.

Bảng 3. Tác nhân và phạm vi tương tác



Mã | Tác nhân | Tương tác thực tế

A01 | Người sử dụng web | Tra cứu, xem chỉ số và bản đồ, xem cảnh báo, lập báo cáo, chat và gửi lời xác nhận hữu ích.

A02 | Người vận hành trên máy | Đọc trạng thái, cấu hình môi trường, duyệt góp ý, chuẩn bị dữ liệu và chạy công cụ huấn luyện.

E01 | Open-Meteo | Cung cấp dữ liệu thời tiết, chất lượng không khí và dự báo theo tọa độ.

E02 | NoiseCapture | Cung cấp tệp dữ liệu tiếng ồn cộng đồng tại Việt Nam.

E03 | OpenStreetMap | Cung cấp ảnh nền bản đồ cho trình duyệt.

## 2.2 Quy trình hiện tại

Khi mở ứng dụng, trình duyệt tải danh mục địa điểm, khôi phục lựa chọn gần nhất và yêu cầu snapshot môi trường của địa điểm đó. Máy chủ kiểm tra cache, gọi các nguồn khi cần, tạo cảnh báo và phân tích, rồi lưu kết quả vào SQL Server. Sau đó, trình duyệt đọc lịch sử và cảnh báo để hoàn thiện nội dung hiển thị. Khi người sử dụng đổi địa điểm, các phản hồi thuộc yêu cầu cũ được loại bỏ để tránh ghép số liệu giữa hai nơi.

Bản đồ dùng tọa độ tham chiếu của địa điểm đã chọn, đồng thời tải lưới AQI theo vùng đang xem. Báo cáo được tạo từ các bản ghi đã lưu trong kỳ 1, 7 hoặc 30 ngày. Hội thoại gửi kèm địa điểm và một số lượt hỏi đáp gần nhất; máy chủ xác định chủ đề, thời gian và nguồn dữ liệu cần dùng trước khi tạo phản hồi.

## 2.3 Hiện trạng các nhóm chức năng

Bảng 4. Kết quả đối chiếu phạm vi chức năng



Nhóm | Hiện trạng | Căn cứ

Địa điểm | Đã triển khai danh mục, tìm kiếm, ghi nhớ lựa chọn và chọn địa điểm gần nhất | locations.json; static/locations.js

Giám sát | Đã triển khai cập nhật, lưu snapshot, năm thông số chính và US AQI | app.py; static/script.js

Bản đồ | Đã triển khai nền bản đồ, marker tham chiếu và lớp AQI nội suy | map.js; air-overlay.js; air_quality_map.py

Cảnh báo | Đã triển khai sinh theo ngưỡng và lịch sử trong nút chuông | build_alerts; CanhBao; dashboard.js

Báo cáo | Đã triển khai tạo, lưu, mở lại, xuất CSV và in bằng trình duyệt | environment_reports.py; static/reports.js

Chatbot | Đã triển khai các nhánh quy tắc, tra cứu tri thức, đọc dữ liệu và sinh cục bộ | chatbot.py; chat_knowledge.py; native_chatbot.py

Học từ trao đổi | Đã triển khai tiếp nhận câu hỏi mới và góp ý; việc học trọng số là quy trình riêng | chat_learning.py; chat_feedback.py; train_xanhnon.py

## 2.4 Đặc điểm dữ liệu và giới hạn nghiệp vụ

Dữ liệu không khí là kết quả của mô hình do nguồn cung cấp, có độ phân giải theo ô lưới. Các địa điểm gần nhau có thể có cùng giá trị. Đối với bản đồ, API chỉ định CAMS Global và trả metadata độ phân giải 45 km; màu được nội suy để hiển thị liên tục, không tạo ra độ chính xác tương đương đo trực tiếp trên từng tuyến đường.

Tiếng ồn được lọc trong bán kính tham chiếu 2 km và tổng hợp theo năng lượng có trọng số. Nếu không có ô dữ liệu phù hợp, trường tiếng ồn để trống. Trạng thái “Hệ thống hoạt động” phản ánh việc tải dữ liệu thành công trên giao diện, không xác nhận sự hoạt động của một mạng trạm vật lý.

Lịch sử trong SQL là lịch sử các snapshot ứng dụng đã lưu. Đồ thị PM2.5 hiển thị tối đa 12 snapshot gần nhất; các điểm không nhất thiết cách đều về thời gian. Hệ thống không suy ra rằng toàn bộ thời gian giữa hai lần cập nhật đã được quan trắc liên tục.

# CHƯƠNG 3  PHƯƠNG PHÁP PHÂN TÍCH VÀ THIẾT KẾ

## 3.1 Phân tích theo chức năng

Phân tích theo chức năng bắt đầu từ các công việc mà hệ thống phải thực hiện. BFD chia nghiệp vụ thành những nhóm có mục tiêu rõ ràng. DFD thể hiện dữ liệu đi từ tác nhân qua các tiến trình, được đọc hoặc ghi ở kho nào và trả về dưới dạng gì. Trong dự án này, cập nhật dữ liệu, đánh giá ngưỡng và lập báo cáo là những luồng phù hợp để phân tích theo cách đó.

Sơ đồ ngữ cảnh xác định ranh giới ứng dụng; DFD mức 0 phân rã các tiến trình chính; mức 1 mô tả cập nhật môi trường. Mã FR, UC và BR lần lượt định danh chức năng, ca sử dụng và quy tắc, được dùng thống nhất trong đặc tả và kiểm thử.

## 3.2 Phân tích hướng đối tượng

UML được dùng để mô tả mục tiêu của tác nhân, sự phối hợp giữa thành phần và vòng đời của mô hình hội thoại. Use Case biểu diễn hành vi nhìn từ người sử dụng; Activity biểu diễn trình tự công việc; Sequence thể hiện các lời gọi giữa giao diện, API, lớp xử lý và lưu trữ. Class Diagram mô tả các lớp Python thực sự tồn tại và trách nhiệm của chúng [T04].

Đối tượng địa điểm, snapshot, cảnh báo và báo cáo được phân tích ở cấp miền nghiệp vụ. Trong mã nguồn hiện tại, nhiều đối tượng được biểu diễn bằng dictionary hoặc hàng SQL, không phải lớp ORM. Báo cáo phân biệt mô hình miền với sơ đồ lớp triển khai để không đồng nhất tên bảng với tên lớp.

Bảng 5. Đối chiếu hai cách phân tích trong dự án



Nội dung | Theo chức năng | Theo đối tượng

Trọng tâm | Công việc và dữ liệu vào ra | Trách nhiệm và sự cộng tác

Mô hình chính | BFD, DFD, đặc tả tiến trình | Use Case, Class, Activity, Sequence, State

Ứng dụng trong demoth1 | Làm rõ cập nhật, cảnh báo, tổng hợp báo cáo | Làm rõ repository, runtime chatbot và xử lý nhiều lượt

Căn cứ triển khai | Các hàm điều phối trong app.py và chatbot.py | LocationStore, ReportRepository, AirMapRepository, NativeChatbot và các lớp lưu học

## 3.3 Cách tổ chức hồ sơ

Phân tích chức năng là trục mô tả nghiệp vụ, phù hợp với cách điều phối bằng hàm và module trong Flask. UML bổ sung tương tác và trách nhiệm; ERD mô tả lưu trữ. Các mô hình được liên kết với yêu cầu, API, dữ liệu và kiểm thử.

# CHƯƠNG 4  ĐẶC TẢ YÊU CẦU HỆ THỐNG

## 4.1 Yêu cầu chức năng và điều kiện truy cập

Danh mục chức năng được chuẩn hóa thành 18 mã. FR01–FR16 phục vụ thao tác trên ứng dụng và xử lý dữ liệu liên quan; FR17–FR18 phục vụ theo dõi và vận hành mô hình. Mỗi mã có một ca sử dụng tương ứng, ví dụ FR03 liên kết UC03. Các chức năng web không yêu cầu tài khoản; thao tác vận hành dùng quyền của tài khoản hệ điều hành đang chạy dự án.

Bảng 6. Danh mục yêu cầu chức năng



Mã | Yêu cầu cần đạt | Tác nhân

FR01 | Chọn và tìm kiếm địa điểm hoặc chức năng trong danh mục | A01

FR02 | Lấy vị trí thiết bị và tự chọn địa điểm gần nhất trong danh sách | A01

FR03 | Cập nhật dữ liệu theo địa điểm và lưu snapshot nhất quán | A01, E01, E02

FR04 | Hiển thị chỉ số, đơn vị, nguồn và thời điểm cập nhật | A01

FR05 | Xem marker, di chuyển, phóng to và mở bản đồ lớn | A01, E03

FR06 | Tải và hiển thị lớp màu chất lượng không khí theo vùng | A01, E01

FR07 | Xem đồ thị PM2.5 từ các snapshot gần nhất | A01

FR08 | Xem lịch sử cảnh báo đúng địa điểm bằng nút chuông | A01

FR09 | Xem kết quả hai mô hình Random Forest và trạng thái dữ liệu | A01

FR10 | Tạo và lưu báo cáo kỳ 1, 7 hoặc 30 ngày | A01

FR11 | Tra cứu danh sách và mở nội dung báo cáo đã lưu | A01

FR12 | Xuất dữ liệu báo cáo thành CSV hoặc in bằng trình duyệt | A01

FR13 | Gửi câu hỏi và điều khiển phiên hội thoại Xanh Non | A01

FR14 | Giữ ngữ cảnh chủ đề, địa điểm và thời gian qua nhiều lượt | A01, E01

FR15 | Giải thích chỉ số và tư vấn từ tri thức có nguồn | A01

FR16 | Ghi nhận lời xác nhận hữu ích và câu hỏi mới phù hợp | A01

FR17 | Tra cứu trạng thái runtime của chatbot | A02

FR18 | Chuẩn bị dữ liệu, huấn luyện và kiểm tra mô hình ứng viên | A02

## 4.2 Quy tắc nghiệp vụ

Bảng 7. Các quy tắc nghiệp vụ sử dụng trong đặc tả



Mã | Quy tắc

BR01 | Mã địa điểm phải thuộc danh mục; bỏ trống dùng Hà Nội. Mã không hợp lệ trả lỗi thay vì tự gán sang địa điểm khác.

BR02 | Cache snapshot hiệu lực 600 giây theo từng địa điểm. Khóa riêng ngăn yêu cầu cùng địa điểm tạo đồng thời nhiều bản ghi trong một tiến trình.

BR03 | Thời gian lấy dữ liệu, thời gian nguồn thời tiết, thời gian nguồn không khí và thời gian đo tiếng ồn có ý nghĩa riêng; metadata nguồn được giữ trong ChiTiet.

BR04 | Không có tiếng ồn phù hợp thì trả null. Không dùng tiếng ồn của địa điểm khác để lấp chỗ trống.

BR05 | Cảnh báo được sinh cho từng thông số có giá trị và liên kết với Manguon; hai mức lưu là Trung bình và Cao.

BR06 | Phân loại Random Forest chỉ chạy khi đủ năm giá trị hữu hạn. Nhãn của mô hình không thay thế chỉ số US AQI.

BR07 | Báo cáo chỉ dùng bản ghi và cảnh báo cùng địa điểm, nằm trong kỳ 1, 7 hoặc 30 ngày; nội dung được lưu thành snapshot JSON.

BR08 | Số liệu thiếu không được dùng như một lần đo bằng 0 khi tính thống kê báo cáo; số thiếu được đếm riêng.

BR09 | Ngữ cảnh hội thoại gồm tối đa tám cặp hỏi đáp hoàn chỉnh; đổi địa điểm trên giao diện sử dụng lịch sử riêng.

BR10 | Dữ liệu hiện tại và dự báo phải được lấy theo địa điểm, thời gian đã giải nghĩa. Không lấy số đã xuất hiện trong câu trả lời cũ làm nguồn mới.

BR11 | Câu hỏi ngoài phạm vi nhận câu giới thiệu cố định; câu hỏi thiếu chủ đề hoặc ngày quan trọng có thể được hỏi lại.

BR12 | Học từ chat chỉ tái sử dụng câu trả lời kiến thức ổn định đã đối chiếu nguồn. Góp ý cần kiểm tra trước khi thành dữ liệu huấn luyện.

BR13 | Lưới bản đồ tối đa 196 điểm; vùng thiếu dữ liệu để trống, không tô màu bằng giá trị giả.

BR14 | Phản hồi cũ đến muộn không thay thế dữ liệu của địa điểm mới đang chọn trên giao diện.

## 4.3 Yêu cầu phi chức năng có căn cứ

Bảng 8. Giới hạn và hành vi phi chức năng hiện có



Mã | Nội dung có thể kiểm tra | Bằng chứng

NFR01 | Cập nhật có cache 600 giây; trình duyệt yêu cầu lại mỗi 605 giây khi trang mở. Đây là chu kỳ yêu cầu, không phải cam kết độ trễ nguồn. | app.py; static/script.js

NFR02 | Luồng chat có status, delta và done hoặc error; có thể dừng nhận khi đang sinh. | chatbot.stream_reply; static/chat.js

NFR03 | Câu hỏi tối đa 8.000 ký tự, history tối đa 16 message đúng cặp; body chat không quá 2 MiB. | validate_chat; app.chat

NFR04 | Lỗi một phần lịch sử hoặc cảnh báo được hiển thị riêng; đổi địa điểm loại phản hồi quá hạn. | static/script.js

NFR05 | Truy vấn SQL dùng tham số; dữ liệu chat hiển thị bằng textContent. Không có chức năng xác thực tài khoản. | app.py; environment_reports.py; static/chat.js

NFR06 | Giao diện đã có kiểm tra trình duyệt ở 1.600 px và 390 px; hỗ trợ bàn phím cho menu, tìm kiếm và đóng hộp nổi. | browser-checks.json; dashboard.js

NFR07 | Dữ liệu báo cáo và snapshot dùng JSON không chấp nhận NaN; RF và thống kê loại giá trị không hữu hạn. | environment_reports.py; environment_predictor.py

NFR08 | Runtime sinh mô hình được khóa tránh chồng phiên; giới hạn tài nguyên được kiểm tra trước huấn luyện. | _generation_lock; training_state.py; daily_train_xanhnon.py

## 4.4 Điều kiện nghiệm thu theo phạm vi

Một chức năng được xác nhận bằng hành vi đầu ra và trạng thái dữ liệu, không chỉ bằng sự có mặt của nút giao diện. Cập nhật phải giữ đúng mã địa điểm và quan hệ bản ghi; báo cáo mở lại phải khớp nội dung đã lưu; câu hỏi nối tiếp phải dùng đúng chủ đề và ngày giờ; tình huống thiếu dữ liệu phải trả trạng thái hoặc thông báo phù hợp. Chương 12 trình bày dữ liệu kiểm thử, điều kiện thực hiện và bằng chứng kết quả của từng nhóm yêu cầu.

# CHƯƠNG 5  PHÂN TÍCH CHỨC NĂNG NGHIỆP VỤ

## 5.1 Cây phân rã và cách đọc đặc tả

Cây chức năng gồm sáu nhánh. Nhóm tra cứu xác định địa điểm và trình bày số liệu; nhóm cập nhật tiếp nhận, đánh giá và lưu; bản đồ và xu hướng cung cấp góc nhìn không gian và thời gian; báo cáo tổng hợp lịch sử; hội thoại hỗ trợ giải thích và tư vấn; vận hành quản lý dữ liệu học và trạng thái mô hình.



Hình 1. Cây phân rã chức năng của hệ thống

Các chức năng dưới đây đều có mã nguồn triển khai. FR01–FR15 là nghiệp vụ sử dụng trực tiếp; FR16 hỗ trợ ghi nhận dữ liệu cải thiện; FR17–FR18 thuộc vận hành cục bộ. Trạng thái triển khai không đồng nghĩa với mọi yêu cầu đều đã được chứng minh bằng kiểm thử trực tiếp; kết quả và phạm vi kiểm chứng được ghi tại chương 12. Mức ưu tiên của FR01–FR15 là cốt lõi trong sản phẩm, FR16–FR18 là hỗ trợ vận hành.

## 5.2 FR01 Chọn và tìm kiếm địa điểm

Mục đích và tác nhân. Xác định địa điểm dùng chung cho chỉ số, bản đồ, cảnh báo, báo cáo và hội thoại. Tác nhân: A01. Ca sử dụng tương ứng: UC01.

Điều kiện trước. Danh mục địa điểm đã tải thành công. Ứng dụng không ở trạng thái khóa lựa chọn do đang chat hoặc xử lý báo cáo.

Đầu vào và giao diện. Người sử dụng chọn MaDiaDiem trong select hoặc nhập từ khóa tối đa 80 ký tự vào ô tìm kiếm. Từ khóa được chuẩn hóa để tìm không dấu; kết quả có thể là địa điểm hoặc mục chức năng. Vị trí thao tác: UI01 và thanh đầu trang.

Luồng chính. 

1. Tải GET /api/diadiem và tạo các nhóm lựa chọn từ danh mục.

2. Lọc gợi ý theo từ khóa; người sử dụng chọn bằng chuột hoặc phím mũi tên và Enter.

3. Nếu là địa điểm, cập nhật lựa chọn, lưu mã vào localStorage và phát locationchange; nếu là chức năng, điều hướng tới hash tương ứng.

4. Các thành phần nạp lại dữ liệu theo mã mới; kết quả của yêu cầu cũ được bỏ qua.

Điều kiện sau và đầu ra. Sau thao tác, tên địa điểm và mã dùng trong yêu cầu API thống nhất. Tải lại trang giữ lựa chọn hợp lệ gần nhất. Tìm kiếm không làm thay đổi danh mục gốc.

Luồng thay thế và ngoại lệ. Không có kết quả thì hiển thị trạng thái tương ứng. Danh mục lỗi có nút thử lại. Mã gửi trực tiếp không thuộc danh mục bị API từ chối với HTTP 400; mã không được tự đổi sang một nơi khác.

Thiết kế và bằng chứng. static/locations.js, dashboard.js và location_catalog.get_location. GET /api/diadiem đồng bộ metadata qua LocationStore. Kho liên quan: DiaDiem và locations.json.

Quy tắc và nghiệm thu. BR01, BR14. Kiểm thử: TC01, TC02.

## 5.3 FR02 Lấy địa điểm gần nhất từ vị trí hiện tại

Mục đích và tác nhân. Rút ngắn việc chọn địa điểm bằng cách đối chiếu vị trí thiết bị với các tọa độ sẵn có. Tác nhân: A01. Ca sử dụng tương ứng: UC02.

Điều kiện trước. Danh mục đã sẵn sàng, trình duyệt hỗ trợ Geolocation và trang được mở trong ngữ cảnh an toàn như localhost hoặc HTTPS.

Đầu vào và giao diện. Nút Lấy vị trí hiện tại yêu cầu quyền truy cập vị trí. Tọa độ latitude và longitude phải là số hữu hạn trong phạm vi địa lý hợp lệ. Vị trí thao tác: UI01.

Luồng chính. 

1. Người sử dụng nhấn nút; giao diện hiển thị trạng thái đang định vị và vô hiệu hóa thao tác trùng.

2. Trình duyệt xin quyền, lấy tọa độ với timeout 12 giây và không dùng tọa độ cũ.

3. Tính khoảng cách Haversine từ thiết bị tới từng địa điểm trong danh mục, chọn giá trị nhỏ nhất.

4. Đặt mã tìm được vào danh sách và gọi lại luồng thay đổi địa điểm; hiển thị tên và khoảng cách ước tính.

Điều kiện sau và đầu ra. Kết quả là một địa điểm đã tồn tại trong danh mục, không tạo địa điểm mới và không xác định trạm đo gần nhất. Tọa độ thiết bị chỉ được xử lý trong trình duyệt.

Luồng thay thế và ngoại lệ. Từ chối quyền, không xác định được vị trí, quá thời gian hoặc tọa độ không hợp lệ đều có thông báo riêng. Người sử dụng vẫn chọn thủ công. Phản hồi GPS cũ không ghi đè lựa chọn mới.

Thiết kế và bằng chứng. static/locations.js: locateNearest, distanceKm và selectPlace. Không có API nhận tọa độ GPS của thiết bị; các API tiếp theo chỉ nhận MaDiaDiem.

Quy tắc và nghiệm thu. BR01, BR14. Kiểm thử: TC03.

## 5.4 FR03 Cập nhật và lưu dữ liệu môi trường

Mục đích và tác nhân. Tạo snapshot thống nhất của dữ liệu nguồn, kết quả đánh giá và cảnh báo tại một địa điểm. Tác nhân: A01, E01, E02. Ca sử dụng tương ứng: UC03.

Điều kiện trước. Mã địa điểm hợp lệ; SQL Server truy cập được. Nguồn bên ngoài chỉ được gọi khi không có snapshot còn hạn.

Đầu vào và giao diện. Nút Cập nhật dữ liệu hoặc chu kỳ tải tự động gửi location dạng chuỗi. GET và POST /api/capnhat đều được khai báo; giao diện hiện dùng GET. Vị trí thao tác: UI01.

Luồng chính. 

1. Lấy khóa riêng cho địa điểm và kiểm tra cache 600 giây; nếu cần, đọc snapshot đã lưu còn hạn trong SQL.

2. Khi cache hết hạn, lấy nhiệt độ, độ ẩm, dữ liệu không khí và phần tiếng ồn phù hợp.

3. Tạo cảnh báo theo ngưỡng và phân tích theo AQI; gọi hai bộ phân loại RF khi đủ năm giá trị.

4. Trong một giao dịch, chèn NguonDL, các CanhBao và PhanTichAI, cập nhật ChiTiet rồi commit; đặt cache và trả JSON.

Điều kiện sau và đầu ra. JSON gồm Manguon, ThoiGian, DiaDiem, DuLieu, DuDoanRF, CanhBao và PhanTich. Snapshot mới có mã nguồn duy nhất; cảnh báo và phân tích cùng tham chiếu mã này.

Luồng thay thế và ngoại lệ. Nguồn HTTP lỗi trả 502; SQL lỗi trả thông báo chung và 503. RF lỗi hoặc thiếu trường không chặn lưu số liệu. Cập nhật còn trong thời hạn cache trả lại snapshot hiện có, không tạo bản ghi mới.

Thiết kế và bằng chứng. app.py: capnhat, update_environment, fetch_environment, build_alerts, build_analysis. Kho ghi: NguonDL, CanhBao, PhanTichAI; DiaDiem được chuẩn bị trước.

Quy tắc và nghiệm thu. BR01–BR06. Kiểm thử: TC04, TC05, TC06.

## 5.5 FR04 Xem các chỉ số môi trường

Mục đích và tác nhân. Trình bày kết quả giám sát theo địa điểm bằng chỉ số, đơn vị và trạng thái dễ đối chiếu. Tác nhân: A01. Ca sử dụng tương ứng: UC04.

Điều kiện trước. Giao diện đã có snapshot hợp lệ hoặc nhận được trạng thái tải lỗi.

Đầu vào và giao diện. Dữ liệu JSON từ FR03. Các trường chính là US_AQI, PM25, PM10, NhietDo, DoAm và TiengOn; metadata thời gian nguồn và tiếng ồn đi cùng snapshot. Vị trí thao tác: UI01 và UI02.

Luồng chính. 

1. Đối chiếu phiên yêu cầu và địa điểm đang chọn trước khi cập nhật DOM.

2. Điền các giá trị, đơn vị và trạng thái thông số; đặt màu, mức AQI và nội dung phân tích.

3. Cập nhật thời điểm lấy dữ liệu và ghi chú nguồn tiếng ồn.

4. Giữ dữ liệu cũ cùng thông báo khi tải mới lỗi tại cùng địa điểm; khi đổi nơi thì xóa số cũ trước khi tải.

Điều kiện sau và đầu ra. Người sử dụng xem được năm chỉ số và US AQI. Thanh tiến trình chỉ phục vụ tỷ lệ hiển thị theo cấu hình, không phải toàn bộ thang chuẩn pháp lý.

Luồng thay thế và ngoại lệ. Trường thiếu hiển thị dấu gạch hoặc trạng thái chưa có dữ liệu. Lỗi tải không được tạo cảm giác số cũ thuộc địa điểm mới. Mức AQI và kết quả RF được hiển thị tách biệt.

Thiết kế và bằng chứng. static/script.js: renderCurrent, renderAnalysis, renderPrediction, renderCurrentFailed; static/index.html. GET /api/dulieu/moinhat cung cấp bản ghi gần nhất khi cần đọc lại.

Quy tắc và nghiệm thu. BR03, BR04, BR06, BR14. Kiểm thử: TC02, TC06, TC07.

## 5.6 FR05 Tương tác với bản đồ địa điểm

Mục đích và tác nhân. Đặt dữ liệu môi trường vào bối cảnh không gian và giúp người sử dụng nhận biết tọa độ tham chiếu. Tác nhân: A01, E03. Ca sử dụng tương ứng: UC05.

Điều kiện trước. Leaflet đã nạp; địa điểm hiện tại có tọa độ hợp lệ.

Đầu vào và giao diện. Các thao tác kéo, phóng to, thu nhỏ, nhấn marker, về địa điểm đã chọn, toàn màn hình và mở bản đồ lớn. Vị trí thao tác: UI03.

Luồng chính. 

1. Khởi tạo nền OpenStreetMap và các điều khiển Leaflet.

2. Đặt marker thời tiết và không khí theo tọa độ địa điểm; marker tiếng ồn dùng tọa độ tham chiếu riêng khi phù hợp.

3. Nhấn marker để xem tên, tọa độ và thông tin nguồn.

4. Khi đổi địa điểm, bỏ marker cũ, tạo marker mới và đưa vùng nhìn về nơi được chọn.

Điều kiện sau và đầu ra. Bản đồ hiển thị đúng địa điểm; liên kết mở bản đồ lớn mang tọa độ tương ứng. Di chuyển vùng nhìn không tự thay danh mục địa điểm.

Luồng thay thế và ngoại lệ. Nếu nền bản đồ không tải được, phần tham chiếu vị trí vẫn có thể hiển thị và giao diện có thao tác thử lại. Toàn màn hình phụ thuộc khả năng của trình duyệt.

Thiết kế và bằng chứng. static/map.js và thư viện static/vendor/leaflet. Nền bản đồ được tải trực tiếp trong trình duyệt từ OpenStreetMap; dữ liệu mẫu AQI thuộc FR06.

Quy tắc và nghiệm thu. BR01, BR14. Kiểm thử: TC08.

## 5.7 FR06 Hiển thị lớp màu AQI theo vùng

Mục đích và tác nhân. Biểu diễn phân bố AQI từ các điểm lưới của mô hình trong vùng đang xem. Tác nhân: A01, E01. Ca sử dụng tương ứng: UC06.

Điều kiện trước. Phạm vi bản đồ hợp lệ và giao với vùng phục vụ của API. Có ít nhất một phần mẫu dữ liệu dùng được.

Đầu vào và giao diện. location và bốn giới hạn south, west, north, east dạng số. Giao diện có công tắc lớp màu và độ đậm 25–85%, mặc định 68%. Vị trí thao tác: UI03.

Luồng chính. 

1. Xác định vùng, tạo lưới lấy mẫu với số điểm không vượt 196.

2. Đọc mẫu còn hiệu lực trong giờ hiện tại từ bộ nhớ và SQL; gọi Open-Meteo cho những điểm còn thiếu.

3. Trả ma trận AQI, PM25, các trục tọa độ, thời gian nguồn và metadata độ phân giải.

4. Trình duyệt nội suy giữa các góc hợp lệ, tô theo sáu mức AQI và đặt độ đậm đã chọn.

Điều kiện sau và đầu ra. Lớp phủ là biểu diễn nội suy từ dữ liệu mô hình CAMS Global. Nhấn bản đồ có thể xem giá trị ước tính tại vị trí đó; đây không phải bản ghi đo mới của một cảm biến.

Luồng thay thế và ngoại lệ. Phạm vi thiếu hoặc sai trả 400. Nguồn lỗi hoàn toàn trả 502; thiếu một phần trả cảnh báo và để trống phần không đủ dữ liệu. Mẫu không được tự gán 0.

Thiết kế và bằng chứng. air_quality_map.py: make_grid, AirMapRepository.get_samples và grid; static/air-overlay.js. API GET /api/bando/khongkhi; kho MauBanDoKhongKhi.

Quy tắc và nghiệm thu. BR03, BR13, BR14. Kiểm thử: TC09, TC10.

## 5.8 FR07 Theo dõi xu hướng PM2.5

Mục đích và tác nhân. Cho phép đối chiếu các snapshot PM2.5 gần đây trong cùng địa điểm. Tác nhân: A01. Ca sử dụng tương ứng: UC07.

Điều kiện trước. Lịch sử trả về có thể có dữ liệu, rỗng hoặc một số giá trị thiếu.

Đầu vào và giao diện. GET /api/dulieu/lichsu với location và limit. Giao diện dùng limit=12; API giới hạn hợp lệ từ 1 đến 500. Vị trí thao tác: UI04.

Luồng chính. 

1. Đọc các bản ghi mới nhất của địa điểm theo thời gian và mã nguồn giảm dần.

2. Sắp thứ tự trình bày theo thời gian tăng dần và lấy các điểm PM2.5 sử dụng được.

3. Tính miền giá trị, chọn bước chia trục số phù hợp và dựng đường biểu diễn trên Canvas.

4. Hiển thị giá trị gần nhất, nhãn xu hướng và các mốc thời gian; vẽ lại khi thay đổi kích thước màn hình.

Điều kiện sau và đầu ra. Đồ thị có trục tung số, đơn vị µg/m³ và các mốc thời gian. Nhận xét tăng giảm dựa trên lịch sử snapshot, không phải dự báo tương lai.

Luồng thay thế và ngoại lệ. Lịch sử rỗng và tải lỗi có trạng thái riêng. Dữ liệu thiếu tạo khoảng trống thay vì điểm đo bằng 0. Phản hồi của địa điểm cũ bị loại bỏ.

Thiết kế và bằng chứng. app.dulieu_lichsu; static/script.js: renderTrend, describeTrend, drawTrend. Đọc NguonDL; không tạo bản ghi mới.

Quy tắc và nghiệm thu. BR03, BR14. Kiểm thử: TC11.

## 5.9 FR08 Xem lịch sử cảnh báo

Mục đích và tác nhân. Cho phép tra cứu các cảnh báo môi trường gần nhất của nơi đang giám sát. Tác nhân: A01. Ca sử dụng tương ứng: UC08.

Điều kiện trước. Địa điểm đã được xác định; cảnh báo có thể chưa phát sinh.

Đầu vào và giao diện. Nhấn biểu tượng chuông trên đầu trang. GET /api/canhbao nhận location và limit; giao diện lấy 8, API mặc định 20 và giới hạn tối đa 200. Vị trí thao tác: UI06 dưới dạng bảng thông báo.

Luồng chính. 

1. Đọc CanhBao liên kết NguonDL theo mã địa điểm.

2. Hiển thị loại, mức, nội dung và thời gian; cập nhật số cảnh báo đã tải trên chuông.

3. Người sử dụng mở bảng bằng chuông và đóng bằng X, Esc hoặc chuyển ngữ cảnh thích hợp.

4. Khi đổi địa điểm, tải lại cảnh báo và xóa trạng thái của nơi cũ.

Điều kiện sau và đầu ra. Lịch sử chỉ chứa cảnh báo của địa điểm hiện tại. Con số trên chuông là số mục gần nhất đang tải, không phải số cảnh báo chưa đọc có lưu bền.

Luồng thay thế và ngoại lệ. Chưa có cảnh báo hiển thị trạng thái rỗng; lỗi tải hiển thị thông báo và khả năng thử lại. Cảnh báo không có vòng đời xác nhận, phân công hoặc đóng trong phiên bản hiện tại.

Thiết kế và bằng chứng. app.canhbao; static/script.js: renderAlerts; static/dashboard.js: setNotifications và syncAlerts. Đọc CanhBao qua NguonDL.

Quy tắc và nghiệm thu. BR01, BR05, BR14. Kiểm thử: TC12.

## 5.10 FR09 Xem phân tích và phân loại Random Forest

Mục đích và tác nhân. Tách phần diễn giải AQI theo quy tắc khỏi nhãn dự đoán của mô hình minh họa. Tác nhân: A01. Ca sử dụng tương ứng: UC09.

Điều kiện trước. Có snapshot và trạng thái DuDoanRF. Đủ năm đặc trưng mới chạy được mô hình.

Đầu vào và giao diện. Năm giá trị PM25, PM10, NhietDo, DoAm, TiengOn. Giá trị phải chuyển được thành số hữu hạn; thứ tự đặc trưng phải khớp model bundle. Vị trí thao tác: UI05.

Luồng chính. 

1. Kiểm tra đầy đủ giá trị và danh sách đặc trưng.

2. Nạp bundle joblib cục bộ một lần và tạo DataFrame đúng thứ tự.

3. Chạy hai classifier cho chất lượng không khí và mức tiếng ồn.

4. Trả nhãn tiếng Việt và TrangThai; giao diện hiển thị cùng phần phân tích AQI nhưng thành khối riêng.

Điều kiện sau và đầu ra. TrangThai là ok, thieu_du_lieu hoặc loi_mo_hinh. Nhãn RF thể hiện kết quả mô hình được huấn luyện theo nhãn của dự án; phân tích AQI được lưu trong PhanTichAI do build_analysis tạo.

Luồng thay thế và ngoại lệ. Thiếu một trường trả danh sách Thieu. Lỗi nạp hoặc suy luận không làm mất dữ liệu nguồn. Tên PhanTichAI không có nghĩa là mọi nội dung trong bảng do mô hình ngôn ngữ sinh ra.

Thiết kế và bằng chứng. environment_predictor.py: FEATURE_FIELDS, load_model, predict_environment; app.build_analysis; static/script.js: renderPrediction. Bundle environment_rf.joblib; snapshot lưu kết quả trong ChiTiet.

Quy tắc và nghiệm thu. BR03, BR06. Kiểm thử: TC06, TC13.

## 5.11 FR10 Tạo và lưu báo cáo môi trường

Mục đích và tác nhân. Tổng hợp dữ liệu đã ghi nhận trong một kỳ thành báo cáo có thể mở lại. Tác nhân: A01. Ca sử dụng tương ứng: UC10.

Điều kiện trước. Địa điểm hợp lệ và SQL Server sẵn sàng. Kỳ không có bản ghi vẫn có thể tạo báo cáo rỗng.

Đầu vào và giao diện. POST /api/baocao nhận JSON days là số nguyên 1, 7 hoặc 30 và location là mã danh mục. Nút Tạo và lưu báo cáo bị khóa trong lúc xử lý. Vị trí thao tác: UI07.

Luồng chính. 

1. Kiểm tra kiểu và giá trị kỳ báo cáo; lấy thời gian tạo và mốc đầu kỳ.

2. Đọc NguonDL cùng các CanhBao đúng mã địa điểm, trong khoảng đầu và cuối kỳ.

3. Chuẩn hóa giá trị, tính số bản ghi, min, max, trung bình phù hợp, số thiếu, số lần vượt ngưỡng và nhóm thời gian.

4. Lưu toàn bộ nội dung JSON trong BaoCaoMT rồi trả HTTP 201 kèm MaBaoCao; cập nhật màn hình và lịch sử.

Điều kiện sau và đầu ra. Báo cáo có địa điểm, kỳ, thời gian tạo, thống kê, dữ liệu nguồn và cảnh báo. Nội dung đã lưu giữ nguyên khi người sử dụng mở lại sau đó.

Luồng thay thế và ngoại lệ. Kỳ sai, số thực hoặc boolean trả 400. SQL lỗi trả 503. Nếu trình duyệt hết thời gian chờ, trạng thái chưa xác định việc lưu được xử lý bằng tải lại lịch sử; không coi timeout là chắc chắn chưa lưu.

Thiết kế và bằng chứng. environment_reports.py: build_report, ReportRepository.create, create_report_blueprint; static/reports.js. Đọc NguonDL và CanhBao; ghi BaoCaoMT.

Quy tắc và nghiệm thu. BR07, BR08, BR14. Kiểm thử: TC14, TC15.

## 5.12 FR11 Tra cứu và mở báo cáo đã lưu

Mục đích và tác nhân. Sử dụng lại đúng nội dung báo cáo đã tạo thay vì tính lại theo dữ liệu hiện tại. Tác nhân: A01. Ca sử dụng tương ứng: UC11.

Điều kiện trước. Người sử dụng đang ở màn hình báo cáo và địa điểm hợp lệ.

Đầu vào và giao diện. GET /api/baocao nhận location, limit và offset; mặc định limit=10, tối đa 50. Chọn Mở báo cáo gửi MaBaoCao trên đường dẫn và mã địa điểm trong query. Vị trí thao tác: UI07.

Luồng chính. 

1. Tải các báo cáo theo địa điểm, sắp mới nhất trước.

2. Nhấn Xem thêm để tăng offset và ghép các mục tiếp theo.

3. Khi mở một mã, repository tìm đồng thời theo MaBaoCao và MaDiaDiem.

4. Đọc NoiDung JSON đã lưu, kiểm tra mã địa điểm và dựng lại phần thống kê, biểu đồ cùng bảng dữ liệu.

Điều kiện sau và đầu ra. Nội dung hiển thị khớp snapshot báo cáo đã lưu. Mở lại không tạo báo cáo mới.

Luồng thay thế và ngoại lệ. Mã không tồn tại hoặc không thuộc địa điểm được yêu cầu trả 404. Lỗi mạng và lỗi SQL có thông báo riêng. Đổi nơi xóa báo cáo đang xem của nơi cũ.

Thiết kế và bằng chứng. ReportRepository.list và get; static/reports.js: openReport và phần lịch sử. Đọc BaoCaoMT; không ghi dữ liệu khi mở.

Quy tắc và nghiệm thu. BR01, BR07, BR14. Kiểm thử: TC15, TC16.

## 5.13 FR12 Xuất CSV và in báo cáo

Mục đích và tác nhân. Đưa nội dung báo cáo đang mở ra tệp dữ liệu hoặc bản in. Tác nhân: A01. Ca sử dụng tương ứng: UC12.

Điều kiện trước. Đã mở báo cáo hợp lệ. CSV yêu cầu báo cáo có bản ghi; in yêu cầu có báo cáo hiện tại.

Đầu vào và giao diện. Nút Tải CSV và In báo cáo. Dữ liệu đầu vào lấy từ báo cáo hiện tại trên trình duyệt, không đọc một kỳ khác từ API. Vị trí thao tác: UI07.

Luồng chính. 

1. Kiểm tra trạng thái báo cáo và địa điểm hiện tại.

2. Với CSV, tạo các cột dữ liệu và số cảnh báo tương ứng từng bản ghi; mã hóa UTF-8 có BOM, xử lý dấu phân cách và nội dung có thể bị hiểu là công thức.

3. Tạo Blob và tải tệp có tên chứa mã địa điểm cùng mã báo cáo.

4. Với in, gọi window.print; CSS in ẩn menu và chatbot. Người sử dụng có thể chọn máy in hoặc lưu PDF trong hộp thoại trình duyệt.

Điều kiện sau và đầu ra. CSV có 17 cột và nhận diện đúng báo cáo. Bản in sử dụng nội dung đang xem; máy chủ không cung cấp endpoint xuất PDF trong phiên bản này.

Luồng thay thế và ngoại lệ. Khi chưa có báo cáo hoặc đang bận, nút bị vô hiệu hóa. Báo cáo rỗng không xuất CSV. Hủy hộp thoại in không thay đổi báo cáo đã lưu.

Thiết kế và bằng chứng. static/reports.js: csvCell, trình xử lý reportCsv và reportPrint; quy tắc @media print trong CSS. Không ghi thêm vào cơ sở dữ liệu.

Quy tắc và nghiệm thu. BR07, BR08. Kiểm thử: TC17.

## 5.14 FR13 Gửi và điều khiển hội thoại

Mục đích và tác nhân. Cho phép trao đổi với Xanh Non trong cửa sổ chat nổi mà không rời chức năng đang xem. Tác nhân: A01. Ca sử dụng tương ứng: UC13.

Điều kiện trước. Widget đã sẵn sàng. Câu hỏi không rỗng và lịch sử đúng cấu trúc.

Đầu vào và giao diện. message tối đa 8.000 ký tự; history tối đa tám cặp user–assistant; location; stream; cờ learn_from_chat. Giao diện có mở, đóng, gửi, dừng, bắt đầu lại và tiếp tục khi câu trả lời bị cắt. Vị trí thao tác: UI08.

Luồng chính. 

1. Người sử dụng mở bong bóng, nhập câu hỏi và gửi; giao diện khóa lựa chọn địa điểm trong lúc tạo câu trả lời.

2. API kiểm tra dữ liệu, chuẩn bị snapshot và điều phối các nhánh trả lời.

3. Với stream, máy chủ phát status, delta và done hoặc error; widget ghép nội dung theo sự kiện.

4. Khi hoàn tất, lưu cặp hỏi đáp trong bộ nhớ của địa điểm, mở khóa thao tác và đánh dấu phản hồi mới nếu widget đang thu gọn.

Điều kiện sau và đầu ra. Câu trả lời hiển thị dạng văn bản an toàn. Thu gọn không xóa hội thoại; bắt đầu lại xóa ngữ cảnh tại giao diện. Không có hồ sơ hội thoại gắn tài khoản đăng nhập.

Luồng thay thế và ngoại lệ. HTTP 400 cho dữ liệu sai; 413 cho body quá lớn; 429 khi khóa sinh đang bận; 503 khi thiếu mô hình. Ngắt kết nối được truyền tới xử lý hủy, không biến câu dở thành một cặp lịch sử hoàn chỉnh.

Thiết kế và bằng chứng. static/chat.js; app.chat; chatbot.validate_chat, generate_reply và stream_reply; NativeChatbot.generate. Lịch sử thông thường nằm trong bộ nhớ trình duyệt; không có bảng ChatSession.

Quy tắc và nghiệm thu. BR09, BR11, BR14. Kiểm thử: TC18, TC19.

## 5.15 FR14 Giữ ngữ cảnh và đọc dữ liệu theo thời gian

Mục đích và tác nhân. Hiểu các câu nối tiếp ngắn và lấy đúng dữ liệu hiện tại hoặc dự báo cho nội dung đang trao đổi. Tác nhân: A01, E01. Ca sử dụng tương ứng: UC14.

Điều kiện trước. Có câu hỏi và lịch sử user–assistant hợp lệ. Thời gian xử lý dựa trên UTC+7.

Đầu vào và giao diện. Các cách nói như mai, ngày kia, tối, 18 giờ 30; câu nối tiếp như độ ẩm thì sao hoặc không khí nữa. Địa điểm có thể ở danh mục đang chọn hoặc được nêu trong câu hỏi. Vị trí thao tác: UI08.

Luồng chính. 

1. Xác định chủ đề và lấy các chi tiết ngữ cảnh từ lượt người sử dụng gần nhất còn liên quan.

2. Giữ hoặc thay địa điểm, ngày và giờ theo thông tin mới; câu hiện tại không tiếp tục dùng mốc dự báo cũ.

3. Nếu chưa rõ chủ đề hoặc thiếu ngày cho một giờ cụ thể, hỏi lại; nếu đủ, đọc nguồn thời tiết hoặc không khí phù hợp.

4. Tổng hợp các mẫu giờ có trong cửa sổ yêu cầu và trả đúng trường được hỏi, kèm tên nơi và mốc thời gian.

Điều kiện sau và đầu ra. Câu hỏi nối tiếp dùng cùng chủ đề khi có căn cứ. Dự báo thời tiết hiện có nhiệt độ và độ ẩm; dự báo không khí dùng dữ liệu Open-Meteo/CAMS. Yêu cầu 18:30 được gắn với khoảng dữ liệu giờ tương ứng.

Luồng thay thế và ngoại lệ. Nguồn thiếu hoặc chuỗi giờ không đủ thì không điền giá trị giả. Đổi sang chủ đề ngoài môi trường dừng kế thừa ngữ cảnh. Số trong câu trả lời cũ không được dùng làm phép đo mới.

Thiết kế và bằng chứng. chatbot.py: _dialogue_question, _consultation_reply, các nhánh weather/air; chat_time_context.py; chat_clarification.py; chat_weather_data.py; chat_air_data.py. Cache dự báo 600 giây theo nơi, tọa độ và ngày.

Quy tắc và nghiệm thu. BR03, BR09–BR11. Kiểm thử: TC20, TC21.

## 5.16 FR15 Giải thích và tư vấn từ tri thức có nguồn

Mục đích và tác nhân. Trả lời câu hỏi kiến thức, cách giảm tiếp xúc với bụi và các tình huống môi trường bằng nội dung có nguồn. Tác nhân: A01. Ca sử dụng tương ứng: UC15.

Điều kiện trước. Câu hỏi thuộc phạm vi hoặc là giao tiếp cơ bản và giới thiệu chức năng được hệ thống nhận biết.

Đầu vào và giao diện. Câu hỏi tự nhiên tiếng Việt, gồm các biến thể không dấu và câu ngắn. Người sử dụng có thể yêu cầu ngắn gọn, chi tiết hoặc nêu một hạn chế cụ thể như chưa có máy lọc. Vị trí thao tác: UI08.

Luồng chính. 

1. Chuẩn hóa tiếng Việt, nhận ý định và ưu tiên câu trả lời chuyên biệt đã kiểm tra.

2. Tìm nội dung phù hợp trong knowledge.json theo câu mẫu, chủ đề hoặc chỉ mục TF-IDF ký tự.

3. Nếu đã có đáp án chắc chắn, trả trực tiếp; nếu cần mô hình sinh, đưa tri thức và dữ liệu liên quan vào ngữ cảnh.

4. Làm sạch nội dung trước khi hiển thị, hạn chế lặp số liệu không liên quan và phần hướng dẫn nội bộ.

Điều kiện sau và đầu ra. Trợ lý giải thích khái niệm, đưa cách thực hiện và lý do trong phạm vi nguồn có sẵn. Kho khảo sát có 26 tài liệu; các bộ chat tổng quát không được dùng như nguồn xác nhận kiến thức AQI.

Luồng thay thế và ngoại lệ. Ngoài phạm vi trả câu giới thiệu cố định. Nội dung chưa đủ căn cứ có thể được hỏi lại hoặc thông báo chưa có dữ liệu cần thiết. Không có chứng nhận độ chính xác chuyên môn chung từ các bài thử hiện có.

Thiết kế và bằng chứng. chat_scope.py; chat_knowledge.py: practical_answer, concept_answer, retrieve; chat_output.py; chatbot._generate_raw. Kho data/xanhnon/knowledge.json; không có cơ sở dữ liệu vector riêng.

Quy tắc và nghiệm thu. BR10–BR12. Kiểm thử: TC22, TC23.

## 5.17 FR16 Tiếp nhận góp ý và câu hỏi mới

Mục đích và tác nhân. Ghi nhận phản hồi hữu ích và biến thể câu hỏi phù hợp để sử dụng trong quy trình cải thiện có kiểm tra. Tác nhân: A01; A02 duyệt bằng công cụ. Ca sử dụng tương ứng: UC16.

Điều kiện trước. Hội thoại có ngữ cảnh cần thiết. Nguồn gửi đáp ứng kiểm tra Origin đối với thao tác ghi; tự học được bật cho các yêu cầu phù hợp.

Đầu vào và giao diện. Tin nhắn xác nhận hữu ích đi qua /api/chat; câu hỏi mới được quan sát khi learn_from_chat=true. API POST /api/chat/feedback tồn tại cho payload góp ý nhưng giao diện không có bộ nút đánh giá riêng. Vị trí thao tác: UI08.

Luồng chính. 

1. Nhận biết lời xác nhận hữu ích và lưu payload có fingerprint để tránh ghi trùng.

2. Với câu hỏi mới, loại dữ liệu nhạy cảm, nội dung ngoài phạm vi và câu thuộc tập kiểm tra; tạo khóa từ câu hỏi cùng ngữ cảnh người dùng.

3. Chỉ gắn learned nếu đáp án khớp tài liệu ổn định có nguồn chính thức, đúng phiên bản tri thức và chính sách.

4. Các câu cần số liệu hoặc nguồn được lưu ở trạng thái chờ phù hợp; góp ý chỉ được xuất thành dữ liệu học sau kiểm tra nội dung và riêng tư.

Điều kiện sau và đầu ra. feedback.sqlite3 lưu góp ý và trạng thái duyệt; questions.sqlite3 lưu câu hỏi, số lần gặp và liên kết tài liệu. Trọng số mô hình không thay đổi sau mỗi tin nhắn.

Luồng thay thế và ngoại lệ. Không đọc được kho học không làm dừng hội thoại chính. Nguồn gửi không hợp lệ trả 403; payload góp ý sai trả 400; lỗi lưu góp ý trả 503. Không tái sử dụng một đáp án learned khi hash tri thức hoặc chính sách đã đổi.

Thiết kế và bằng chứng. chat_feedback.FeedbackStore; record_helpful_message; chat_learning.ConversationLearner.observe; feedback_training_data.py. Hai cơ sở dữ liệu SQLite độc lập với SQL Server.

Quy tắc và nghiệm thu. BR09, BR12. Kiểm thử: TC24, TC25.

## 5.18 FR17 Theo dõi trạng thái mô hình

Mục đích và tác nhân. Phân biệt chatbot chưa nạp, đang nạp, sẵn sàng, gặp lỗi hoặc đang bị khóa bởi huấn luyện. Tác nhân: A02; giao diện đọc khi cần. Ca sử dụng tương ứng: UC17.

Điều kiện trước. Flask đang chạy. Kiểm tra trạng thái không yêu cầu sinh một câu trả lời.

Đầu vào và giao diện. GET /api/chat/status không có payload. Trạng thái phụ thuộc runtime và khóa huấn luyện. Vị trí thao tác: API và công cụ vận hành.

Luồng chính. 

1. Đọc trạng thái runtime đang giữ trong tiến trình.

2. Kiểm tra huấn luyện đang hoạt động và cấu hình cho phép sử dụng đồng thời.

3. Trả state và, nếu phù hợp, background_training.

4. Người vận hành đối chiếu thông tin với log native, khóa huấn luyện và manifest bản phát hành.

Điều kiện sau và đầu ra. JSON có các trạng thái cold, loading, ready, training hoặc error. ready chỉ xác nhận runtime đã nạp, không đánh giá chất lượng câu trả lời hoặc độ mới dữ liệu.

Luồng thay thế và ngoại lệ. Máy chủ không chạy thì không nhận được phản hồi HTTP. Runtime nạp lỗi có log và trạng thái error; các nhánh trả lời bằng quy tắc hoặc tri thức có thể hoạt động độc lập với phần sinh mô hình.

Thiết kế và bằng chứng. app.chat_status; chatbot.runtime_status, _load_runtime, warm_up_chatbot; native_chatbot.py; models/xanhnon-active.json.

Quy tắc và nghiệm thu. BR09, BR12. Kiểm thử: TC26.

## 5.19 FR18 Chuẩn bị dữ liệu và huấn luyện cục bộ

Mục đích và tác nhân. Tạo bộ dữ liệu đã lọc và mô hình ứng viên, tách khỏi bản đang phục vụ hội thoại. Tác nhân: A02. Ca sử dụng tương ứng: UC18.

Điều kiện trước. Có bộ dữ liệu hợp lệ, mô hình nền hoặc checkpoint có thể sử dụng, đủ RAM và ổ đĩa; không trùng phiên huấn luyện.

Đầu vào và giao diện. JSONL hội thoại, manifest nguồn, dữ liệu cảm biến đã chuyển thành tình huống và góp ý đã duyệt. Tham số học được truyền cho các script; không có màn hình quản trị huấn luyện trên web. Vị trí thao tác: Công cụ dòng lệnh và lịch chạy Windows.

Luồng chính. 

1. Kiểm tra nguồn, hash, trùng câu và giao nhau giữa các tập; chuẩn bị train và validation.

2. Token hóa toàn bộ mẫu và chỉ tính loss trên token phía assistant.

3. Kiểm tra RAM, ổ đĩa và khóa chạy; huấn luyện LoRA khi đáp ứng điều kiện.

4. Lưu checkpoint, đánh giá ứng viên và xuất GGUF riêng. Bản dùng trong ứng dụng được xác định bởi manifest phát hành, không tự coi mọi ứng viên là bản đã áp dụng.

Điều kiện sau và đầu ra. Các sản phẩm gồm JSONL đã lọc, báo cáo tiền kiểm tra, checkpoint hoặc adapter, kết quả đánh giá và bản xuất. Hồ sơ ngày 27/10 ghi nhận 452 mẫu train, 124 validation đã tiền kiểm tra; lịch tự động thực tế đang chờ bộ nhớ.

Luồng thay thế và ngoại lệ. Thiếu RAM chuyển waiting_for_memory. Dữ liệu không hợp lệ, nguồn trùng hoặc mất trạng thái tối ưu không được coi là một lần tiếp tục học thành công. Khôi phục checkpoint gộp chỉ hỗ trợ đợt LoRA mới, không phục dựng optimizer cũ.

Thiết kế và bằng chứng. daily_train_xanhnon.py; train_xanhnon.py; training_state.py; training_resume.py; export_xanhnon.py; model_release.py. Lịch XanhNon-Train-Reviewed-Data và các manifest cục bộ.

Quy tắc và nghiệm thu. BR12. Kiểm thử: TC27, TC28.

# CHƯƠNG 6  MÔ HÌNH HÓA HỆ THỐNG

## 6.1 Ranh giới hệ thống và sơ đồ ngữ cảnh

Ranh giới hệ thống bao gồm phần giao diện, API, lưu trữ nghiệp vụ, chatbot và công cụ học trên máy. Người sử dụng cung cấp địa điểm, câu hỏi và kỳ báo cáo; người vận hành cung cấp lệnh cùng dữ liệu đã chuẩn bị. Open-Meteo, NoiseCapture và OpenStreetMap là hệ thống bên ngoài. SQL Server, SQLite và mô hình cục bộ nằm trong ranh giới thiết kế, không phải tác nhân người dùng.



Hình 2. Sơ đồ ngữ cảnh của hệ thống

## 6.2 DFD mức 0

DFD mức 0 tổ chức thành năm tiến trình. Tiến trình 1.0 phục vụ địa điểm và bản đồ; 2.0 cập nhật và đánh giá; 3.0 tạo báo cáo; 4.0 hội thoại và góp ý; 5.0 chuẩn bị và huấn luyện. Các kho D1–D8 là nhóm lưu trữ logic, không mặc định tương ứng một bảng. Cụ thể, D3 gồm CanhBao và PhanTichAI; D7 gồm hai cơ sở dữ liệu SQLite; D8 gồm JSONL, manifest và tệp mô hình.



Hình 3. DFD mức 0 phần tra cứu giám sát và báo cáo



Hình 4. DFD mức 0 phần hội thoại và huấn luyện

DFD mức 0 được trình bày ở hai hình cùng cấp; tác nhân và kho được lặp lại khi cần để các dòng dữ liệu rõ ràng. Tiến trình 4.0 đọc D2 và nguồn dự báo theo ngữ cảnh, không yêu cầu mỗi câu hỏi phải tạo snapshot SQL. Ảnh nền bản đồ do trình duyệt trao đổi trực tiếp với OpenStreetMap trong phạm vi 1.0. Các kho ghép trong một khung là nhóm logic, không bổ sung bảng mới. Tất cả thao tác đọc ghi kho đều đi qua tiến trình xử lý.

## 6.3 DFD mức 1 của cập nhật dữ liệu



Hình 5. DFD mức 1 của tiến trình cập nhật và đánh giá

Đầu vào của tiến trình 2.0 là mã địa điểm và yêu cầu cập nhật; đầu ra là snapshot hoặc lỗi. Khi phân rã, các bước 2.1–2.5 giữ nguyên hai đầu giao tiếp đó. Nhánh cache trả cùng cấu trúc JSON với nhánh lấy mới. Lưu bản ghi, cảnh báo và phân tích chỉ diễn ra khi đã có dữ liệu nguồn sử dụng được và việc commit thành công.

Bảng 9. Đặc tả các tiến trình con của cập nhật



Tiến trình | Đầu vào | Xử lý và đầu ra

2.1 Xác định địa điểm | location | Kiểm tra danh mục; trả cấu hình tọa độ hoặc lỗi 400.

2.2 Kiểm tra cache | Mã địa điểm và thời gian hiện tại | Khóa theo nơi; kiểm tra bộ nhớ và ChiTiet SQL. Còn hạn thì trả snapshot.

2.3 Nhận dữ liệu | Tọa độ và tham chiếu tiếng ồn | Gọi nguồn thời tiết, không khí; tổng hợp tiếng ồn; giữ thời điểm nguồn.

2.4 Đánh giá | Dictionary DuLieu | Sinh cảnh báo, phân tích AQI và trạng thái RF; RF lỗi không chặn luồng dữ liệu.

2.5 Lưu và trả | Dữ liệu cùng kết quả | Ghi các bảng liên quan trong giao dịch; cập nhật JSON; trả snapshot sau commit.

## 6.4 Use Case tổng thể và quan hệ giữa các ca sử dụng



Hình 6. Use Case tổng thể theo nhóm nghiệp vụ

Các UC được gom theo khoảng mã trong sơ đồ để tránh lặp 18 hình bầu dục trên một trang. Đặc tả riêng của từng UC sử dụng cùng hậu tố với FR ở chương 5. Cập nhật dữ liệu có thể dẫn tới phát sinh cảnh báo; việc xem lịch sử cảnh báo là một mục tiêu riêng. Xuất CSV và in chỉ được thực hiện khi đã có báo cáo hiện tại. Giao tiếp xã hội và câu ngoài phạm vi là các nhánh của UC13, không tạo thành chức năng quản lý tài khoản.

## 6.5 Luồng tra cứu môi trường theo địa điểm



Hình 7. Activity của luồng chọn địa điểm và tra cứu

Luồng kết thúc khi các phần đang hiển thị đã nhận dữ liệu của nơi mới hoặc thông báo lỗi tương ứng. Nếu GPS không được cấp quyền, người sử dụng quay về danh sách. Nếu API không tải được, giao diện giữ khả năng thử lại. Các kết quả đến muộn được kiểm tra bằng phiên yêu cầu và mã địa điểm trước khi cập nhật màn hình.

## 6.6 Các tương tác tuần tự quan trọng



Hình 8. Sequence cập nhật snapshot và ghi dữ liệu

Nhánh lấy nguồn trong hình chỉ chạy khi kiểm tra cache không trả được kết quả còn hạn. Bộ dữ liệu, cảnh báo và phân tích được ghi trong cùng khối giao dịch. Sau đó giao diện đọc lịch sử và cảnh báo bằng các yêu cầu độc lập để một phần lỗi không che lấp toàn bộ màn hình.



Hình 9. Sequence điều phối hội thoại và phản hồi SSE

Bước trả trực tiếp và bước gọi NativeChatbot là hai nhánh thay thế. Quy tắc và tri thức đã xác định được câu trả lời thì không gọi mô hình sinh. Bước Dừng từ widget hủy quá trình nhận phản hồi; bộ xử lý phía máy chủ chuyển tín hiệu hủy tới runtime khi kết nối đóng.



Hình 10. Sequence tạo và lưu báo cáo môi trường

ReportRepository là lớp chịu trách nhiệm lấy dữ liệu theo kỳ và lưu snapshot báo cáo. build_report thực hiện tính toán trên dữ liệu đã đọc. Mã báo cáo chỉ được trả cùng phản hồi thành công sau khi lệnh lưu được commit; thao tác mở lại sử dụng NoiDung đã lưu, không gọi lại build_report.

## 6.7 Đối tượng miền nghiệp vụ

Bảng 10. Đối tượng miền và bất biến dữ liệu



Đối tượng | Trách nhiệm và thuộc tính chính | Bất biến hoặc vòng đời

Địa điểm | Nhận diện nơi tra cứu; mã, tên, nhóm, hai bộ tọa độ tham chiếu | Mã thuộc danh mục; tọa độ thời tiết và tiếng ồn có thể khác nhau.

Snapshot môi trường | Gắn bộ số liệu, nguồn, thời điểm lấy và kết quả với Manguon | Sau commit là bản ghi lịch sử; thiếu trường giữ ý nghĩa chưa có dữ liệu.

Cảnh báo | Ghi loại chỉ số, mức và nội dung tại lần cập nhật | Bắt buộc có NguonDL cha; được lưu và tra cứu, không có trạng thái giao việc.

Phân tích môi trường | Lưu kết luận và diễn giải được build_analysis tạo | Mỗi lần cập nhật hiện chèn một hàng; schema cho phép nhiều hàng trên một nguồn.

Báo cáo | Đóng gói kết quả theo kỳ và địa điểm | Nội dung là snapshot; mở lại không thay đổi theo bản ghi mới.

Mẫu lưới AQI | Lưu tọa độ, thời gian lấy, thời gian nguồn và AQI | Mã vị trí là khóa tra cứu logic; mỗi lần lấy có MaMau riêng.

Hội thoại đang mở | Giữ các cặp hỏi đáp và địa điểm của widget | Tồn tại trong bộ nhớ trình duyệt; tách theo địa điểm, giới hạn tám cặp gửi lên API.

Góp ý và câu hỏi học | Lưu dấu vết tiếp nhận, nguồn liên kết và trạng thái kiểm tra | Câu hỏi learned phụ thuộc hash tri thức; góp ý approved phải qua kiểm tra riêng tư và nội dung.

## 6.8 Sơ đồ lớp triển khai



Hình 11. Class Diagram các lớp triển khai nghiệp vụ

LocationStore phụ trách tạo và đồng bộ metadata địa điểm. ReportRepository phụ trách truy vấn và lưu báo cáo; nó nhận ensure_locations dưới dạng hàm phụ thuộc, trong ứng dụng hàm này được cấp từ LocationStore. AirMapRepository giữ cache và các thao tác đọc ghi mẫu lưới. NoiseData quản lý tệp NoiseCapture dùng chung. NativeChatbot sở hữu tiến trình suy luận cục bộ và đóng tiến trình đó khi kết thúc. FeedbackStore đóng gói thao tác SQLite cho góp ý.



Hình 12. Các phụ thuộc của lớp học từ câu hỏi mới

ConversationLearner sử dụng các hàm của chat_knowledge để tìm nội dung ổn định có nguồn, sau đó lưu câu hỏi và liên kết tài liệu trong SQLite. Việc thay đổi phiên bản tri thức làm mất hiệu lực của liên kết học cũ cho đến khi được kiểm tra lại. Quan hệ trong hình là phụ thuộc xử lý và đọc ghi dữ liệu, không phải quan hệ kế thừa.

## 6.9 Trách nhiệm và quan hệ giữa các thành phần

Các repository có trách nhiệm tập trung đối với một nhóm lưu trữ; hàm build_report không phụ thuộc Flask nên có thể kiểm thử bằng danh sách hàng dữ liệu. Đây là biểu hiện phân tách trách nhiệm trong thiết kế hiện tại. Ngược lại, app.py vẫn giữ điều phối cập nhật, giao dịch và một số quy tắc đánh giá; chatbot.py giữ phần lớn quyết định nhánh hội thoại. Báo cáo không mô tả các module này như một tập microservice hoặc một hệ lớp miền hoàn chỉnh.

Quan hệ phụ thuộc xuất hiện khi một bộ xử lý gọi hàm hoặc dùng đối tượng khác. Quan hệ sở hữu thể hiện rõ ở NativeChatbot với tiến trình con; vòng đời tiến trình được đối tượng tạo và kết thúc. Các lớp nghiệp vụ nêu trên không có cây kế thừa chung. Số lượng một–nhiều của snapshot và cảnh báo là quan hệ dữ liệu trong ERD, không phải bằng chứng rằng mã Python đã định nghĩa các lớp NguonDL và CanhBao.

## 6.10 Vòng đời runtime chatbot



Hình 13. State Diagram của runtime chatbot

Runtime bắt đầu ở cold, chuyển loading khi nạp và ready khi thành công; nạp thất bại chuyển error. Trạng thái trả ra có thể là training khi khóa huấn luyện không cho phép suy luận đồng thời. Với cấu hình cho phép dùng chung tài nguyên, phản hồi giữ trạng thái runtime và thêm background_training. Việc nhận biết ready không kiểm tra khả năng trả lời đúng mọi câu hỏi.

# CHƯƠNG 7  THIẾT KẾ KIẾN TRÚC PHẦN MỀM

## 7.1 Kiến trúc tổng thể

Ứng dụng là một hệ Flask triển khai tập trung theo module. Giao diện và API được phục vụ từ cùng tiến trình; bản đồ, báo cáo và góp ý được tách thành blueprint. SQL Server giữ dữ liệu nghiệp vụ; các tệp mô hình, tri thức và SQLite nằm trên máy chạy ứng dụng. Cách sử dụng blueprint ở đây là phân nhóm chức năng trong một ứng dụng Flask [T05].



Hình 14. Component Diagram của ứng dụng

## 7.2 Phân chia thành phần

Bảng 11. Trách nhiệm các thành phần kiến trúc



Thành phần | Trách nhiệm | Giao tiếp chính

Giao diện | Điều hướng, chọn địa điểm, khóa trạng thái bận, dựng DOM và đồ thị | HTTP JSON, SSE, sự kiện locationchange

Routes giám sát | Điều phối nguồn, cache, giao dịch và truy vấn lịch sử | app.py và pyodbc

Bản đồ | Tạo lưới, chia sẻ cache mẫu, trả ma trận theo vùng | AirMapRepository; Open-Meteo; SQL

Báo cáo | Đọc dữ liệu theo kỳ, tính thống kê và lưu nội dung | build_report; ReportRepository

Hội thoại | Giải nghĩa ý định, ngữ cảnh, nguồn dữ liệu, tri thức và đầu ra | chatbot; các module chat_*

Suy luận native | Quản lý tiến trình mô hình và nhận token sinh | NativeChatbot; HTTP loopback

Dữ liệu học | Ghi góp ý, biến thể câu hỏi và dữ liệu đã duyệt | FeedbackStore; ConversationLearner; SQLite

Huấn luyện | Lọc tập học, LoRA, kiểm tra, xuất bản ứng viên | Các script train, evaluate, export và manifest

## 7.3 Hợp đồng trao đổi dữ liệu

Các API dữ liệu trả JSON, trong đó lỗi nghiệp vụ thường có trường loi. Các mã 400, 404, 413, 429, 502 và 503 được dùng tùy tình huống cụ thể. Luồng chat sử dụng cùng endpoint với cờ stream=true và kiểu text/event-stream. Client xử lý từng sự kiện, vì vậy phản hồi sinh dần không được coi như một JSON duy nhất.

Snapshot giám sát bao gồm định danh nguồn, thời điểm lấy, địa điểm, bộ giá trị nguồn, kết quả RF, danh sách cảnh báo và phân tích. Nội dung này cũng được lưu trong NguonDL.ChiTiet. Các API lịch sử trả hàng dữ liệu dạng danh sách; báo cáo trả cả thống kê và dữ liệu nguồn đã dùng. Chi tiết tham số và giới hạn được trình bày ở phụ lục A.

## 7.4 Xử lý đồng thời và tính nhất quán

Máy chủ dùng khóa riêng cho từng địa điểm khi cập nhật snapshot. Điều này ngăn các yêu cầu cùng nơi chạy đồng thời trong một tiến trình, đồng thời cho phép tách cache giữa các nơi. Bản đồ dùng khóa của AirMapRepository để chia sẻ mẫu; NoiseData dùng một khóa để quản lý tệp chung. Khóa sinh hội thoại hạn chế chồng phiên mô hình. Đây là cơ chế trong bộ nhớ của tiến trình, không phải khóa phân tán giữa nhiều máy chủ.

Ở giao diện, số phiên yêu cầu và AbortController được dùng khi đổi địa điểm. Báo cáo và hội thoại cũng kiểm tra mã nơi đang chọn trước khi trình bày. Nút thao tác được khóa trong những bước có thể gây lẫn ngữ cảnh, ví dụ đổi địa điểm trong lúc gửi câu hỏi hoặc tạo báo cáo.

## 7.5 Mô hình triển khai hiện tại



Hình 15. Deployment Diagram trên máy chạy dự án

Flask được cấu hình lắng nghe 127.0.0.1:5000, debug=False và không dùng reloader. NativeChatbot mở tiến trình llama.cpp trên 127.0.0.1 với cổng động; luồng giao tiếp mô hình không đi qua dịch vụ ChatGPT. SQL Server được kết nối bằng ODBC, mặc định dùng xác thực Windows khi không cấu hình tài khoản SQL. Internet phục vụ nguồn môi trường và nền bản đồ, còn trọng số mô hình nằm cục bộ.

# CHƯƠNG 8  THIẾT KẾ CƠ SỞ DỮ LIỆU

## 8.1 Mô hình logic và mô hình vật lý

Mô hình dữ liệu nghiệp vụ lấy địa điểm và snapshot làm trục. Một địa điểm có nhiều snapshot và nhiều báo cáo; một snapshot có thể sinh nhiều cảnh báo. Phân tích và cảnh báo tham chiếu nguồn đã ghi. Mẫu bản đồ được tổ chức theo tọa độ lưới, có thể dùng chung giữa các địa điểm và vùng nhìn nên không có quan hệ khóa ngoại đến một địa điểm cụ thể.

Trong lược đồ SQL hiện tại, chỉ hai quan hệ được khai báo bằng FOREIGN KEY: CanhBao.Manguon và PhanTichAI.Manguon cùng tham chiếu NguonDL.Manguon. MaDiaDiem trong NguonDL và BaoCaoMT được dùng để liên kết ở tầng ứng dụng nhưng chưa khai báo FK trong các tệp schema. ERD dưới đây dùng nét đứt cho các liên kết logic đó, tránh thể hiện như ràng buộc vật lý đã tồn tại [T06].



Hình 16. ERD sáu bảng nghiệp vụ và loại liên kết

Trong phạm vi dữ liệu mới do ứng dụng tạo, MaDiaDiem luôn được lấy từ danh mục hợp lệ. Cột này vẫn cho phép NULL ở NguonDL để tương thích dữ liệu cũ. Phần migration chỉ gắn hanoi cho các hàng cũ nhận diện rõ nguồn Hà Nội; các hàng khác không được gán địa điểm suy đoán. CanhBao và PhanTichAI bắt buộc có Manguon; NguonDL không bắt buộc phải có cảnh báo. Mỗi lượt cập nhật hiện tạo một phân tích, trong khi ràng buộc vật lý cho phép 0 đến nhiều phân tích trên một nguồn.

## 8.2 Từ điển bảng DiaDiem

Bảng 12. Cấu trúc bảng DiaDiem



Cột | Kiểu và ràng buộc | Ý nghĩa

MaDiaDiem | VARCHAR(64), PK | Mã ổn định trong danh mục.

Ten | NVARCHAR(200), NOT NULL | Tên hiển thị.

Nhom | NVARCHAR(120), NOT NULL | Nhóm lựa chọn địa điểm.

ViDo và KinhDo | FLOAT, NOT NULL | Tọa độ lấy dữ liệu thời tiết và không khí.

ViDoTiengOn và KinhDoTiengOn | FLOAT, NOT NULL | Tọa độ tham chiếu dữ liệu tiếng ồn.

TenKhuVucTiengOn | NVARCHAR(200), NOT NULL | Tên khu vực tiếng ồn theo nguồn.

ChiTiet | NVARCHAR(MAX), NULL | Metadata JSON của địa điểm.

locations.json là danh mục cấu hình được ứng dụng đọc khi khởi động. LocationStore.ensure_schema đưa các thuộc tính tương ứng vào DiaDiem theo cơ chế cập nhật hoặc thêm. Bảng này không có màn hình CRUD địa điểm; việc đồng bộ không biến các mục thành trạm cảm biến.

## 8.3 Từ điển bảng NguonDL

Bảng 13. Cấu trúc bảng NguonDL



Cột | Kiểu và ràng buộc | Ý nghĩa

Manguon | INT IDENTITY, PK | Định danh snapshot.

TenNguon | NVARCHAR(100), NOT NULL | Tên nguồn gắn với địa điểm.

ThoiGian | DATETIME, NOT NULL | Thời điểm ứng dụng lấy và lưu dữ liệu.

PM25 và PM10 | DECIMAL(6,2), NULL | Nồng độ bụi, µg/m³.

NhietDo | DECIMAL(5,2), NULL | Nhiệt độ, °C.

DoAm | DECIMAL(5,2), NULL | Độ ẩm tương đối, %.

TiengOn | DECIMAL(6,2), NULL | Giá trị tổng hợp tiếng ồn, dBA.

MaDiaDiem | VARCHAR(64), NULL | Mã liên kết địa điểm ở tầng ứng dụng.

ChiTiet | NVARCHAR(MAX), NULL | Snapshot JSON gồm dữ liệu nguồn và kết quả.

Thời gian nguồn thời tiết, nguồn không khí, thông tin số ô và thời gian đo tiếng ồn, các khí bổ sung cùng US AQI nằm trong ChiTiet. Các giá trị hiển thị thường xuyên cũng được lưu ở cột quan hệ để truy vấn lịch sử và tổng hợp. Việc lưu song song là chủ đích lưu snapshot và phục vụ truy vấn; hai phần được ghi trong cùng giao dịch cập nhật.

## 8.4 Từ điển bảng CanhBao và PhanTichAI

Bảng 14. Cấu trúc bảng CanhBao



Cột | Kiểu và ràng buộc | Ý nghĩa

Macanhbao | INT IDENTITY, PK | Mã cảnh báo.

Manguon | INT, NOT NULL, FK | Nguồn snapshot gây cảnh báo.

LoaiCanhBao | NVARCHAR(100), NULL | Tên thông số.

MucDo | NVARCHAR(50), NULL | Trung bình hoặc Cao theo xử lý ứng dụng.

NoiDung | NVARCHAR(255), NULL | Thông tin giá trị và ngưỡng.

ThoiGian | DATETIME, NOT NULL | Thời gian tạo cảnh báo.

Bảng 15. Cấu trúc bảng PhanTichAI



Cột | Kiểu và ràng buộc | Ý nghĩa

Maphantich | INT IDENTITY, PK | Mã hàng phân tích.

Manguon | INT, NOT NULL, FK | Snapshot được đánh giá.

KetQua | NVARCHAR(100), NULL | Mức chất lượng không khí.

NhanXet | NVARCHAR(255), NULL | Diễn giải từ quy tắc AQI.

KhuyenNghi | NVARCHAR(255), NULL | Nội dung gợi ý do build_analysis chọn.

ThoiGian | DATETIME, NOT NULL | Thời gian lưu phân tích.

Lược đồ không có cột người xử lý, thời gian xác nhận hoặc trạng thái đóng cảnh báo. Thao tác hiện tại là ghi nhận và tra cứu sự kiện. Tên bảng PhanTichAI được giữ theo dự án; cơ chế tạo dữ liệu trong bảng là hàm quy tắc, tách khỏi việc chatbot sinh văn bản.

## 8.5 Từ điển bảng BaoCaoMT và MauBanDoKhongKhi

Bảng 16. Cấu trúc bảng BaoCaoMT



Cột | Kiểu và ràng buộc | Ý nghĩa

MaBaoCao | INT IDENTITY, PK | Mã báo cáo.

MaDiaDiem | VARCHAR(64), NOT NULL; mặc định hanoi | Mã địa điểm của báo cáo.

TieuDe | NVARCHAR(200), NOT NULL | Tên báo cáo.

TuNgay và DenNgay | DATETIME2, NOT NULL | Khoảng dữ liệu được tổng hợp.

ThoiGianTao | DATETIME2, NOT NULL | Thời điểm tạo snapshot báo cáo.

SoNgay | INT, NOT NULL | Kỳ 1, 7 hoặc 30 do API kiểm tra.

SoBanGhi và SoCanhBao | INT, NOT NULL | Tổng số bản ghi và cảnh báo trong kỳ.

NoiDung | NVARCHAR(MAX), NOT NULL | JSON đầy đủ của báo cáo đã tạo.

Bảng 17. Cấu trúc bảng MauBanDoKhongKhi



Cột | Kiểu và ràng buộc | Ý nghĩa

MaMau | INT IDENTITY, PK | Mã lần lấy mẫu.

MaViTri | VARCHAR(64), NOT NULL | Khóa tra cứu điểm tọa độ; không là FK địa điểm.

ViDo và KinhDo | FLOAT, NOT NULL | Tọa độ điểm lưới yêu cầu.

ThoiGianLay | DATETIME2, NOT NULL | Thời điểm ứng dụng lấy mẫu.

ThoiGianNguon | DATETIME2, NULL | Thời điểm do nguồn không khí cung cấp.

US_AQI và PM25 | FLOAT, NULL | Giá trị mẫu mô hình.

ChiTiet | NVARCHAR(MAX), NOT NULL | JSON gắn tọa độ và giá trị nguồn.

## 8.6 Kho góp ý và kho học câu hỏi trong SQLite

Hai cơ sở SQLite có phạm vi riêng, không khai báo khóa ngoại sang SQL Server. feedback chứa một hàng cho mỗi payload có fingerprint duy nhất; questions dùng question_key làm khóa chính. document_id trong questions tham chiếu mã tài liệu trong JSON ở cấp ứng dụng, không phải một FK tới bảng SQL.

Bảng 18. Các trường của hai kho SQLite



Kho | Các trường và vai trò

feedback | id INTEGER PK; fingerprint TEXT UNIQUE NOT NULL; created_at, payload, model và status TEXT NOT NULL; review, reviewed_at TEXT cho phép trống. status mặc định pending; công cụ duyệt dùng approved hoặc rejected.

questions | question_key TEXT PK; question và context_user TEXT NOT NULL; status TEXT NOT NULL; document_id, variant TEXT; knowledge_hash và policy TEXT NOT NULL; created_at, last_seen TEXT NOT NULL; seen_count INTEGER NOT NULL.

## 8.7 Chuẩn hóa và lưu snapshot

Ở phần dữ liệu quan hệ, mỗi bảng có khóa chính đơn và lưu các thuộc tính của chính thực thể đó. Các thuộc tính cảnh báo được tách khỏi snapshot để biểu diễn quan hệ một–nhiều; metadata địa điểm được tách thành DiaDiem. Với các cột quan hệ được liệt kê, không có nhóm thuộc tính lặp và không có khóa ghép làm phát sinh phụ thuộc bộ phận. Việc phân tích dạng chuẩn được giới hạn ở cấu trúc quan hệ, không xem JSON lồng nhau là một tập cột đã chuẩn hóa.

NguonDL.ChiTiet và BaoCaoMT.NoiDung giữ nội dung snapshot phục vụ khôi phục cache và mở lại báo cáo. Một số thuộc tính được lặp có chủ đích trong cột và JSON, vì vậy không mô tả toàn bộ thiết kế là một lược đồ thuần 3NF không dư thừa. Nội dung JSON được kiểm tra ở mã Python và ghi bằng tham số; các tệp schema không khai báo CHECK ISJSON hay CHECK cho khoảng độ ẩm và kỳ báo cáo.

## 8.8 Chỉ mục tính toàn vẹn và chống trùng

Bảng 19. Chỉ mục và cơ chế tra cứu hiện có



Đối tượng | Cơ chế | Phục vụ

NguonDL | IX_NguonDL_DiaDiem_ThoiGian trên MaDiaDiem, ThoiGian DESC, Manguon DESC | Bản gần nhất và lịch sử theo nơi.

BaoCaoMT | IX_BaoCaoMT_ThoiGianTao; IX_BaoCaoMT_DiaDiem | Danh sách báo cáo mới nhất và phân trang theo địa điểm.

MauBanDoKhongKhi | IX_MauBanDoKK_ViTri_ThoiGian trên MaViTri, ThoiGianLay DESC, MaMau DESC | Đọc mẫu mới nhất của một điểm trong giờ.

Góp ý | fingerprint duy nhất và INSERT OR IGNORE | Không ghi lặp cùng payload và phiên bản mô hình.

Câu hỏi học | question_key và hash của câu hỏi cùng ngữ cảnh | Tăng số lần gặp trên hàng đã có.

Snapshot và mẫu bản đồ | Khóa trong tiến trình, thời hạn cache và đọc lại SQL | Giảm bản ghi lặp do yêu cầu đồng thời; không là UNIQUE theo thời gian nguồn.

Khóa ngoại bảo vệ sự tồn tại của snapshot cha đối với cảnh báo và phân tích. Hệ thống không có API xóa snapshot, xóa địa điểm hoặc xóa báo cáo. Các quy tắc nghiệp vụ như kỳ báo cáo hợp lệ, giới hạn lưới và chuẩn dữ liệu đầu vào nằm trong xử lý ứng dụng. Cơ chế cache ngăn phần lớn lần lấy lại trong thời hạn, nhưng schema không cấm hai snapshot khác nhau có cùng thời gian nguồn.

# CHƯƠNG 9  THIẾT KẾ GIAO DIỆN VÀ TƯƠNG TÁC NGƯỜI DÙNG

## 9.1 Cấu trúc điều hướng và luồng màn hình

Ứng dụng sử dụng một trang HTML và chuyển phần nội dung theo hash. Tổng quan gồm ba khu vực: địa điểm đang giám sát, chỉ số môi trường và bản đồ. Các chức năng còn lại được mở từ menu để giữ trang tổng quan ngắn. Nút chuông và chatbot là hai phần nổi dùng chung trên các màn hình; chúng không tạo thêm mục dài trong trang chính.

Bảng 20. Danh mục màn hình và quan hệ điều hướng



Mã | Màn hình và đường dẫn | Điều hướng và ca sử dụng

UI01 | Tổng quan /#overview | Menu hoặc thương hiệu về tổng quan; UC01–04, UC05–06.

UI02 | Chỉ số /#air | Menu Chỉ số môi trường; quay lại tổng quan; UC04.

UI03 | Bản đồ /#environmentMap | Menu Bản đồ chất lượng không khí; UC05–06.

UI04 | Xu hướng /#trends | Menu Xu hướng dữ liệu; UC07.

UI05 | Phân tích /#insights | Menu Phân tích và tư vấn; UC09.

UI06 | Bảng cảnh báo nổi | Nút chuông mở; X hoặc Esc đóng; UC08.

UI07 | Báo cáo /#reports | Menu Báo cáo môi trường; UC10–12.

UI08 | Cửa sổ Xanh Non nổi | Bong bóng chat mở; nút đóng thu gọn; UC13–16.

Luồng màn hình được giữ bằng URL, nên tải lại, Quay lại và Tiến của trình duyệt khôi phục đúng mục. Mỗi màn hình chức năng hiển thị địa điểm dùng chung và đường về tổng quan. Việc mở menu không thay địa điểm; chọn một địa điểm từ tìm kiếm mới phát sinh locationchange.



Hình 17. Wireframe tổng quan theo giao diện đã triển khai

## 9.2 UI01 Tổng quan và lựa chọn địa điểm

Khu vực đầu có tên địa điểm, trạng thái tải, nguồn, danh sách chọn và nút lấy vị trí. Bên phải là nút Cập nhật dữ liệu, ngay dưới là thời điểm cập nhật gần nhất. Danh sách địa điểm giới hạn chiều rộng trên máy tính và co theo màn hình nhỏ. Chọn nơi mới làm thay đổi toàn bộ phần dữ liệu đang dùng chung, thay vì chỉ đổi tiêu đề.

Đầu vào gồm mã địa điểm từ danh sách và từ khóa tìm kiếm trên thanh đầu trang. Dữ liệu đến từ /api/diadiem và /api/capnhat. Trạng thái đang tải được thể hiện ở nhãn trạng thái cùng aria-busy; lỗi danh mục có nút thử lại riêng. Khi GPS thành công, thông báo ghi rõ địa điểm gần nhất trong danh sách và khoảng cách theo đường thẳng. UI01 phục vụ UC01–UC04; mã nguồn liên quan là index.html, locations.js, dashboard.js và script.js.



Hình 18. Giao diện tổng quan trên máy tính

Ảnh chạy ứng dụng lưu ngày 27/10/2026. Các giá trị trong ảnh minh họa snapshot tại thời điểm chụp, không phải số liệu cập nhật ở thời điểm đọc báo cáo.

## 9.3 UI02 Chỉ số môi trường

Thẻ US AQI trình bày giá trị, tên mức, màu và nội dung đánh giá. Năm thẻ còn lại trình bày PM2.5, PM10, nhiệt độ, độ ẩm và tiếng ồn. Tên đơn vị gắn với từng giá trị; nhãn theo dõi trên mỗi thẻ lấy từ cảnh báo nội bộ tương ứng. Thẻ không phải nút điều hướng tới hồ sơ trạm. Khi thiếu giá trị, giao diện biểu diễn chưa có dữ liệu thay vì tự tạo một thông số.

Phần ghi chú tiếng ồn thể hiện khu vực tổng hợp và lần đo gần nhất trong nguồn. Thời gian ở khối Cập nhật gần nhất là lúc ứng dụng lấy snapshot. UI02 dùng dữ liệu đã tải theo FR03 và các hàm renderCurrent, renderAnalysis; không có bộ chọn thông số tùy ý hoặc chỉnh sửa ngưỡng tại màn hình này. UC liên quan là UC04.

## 9.4 UI03 Bản đồ chất lượng không khí

Phía trên bản đồ có tên nơi, tọa độ, nút về địa điểm đã chọn, toàn màn hình và mở bản đồ lớn. Phần lớp phủ có công tắc và thanh độ đậm. Marker cung cấp popup tham chiếu; bản đồ cho phép kéo và thay mức zoom. Lớp màu nhận dữ liệu từ /api/bando/khongkhi, trong khi ảnh nền do Leaflet tải trực tiếp [T07].

Trong trạng thái đang tải, lớp phủ không được xem là một bộ số liệu mới đã hoàn thành. Khi tải thiếu, vùng không có mẫu giữ trong suốt và thông báo nguồn đi cùng. Lỗi ảnh nền và lỗi nguồn AQI là hai lỗi khác nhau. Những lần pan hoặc đổi nơi tạo yêu cầu cũ không được ghi đè lớp mới. UI03 phục vụ UC05–UC06; file triển khai là map.js và air-overlay.js.

## 9.5 UI04 Xu hướng dữ liệu

Màn hình có tên xu hướng PM2.5, nhận xét tăng giảm, giá trị gần nhất và đồ thị Canvas. Trục tung có số, đơn vị µg/m³ và bước chia tự chọn theo miền dữ liệu; trục hoành có nhãn thời gian. Đồ thị được vẽ lại theo kích thước phần chứa. Phiên bản hiện tại dùng 12 snapshot gần nhất, không có date picker hoặc danh sách chọn tất cả thông số trên màn hình này.

Nguồn là /api/dulieu/lichsu?limit=12&location=...; UC07. Các trạng thái rỗng, lỗi tải và thiếu điểm có cách hiển thị riêng. Màn hình không kết luận xu hướng dài hạn từ số điểm thưa, không biến các mốc snapshot thành dữ liệu quan trắc liên tục.



Hình 19. Màn hình xu hướng với trục số

Ảnh từ kiểm thử trình duyệt ngày 27/10/2026, sử dụng dữ liệu kiểm thử có kiểm soát để kiểm tra trục và điều hướng.

## 9.6 UI05 Phân tích và tư vấn

Màn hình trình bày phân tích AQI, nội dung gợi ý theo quy tắc và kết quả Random Forest. Dữ liệu RF có trạng thái riêng, gồm đủ dữ liệu, thiếu dữ liệu và lỗi mô hình. Người sử dụng có thể nhìn đồng thời nhãn AQI và nhãn RF; hai nhãn có thể khác nhau vì dùng cơ chế phân loại khác nhau.

Phần này đọc kết quả PhanTich và DuDoanRF từ snapshot, không gọi chatbot để dựng toàn bộ nội dung. UC09 được thực hiện bởi renderPrediction và renderAnalysis trong script.js. Không có thao tác cấu hình lại classifier hoặc gửi lệnh huấn luyện từ giao diện này.

## 9.7 UI06 Lịch sử cảnh báo trong nút chuông

Nút chuông luôn nằm trên thanh đầu trang; số đếm gắn với những mục cảnh báo gần nhất đã tải. Khi mở, bảng nổi có tên địa điểm, danh sách, mức, nội dung, thời gian và nút đóng. Đang tải, chưa có cảnh báo và lỗi được trình bày trong chính bảng nổi. Đóng bảng không cập nhật trạng thái đã đọc trong cơ sở dữ liệu vì lược đồ chưa có thuộc tính này.

Dữ liệu được đọc từ /api/canhbao?limit=8&location=... và liên kết UC08. Khi đổi nơi, tên bảng và danh sách đổi theo. Thành phần điều khiển được đặt tại notificationToggle, notificationClose và warningHistory; hành vi nằm trong dashboard.js cùng script.js.

## 9.8 UI07 Báo cáo môi trường

Màn hình có bộ chọn kỳ 24 giờ, 7 ngày hoặc 30 ngày, nút Tạo và lưu báo cáo, khu vực kết quả và lịch sử. Kết quả gồm thống kê, nhóm xu hướng, cảnh báo theo loại, nội dung quy tắc và bảng dữ liệu. Mở một báo cáo cũ cập nhật bộ chọn kỳ theo báo cáo đó; hành vi này không tạo mới báo cáo.

Trong lúc tạo hoặc mở báo cáo, các nút liên quan và bộ chọn địa điểm được khóa để giữ ngữ cảnh. Tải CSV chỉ được bật khi có bản ghi; in chỉ được bật khi có báo cáo hiện tại. Lịch sử hỗ trợ Xem thêm theo offset. Lỗi vượt thời gian chờ giữ khả năng tải lại lịch sử để xác định một báo cáo có thể đã được lưu. UI07 phục vụ UC10–UC12; dữ liệu trao đổi với /api/baocao và /api/baocao/<id>.

## 9.9 UI08 Chatbot Xanh Non

Bong bóng ở góc phải mở một cửa sổ có tên Xanh Non, lịch sử tin nhắn, gợi ý hỏi, ô nhập, nút gửi và nút đóng. Người sử dụng nhấn Enter để gửi, Shift+Enter để xuống dòng. Đang trả lời có trạng thái chờ và thao tác dừng. Khi câu trả lời bị cắt do giới hạn sinh, giao diện có thao tác tiếp tục. Bắt đầu lại xóa ngữ cảnh trên widget của nơi đang chọn.

Thu gọn chỉ ẩn cửa sổ; quá trình nhận phản hồi vẫn tiếp tục và dấu báo phản hồi mới được cập nhật. Các tin nhắn được giữ riêng theo địa điểm trong bộ nhớ của trang. Lời xác nhận hữu ích được gửi như tin nhắn, không dùng bộ nút chấm điểm riêng. UI08 phục vụ UC13–UC16 và các nhánh /api/chat. Widget hiển thị văn bản bằng textContent; đầu ra mô hình không được thực thi như HTML.

## 9.10 Đặc tả các thành phần điều khiển dùng chung

Bảng 21. Hành vi thành phần giao diện



Thành phần | Điều kiện và thao tác | Kết quả hoặc ngoại lệ

Nút menu và X | Nhấn menu khi đang đóng; nhấn X hoặc Esc khi đang mở | Mở hoặc đóng drawer; ẩn nút menu khi mở; trả focus khi đóng.

Tìm kiếm đầu trang | Nhập từ khóa, di chuyển bằng phím và Enter | Gợi ý địa điểm hoặc chức năng; không có kết quả thì giữ lựa chọn hiện tại.

Danh sách địa điểm | Danh mục sẵn sàng, không có tác vụ khóa | Lưu mã, phát locationchange và tải lại nội dung liên quan.

Lấy vị trí hiện tại | Trang an toàn, chưa có yêu cầu định vị đang chạy | Xin quyền; tự chọn mục gần nhất; lỗi vẫn cho chọn thủ công.

Cập nhật dữ liệu | Không tải trùng cùng phiên | Đổi trạng thái chờ rồi hiển thị snapshot hoặc thông báo lỗi.

Chuông và nút đóng | Nhấn chuông mở; X, Esc đóng | Hiện lịch sử đúng nơi; số đếm không là số chưa đọc có lưu bền.

Công tắc và độ đậm AQI | Lớp bản đồ đã khởi tạo | Ẩn hoặc hiện; đổi alpha lớp phủ, không thay giá trị nguồn.

Marker bản đồ | Nhấn tại dấu tham chiếu | Mở popup tên, tọa độ và nguồn; không mở CRUD trạm.

Tạo báo cáo | Kỳ hợp lệ và không đang bận | POST, lưu SQL, HTTP 201; lỗi hiển thị tại báo cáo.

Mở và Xem thêm | Có lịch sử; không đang bận | Đọc nội dung hoặc tăng phân trang; 404 không tự mở nơi khác.

CSV và In | Đã có báo cáo; CSV cần có dữ liệu | Tải tệp hoặc mở hộp thoại in; không gọi endpoint xuất PDF.

Gửi Dừng Bắt đầu lại | Theo trạng thái của phiên hội thoại | Gửi stream, hủy nhận hoặc xóa ngữ cảnh đang giữ trong trang.

Các trạng thái hiển thị gắn với kết quả từng thành phần. Ứng dụng không có chế độ offline đầy đủ; khi mất kết nối, dữ liệu đã tải trong cùng trang có thể còn được hiển thị cùng lỗi tải mới. Phần thanh cuộn được ẩn về hình thức nhưng thao tác cuộn vẫn được giữ. Kiểm tra giao diện được thực hiện ở cả kích thước máy tính và điện thoại.

# CHƯƠNG 10  THIẾT KẾ XỬ LÝ VÀ GIÁM SÁT MÔI TRƯỜNG

## 10.1 Nguồn và ý nghĩa các thông số

Bảng 22. Thông số và đặc tính nguồn dữ liệu



Thông số | Nguồn và đơn vị | Ý nghĩa trong ứng dụng

Nhiệt độ | Open-Meteo, °C | temperature_2m tại tọa độ tham chiếu.

Độ ẩm | Open-Meteo, % | relative_humidity_2m; dữ liệu nguồn thời tiết.

PM2.5 và PM10 | Open-Meteo Air Quality, µg/m³ | Nồng độ bụi mô hình tại vị trí tham chiếu.

US AQI | Open-Meteo Air Quality, chỉ số không thứ nguyên | Chỉ số do nguồn trả về; ứng dụng dùng để chọn mức và diễn giải.

CO NO2 SO2 O3 | Open-Meteo Air Quality | Các trường bổ sung nằm trong DuLieu và snapshot JSON, không là năm thẻ chính.

Tiếng ồn | NoiseCapture, dBA | Tổng hợp theo vùng từ các ô có số lần đo và metadata thời gian.

Tài liệu Open-Meteo xác định các biến thời tiết, biến chất lượng không khí và dữ liệu dự báo. NoiseCapture cung cấp dữ liệu cộng đồng có vị trí; ứng dụng lấy tệp Việt Nam và tự tổng hợp vùng tham chiếu [T01]–[T03]. Quy trình của dự án không tiếp nhận MQTT hoặc gói tin trực tiếp từ thiết bị IoT.

## 10.2 Tiếp nhận và kiểm tra dữ liệu

fetch_environment thực hiện hai yêu cầu HTTP với timeout 15 giây cho thời tiết và không khí. Dữ liệu hiện tại được ghép vào dictionary, giữ riêng ThoiGianNguonThoiTiet và ThoiGianNguonKhongKhi. NoiseData quản lý bản tải quốc gia dùng chung, kiểm tra tệp mới trước khi thay tệp cũ và dùng lại bản có sẵn khi cập nhật nguồn thất bại. Chu kỳ làm mới tệp tiếng ồn là 24 giờ; điều này không thay đổi thời điểm các phép đo bên trong nguồn.

Mức kiểm tra được thực hiện ở từng nhánh: dữ liệu NoiseCapture phải có tọa độ và giá trị hữu hạn, trọng số dương; RF yêu cầu đủ năm số hữu hạn; thống kê báo cáo loại None, boolean và giá trị không hữu hạn. Nhánh dự báo thời tiết kiểm tra đơn vị, độ dài mảng và UTC+7. Nhánh không khí kiểm tra hình dạng dữ liệu và thời gian nguồn. Bộ thu thập snapshot không phải một cổng chuẩn hóa cảm biến có kiểm định chất lượng đo.

## 10.3 Tổng hợp tiếng ồn theo năng lượng

Với mỗi ô tiếng ồn, hệ thống xác định tâm hình học và khoảng cách đến tọa độ tiếng ồn của địa điểm. Chỉ các ô trong bán kính được cấu hình mới tham gia tổng hợp. Gọi Li là mức của ô và wi là số lần đo, kết quả được tính bằng 10 log10 của tỷ số giữa tổng wi × 10 mũ (Li/10) và tổng wi. Việc tính trên năng lượng tránh dùng trung bình cộng trực tiếp các mức decibel.

Kết quả đi cùng số ô, số lần đo, bán kính, lần đo đầu và lần đo gần nhất. Nếu không có ô phù hợp thì trả None. Phép tổng hợp này mô tả tập dữ liệu vùng đã có; nó không khẳng định mức ồn tại đúng vị trí thiết bị của người sử dụng hoặc tại thời điểm hiện tại.

## 10.4 Quy tắc sinh cảnh báo

Bảng 23. Ngưỡng cảnh báo nội bộ được khai báo trong mã nguồn



Thông số | Mức Trung bình từ | Mức Cao từ | Đơn vị

PM2.5 | 35,5 | 55,5 | µg/m³

PM10 | 100 | 154 | µg/m³

Nhiệt độ | 35 | 38 | °C

Độ ẩm | 85 | 95 | %

Tiếng ồn | 70 | 85 | dBA

Hàm build_alerts kiểm tra mức cao trước, sau đó mức lưu ý. Một thông số chỉ tạo tối đa một cảnh báo trong một snapshot; giá trị thiếu được bỏ qua. Các ngưỡng trong bảng là ngưỡng vận hành của dự án, không được xác định như giới hạn quy chuẩn pháp luật. Đặc biệt, mức tiếng ồn tổng hợp có thời gian thu thập khác nhau nên không được coi là bằng chứng vượt quy chuẩn tại thời điểm cập nhật ứng dụng.

## 10.5 Phân tích US AQI và nhánh giá trị thay thế

Bảng 24. Các mức US AQI được giao diện sử dụng



Khoảng chỉ số nguyên | Tên trong ứng dụng | Màu

0–50 | Tốt | Xanh lá

51–100 | Trung bình | Vàng

101–150 | Kém | Cam

151–200 | Xấu | Đỏ

201–300 | Rất xấu | Tím

Trên 300 | Nguy hại | Đỏ sẫm

Sáu khoảng AQI được đối chiếu với tài liệu AirNow; tên tiếng Việt là cách đặt nhãn trong ứng dụng [T08]. US AQI khác nồng độ PM2.5 tại một giờ. Một giá trị bụi đơn lẻ hoặc một màu bản đồ không phải kết luận tuân thủ hay vi phạm quy chuẩn môi trường.

build_analysis ưu tiên US_AQI của nguồn. Khi trường này thiếu, hàm đang gán các mức AQI đại diện theo khoảng PM2.5 là 25, 75, 125, 175 hoặc 250. Đây là nhánh quy tắc thay thế trong mã, không phải phép tính đầy đủ chỉ số US AQI. Nếu cả PM2.5 cũng trống, biểu thức hiện tại dùng 0 ở bước này; nhãn phân tích khi đó không xác nhận đã có dữ liệu không khí. Trên giao diện và trong hội thoại, trạng thái thiếu của giá trị nguồn vẫn có ý nghĩa riêng.

## 10.6 Phân loại Random Forest

Mô hình nhận năm đặc trưng theo đúng thứ tự: pm25, pm10, temperature_c, humidity_pct và noise_db. Bundle chứa air_quality_model và noise_level_model. Nhãn chất lượng không khí có bốn mức, nhãn tiếng ồn có ba mức. Các nhãn này được tạo theo quy tắc của bộ dữ liệu huấn luyện minh họa nên số mức và ý nghĩa không trùng hoàn toàn với sáu mức US AQI.

Nếu thiếu tiếng ồn ở một nơi, hệ thống không suy đoán thêm để đủ đầu vào mô hình. predict_environment trả thieu_du_lieu và danh sách trường thiếu. Lỗi model bundle hoặc suy luận được chuyển thành loi_mo_hinh trong snapshot; dữ liệu từ các nguồn vẫn được lưu. Kết quả RF là phân loại một hàng đầu vào, không phải mô hình dự báo diễn biến các ngày tiếp theo.

## 10.7 Thống kê và báo cáo theo thời gian

Báo cáo chuẩn hóa các giá trị hợp lệ, đếm số thiếu và tính min, max, giá trị gần nhất cho từng thông số. Với các thông số ngoài tiếng ồn, hệ thống tính trung bình cộng các snapshot có dữ liệu và độ thay đổi giữa lần đầu với lần cuối. Tiếng ồn không được tính lại trung bình cộng hoặc độ thay đổi vì giá trị đã là tổng hợp vùng. Thống kê này mô tả các snapshot được thu, không phải trung bình có trọng số theo thời gian quan trắc liên tục.

Kỳ 24 giờ nhóm xu hướng PM2.5 theo giờ; kỳ 7 và 30 ngày nhóm theo ngày. Mỗi nhóm có số bản ghi, số giá trị PM2.5 hợp lệ, trung bình và cực đại. Cảnh báo được lọc lại theo các mã nguồn trong kỳ để tránh ghép sự kiện không thuộc dữ liệu báo cáo. Báo cáo còn giữ số nguồn, số bản ghi có cảnh báo và tỷ lệ, cùng nội dung quy tắc có căn cứ từ chính thống kê này.

# CHƯƠNG 11  THIẾT KẾ CHATBOT TƯ VẤN XANH NON

## 11.1 Kiến trúc trả lời kết hợp

Xanh Non kết hợp nhận diện ý định bằng quy tắc, tra cứu tri thức, đọc dữ liệu môi trường và mô hình ngôn ngữ cục bộ. Quy trình không bắt buộc đi qua mô hình sinh ở mọi câu hỏi. Những nội dung đã được xác định chắc chắn, như giao tiếp cơ bản, chức năng ứng dụng, số liệu cần đọc, dự báo theo cửa sổ giờ hoặc một đáp án kiến thức phù hợp, được trả trực tiếp. Nhánh chưa có đáp án trực tiếp mới xây dựng ngữ cảnh và gọi runtime.

Manifest đang hoạt động xác định XanhNon-Style-v2, với nền Qwen2.5 0.5B và bản GGUF F16 dùng bởi llama.cpp. Bản phát hành có hash để nhận diện tệp; thông tin số bước học trong manifest là thông tin của bản đã phát hành. Một đợt chuẩn bị dữ liệu hoặc kiểm tra token mới không đồng nghĩa bản mô hình đó đã được thay thế. NativeChatbot quản lý tiến trình cục bộ, còn Flask giao tiếp với tiến trình qua HTTP loopback [T09].

## 11.2 Chuỗi quyết định của câu trả lời

1. Kiểm tra cấu trúc yêu cầu và tách câu hỏi khỏi lịch sử giới hạn. Với lời xác nhận hữu ích, ghi nhận theo nhánh góp ý riêng.

2. Giải nghĩa câu nối tiếp, chủ đề và chi tiết còn thiếu. Nếu cần, hỏi lại trước khi kết luận.

3. Nhận biết giao tiếp cơ bản, câu giới thiệu chức năng hoặc câu ngoài phạm vi.

4. Trong phạm vi, ưu tiên các nhánh dữ liệu người dùng nêu, thời tiết, không khí, tư vấn và kiến thức phù hợp.

5. Khi cần mô hình, tạo thông điệp hệ thống và phần dữ liệu chỉ liên quan đến câu hỏi; không đưa toàn bộ bộ dữ liệu chat thô vào ngữ cảnh.

6. Nhận nội dung trực tiếp hoặc token sinh, làm sạch đầu ra và trả JSON hoặc SSE thống nhất.

## 11.3 Quản lý ngữ cảnh nhiều lượt

Ngữ cảnh được giải từ lượt người sử dụng, kết hợp chủ đề, địa điểm và mốc thời gian. Câu hỏi mới có thể thay một phần ngữ cảnh mà vẫn giữ những phần còn liên quan. Ví dụ, sau một câu về thời tiết ngày mai ở Đà Nẵng lúc 18:30, câu “độ ẩm thì sao” giữ Đà Nẵng, ngày mai và khoảng 18:00–19:00. Câu “không khí nữa” đổi lĩnh vực dữ liệu nhưng có thể tiếp tục dùng cùng địa điểm, ngày và giờ.

Nếu hỏi “19 giờ thì sao”, giờ mới thay cho giờ cũ. Nếu hỏi “hiện tại”, mốc dự báo không còn áp dụng. Khi chỉ nêu một giờ mà chưa có ngày rõ ràng, hệ thống có thể hỏi người sử dụng muốn xem hôm nay hay ngày khác. Các câu cảm ơn được nhận diện riêng; việc chuyển sang một chủ đề không liên quan không tiếp tục kéo nội dung môi trường cũ vào câu trả lời.

Bảng 25. Các biến ngữ cảnh và cách sử dụng



Biến | Nguồn xác định | Điều kiện giữ hoặc thay

Địa điểm | Danh mục đang chọn hoặc tên được nêu rõ | Giữ khi câu nối tiếp không đổi nơi; tên mới phải được nhận diện từ danh mục.

Chủ đề | Câu hỏi hiện tại và lượt user liên quan | Giữ khi câu rút gọn còn liên quan; hỏi lại khi hai chủ đề cùng có thể đúng.

Ngày | Hôm nay, mai, ngày kia hoặc ngữ cảnh ngày | Thông tin ngày mới thay ngày cũ; câu hiện tại dùng mốc hiện tại.

Giờ và buổi | Giờ cụ thể hoặc buổi được nhận biết | Giữ khi hỏi thêm chỉ số; giờ mới thay giờ cũ; dữ liệu theo giờ nguồn.

Chỉ số cần trả | Từ khóa và trường được hỏi | Đổi từ nhiệt độ sang độ ẩm không thêm các chỉ số không được hỏi.

Mức chi tiết | Yêu cầu ngắn, kỹ hoặc đầy đủ | Điều chỉnh nội dung và giới hạn sinh trong phạm vi cấu hình.

## 11.4 Truy xuất dữ liệu và xử lý thiếu

Số liệu hiện tại lấy từ snapshot hoặc nguồn đọc theo câu hỏi. Dữ liệu dự báo được truy xuất riêng, cache 600 giây theo mã địa điểm, tọa độ và ngày. Thời tiết dự báo hiện dùng nhiệt độ và độ ẩm; không khí dự báo được đọc từ Open-Meteo/CAMS. Các chuỗi dữ liệu giờ phải phù hợp cửa sổ cần trả; thiếu giờ quan trọng không được tự nội suy thành một câu trả lời chắc chắn.

Câu hỏi về thời tiết chỉ trả trường thời tiết cần thiết. Câu hỏi thiếu dữ liệu được giải thích ở đúng phần cần dùng, không thêm nhận xét về một chỉ số người sử dụng không hỏi. Hỏi riêng độ ẩm không kéo tiếng ồn hoặc AQI vào phản hồi. Các câu dự báo có nhãn dự báo, tên nơi và ngày giờ tương ứng, để tách khỏi số liệu bảng giám sát.

## 11.5 Kho tri thức và tư vấn chuyên môn

knowledge.json chứa 26 tài liệu cùng mã nguồn tham chiếu. Nội dung được tìm bằng câu mẫu, chủ đề, các quy tắc và TF-IDF trên n-gram ký tự từ 3 đến 5. Cơ chế này là tra cứu văn bản có kiểm soát; dự án không vận hành một cơ sở dữ liệu vector độc lập. reference_context đưa các đoạn phù hợp vào phần ngữ cảnh khi cần mô hình sinh.

Các đáp án tư vấn có thể điều chỉnh theo nội dung người sử dụng vừa nêu, chẳng hạn muốn giảm bụi gần đường lớn nhưng chưa có máy lọc. Việc sử dụng tình huống trong hội thoại không tạo hồ sơ cá nhân hoặc hệ gợi ý theo tài khoản. Nguồn được lưu ở mức tài liệu tri thức; không có định dạng trích dẫn bấm được được bảo đảm trong mọi câu trả lời của widget.

## 11.6 Dữ liệu hội thoại và dữ liệu cảm biến dùng cho học

Bảng 26. Nhóm dữ liệu và vai trò trong quy trình học



Nhóm nguồn | Vai trò có trong dự án | Giới hạn sử dụng

Vietnamese Multi-turn và Vietnamese Chatting đã lọc | Bổ sung cách diễn đạt và nối lượt trong tập hội thoại | Không làm nguồn khẳng định chuyên môn hoặc số liệu hiện tại.

Hỏi đáp môi trường của dự án | Dạy cách trả lời AQI, PM2.5, thiếu dữ liệu và nhánh tư vấn | Kiến thức có nguồn; các con số theo thời gian phải là tình huống giả định rõ ràng.

iSCAPE Outdoor Sensor Deployment | Nguồn dữ liệu cảm biến ngoài trời trong kho đã khôi phục [T10] | Dữ liệu lịch sử của dự án nghiên cứu; không là số liệu hiện tại tại Việt Nam.

iSCAPE Citizen Science Workshops | Dữ liệu các hoạt động cảm biến cộng đồng [T11] | Các kênh có thể khác theo thiết bị; không tự gán trường thiếu.

iSCAPE Low Cost Sensor Development | Dữ liệu thử nghiệm và phát triển cảm biến [T12] | Điều kiện thí nghiệm khác môi trường sử dụng thực tế.

Beijing Multi-Site Air Quality | Bổ sung dữ liệu bụi và khí tượng trong kho nguồn [T13] | Không có trường tiếng ồn hoặc độ ẩm tương đối trực tiếp như đầu vào năm đặc trưng.

Các bộ dữ liệu thô được kiểm tra trùng và chuẩn hóa trước khi chuyển thành mẫu. Sự có mặt của một bộ dữ liệu trong kho không xác nhận toàn bộ hàng của nó đã tham gia huấn luyện bản đang hoạt động. Hồ sơ khôi phục ghi nhận 21 phiên bản dữ liệu và 388 tệp nguồn, trong khi tập JSONL mặc định đã chuẩn bị gồm 452 mẫu train và 124 validation. Đây là các đơn vị đếm khác nhau.

## 11.7 Học từ chat và quy trình huấn luyện

ConversationLearner quan sát câu hỏi phù hợp khi cờ learn_from_chat được bật. Câu hỏi có số liệu hiện tại hoặc dự báo được chuyển sang trạng thái cần dữ liệu; nội dung cần nguồn được giữ chờ xử lý. Chỉ câu hỏi có thể gắn với một đáp án kiến thức ổn định có nguồn mới được dùng như biến thể learned. Hash kho tri thức và phiên bản chính sách là điều kiện để tái sử dụng đáp án đó.

Góp ý có chuỗi trạng thái pending, approved hoặc rejected. Khi duyệt, công cụ yêu cầu kiểm tra nội dung và thông tin riêng tư, nguồn tham chiếu hợp lệ và chính sách cho dữ liệu thời gian. Góp ý đã duyệt có thể được chuyển thành mẫu học. Tinh chỉnh LoRA là bước riêng với dữ liệu, checkpoint và kiểm thử; trọng số không cập nhật tức thời sau mỗi cuộc trò chuyện [T14].



Hình 20. Quy trình dữ liệu học và huấn luyện cục bộ

## 11.8 Kiểm soát đầu ra và phạm vi an toàn

Đầu vào được giới hạn kích thước, vai trò lịch sử phải luân phiên đúng cặp và đầu ra được xử lý như văn bản. chat_output làm sạch một số phần lặp, lời dẫn thừa và hướng dẫn nội bộ. Nội dung cần giá trị hiện tại được ưu tiên nhánh đọc dữ liệu để giảm phụ thuộc mô hình nhớ con số. Các biện pháp này là kiểm soát cụ thể trong mã; chúng không tạo bảo đảm rằng mô hình không thể sai hoặc không chịu ảnh hưởng của chỉ dẫn độc hại.

Ứng dụng không có đăng nhập nên việc kiểm tra Origin ở các nhánh ghi góp ý và câu hỏi không phải cơ chế phân quyền người dùng. CORS được bật ở Flask; phạm vi triển khai hiện tại là máy cục bộ. Kho học lọc một số mẫu thông tin nhạy cảm và tách khỏi tập kiểm tra, nhưng hội thoại không được mô tả như đã có cơ chế ẩn danh hóa toàn diện hoặc chứng nhận bảo mật.

# CHƯƠNG 12  KIỂM THỬ VÀ TRUY VẾT YÊU CẦU

## 12.1 Phạm vi và tổ chức kiểm thử

Kiểm thử được tổ chức theo bốn lớp: đơn vị xử lý thuần và dữ liệu; tích hợp API với các phụ thuộc được mock; giao diện trình duyệt với dữ liệu kiểm soát; và đối chiếu API, SQL, mô hình thật trong các hồ sơ chạy đã lưu. Cách chia này tách việc kiểm tra quy tắc khỏi sự thay đổi của nguồn ngoài và chi phí nạp mô hình.

Dữ liệu kiểm thử bao gồm mã địa điểm hợp lệ và sai, giá trị đúng ngưỡng, trường thiếu, mảng dự báo thiếu giờ, phản hồi API lỗi, chuỗi nhiều lượt và các payload không đúng kiểu. Các kịch bản trình duyệt dùng Edge ở kích thước máy tính và điện thoại. Bộ kiểm thử có mock không được tính như một lần đo tốc độ suy luận hoặc một lần xác minh dữ liệu thật của nguồn.

## 12.2 Kết quả có bằng chứng

Bảng 27. Tổng hợp các kết quả đã ghi nhận



Đợt kiểm tra | Kết quả | Bằng chứng

Hồ sơ khôi phục 27/10 | 209 kiểm thử Python duy nhất; 13 kiểm tra JavaScript đạt | restoration-state.json; ba log kiểm thử và javascript-tests.txt

Chạy kiểm tra phục vụ lập hồ sơ | 179/180 kiểm thử đạt; 1 thất bại; 0 lỗi | qa/document-evidence-tests.json; qa/document-evidence-tests.txt

Giao diện 27/10 | Kiểm tra 1.600 px và 390 px, menu, chuông, tìm kiếm, đồ thị, chat và không tràn ngang | browser-checks.json

Dữ liệu và hội thoại thật 27/10 | HTTP giám sát và RF; tám câu chat; đối chiếu JSON/SSE | live-verification.json

Tiền kiểm tra dữ liệu học | 452 mẫu train, 124 validation đã token hóa; chưa là lần học trọng số mới | preflight.json; restoration-state.json

Con số 209 là tổng số ca duy nhất trong hồ sơ khôi phục, không phải tổng cộng trực tiếp 177, 30 và 5 vì có ca trùng giữa các lần chạy. Bộ kiểm tra phục vụ biên soạn được ghi riêng, không cộng vào con số đó như một nhóm ca mới. Các hash của những tệp chính trong hồ sơ đã được đối chiếu với phiên bản đang khảo sát.

Lần chạy bổ sung có một ca không đạt kỳ vọng trong test_chat_intents.py: câu “Ở Đà Nẵng hôm nay nên làm gì?” mong _grounded_reply trả None khi snapshot đầu vào thuộc nơi khác. Nhánh hiện tại đã đọc được AQI của Đà Nẵng và trả tư vấn, nên không khớp điều kiện khẳng định của bài thử. Kết quả được giữ nguyên là một ca không đạt; không gộp lần chạy này vào kết quả 209 ca của hồ sơ trước.

Trong tám câu chat thật được lưu, thời gian hoàn tất nằm từ 0,032 đến 2,218 giây. Các câu này chủ yếu đi qua nhánh quy tắc, tra cứu hoặc nguồn dự báo có cache, nên không đại diện cho tốc độ sinh tự do của mô hình. Kết quả không được sử dụng như chứng nhận độ chính xác chuyên môn hoặc độ trễ cam kết của toàn hệ thống.

## 12.3 Danh mục tình huống kiểm thử và nghiệm thu

Mỗi dòng dưới đây quy định điều kiện trước hoặc dữ liệu, thao tác, kết quả mong đợi và tình trạng bằng chứng. Trạng thái “đặc tả nghiệm thu” có nghĩa hồ sơ chưa chứa kết quả chạy riêng đầy đủ cho tình huống đó. Các bộ đơn vị có mock sử dụng dữ liệu cố định hoặc kho tạm; chúng không sửa cơ sở dữ liệu nghiệp vụ đang chạy.

Bảng 28. Tình huống kiểm thử địa điểm giám sát và bản đồ



Mã và yêu cầu | Điều kiện trước và đầu vào | Bước thực hiện và kết quả mong đợi | Bằng chứng và trạng thái

TC01
FR01 | Danh mục 86 địa điểm; từ khóa cau giay hoặc xu huong | Tải danh mục, tìm không dấu, chọn kết quả. Mã địa điểm hoặc hash chức năng đổi đúng; tải lại giữ nơi đã chọn. | Đã kiểm tra giao diện 27/10.
browser-checks.json; test_locations

TC02
FR01, FR04 | Hai địa điểm và phản hồi nơi cũ đến muộn | Đổi nơi trong lúc tải. Dữ liệu nơi cũ không ghi đè tên, chỉ số hoặc nội dung báo cáo của nơi mới. | Có kiểm thử cách ly địa điểm; kiểm tra UI 27/10.
test_locations; mã phiên trong script.js

TC03
FR02 | GPS giả lập gần tọa độ danh mục; sau đó từ chối quyền hoặc timeout | Nhấn Lấy vị trí. Chọn đúng mục gần nhất; lỗi quyền và timeout hiển thị thông báo, vẫn chọn thủ công. | Đã kiểm tra GPS giả lập 27/10.
tests/browser/check_geolocation.py; ảnh kết quả

TC04
FR03 | Snapshot cùng địa điểm còn hạn dưới 600 giây | Gửi cập nhật đồng thời. Các yêu cầu dùng lại kết quả còn hạn và không ghi chéo dữ liệu nơi khác. | Kiểm thử cache và cách ly; hồ sơ API/SQL 07/10.
test_locations; TEST_REPORT.md

TC05
FR03 | Nguồn trả lỗi hoặc pyodbc phát sinh ngoại lệ | Gửi cập nhật. Mã lỗi và trường loi đúng; giao diện không báo tải mới thành công. | Đặc tả nghiệm thu lỗi giao dịch; chưa có kết quả riêng cho mọi điểm lỗi.
app.update_environment; test_locations

TC06
FR03, FR09 | Thiếu TiengOn trong bộ năm giá trị | Chạy phân loại. Trả thieu_du_lieu; dữ liệu còn lại được trình bày, không lấy tiếng ồn nơi khác. | Đã kiểm tra mô hình và trường thiếu trong hồ sơ.
environment_predictor.py; TEST_REPORT.md

TC07
FR04 | Snapshot có metadata nguồn và thời gian riêng | Mở tổng quan. Giá trị, đơn vị, địa điểm và ghi chú tiếng ồn đúng snapshot. | Đã kiểm tra dữ liệu thật 27/10.
home-live-desktop.png; live-verification.json

TC08
FR05 | Nền OSM sẵn sàng; sau đó giả lập tải nền lỗi | Nhấn marker, zoom, về vị trí và thử lại. Giữ dấu tham chiếu; lỗi nền không biến thành dữ liệu AQI giả. | Đã có hồ sơ kiểm tra 07/10; không chạy lại trong phiên biên soạn.
tests/browser/check_map.py; TEST_REPORT.md

TC09
FR06 | Phạm vi quá rộng, ngoài vùng hoặc mẫu nguồn thiếu | Gọi lưới. Không quá 196 điểm; dữ liệu thiếu giữ trống; phạm vi sai trả lỗi phù hợp. | Kiểm thử đơn vị có mock.
test_air_quality_map

TC10
FR06 | AQI bằng 0, góc lưới thiếu và giá trị trên 500 | Chạy kiểm tra nội suy, phân mức và màu. Không biến giá trị thiếu thành 0; nhận đúng 0 hợp lệ. | 13 kiểm tra JavaScript đạt trong hồ sơ 27/10.
tests/test_air_overlay.cjs; javascript-tests.txt

Bảng 29. Tình huống kiểm thử xu hướng cảnh báo và báo cáo



Mã và yêu cầu | Điều kiện trước và đầu vào | Bước thực hiện và kết quả mong đợi | Bằng chứng và trạng thái

TC11
FR07 | Lịch sử kiểm thử có các giá trị 10, 20 và 36,4 | Mở #trends. Trục số có mốc phù hợp, nhãn thời gian và giá trị cuối; không tràn ngang ở 390 px. | Đã kiểm tra bằng dữ liệu giả lập 27/10.
browser-checks.json; trends-restored-1600.png

TC12
FR08 | Cảnh báo có dữ liệu, rỗng và lỗi | Mở chuông, đóng bằng X hoặc Esc; đổi nơi. Bảng đúng địa điểm và số đếm phản ánh mục đã tải. | Đã kiểm tra giao diện 27/10.
browser-checks.json; dashboard.js

TC13
FR09 | Năm giá trị đủ và bundle mô hình hiện tại | Đọc DuDoanRF. TrangThai=ok khi suy luận được; nhãn RF được tách khỏi mức US AQI. | Đã kiểm tra RF qua HTTP 27/10.
live-verification.json

TC14
FR10 | Hai snapshot PM2.5 bằng 10 và 50; hai cảnh báo trong kỳ | Tính báo cáo. Trung bình 30, min 10, max 50, thay đổi 40; đếm cảnh báo và mẫu thiếu đúng. | Kiểm thử đơn vị có dữ liệu cố định.
test_environment_reports

TC15
FR10, FR11 | days là 1, 7, 30; thử thêm true, 2 và giá trị sai | Tạo, lưu và mở báo cáo. Kỳ hợp lệ trả 201; kỳ sai trả 400; nội dung mở lại khớp snapshot. | Đơn vị có mock; lưu mở SQL thật có hồ sơ 07/10.
test_environment_reports; test_locations; TEST_REPORT.md

TC16
FR11 | Mã báo cáo tồn tại nhưng location khác | Gọi chi tiết bằng mã nơi khác. Trả 404, không tiết lộ nội dung báo cáo qua nhầm ngữ cảnh. | Kiểm thử cách ly báo cáo theo địa điểm.
test_locations

TC17
FR12 | Báo cáo có tiếng Việt, nguồn bắt đầu bằng dấu = và 17 cột | Tải CSV và mở in. CSV có BOM, escape phù hợp và đúng nơi; hộp thoại in dùng báo cáo hiện tại. | CSV có hồ sơ 07/10; hộp thoại in là tình huống nghiệm thu giao diện.
static/reports.js; tests/browser/check_locations.py

Bảng 30. Tình huống kiểm thử hội thoại dữ liệu học và vận hành



Mã và yêu cầu | Điều kiện trước và đầu vào | Bước thực hiện và kết quả mong đợi | Bằng chứng và trạng thái

TC18
FR13 | message rỗng, quá 8.000 ký tự hoặc history sai vai trò | Gửi POST chat. Trả lỗi 400; body quá lớn bị từ chối 413. | Kiểm thử xác thực dữ liệu đầu vào.
test_chat_stream; chatbot.validate_chat

TC19
FR13 | Cùng câu hỏi trong JSON và SSE; thu gọn khi đang trả lời | Đối chiếu reply cuối; đóng mở widget. Câu hoàn tất nhất quán và hội thoại không bị xóa. | Đã kiểm tra JSON/SSE và widget 27/10.
live-verification.json; browser-checks.json

TC20
FR14 | Hỏi thời tiết mai ở Đà Nẵng 18:30 rồi hỏi độ ẩm và không khí | Gửi chuỗi câu. Giữ đúng nơi, ngày và khoảng 18:00–19:00; đổi chỉ số không mất ngữ cảnh. | Đơn vị và câu hỏi thật đã kiểm tra 27/10.
test_chat_reading_followups; live-verification.json

TC21
FR14 | Chỉ hỏi lúc 18 giờ khi chưa rõ ngày; hoặc câu nối tiếp mơ hồ | Gửi yêu cầu. Trợ lý hỏi lại ngày hoặc chủ đề cần thiết, không tự chọn chắc chắn. | Đã có kiểm thử và câu hỏi thật 27/10.
test_chat_clarification; live-verification.json

TC22
FR15 | Câu hỏi giảm bụi gần đường lớn hoặc chưa có máy lọc | Yêu cầu tư vấn. Có biện pháp cụ thể, hoàn chỉnh; phần nối tiếp giữ đúng hạn chế đã nêu. | Đơn vị và tư vấn thật đã kiểm tra 27/10.
test_chat_advice; test_chat_knowledge; live-verification.json

TC23
FR15 | Xin chào, hỏi chức năng và một câu ngoài môi trường | Gửi lần lượt. Giao tiếp và chức năng có nhánh phù hợp; ngoài phạm vi dùng câu cố định. | Kiểm thử đơn vị và câu hỏi thật 27/10.
test_chat_social; test_chat_intents; test_chat_scope; live-verification.json

TC24
FR16 | Gửi hữu ích cho cùng một phản hồi hai lần | Quan sát lưu góp ý. Payload trùng chỉ có một fingerprint; câu xác nhận được trả về. | Kiểm thử kho tạm và API có mock.
test_chat_text_feedback; test_chat_feedback

TC25
FR16 | Câu hỏi mới ổn định; câu có thông tin nhạy cảm hoặc số liệu hiện tại | Quan sát kho học. Chỉ mẫu phù hợp được liên kết; không cập nhật trọng số; hash thay đổi làm đáp án cũ mất hiệu lực. | Kiểm thử kho tạm và dữ liệu kiểm soát.
test_chat_learning; test_chat_reviewed_safety

TC26
FR17 | Runtime cold, ready hoặc có khóa training | Gọi status. Trả trạng thái phù hợp; không sinh câu hỏi để kiểm tra tình trạng. | Kiểm thử trạng thái; runtime ready có hồ sơ 27/10.
test_chat_training_state; restoration-state.json

TC27
FR18 | Tập train và validation đã chuẩn bị | Đối chiếu tiền kiểm tra. 452 mẫu train và 124 validation được token hóa; không coi đây là optimizer step. | Đã tiền kiểm tra 576 mẫu trong hồ sơ 27/10.
.runtime/xanhnon-data/preflight.json

TC28
FR18 | Lịch chạy có dữ liệu nhưng RAM chưa đáp ứng | Đối chiếu trạng thái tự động. waiting_for_memory; model_activated=false; bản đang chạy không tự thay. | Đã ghi nhận trạng thái thực tế 27/10.
restoration-state.json; automatic-training-check.json

## 12.4 Ma trận tác nhân chức năng và phạm vi quyền

Bảng 31. Tác nhân và nhóm chức năng



Nhóm chức năng | A01 Người sử dụng | A02 Người vận hành | Hệ thống ngoài

FR01–02 Địa điểm | Sử dụng trên web | Không có quyền web riêng | GPS do trình duyệt cung cấp

FR03–09 Giám sát và bản đồ | Tra cứu và yêu cầu cập nhật | Khởi chạy và theo dõi dịch vụ | Open-Meteo, NoiseCapture, OSM

FR10–12 Báo cáo | Tạo mở xuất, không cần đăng nhập | Truy cập dữ liệu bằng quyền máy nếu có | Không có vai trò quản trị ngoài

FR13–16 Hội thoại và góp ý | Chat và xác nhận hữu ích | Duyệt góp ý bằng công cụ cục bộ | Open-Meteo cho dữ liệu cần đọc

FR17–18 Runtime và huấn luyện | Không có màn hình huấn luyện | Chạy lệnh và quản lý dữ liệu mô hình | Nguồn dữ liệu tải về, không có API ChatGPT

## 12.5 Ma trận truy vết xuyên suốt

Ma trận sau đồng thời thể hiện quan hệ chức năng với giao diện, API, lớp hoặc module, dữ liệu và kiểm thử. Các UC dùng cùng hậu tố với FR. Nhóm luồng tham chiếu là L1 tra cứu và cập nhật, L2 bản đồ và xu hướng, L3 báo cáo, L4 hội thoại, L5 dữ liệu học và vận hành. Sequence, Activity và State ở chương 6 giải thích các tương tác tương ứng.

Bảng 32. Truy vết yêu cầu đến thiết kế và kiểm thử



FR và UC | UI và luồng | API hoặc module xử lý | Kho dữ liệu | Kiểm thử

01–02 | UI01; L1 | /diadiem; locations.js; LocationStore | D1; localStorage | TC01–03

03–04 | UI01–02; L1 | /capnhat; /dulieu/moinhat; app.py | D1 D2 D3 | TC04–07

05–06 | UI03; L2 | /bando/khongkhi; AirMapRepository; map.js | D4; ảnh nền OSM | TC08–10

07 | UI04; L2 | /dulieu/lichsu; drawTrend | D2 | TC11

08 | UI06; L1 | /canhbao; renderAlerts | D2 D3 | TC12

09 | UI05; L1 | predict_environment; build_analysis | D2 D3 D8 | TC06 TC13

10 | UI07; L3 | POST /baocao; ReportRepository.create | Đọc D2 D3; ghi D5 | TC14–15

11 | UI07; L3 | GET /baocao và /baocao/<id> | Đọc D5 | TC15–16

12 | UI07; L3 | reports.js; Blob; window.print | Snapshot báo cáo trên trình duyệt | TC17

13 | UI08; L4 | POST /chat; NativeChatbot | D2 D6 D8; lịch sử trong trang | TC18–19

14–15 | UI08; L4 | Các module chat_*; Open-Meteo | D2 D6; cache dự báo | TC20–23

16 | UI08; L5 | ConversationLearner; FeedbackStore | Đọc D6; ghi D7 | TC24–25

17 | API; L5 | GET /chat/status; runtime_status | Trạng thái trong tiến trình | TC26

18 | Công cụ; L5 | train_xanhnon; export; model_release | Đọc D6 D7 D8; ghi ứng viên D8 | TC27–28

Các đường dẫn API rút gọn trong ma trận đều có tiền tố /api. D1 là danh mục địa điểm; D2 là snapshot; D3 là cảnh báo và phân tích; D4 là mẫu bản đồ; D5 là báo cáo; D6 là tri thức JSON; D7 là hai kho SQLite; D8 là dữ liệu học và mô hình. Mỗi nhóm có thể liên quan nhiều bảng hoặc nhiều API, không giả định quan hệ một–một.

# CHƯƠNG 13  TRIỂN KHAI VÀ VẬN HÀNH

## 13.1 Môi trường và cấu hình

Dự án chạy trên Windows với môi trường Python của ứng dụng, SQL Server, ODBC Driver 17 và trình duyệt. requirements.txt ghi các thư viện chạy, bao gồm scikit-learn 1.8.0 để khớp bundle Random Forest, Torch, Transformers, PEFT và các thư viện dữ liệu. Các binary llama.cpp, GGUF, tokenizer và mô hình cần có ở vị trí được cấu hình; Internet được dùng khi đọc các nguồn ngoài.

Kết nối SQL được điều khiển bằng DB_SERVER, DB_NAME, DB_DRIVER, DB_USER và DB_PASSWORD. Khi không khai báo tài khoản SQL, ứng dụng sử dụng xác thực Windows. Cấu hình chatbot cho phép chọn backend tự động, llama_cpp hoặc transformers; cấu hình GPU mặc định là 0 layer. Phiên bản triển khai hiện tại ưu tiên CPU, số luồng sinh mặc định là 4 và được giới hạn bởi tham số môi trường.

## 13.2 Khởi chạy và kiểm tra dịch vụ

1. Kích hoạt hoặc gọi trực tiếp Python trong .venv đã có các thư viện của dự án.

2. Xác nhận SQL Server và cơ sở dữ liệu GiamsatMT sẵn sàng; các schema nằm trong Demodatabase.sql, location_schema.sql, report_schema.sql và air_map_schema.sql.

3. Chạy .venv\Scripts\python.exe app.py rồi mở http://127.0.0.1:5000.

4. Đọc /api/chat/status và kiểm tra một lượt tải địa điểm để phân biệt tình trạng Flask, SQL, nguồn dữ liệu và runtime mô hình.

Ứng dụng có nhánh kiểm tra dịch vụ hiện hữu trước khi khởi tạo thêm phiên chạy trực tiếp, nhằm tránh nạp trùng mô hình tại cổng ứng dụng. Các schema bổ sung được kiểm tra và tạo bằng ensure_schema trong quá trình sử dụng. Bản báo cáo chỉ khảo sát cơ chế này; việc biên soạn không thực hiện migration hoặc thay đổi dữ liệu nghiệp vụ.

## 13.3 Các trạng thái cần theo dõi

Bảng 33. Dấu hiệu vận hành và ý nghĩa



Thông tin | Vị trí quan sát | Ý nghĩa

HTTP Flask | 127.0.0.1:5000 và log ứng dụng | Xác định dịch vụ web đang trả lời.

Runtime chatbot | /api/chat/status | Phân biệt cold, loading, ready, training, error.

Nguồn môi trường | ThoiGianNguonThoiTiet và ThoiGianNguonKhongKhi | Xác định thời điểm dữ liệu nguồn, khác thời điểm lấy snapshot.

Tiếng ồn | TiengOn_ChiTiet và tệp noise-vietnam.zip | Kiểm tra vùng, số mẫu, ngày đo và bản dữ liệu dùng lại.

Huấn luyện | Trạng thái JSON và lịch Windows | Phân biệt đang chạy, chưa có thay đổi dữ liệu, thiếu tài nguyên và kết thúc.

Bản mô hình hoạt động | models/xanhnon-active.json | Nhận diện tệp phát hành, hash và lịch sử kích hoạt.

## 13.4 Lịch tự động và giới hạn tài nguyên

Lịch Windows XanhNon-Train-Reviewed-Data gọi daily_train_xanhnon.py từ thư mục dự án. Script kiểm tra điều kiện tài nguyên và dấu vết dữ liệu trước khi học; cấu hình lịch hiện có dùng tập pilot giới hạn 128 mẫu train và 24 validation, không mặc định học lại toàn bộ kho ở mỗi lần gọi. Dữ liệu không đổi có thể được bỏ qua theo fingerprint.

Hồ sơ vận hành ngày 27/10/2026 ghi nhận lịch đã chạy và chuyển waiting_for_memory, model_activated=false. Bản phát hành XanhNon-Style-v2 tiếp tục được dùng. Tiền kiểm tra 576 mẫu đã thành công không được diễn giải thành việc lịch đã thực hiện bước tối ưu trọng số. Công cụ đánh giá, xuất và quản lý release là các bước tách biệt.

## 13.5 Lưu trữ sao lưu và phục hồi

Các nhóm tài sản cần nhận diện trong vận hành gồm dữ liệu SQL Server, hai SQLite, tri thức JSON, danh mục địa điểm, manifest phát hành, GGUF và checkpoint huấn luyện. Repository hiện có hồ sơ phục hồi, kiểm tra hash và các công cụ sao chép hoặc xuất tài sản mô hình; không có màn hình quản trị sao lưu SQL hoặc lịch sao lưu cơ sở dữ liệu được khai báo trong source ứng dụng.

Đợt phục hồi đã giữ lại một checkpoint trọng số gộp để làm điểm bắt đầu cho LoRA mới. Checkpoint gộp không khôi phục chính xác optimizer, RNG hoặc adapter riêng của lần học cũ. Công cụ training_resume xử lý trạng thái học nếu có đầy đủ tệp cần thiết; thiếu tài sản không được ghi nhận như một lần resume đúng trạng thái. Việc lưu snapshot SQL giúp sử dụng lại cache còn hạn sau khi khởi động lại ứng dụng.

## 13.6 Phạm vi bảo mật hiện có

Flask chỉ công bố thư mục static, không phục vụ toàn bộ thư mục dự án; native server chỉ lắng nghe loopback. Truy vấn nghiệp vụ dùng tham số và lỗi SQL được ghi log, còn người sử dụng nhận thông báo chung. CSV xử lý ký tự có nguy cơ bị hiểu như công thức, nội dung chat dùng textContent. Các thao tác ghi học và góp ý có kiểm tra Origin theo những nhánh được triển khai.

# CHƯƠNG 14  KẾT QUẢ PHÂN TÍCH VÀ THIẾT KẾ

Hồ sơ xác định hệ thống demoth1 là ứng dụng giám sát môi trường theo địa điểm, gồm giao diện web, API Flask, lưu trữ SQL Server, bản đồ AQI, báo cáo và trợ lý Xanh Non. Phần nghiệp vụ được phân tích thành 18 chức năng, tám màn hình hoặc phần giao diện, các quy tắc dữ liệu và điều kiện nghiệm thu tương ứng. Các sơ đồ thể hiện thống nhất giữa luồng cập nhật, quan hệ lưu trữ, quá trình tạo báo cáo và điều phối hội thoại.

Phân tích theo chức năng làm rõ dòng dữ liệu và thứ tự xử lý. Mô hình UML bổ sung trách nhiệm của các lớp triển khai, tương tác giữa thành phần và vòng đời runtime. ERD giữ nguyên sáu bảng SQL Server, phân biệt hai khóa ngoại vật lý với liên kết địa điểm ở tầng ứng dụng; hai kho SQLite được mô tả riêng theo nhiệm vụ góp ý và học câu hỏi.

Thiết kế giao diện được đối chiếu theo hành vi thực tế của menu, tìm kiếm, định vị, chuông cảnh báo, bản đồ, báo cáo và chat nổi. Phần dữ liệu phân biệt nguồn mô hình, tiếng ồn tổng hợp, snapshot ứng dụng và dự báo; các nhãn RF được tách khỏi US AQI. Phần chatbot phân biệt nhánh quy tắc, truy xuất tri thức, đọc dữ liệu theo ngữ cảnh và suy luận mô hình cục bộ.

Các kết quả kiểm thử được ghi theo hồ sơ thực tế, kèm điều kiện và phạm vi. Những nội dung như quản trị tài khoản, CRUD trạm, quy trình xử lý cảnh báo hoặc hồ sơ cá nhân không thuộc phiên bản được khảo sát. Báo cáo kết thúc ở cấu trúc và hành vi hiện có của hệ thống, với bảng API và danh mục bằng chứng mã nguồn làm căn cứ tra cứu.

# PHỤ LỤC A  DANH MỤC API

Các hợp đồng dưới đây lấy từ các route Flask và blueprint hiện có. location không truyền dùng hanoi; mã không hợp lệ trả 400. Những giới hạn limit được chặn về miền cho phép ở API; không mô tả chúng như tham số phân trang tùy ý không giới hạn.

Bảng 34. Các hợp đồng API của ứng dụng



Phương thức và đường dẫn | Đầu vào và kiểm tra | Đầu ra và dữ liệu liên quan

GET /api/diadiem | Không có payload | Danh sách 86 địa điểm; chuẩn bị metadata qua LocationStore.

GET hoặc POST /api/capnhat | location trong query; thuộc danh mục | Snapshot hoàn chỉnh; đọc ghi NguonDL, CanhBao, PhanTichAI; cache 600 giây.

GET /api/dulieu/moinhat | location | Hàng NguonDL gần nhất hoặc {}; không cùng cấu trúc ngoài cùng với /capnhat.

GET /api/dulieu/lichsu | location; limit mặc định 12, trong 1–500 | Danh sách NguonDL được trả theo thứ tự cũ tới mới.

GET /api/canhbao | location; limit mặc định 20, trong 1–200 | Cảnh báo mới nhất theo địa điểm thông qua JOIN NguonDL.

GET /api/phantich | location; limit mặc định 1, trong 1–50 | Các hàng PhanTichAI mới nhất theo địa điểm.

GET /api/bando/khongkhi | location; cả bốn south west north east nếu chỉ định phạm vi | Trục tọa độ, ma trận AQI/PM25, thời gian nguồn và cảnh báo thiếu; tối đa 196 điểm.

POST /api/chat | JSON message history location; stream, learn_from_chat tùy chọn | JSON reply, truncated hoặc SSE status/delta/done/error; có giới hạn body, lịch sử và khóa sinh.

GET /api/chat/status | Không có payload | state và có thể có background_training; không gọi sinh văn bản.

POST /api/chat/feedback | JSON góp ý theo validate_feedback; Origin hợp lệ; tối đa 512 KiB | 201 saved=true khi ghi được; kho SQLite, không công khai danh sách góp ý qua API.

POST /api/baocao | JSON days là int 1, 7, 30; location | 201 cùng MaBaoCao sau khi lưu BaoCaoMT.

GET /api/baocao | location; limit mặc định 10, 1–50; offset 0–1.000.000 | Danh sách metadata mới nhất; đọc BaoCaoMT.

GET /api/baocao/<int:report_id> | Mã trên đường dẫn; location trong query | Nội dung snapshot đã lưu; 404 nếu không cùng nơi hoặc không tồn tại.

## A.1 Dữ liệu câu hỏi và lịch sử

message bắt buộc là chuỗi có nội dung sau khi loại khoảng trắng. history là danh sách có số phần tử chẵn, tối đa 16, bắt đầu bằng user rồi assistant; mỗi content phải có nội dung và không dài quá 32.768 ký tự. Trường stream chỉ kích hoạt đường SSE khi bằng true. Các kiểm tra này chặn cấu trúc yêu cầu sai nhưng không phải xác thực danh tính.

## A.2 Phân biệt dữ liệu trả về

/api/capnhat trả bộ kết quả điều phối đã ghép; /api/dulieu/moinhat trả hàng dữ liệu NguonDL. Khi cần snapshot đầy đủ từ hàng SQL, xử lý phải đọc và kiểm tra ChiTiet. /api/phantich trả danh sách phân tích lưu theo nguồn, không trực tiếp gọi mô hình ngôn ngữ. /api/baocao/<id> trả nội dung đã lưu để giữ khả năng tái hiện báo cáo.

# PHỤ LỤC B  BẰNG CHỨNG MÃ NGUỒN

Bảng 35. Danh mục mã nguồn phục vụ kiểm chứng



Mã | Tệp và điểm xử lý | Nội dung đối chiếu

S01 | app.py: capnhat, update_environment, fetch_environment | Nguồn dữ liệu, cache, giao dịch và snapshot.

S02 | app.py: build_alerts, build_analysis, các route đọc | Ngưỡng, nhãn phân tích, giới hạn truy vấn và lọc địa điểm.

S03 | location_catalog.py: get_location, LocationStore; locations.json | Danh mục, địa danh và đồng bộ SQL.

S04 | noise_data.py: read_cells, aggregate_noise, NoiseData | Lọc vùng, tổng hợp năng lượng và cache tệp tiếng ồn.

S05 | environment_predictor.py: load_model, predict_environment | Đặc trưng, nhãn, dữ liệu thiếu và bundle RF.

S06 | air_quality_map.py: make_grid, AirMapRepository | Lưới, nguồn CAMS Global, số điểm và cache theo giờ.

S07 | environment_reports.py: build_report, ReportRepository | Thống kê, kỳ, snapshot báo cáo và cách ly địa điểm.

S08 | Demodatabase.sql; location_schema.sql; report_schema.sql; air_map_schema.sql | Sáu bảng, hai FK vật lý và các chỉ mục.

S09 | static/index.html; dashboard.js; dashboard.css | Bố cục, điều hướng hash, menu, chuông và tìm kiếm.

S10 | static/locations.js; script.js | Định vị, lựa chọn, cache trên giao diện, trạng thái tải và đồ thị.

S11 | static/map.js; air-overlay.js; tests/test_air_overlay.cjs | Tương tác bản đồ, nội suy và thang màu.

S12 | static/reports.js; static/chat.js | Báo cáo, xuất tệp, chat nổi, history và luồng SSE.

S13 | chatbot.py: validate_chat, _generate_raw, _dialogue_question, stream_reply | Kiểm tra dữ liệu, thứ tự nhánh trả lời và ngữ cảnh.

S14 | chat_scope.py; chat_clarification.py; chat_time_context.py | Phạm vi, câu hỏi làm rõ và mốc thời gian.

S15 | chat_air_data.py; chat_weather_data.py | Nguồn hiện tại, dự báo, cache và kiểm tra chuỗi giờ.

S16 | chat_knowledge.py; chat_output.py; data/xanhnon/knowledge.json | Tra cứu TF-IDF, tài liệu có nguồn và xử lý đầu ra.

S17 | chat_feedback.py; chat_learning.py; feedback_training_data.py | Góp ý, câu hỏi mới, trạng thái duyệt và dữ liệu học.

S18 | native_chatbot.py; model_release.py; models/xanhnon-active.json | Tiến trình suy luận, vòng đời và nhận diện bản phát hành.

S19 | train_xanhnon.py; daily_train_xanhnon.py; export_xanhnon.py | Tinh chỉnh, lịch tự động, kiểm tra tài nguyên và xuất ứng viên.

S20 | training_state.py; training_resume.py; sensor_training_data.py | Khóa học, điều kiện resume và xử lý nguồn cảm biến.

## B.1 Hồ sơ kiểm thử được sử dụng

Thư mục recovery/history-restoration-20261027 chứa restoration-state.json, live-verification.json, browser-checks.json, runtime-tests-final.txt, backend-tests-final.txt, training-seed-export-tests.txt và javascript-tests.txt. Các ảnh home-live-desktop.png, home-live-mobile.png và trends-restored-1600.png được lấy từ cùng hồ sơ. Kết quả bổ sung phục vụ tài liệu được lưu trong docs/system-analysis-design/qa/document-evidence-tests.json và log tương ứng.

## B.2 Phạm vi đối chiếu phiên bản

Các tệp chính được kiểm tra SHA-256 với danh mục source_sha256 của hồ sơ khôi phục. Kiểm tra tại thời điểm biên soạn không ghi nhận thay đổi ở các tệp có trong danh mục đó. Việc này xác định phạm vi mã đã đối chiếu, không có nghĩa mọi tệp trong toàn bộ repository đều đã được kiểm toán bảo mật.

# TÀI LIỆU THAM KHẢO

Các tài liệu trực tuyến được kiểm tra ngày 27/10/2026. Mã nguồn dự án và các hồ sơ kiểm thử ở phụ lục B là nguồn chính cho các chức năng, cấu hình, số liệu và trạng thái triển khai được mô tả trong báo cáo.

[T01] Open-Meteo. Weather Forecast API. Tài liệu biến thời tiết và dữ liệu theo giờ. 

[T02] Open-Meteo. Air Quality API. Tài liệu biến chất lượng không khí, AQI và dữ liệu mô hình. 

[T03] Noise-Planet. NoiseCapture. Giới thiệu dữ liệu cộng đồng và phương pháp thu thập. 

[T04] Object Management Group. Unified Modeling Language version 2.5.1. 2017. 

[T05] Pallets Projects. Modular Applications with Blueprints. Flask Documentation. 

[T06] Microsoft. Primary and foreign key constraints. SQL Server documentation. 

[T07] Leaflet. API reference for Leaflet 1.9.4. 

[T08] AirNow. Air Quality Index Basics. Tài liệu về sáu mức US AQI. 

[T09] ggml-org. llama.cpp. Mã nguồn và hướng dẫn chạy mô hình cục bộ. 

[T10] González, Óscar và cộng sự. iSCAPE Outdoor Sensor Deployment Data. Zenodo, 2019. 

[T11] González, Óscar và cộng sự. iSCAPE Citizen Science Workshops Data. Zenodo, 2019. 

[T12] González, Óscar; Barberán, Víctor; Camprodon, Guillem. iSCAPE Low Cost Sensor Development Data. Zenodo, 2019. 

[T13] UCI Machine Learning Repository. Beijing Multi-Site Air Quality. Dataset 501, 2019. 

[T14] Hugging Face. Low-Rank Adaptation. PEFT documentation. 

[T15] Themesberg. Volt Bootstrap 5 Dashboard. Mã nguồn và giấy phép MIT. 