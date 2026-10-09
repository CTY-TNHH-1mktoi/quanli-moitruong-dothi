# Kết quả kiểm thử — 07/10/2026

Môi trường: Flask tại `http://127.0.0.1:5000`, SQL Server `GiamsatMT`, trình duyệt Edge chạy tự động, mô hình Xanh Non gốc qua llama.cpp trên CPU.

## Kết quả

| Phần kiểm tra | Kết quả quan sát |
|---|---|
| Kiểm thử tự động Python | 34/34 đạt; lần chạy 10/10/2026 mất 25,570 giây |
| Danh mục địa điểm | API trả 86 lựa chọn; SQL có metadata của đủ 86 địa điểm |
| Tìm kiếm trên giao diện | Tìm `cau giay` nhận được Cầu Giấy |
| Đổi địa điểm | Chỉ số, lịch sử và báo cáo cập nhật theo nơi chọn |
| Phản hồi cũ đến muộn | Không ghi đè dữ liệu của địa điểm mới |
| Tải lại trang | Giữ địa điểm đã chọn |
| Giao diện điện thoại | Kiểm tra chiều rộng 390 px; không tràn ngang toàn trang |
| CSV báo cáo | 17 cột, đúng mã địa điểm, tên file có địa điểm, tiếng Việt UTF-8 BOM |
| Cập nhật đồng thời | 4 yêu cầu TP.HCM trả cùng bản ghi #97; không tạo thêm bản ghi khi cache còn hiệu lực |
| Lưu snapshot SQL | JSON trong `NguonDL.ChiTiet` khớp phản hồi API |
| Lịch sử, cảnh báo, phân tích | Các bản ghi trả về thuộc đúng địa điểm |
| Lưu và mở báo cáo | Báo cáo TP.HCM #6 lưu thật trong SQL; mở lại khớp toàn bộ nội dung |
| Mở báo cáo sai địa điểm | HTTP 404 |
| Kỳ báo cáo hoặc địa điểm không hợp lệ | HTTP 400 |
| Báo cáo Hà Nội cũ | Báo cáo #1 vẫn mở được |
| Khởi động lại server | Dùng lại snapshot #97 còn hạn từ SQL |
| Hội thoại theo địa điểm | Không trộn lịch sử TP.HCM và Hà Nội; khóa bộ chọn trong lúc trả lời |
| Trạng thái cuối | Flask vẫn chạy; chatbot `ready` |

## Lỗi đã phát hiện và sửa

Mô hình từng trả lời rằng chưa biết địa điểm, dù tên TP.HCM có trong thông điệp hệ thống. Đã bổ sung dữ liệu bảng giám sát vào lượt hỏi hiện tại, nêu rõ địa điểm và những chỉ số chưa có dữ liệu. Thay đổi nằm trong `chatbot.py`, kèm kiểm thử hồi quy trong `tests/test_locations.py`.

Ba câu thử trực tiếp qua `/api/chat` sau sửa đều kết thúc tự nhiên, không giới hạn độ dài hoặc thời gian sinh câu trả lời:

| Câu hỏi | Phản hồi thực tế | Chữ đầu tiên | Hoàn tất |
|---|---|---|---|
| Địa điểm đang chọn là gì? | Thành phố Hồ Chí Minh. | 5,19 giây | 5,88 giây |
| PM2.5 ở địa điểm đang chọn là bao nhiêu? | PM2.5 ở địa điểm đang chọn là 52.7 µg/m³. | 0,55 giây | 2,77 giây |
| Tiếng ồn ở địa điểm đang chọn là bao nhiêu? | Tiếng ồn tại địa điểm đang chọn trên bảng giám sát là chưa có dữ liệu. | 0,55 giây | 2,50 giây |

Số PM2.5 và tình trạng thiếu tiếng ồn được đối chiếu với snapshot TP.HCM #97. Các thời gian trên là kết quả của ba câu thử này.

## Chạy lại kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Kiểm thử trình duyệt nằm trong `tests/browser/check_locations.py`; các phản hồi chatbot thực tế được ghi tại `.runtime/test-results/chat-grounding.json`. Kiểm thử API/SQL trước đó đã tạo báo cáo #6 từ dữ liệu thật để xác minh lưu và mở lại.

## Kiểm thử bổ sung: bản đồ địa điểm

Đã chạy `tests/browser/check_map.py` với Edge và nền bản đồ thật:

- Hà Nội có dấu vị trí thời tiết/không khí và dấu tham chiếu tiếng ồn Cầu Giấy; nội dung khi bấm từng dấu đúng tên và tọa độ.
- Chuyển sang TP.HCM xóa dấu cũ; yêu cầu ảnh nền chứa đúng ô bản đồ của tọa độ đã chọn.
- Phóng to, nút trở về địa điểm, liên kết mở bản đồ lớn và nhớ địa điểm sau tải lại hoạt động.
- Giao diện 390 px không tràn ngang; tên nguồn bản đồ vẫn hiển thị.
- Giả lập nền bản đồ không kết nối được: dấu vị trí/tọa độ vẫn còn, có nút thử lại; khôi phục kết nối và thử lại tải được nền.
- Không có lỗi JavaScript trong các tình huống trên. Kiểm thử này giữ API dữ liệu bằng phản hồi giả để không tạo thêm bản ghi hoặc báo cáo.

## Kiểm thử bổ sung: lớp màu chất lượng không khí

