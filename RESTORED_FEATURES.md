# Chức năng được phục hồi theo lịch sử chat — 27/10/2026

## Chạy và mở project

Thư mục thực: `D:/Recovered-demoth1-20261026`. Chạy `run_project.cmd`, mở http://127.0.0.1:5000. Các thay đổi đã được nạp vào ứng dụng đang phục vụ. Mở lại trang hoặc dùng Ctrl+F5 nếu trình duyệt còn giữ tài nguyên cũ.

## Giao diện

| Yêu cầu đã chốt | Đã phục hồi |
| --- | --- |
| Giao diện Volt, menu kiểu Tabler | CSS Volt Free 1.4.1 có giấy phép MIT; menu dọc nền tối |
| Nút ba gạch mở menu | Mặc định thu gọn; mở có X; ẩn nút ba gạch khi đang mở |
| Tổng quan chỉ có ba phần | Khu vực đang giám sát, chỉ số môi trường, bản đồ |
| Chức năng khác mở từ menu | Chỉ số, bản đồ, xu hướng, phân tích/tư vấn, báo cáo; có điều hướng hash và quay lại |
| Tìm kiếm trên đầu trang | Tìm địa điểm hoặc chức năng, có dấu/không dấu, hỗ trợ bàn phím |
| Đưa lịch sử cảnh báo vào chuông | Mở/đóng bảng cảnh báo; số lượng và nội dung theo địa điểm |
| Cập nhật dữ liệu nằm trên giờ cập nhật | Cùng khối bên phải khu vực đang giám sát |
| Ô chọn địa điểm ngắn hơn | Khoảng 350px trên desktop, thích ứng màn hình nhỏ |
| Lấy vị trí hiện tại | Xin quyền khi bấm; chọn địa điểm gần nhất trong 86 địa điểm bằng khoảng cách tọa độ; nhớ lựa chọn |
| Trục số biểu đồ | Mốc số theo khoảng dữ liệu, có mốc 0/10 trong trường hợp kiểm tra |
| Ẩn thanh cuộn | Vẫn cuộn được bằng chuột, cảm ứng, bàn phím |
| Xanh Non dạng bong bóng | Mở, thu gọn, giữ hội thoại khi đóng; dừng/viết tiếp; tối đa 8 cặp hỏi đáp trong ngữ cảnh |
| Bỏ thẻ quảng bá chat bên menu | Không còn thẻ “Cùng Xanh Non hiểu môi trường” |
| Góp ý bằng lời | Nhắn “hữu ích”, không có nút chấm điểm trong chat |

Đã kiểm tra trên Edge headless ở 1600px và 390px: không lỗi JavaScript hoặc tràn ngang. Kiểm tra định vị bao phủ cấp/từ chối quyền, timeout, tọa độ lỗi, đổi tay khi đang định vị và trình duyệt không hỗ trợ. Kiểm thử dùng fixture có kiểm soát, không ghi số liệu cảm biến giả vào database.

## Chatbot và dữ liệu

- Khôi phục các bản nguồn ngày 24/10 có SHA-256 trùng bản ghi đã triển khai, cùng các module phụ thuộc còn trong lịch sử chỉnh sửa.
- Giữ chủ đề, thành phố, ngày và giờ khi hỏi “còn độ ẩm?”, “còn AQI?”, “còn Đà Nẵng?”, “còn ngày kia?”, “đổi sang 19h”.
- Hỏi lại khi thiếu ngày hoặc chưa rõ chủ đề; giải thích vì sao cần biết giờ. Lời cảm ơn/gọi trợ lý không làm mất ngữ cảnh.
- Dự báo theo giờ từ Open-Meteo/CAMS; không lấy số hiện tại hoặc số trong câu trả lời cũ để kết luận cho ngày mai.
- Câu hỏi thời tiết chỉ trả thông tin liên quan; lọc lời chỉ dẫn nội bộ và câu nhận xét thừa về điều người dùng không hỏi.
- Kho kiến thức hiện có 26 mục; truy xuất các nội dung và nguồn đã lưu, không dùng dữ liệu hội thoại thô làm tài liệu chuyên môn.
- Tư vấn giảm bụi trả biện pháp cụ thể, không dừng ở câu dẫn. Câu ngoài phạm vi dùng lời giới thiệu Xanh Non đã chốt.
- Lưu góp ý/câu hỏi trên SQLite cục bộ; dữ liệu chưa được duyệt không tự trở thành trọng số phục vụ.
- Bản đồ, Random Forest, báo cáo lưu/CSV/PDF và database cũ được giữ. Không xóa bản ghi quan trắc hoặc báo cáo.

