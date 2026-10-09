# Luồng giao diện và kiểm tra UI/UX

Bản nháp tham khảo, chuẩn bị 10/10/2026. Người dự kiến rà soát: Tạ Đăng Dương. Đầu ra sau rà soát: `docs/frontend/UI_UX.md`.

## Luồng chính

1. Tìm/chọn địa điểm trong hero.
2. Cập nhật chỉ số, bản đồ, lịch sử, báo cáo và ngữ cảnh chatbot theo nơi đó.
3. Trên bản đồ: dấu tham chiếu, bật/tắt AQI, chỉnh độ đậm, kéo/zoom, trở về nơi đã chọn, toàn màn hình và bấm xem AQI nội suy.
4. Tạo/lưu báo cáo → mở từ lịch sử → tải CSV hoặc in/PDF.
5. Hỏi chatbot → nhận từng đoạn → có thể chủ động dừng; bộ chọn giữ nguyên trong lúc trả lời.

## Thành phần mã

| File | Phần phụ trách |
|---|---|
| `locations.js` | Danh mục, tìm không dấu, localStorage, sự kiện đổi nơi, trạng thái bận |
| `script.js` | Chỉ số, biểu đồ, cảnh báo, tải dữ liệu và bỏ phản hồi cũ |
| `map.js` | Vị trí, lớp AQI, kéo/zoom, popup, retry, toàn màn hình |
| `air-overlay.js` | Nội suy song tuyến tính và vẽ canvas theo tọa độ bản đồ |
| `reports.js` | Lịch sử, xem/tạo báo cáo, CSV, chế độ in |
| `chat.js` | SSE, hội thoại theo nơi, dừng/viết tiếp |
| `index.html`, `style.css` | Nội dung, bố cục, trạng thái, màn hình nhỏ |

## Trạng thái cần ghi nhận

| Trạng thái | Kết quả mong đợi |
|---|---|
| Đang tải | Có thông báo tiến trình; tránh hiểu số liệu cũ là của nơi mới |
| Thiếu dữ liệu | Hiển thị thiếu; không thành AQI/tiếng ồn bằng 0 |
| Nguồn bản đồ lỗi | Vị trí/tọa độ còn đọc được; retry khôi phục được nền/lớp AQI |
| Đổi nơi nhanh | Phản hồi cũ không ghi đè nơi hiện tại |
| Chat đang sinh | Hiển thị streaming; khóa chọn nơi theo trạng thái bận |
| Màn hình 390 px | Không tràn ngang; nút, nguồn và 6 mức màu đọc được |

## Bằng chứng cần chuẩn bị

- Ảnh desktop và 390 px của lần chạy mới, đã tránh thông tin riêng.
- Kết quả chạy `check_locations.py`, `check_map.py`, `check_air_map.py`.
- CSV đã kiểm tra mã địa điểm, 17 cột và UTF-8 BOM.
- Ghi vấn đề UI thực tế nếu có, sửa ở commit riêng và kiểm tra lại tình huống đó.
- Thang màu phải ghi US AQI; CAMS Global là mô hình khoảng 45 km, lớp màu không phải đo từng đường phố.

Ghi ngày/môi trường/kết quả ở `docs/frontend/TEST_RESULT.md`; ảnh kiểm thử tạo tại `.runtime/test-results/` có thể đính kèm PR sau khi kiểm tra nội dung.
