# Hợp đồng API và lưu dữ liệu

Bản nháp tham khảo, chuẩn bị 10/10/2026. Người dự kiến rà soát: Trịnh Trung Kiên. Đầu ra sau rà soát: `docs/backend/API_SQL.md`.

## Luồng cập nhật

Chọn mã trong danh mục → `/api/capnhat?location=<mã>` → khóa/cache riêng theo nơi → Open-Meteo + tổng hợp NoiseCapture → RF + cảnh báo/phân tích → giao dịch SQL lưu chỉ số và JSON snapshot → phản hồi giao diện. Cache cập nhật 600 giây; snapshot SQL còn hạn được dùng lại sau khởi động.

## API chính

| API | Đầu vào | Nội dung / lỗi cần kiểm tra |
|---|---|---|
| GET `/api/diadiem` | Không | `MacDinh`, `DiaDiem`; metadata danh mục lưu SQL |
| GET `/api/capnhat` | Query `location` | `Manguon`, `DiaDiem`, `DuLieu`, `DuDoanRF`, `CanhBao`, `PhanTich`; lỗi nguồn 502, SQL 503 |
| GET `/api/dulieu/lichsu` | `location`, `limit` 1–500 | Các dòng cùng nơi, thứ tự cũ → mới |
| GET `/api/canhbao` | `location`, `limit` 1–200 | Cảnh báo JOIN dữ liệu theo nơi |
| GET `/api/phantich` | `location`, `limit` 1–50 | Phân tích theo nơi |
| GET `/api/bando/khongkhi` | `location`, bộ `south,west,north,east` tùy chọn | Ma trận `AQI`, `PM25`, `ViDo`, `KinhDo`, bước lưới, thời gian; phạm vi sai 400, nguồn 502, SQL 503 |
| POST `/api/baocao` | JSON `days`: 1/7/30, `location` | Lưu và trả nội dung báo cáo, HTTP 201 |
| GET `/api/baocao` | `location`, `limit`, `offset` | Lịch sử báo cáo theo nơi |
| GET `/api/baocao/<id>` | `location` | JSON đã lưu; không đúng nơi/không có trả 404 |
| POST `/api/chat` | `message`, `history`, `location`, `stream` | JSON hoặc SSE; sai đầu vào 400, bận 429 |
| GET `/api/chat/status` | Không | `cold/loading/ready/error` |

Mã địa điểm không có trong danh mục trả 400. Khi bỏ mã, dùng Hà Nội. SQL dùng tham số; các truy vấn lịch sử, báo cáo và phân tích cần được đối chiếu về điều kiện `MaDiaDiem`.

## Bảng SQL

| Bảng | Vai trò | Liên hệ |
|---|---|---|
| `DiaDiem` | Mã, tên, nhóm, tọa độ và JSON metadata | Mã tham chiếu trong dữ liệu/báo cáo; không có FK vật lý được khai báo trong các schema hiện có |
| `NguonDL` | Chỉ số, thời điểm, `MaDiaDiem`, JSON `ChiTiet` | PK `Manguon` |
| `CanhBao` | Nội dung/ngưỡng cảnh báo | FK `Manguon` → `NguonDL` |
| `PhanTichAI` | Phân loại/tư vấn theo quy tắc AQI | FK `Manguon` → `NguonDL`; không phải đầu ra chatbot |
| `BaoCaoMT` | Báo cáo snapshot theo nơi/kỳ, JSON nội dung | Dữ liệu đã kết xuất; mã địa điểm dạng tham chiếu logic |
| `MauBanDoKhongKhi` | Mẫu AQI/PM2.5 theo tọa độ, thời gian và JSON nguồn | Tách khỏi bản ghi giám sát; dùng lại trong cùng giờ Việt Nam |

Đọc `Demodatabase.sql`, `location_schema.sql`, `report_schema.sql`, `air_map_schema.sql` và [sơ đồ ERD](https://github.com/CTY-TNHH-1mktoi/quanli-moitruong-dothi/blob/main/docs/diagrams/so-do-erd.svg). Sơ đồ cần được rà soát với schema hiện tại; phân biệt quan hệ logic với FK đã khai báo.

## Các trường hợp cần kiểm chứng

- Đổi Hà Nội ↔ TP.HCM không đọc lẫn dữ liệu.
- Cùng nơi/cùng thời điểm chỉ ghi một snapshot khi cache còn hạn.
- Thiếu tiếng ồn không lấy dữ liệu nơi khác; null khác 0.
- Mở báo cáo của nơi khác trả 404; thời kỳ không hợp lệ trả 400.
- Lưới AQI tối đa 196 điểm; tọa độ khớp JSON nguồn; phản hồi thiếu không gắn sang điểm khác.
- SQL/source lỗi không trả thông báo đã lưu thành công.

Ghi lệnh, kết quả thực tế và hạn chế trong `docs/backend/TEST_RESULT.md`.
