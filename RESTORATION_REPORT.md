# Phục hồi project demoth1 — 26–27/10/2026

## Cập nhật phục hồi theo lịch sử chat, 27/10

Bản chức năng mới đã được ghép vào `D:/Recovered-demoth1-20261026` và chạy tại http://127.0.0.1:5000. Đã phục hồi giao diện Volt/menu Tabler, chat bong bóng, ba phần tổng quan, tìm kiếm đầu trang, chuông cảnh báo, định vị gần nhất, trục số biểu đồ và các sửa ngữ cảnh chatbot ngày 24/10.

Đã lấy lại 21 phiên bản dataset và lập danh mục 388 tệp nguồn còn ở D:. Tập mặc định gồm 452 hội thoại train và 124 validation, không trùng nhóm/cặp hỏi đáp giữa hai tập. Toàn bộ được mã hóa trọn vẹn ở giới hạn 1536 token. Pool có đánh giá ngữ nghĩa không đạt được lưu riêng, không trộn vào tập này.

Trọng số phục vụ vẫn là Style-v2 đã xác minh. Tệp `C:/Codex-demoth1-intermediates-20261019/style-v2-merged.safetensors` được kiểm tra đủ 290 tên/chiều tensor và SHA-256, sao chép thành nền huấn luyện riêng. Khi không còn adapter LoRA gốc, lượt train sau tạo LoRA mới trên checkpoint đã gộp này; không khẳng định khôi phục optimizer/adapter cũ.

Lịch Windows `XanhNon-Train-Reviewed-Data` được sửa đường dẫn sang bản D:, giữ các trigger cũ. Job chỉ tạo candidate, không tự thay trọng số đang phục vụ. Bước kiểm tra thực ghi `waiting_for_memory`; không tuyên bố đang train khi chưa có tiến trình trainer. Đã thêm chặn chạy thêm ứng dụng khi cổng 5000 đã phục vụ Xanh Non để tránh nạp trùng mô hình.

Chi tiết và bằng chứng: [RESTORED_FEATURES.md](RESTORED_FEATURES.md), `recovery/history-restoration-20261027/`. Các phần bên dưới ghi lại việc phục hồi ban đầu ngày 26/10.

## Mở và chạy

- Thư mục: `D:\Recovered-demoth1-20261026`.
- Ứng dụng đang phục vụ tại http://127.0.0.1:5000.
- Mở `run_project.cmd` để chạy. Nếu ứng dụng đã hoạt động, file này mở trang đang chạy.
- Cửa sổ chạy ứng dụng cần được giữ mở; nhấn Ctrl+C để dừng khi tự chạy từ terminal.

```powershell
cd D:\Recovered-demoth1-20261026
.\run_project.cmd
```

## Phần đã phục hồi

- Đủ 243 file được quản lý trên nhánh main của repo `CTY-TNHH-1mktoi/quanli-moitruong-dothi`, commit `814eccea39dc5a5917a65598912a77a587e759f4`, ngày 10/10/2026. Gồm backend, giao diện, danh mục, SQL, báo cáo, mô hình Random Forest, runtime llama.cpp và các kiểm thử.
- Hai tài sản Git LFS gốc, tổng khoảng 1,98 GB, đã được xác minh SHA-256.
- Mô hình đang được chọn trước khi mất dữ liệu: **XanhNon-Style-v2**. Tệp GGUF có SHA-256 `faafda1900c033ab1ae89f2c7881229d8aa08a1a564405149669ab9e0ad3f1d2`.
- Đã khôi phục `models/xanhnon-active.json` với SHA-256 khớp bản ghi cũ: `6e16a3c432e6440877e025f877530f9c3ad623d43c745016af028fcab2f78564`.
- Bộ dữ liệu tiếng ồn NoiseCapture Vietnam.zip đã tải lại và kiểm tra cấu trúc ZIP.
- Database SQL Server `GiamsatMT` còn 225 snapshot và 86 địa điểm trước kiểm tra phục hồi. Lượt cập nhật thật đã tạo snapshot Hà Nội #226 theo hoạt động thông thường.
- Có bản sao lưu database tại `recovery/database/GiamsatMT-20261026.bak`, dung lượng khoảng 3 MB; SQL Server đã xác minh bằng RESTORE VERIFYONLY WITH CHECKSUM. Sao lưu dùng COPY_ONLY và không thay thế database đang dùng.
- Môi trường `.venv` dùng các thư viện Python đã cài trên máy. scikit-learn 1.8.0 được cài riêng trong `.venv`, khớp phiên bản của mô hình RF.

## Kết quả kiểm tra

- 34 kiểm thử Python và 13 kiểm tra JavaScript đạt.
- Trang chủ và 9 tài nguyên JavaScript/CSS trả HTTP 200; API địa điểm trả đủ 86 địa điểm.
- API cập nhật môi trường trả HTTP 200; nhiệt độ, PM, AQI và tiếng ồn được đọc từ nguồn dữ liệu hiện có.
- Chatbot nạp bằng llama.cpp với mô hình Style-v2; streaming kết thúc tự nhiên và câu thử địa điểm trả “Hà Nội.”.
- Random Forest thực chạy với scikit-learn 1.8.0 và không phát sinh cảnh báo lệch phiên bản trong lượt kiểm tra.
- Các kết quả này xác minh khả năng hoạt động của bản phục hồi; không khẳng định mọi câu trả lời AI đều chính xác.

## Giới hạn của bản phục hồi ban đầu ngày 26/10

Mã nguồn đang chạy dựa trên bản GitHub ngày 10/10, cùng mô hình Style-v2 đã khôi phục. Các thay đổi ứng dụng chưa push sau ngày đó chưa có đủ toàn bộ file để khôi phục nguyên vẹn phiên bản ngày 24/10.

Những bản nguồn đọc được ngày 24/10 đã giữ tại `recovery/partial-uncommitted-sources/`, gồm chatbot.py, chat_scope.py, chat_clarification.py, chat_air_data.py, chat_time_context.py, location_catalog.py và một số kiểm thử. Các bản ghi triển khai và bản diff cũng được giữ.

Phiên bản chatbot đó cần thêm các module như chat_output.py, chat_weather_data.py, model_release.py và training_state.py; bản app.py mới và dữ liệu kiến thức tương ứng cũng chưa được khôi phục đầy đủ. Vì vậy các bản nguồn này được bảo quản riêng, chưa được ghép vào bản chạy hiện tại. Các file bytecode thu được từ File Recovery có phần đầu không hợp lệ và chưa dùng được.

Các mô hình thử nghiệm và dữ liệu huấn luyện còn tại `D:\XanhNon-auto-training` và `C:\Codex-demoth1-intermediates-20261019`.

## Lưu ý về các bản sao

Tệp mô hình trong project dùng liên kết cứng NTFS tới các đối tượng LFS còn trên D:, để dùng lại dữ liệu đã có. Khi xuất hoặc huấn luyện mô hình mới, hãy ghi ra tên tệp mới; ghi đè trực tiếp tệp đã nối cứng sẽ thay đổi cả bản được liên kết.

Thư mục recovery chứa bản sao database và dữ liệu kiểm tra cục bộ; hãy kiểm tra trước khi đưa các tệp này lên một repo công khai. C: và D: cùng nằm trên một SSD, nên bản phục hồi và bản sao lưu database cần được chép sang thiết bị khác để có thêm một bản độc lập.

Chi tiết đối chiếu nằm trong `recovery/restore-manifest.json`, `recovery/final-checks.json`, `recovery/live-checks.json`, `recovery/unit-tests.txt` và `recovery/javascript-tests.txt`.