- 7 bài Python mới về phạm vi, giới hạn số điểm, gắn đúng tọa độ nguồn, dữ liệu thiếu, dùng chung cache đồng thời và lỗi nguồn; toàn bộ 34 bài Python đạt.
- `node tests/test_air_overlay.cjs`: 13 kiểm tra nội suy/thang màu đạt, gồm AQI bằng 0, vùng ngoài lưới, góc thiếu dữ liệu và giá trị vượt 500.
- API thật quanh Hà Nội và TP.HCM: mỗi vùng mặc định có 140 điểm hợp lệ; số mẫu mỗi lượt không vượt 196. Địa điểm sai trả 400; vùng ngoài phạm vi trả lưới rỗng.
- SQL lưu cả chỉ số và JSON nguồn. Một repository mới đọc lại đúng mẫu trong SQL, không chèn thêm khi các điểm còn trong giờ hiện tại.
- `tests/browser/check_air_map.py`: Edge hiển thị lớp màu thật tại Hà Nội, TP.HCM, Huế; thử nút bật/tắt, độ đậm, toàn màn hình, thông tin AQI khi bấm bản đồ, màn hình 390 px và khôi phục sau lỗi nguồn.
- Thử phản hồi Hà Nội đến muộn sau khi chọn TP.HCM: lớp màu TP.HCM giữ nguyên. Không có lỗi JavaScript.
- Thời gian nguồn và bước lấy mẫu được hiển thị; đây là màu nội suy từ mô hình, không phải bản đồ các trạm đo trực tiếp.

## Lần kiểm thử và dọn dự án mới nhất

- 34/34 kiểm thử Python và 13 kiểm tra JavaScript đạt; cú pháp tất cả mã Python và JavaScript của ứng dụng hợp lệ.
- Chạy lại cả 3 kịch bản Edge trong `tests/browser/`: bản đồ AQI, bản đồ địa điểm và bộ chọn/báo cáo/hội thoại đều đạt. Giao diện 390 px không tràn ngang; không ghi nhận lỗi JavaScript.
- Snapshot Hà Nội #109 và TP.HCM #110 khớp JSON lưu trong SQL; API lịch sử và báo cáo tách đúng địa điểm. Báo cáo #6 vẫn mở được tại TP.HCM và trả 404 khi mở tại Hà Nội.
- SQL có đủ 86 địa điểm và 663 mẫu AQI tại thời điểm kiểm tra. Đối chiếu 20 mẫu gần nhất với tọa độ, chỉ số và JSON nguồn: khớp. Hai lần tải lại cùng vùng AQI trả kết quả giống nhau, không thêm bản ghi.
- Nạp mô hình Random Forest thật: dự đoán được khi đủ chỉ số, báo thiếu dữ liệu khi thiếu tiếng ồn. Chatbot hiện có trạng thái `ready`; phiên này không gửi câu sinh văn bản mới.
- Gom kịch bản trình duyệt vào `tests/browser/`, fixture vào `tests/fixtures/`, ảnh/kết quả vào `.runtime/test-results/`. Thêm cấu hình thư viện kiểm thử tùy chọn và hướng dẫn chạy lại trong README.
- Bỏ các lời gọi tải AQI lặp, sửa thụt dòng và bỏ biến/import thừa trong kịch bản bản đồ. Import kịch bản không tự chạy trình duyệt.
- Xóa 7 ảnh kiểm thử cũ, 18 file bytecode và 6 thư mục rỗng. Dữ liệu SQL, mô hình, binary chatbot, dữ liệu tiếng ồn và ảnh xem trước đã gửi được giữ nguyên.
- Kết quả API/SQL: `.runtime/test-results/api-sql.json`. Flask và chatbot tiếp tục chạy sau khi dọn.

## Chuẩn bị bàn giao GitHub — 10/10/2026

- Chạy lại 34 kiểm thử Python: đạt, 25,570 giây. Đây là kiểm thử đơn vị với mock, không khởi chạy mô hình thật hoặc ghi dữ liệu SQL.
- `node tests/test_air_overlay.cjs`: 13 kiểm tra đạt.
- Kiểm tra khối code Markdown và liên kết file của README cùng 6 tài liệu nhóm: hợp lệ.
- Các kiểm thử trình duyệt/API/SQL thật trong phần trước là kết quả phiên 07/10/2026; chưa chạy lại các phần đó trong lượt bàn giao này.
- Giữ quy tắc `CODEOWNERS` của repository, thêm mẫu PR và kịch bản cho từng thành viên. Trong giai đoạn chỉ soạn hướng dẫn, chưa tạo commit mới, push, PR hoặc issue; staging và cấu hình tác giả tạm đã được gỡ.

## Kiểm tra bản nền theo ủy quyền của Giang — 10/10/2026

- Giang xác nhận là owner và ủy quyền thực hiện phần chuẩn bị repository cùng hai bước tài liệu trong `README.md`. Phần sửa ứng dụng của Kiên, Dương và Nghĩa vẫn là việc được giao, chưa thực hiện trong lượt này.
- Chạy lại `python -m unittest discover -s tests -v`: 34/34 bài đạt trong 21,525 giây. Kiểm thử dùng mock, không ghi SQL hoặc sinh câu trả lời từ mô hình thật.
- `node tests/test_air_overlay.cjs`: 13 kiểm tra đạt; `node --check` các file JavaScript trực tiếp trong `static/` thành công.
- Dọn khoảng trắng cuối dòng và dòng trống cuối `Demodatabase.sql`; không thay đổi câu lệnh hoặc thực thi SQL.
- Các kết quả trình duyệt/API/SQL trực tiếp ngày 07/10/2026 phía trên không được chạy lại trong lượt công việc Git này.
