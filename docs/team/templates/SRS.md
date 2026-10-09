# Yêu cầu và tiêu chí nghiệm thu

Bản nháp tham khảo từ mã hiện có, chuẩn bị 10/10/2026. Người dự kiến rà soát: Nguyễn Trường Giang. Khi đưa vào `docs/requirements/SRS.md`, ghi người rà soát, ngày và các điều chỉnh đã xác nhận.

## Phạm vi

Dashboard giám sát môi trường theo địa điểm tại Hà Nội và các thành phố khác ở Việt Nam. Nguồn Open-Meteo/CAMS và NoiseCapture; lưu SQL Server; có bản đồ, báo cáo, RF và chatbot cục bộ. Dữ liệu mô hình và dữ liệu tiếng ồn tổng hợp không đại diện cho cảm biến thời gian thực tại từng đường phố.

## Yêu cầu

| Mã | Yêu cầu | Điều kiện kiểm chứng | Người kiểm chứng kỹ thuật |
|---|---|---|---|
| FR-01 | Chọn và tìm địa điểm | Danh mục hiện có 86 nơi; tìm `cau giay` thấy Cầu Giấy | Dương |
| FR-02 | Nhớ địa điểm | Reload vẫn giữ nơi đang chọn | Dương |
| FR-03 | Cách ly dữ liệu | Lịch sử, báo cáo và ngữ cảnh chat đúng `MaDiaDiem` | Kiên, Nghĩa |
| FR-04 | Lưu snapshot | Phản hồi cập nhật khớp JSON và chỉ số lưu trong SQL | Kiên |
| FR-05 | Cache cập nhật | Các yêu cầu đồng thời cùng nơi dùng một lần cập nhật; cache 600 giây | Kiên |
| FR-06 | Thể hiện thiếu dữ liệu | Nơi không có tiếng ồn trả null; RF báo thiếu, không điền tiếng ồn nơi khác | Kiên, Nghĩa |
| FR-07 | Bản đồ vị trí | Đổi nơi cập nhật dấu/tọa độ; Hà Nội có tham chiếu tiếng ồn riêng khi tắt AQI | Dương |
| FR-08 | Lớp màu AQI | Có 6 mức, độ đậm/toàn màn hình, thời gian nguồn; vùng thiếu để trống | Kiên, Dương |
| FR-09 | Báo cáo | Tạo/lưu/mở lại kỳ 1, 7, 30 ngày cho đúng nơi | Kiên, Dương |
| FR-10 | Xuất báo cáo | CSV đúng 17 cột, tiếng Việt; chế độ in chỉ có báo cáo | Dương |
| FR-11 | Hội thoại | Dữ liệu đầu vào đúng nơi; lịch sử tách theo nơi | Nghĩa, Dương |
| FR-12 | Phản hồi liên tục | Hiển thị SSE; mặc định sinh đến EOS; dừng chỉ do người dùng/mất kết nối/lỗi | Nghĩa |
| NFR-01 | Màn hình nhỏ | 390 px không tràn ngang; nút và chú thích đọc được | Dương |
| NFR-02 | Lỗi nguồn | Thông báo lỗi và thử lại; không tô số liệu giả | Kiên, Dương |
| NFR-03 | Giới hạn truy vấn vùng | Tối đa 196 điểm AQI mỗi yêu cầu; chỉ Việt Nam/vùng lân cận | Kiên |
| NFR-04 | Đọc đúng nguồn | Phân biệt US AQI, nhãn RF tham khảo, NoiseCapture và chatbot | Cả nhóm |

## Ngoài phạm vi hiện tại

Tài khoản/đăng nhập người dùng, quyền nghiệp vụ, cảnh báo SMS/email, dữ liệu cảm biến do nhóm tự lắp và kết luận vi phạm quy chuẩn chưa thuộc chức năng hiện có.

## Cần hoàn thiện sau khi rà soát

- Đối chiếu từng mã với bước kiểm tra và bằng chứng thực tế.
- Chốt tiêu chí bắt buộc, ưu tiên và hạn chế của đợt nghiệm thu.
- Ghi các yêu cầu mới nếu nhóm thống nhất bổ sung; không đánh dấu đạt khi chưa kiểm chứng.