## Dữ liệu huấn luyện

- `data/training-restored/registry.json`: danh mục 21 phiên bản tập dữ liệu, checksum, vị trí bản gốc và 388 tệp nguồn.
- `data/training-restored/datasets/`: bản khôi phục từng train/validation, manifest, giấy phép, NOTICE và báo cáo chất lượng. Tệp giống nhau dùng chung nội dung trong kho cục bộ; không nối cứng tới bản gốc trên D:.
- `data/xanhnon/train.jsonl`: 452 mẫu đã chọn; `validation.jsonl`: 124 mẫu.
- Đã loại 173 bản hội thoại trùng và 23 mẫu giao nhau với nhóm/cặp hỏi đáp validation trong các tập được chọn. Không cắt câu trả lời để đạt giới hạn độ dài.
- Có dữ liệu từ iSCAPE Outdoor, Workshops, Low Cost Sensor Development và Beijing Multi-Site; dữ liệu ở nước ngoài giữ nguyên phạm vi và nguồn, không mô tả như số đo hiện tại tại Việt Nam.
- Các pool hội thoại tiếng Việt đã tải được giữ trong kho phục hồi. Pool có quyết định `candidate_pool_requires_semantic_curation` và dữ liệu cũ có vấn đề căn chỉnh được tách khỏi tập mặc định.
- Preflight thực: 452/452 train, 124/124 validation được mã hóa đầy đủ, tổng 254.387 token; chưa chạy optimizer trong bước này.

```powershell
cd D:\Recovered-demoth1-20261026
.\.venv\Scripts\python.exe train_xanhnon.py --data-dir data\xanhnon --max-length 1536 --threads 2
.\.venv\Scripts\python.exe daily_train_xanhnon.py --check
```

Không thêm `--train` vào lệnh kiểm tra dữ liệu nếu chỉ cần kiểm tra. Job hằng giờ có giới hạn bộ nhớ/dung lượng, bỏ qua dữ liệu chưa đổi, lưu checkpoint và tạo candidate để đánh giá riêng. Một lượt tự động chọn tối đa 128 mẫu theo nguồn; không coi đó là đã huấn luyện trọn tập 452 mẫu. Candidate không tự thay thế mô hình đang chạy.

## Trọng số và giới hạn phục hồi

- GGUF đang phục vụ: `models/xanhnon-style-v2-f16.gguf`, SHA-256 `faafda1900c033ab1ae89f2c7881229d8aa08a1a564405149669ab9e0ad3f1d2`.
- Manifest đang chọn có SHA-256 `6e16a3c432e6440877e025f877530f9c3ad623d43c745016af028fcab2f78564`.
- Nền huấn luyện riêng lấy từ tệp merged bạn cung cấp trên C:, SHA-256 `a0c48e0724a400d16f8301d00e7efb98d45b2db0bbcc56852501889792785fc4`. Đã đối chiếu 290 tên và chiều tensor với nền Qwen. Không sửa tệp gốc C: hoặc các đối tượng LFS trên D:.
- Adapter/optimizer gốc Style-v2 chưa được lấy lại dưới dạng riêng. Lượt fine-tune mới dùng checkpoint merged làm nền và khởi tạo adapter mới, không giả lập việc tiếp tục đúng bước train cũ.
- Một số markup chat phải dựng lại theo yêu cầu đã chốt; không khẳng định mọi byte giao diện giống hệt bản đã mất. Các sửa lỗi hội thoại có bản snapshot được kiểm tra checksum.
- Các adapter 4B từng bị loại không được áp dụng. Giới hạn danh mục địa điểm, độ phân giải theo giờ và phụ thuộc mạng của nguồn vẫn còn.

## Bằng chứng

`recovery/history-restoration-20261027/` chứa bản nguồn trước khi ghép, nhật ký trích patch, đối chiếu snapshot, 177 kiểm thử hội thoại/kiến thức/học từ góp ý, 30 kiểm thử bản đồ/báo cáo/địa điểm/nền train, kết quả trình duyệt, API thật, preflight, lịch Windows trước/sau và ảnh giao diện. Đây là kiểm tra phục hồi chức năng, không phải chứng nhận độ chính xác chuyên môn tổng quát.
