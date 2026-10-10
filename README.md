# Giám sát môi trường đô thị tại Việt Nam

Ứng dụng web hiển thị thời tiết và chất lượng môi trường theo địa điểm được chọn tại Hà Nội và các thành phố khác ở Việt Nam.
Backend Flask gọi Open-Meteo và NoiseCapture, lưu vào SQL Server; frontend (HTML/JS) đọc dữ liệu từ backend và hiển thị. Hai mô hình Random Forest phân loại tham khảo chất lượng không khí và tiếng ồn từ dữ liệu mới nhất.

## Làm việc nhóm trên GitHub

Repository: [CTY-TNHH-1mktoi/quanli-moitruong-dothi](https://github.com/CTY-TNHH-1mktoi/quanli-moitruong-dothi). Owner `trxyan` duyệt và quyết định hợp nhất PR vào `main`; thành viên làm việc trên `member/<github-username>`. Các tài khoản thành viên ghi trong README ban đầu là `247480201033-code` và `tadangduong1504-art`; cần xác nhận liên hệ với bảng phân công trước khi gán assignee/reviewer.

[Kịch bản, phân công và lệnh thực hiện cho Giang, Kiên, Dương, Nghĩa](docs/team/KICH_BAN_GITHUB.md). Các file trong `docs/team/templates/` là bản nháp để thành viên rà soát, chỉnh sửa và kiểm chứng trên nhánh của mình. Mã hiện có được nhập như bản nền chung; commit tiếp theo thể hiện phần việc mới thực tế.

[Bộ lệnh terminal riêng, mỗi người một file dự án](docs/team/terminal/README.md): Giang `README.md`, Kiên `app.py`, Dương `static/index.html`, Nghĩa `chatbot.py`. Hướng dẫn đi từ clone/cấu hình tài khoản đến sửa cơ bản, hoàn thiện, commit/push và tạo PR. Giang (owner `trxyan`) ủy quyền trợ lý thực hiện phần của mình; ba thành viên còn lại tự thực hiện bằng tài khoản cá nhân.

## Phân công và phạm vi nghiệm thu

Nguyễn Trường Giang là owner GitHub `trxyan`, phụ trách chốt phạm vi, hướng dẫn chạy, đối chiếu tiêu chí nghiệm thu và điều phối hợp nhất PR. Trong đợt này, mỗi thành viên sửa một file; kết quả kiểm chứng được ghi trong mô tả PR.

| Thành viên | Vai trò | File phụ trách trong đợt này | Đầu ra mới |
|---|---|---|---|
| Nguyễn Trường Giang (`trxyan`) | Điều phối và phân tích yêu cầu | `README.md` | Phân công, phạm vi và checklist nghiệm thu |
| Trịnh Trung Kiên | Backend và dữ liệu | `app.py` | API health kiểm tra Flask và kết nối SQL, phản hồi lỗi an toàn |
| Tạ Đăng Dương | Frontend và UI/UX | `static/index.html` | Điều hướng nhanh các mục không khí, bản đồ, báo cáo, hội thoại |
| Trần Trọng Nghĩa | Mô hình và tích hợp AI | `chatbot.py` | Thời gian nguồn không khí, thời tiết và tiếng ồn trong ngữ cảnh chatbot |

Các đầu ra mới của Kiên, Dương và Nghĩa đang được giao, chưa được triển khai trong bản nền. Từng người dùng tài khoản của mình; Giang xác nhận username trước khi gán reviewer hoặc cấp quyền cộng tác.

### Phạm vi được chốt

- Dashboard theo địa điểm tại Hà Nội và các thành phố khác ở Việt Nam; khi chuyển địa điểm, dữ liệu, lịch sử và báo cáo phải theo đúng lựa chọn.
- Lưu snapshot nguồn, danh mục địa điểm, mẫu AQI và báo cáo vào SQL Server; báo cáo đã lưu mở lại từ dữ liệu được lưu.
- Bản đồ theo tọa độ địa điểm và lớp màu AQI, có thời gian nguồn và thông tin khi bấm bản đồ.
- Random Forest phân loại tham khảo khi đủ đầu vào; chatbot Xanh Non dùng dữ liệu địa điểm đang chọn và cho phép sinh đến khi mô hình tự kết thúc.
- Không khí/thời tiết lấy từ mô hình Open-Meteo; tiếng ồn lấy từ bộ dữ liệu NoiseCapture tổng hợp theo vùng. Đây là các nguồn tham khảo, không đại diện cho cảm biến thời gian thực tại từng đường phố. Khi thiếu dữ liệu, giao diện và AI phải nêu rõ tình trạng thiếu.

### Quy trình nghiệm thu

1. Thành viên cập nhật nhánh từ bản nền chung, sửa file được giao và chạy kiểm tra tương ứng trong hướng dẫn terminal.
2. PR ghi rõ thay đổi, lệnh kiểm tra, kết quả thực tế và giới hạn còn lại; đối chiếu với checklist bên dưới.
3. Giang đối chiếu phạm vi và bằng chứng; reviewer có quyền ghi thực hiện review theo quy định repository. PR do Giang tạo cần người khác review nếu nhánh đích yêu cầu.
4. Owner hợp nhất khi đáp ứng quy định nhánh và ghi nhận kết quả nghiệm thu thực tế trong PR.

### Checklist nghiệm thu của đợt này

| Phần việc / người phụ trách | Thao tác kiểm tra | Điều kiện đạt | Trạng thái |
|---|---|---|---|
| Backend / Kiên | Gọi `GET /api/health` với kết nối SQL hoạt động | HTTP 200; trường `Database` là `ok`; kết nối được đóng | Chờ triển khai và kiểm chứng |
| Backend lỗi SQL / Kiên | Giả lập lỗi kết nối SQL, gọi cùng endpoint | HTTP 503; không lộ mật khẩu, chuỗi kết nối hoặc traceback | Chờ triển khai và kiểm chứng |
| UI / Dương | Bấm Không khí, Bản đồ, Báo cáo, Chatbot; thử Tab và Enter | Chuyển đúng `#air`, `#locationMap`, `#reports`, `#chat`; thao tác được bằng bàn phím | Chờ triển khai và kiểm chứng |
| UI màn hình nhỏ / Dương | Mở dashboard ở chiều rộng 390 px | Menu và nội dung không tràn ngang, không che thao tác chính | Chờ kiểm chứng sau thay đổi |
| AI thời gian nguồn / Nghĩa | Tạo snapshot có thời gian nguồn không khí, thời tiết và `TiengOn_ChiTiet.DoGanNhat`; kiểm tra ngữ cảnh | Ngữ cảnh giữ đúng thời gian được cung cấp và phân biệt tiếng ồn tổng hợp với đo trực tiếp | Chờ triển khai và kiểm chứng |
| AI thiếu dữ liệu / Nghĩa | Tạo snapshot thiếu thời gian nguồn hoặc chỉ số tiếng ồn; kiểm tra ngữ cảnh và kiểm thử hồi quy | Không bịa thời gian hoặc số đo; nêu rõ chỉ số chưa có dữ liệu; streaming tiếp tục hoạt động | Chờ triển khai và kiểm chứng |
| Tài liệu / Giang | Đối chiếu phân công, phạm vi, cách chạy và checklist với hướng dẫn terminal | File được giao và điều kiện đạt rõ ràng; các mục chưa thực hiện có trạng thái chờ | Đã rà soát tài liệu ngày 10/10/2026; PR chờ review |

**Bằng chứng của bản nền ngày 10/10/2026:** 34/34 kiểm thử Python với mock đạt trong 21,525 giây; 13 kiểm tra nội suy/thang màu JavaScript đạt; kiểm tra cú pháp các file JavaScript trực tiếp trong `static/` thành công. Lệnh chạy lại và kết quả được ghi trong [TEST_REPORT.md](TEST_REPORT.md). Những kết quả này kiểm chứng bản nền, chưa chứng minh các thay đổi mới đang giao cho Kiên, Dương và Nghĩa.

Mỗi PR nghiệm thu phải ghi ngày kiểm tra, người kiểm tra, môi trường, lệnh hoặc bước thao tác, kết quả thực tế và giới hạn còn lại. Chỉ đổi trạng thái sang đạt khi có bằng chứng; các kiểm thử trình duyệt/API/SQL trực tiếp ngày 07/10/2026 được giữ nguyên ngày trong báo cáo. Hợp nhất vào `main` cần đáp ứng quy định review của repository.

## Cấu trúc

```
demoth1/
├── app.py                  Backend Flask (API + phục vụ giao diện)
├── environment_predictor.py  Nạp mô hình và dự đoán
├── environment_reports.py    Phân tích, lưu và mở báo cáo
├── report_schema.sql         Tạo bảng lưu báo cáo (có thể chạy lại)
├── location_catalog.py       Danh mục và lưu thông tin địa điểm
├── locations.json            86 địa điểm tham chiếu từ tài nguyên hiện có
├── location_schema.sql       Bảng địa điểm, liên kết và snapshot dữ liệu
├── air_quality_map.py         Lấy mẫu AQI theo vùng và lưu/cache SQL
├── air_map_schema.sql         Bảng dữ liệu mẫu bản đồ AQI
├── noise_data.py             Bộ dữ liệu tiếng ồn chung, lọc theo địa điểm
├── environment_rf.joblib    Hai mô hình Random Forest đã huấn luyện
├── train_environment_rf.py  Mã tái huấn luyện (tùy chọn)
├── chatbot.py               Chạy chatbot Xanh Non trên máy
├── native_chatbot.py        Quản lý tiến trình llama.cpp cho CPU
├── models/
│   ├── xanhnon-qwen2.5-0.5b-vietnamese/  Trọng số và tokenizer từ ZIP
│   └── xanhnon-f16.gguf      Bản chuyển đổi từ trọng số gốc
├── .runtime/llama-bin/      llama.cpp b11471, Windows CPU
├── requirements.txt        Thư viện Python
├── requirements-dev.txt    Thư viện kiểm thử trình duyệt (tùy chọn)
├── tests/                  Kiểm thử Python, JavaScript và trình duyệt
├── README.md
└── static/
    ├── index.html     Giao diện
    ├── locations.js   Chọn, tìm và nhớ địa điểm
    ├── map.js         Bản đồ theo địa điểm đang chọn
    ├── air-overlay.js Lớp màu AQI theo tọa độ và nội suy
    ├── vendor/leaflet/  Thư viện bản đồ và giấy phép
    ├── script.js      Gọi API, đổ dữ liệu, vẽ biểu đồ
    ├── chat.js        Gửi câu hỏi và hiển thị hội thoại
    ├── reports.js     Tạo, mở, xuất báo cáo
    └── style.css      Giao diện
```

## Yêu cầu

- Python tương thích với `scikit-learn==1.8.0` (đã kiểm tra với Python 3.13)
- SQL Server đang chạy trên máy, đã tạo database `GiamsatMT` (chạy `Demodatabase.sql` trong SSMS)
- ODBC Driver 17 for SQL Server
- Kết nối Internet (gọi Open-Meteo và tải dữ liệu tiếng ồn)

## Cách chạy

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Nếu `.venv` đã tồn tại thì chỉ cần chạy hai lệnh cuối. Môi trường `.venv` trong dự án đã được cài `scikit-learn==1.8.0` để khớp với file mô hình.

Mở trình duyệt tại **http://localhost:5000**

Lần đầu tiên backend phải tải file dữ liệu tiếng ồn `Vietnam.zip` nên có thể chậm hơn bình thường.
Sau đó file được giữ ở `.runtime/noise-vietnam.zip`, dùng chung cho các địa điểm và làm mới sau 24 giờ; khi tải lại thất bại, ứng dụng tiếp tục dùng file đã có.
Mô hình được nạp từ `environment_rf.joblib` trong thư mục dự án ở lần dự đoán đầu tiên; chỉ dùng file mô hình từ nguồn tin cậy.

## Cấu hình

Đặt bằng biến môi trường, không cần sửa code:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `DB_SERVER` | `LAPTOP-2HSL339M` | Tên server SQL Server (xem trong SSMS, ví dụ `.\SQLEXPRESS`) |
| `DB_NAME` | `GiamsatMT` | Tên database |
| `DB_USER` / `DB_PASSWORD` | để trống | Để trống = dùng Windows Authentication |
| `DB_DRIVER` | `ODBC Driver 17 for SQL Server` | Tên ODBC driver |
| `NOISE_RADIUS_KM` | `2` | Bán kính lấy dữ liệu tiếng ồn quanh tọa độ tiếng ồn của địa điểm đang chọn |
| `CHATBOT_MODEL_DIR` | `models/xanhnon-qwen2.5-0.5b-vietnamese` | Thư mục mô hình Xanh Non; mặc định tính từ thư mục dự án |
| `CHATBOT_CPU_THREADS` | `4` | Số luồng CPU chạy chatbot (giới hạn 1–8) |
| `CHATBOT_MAX_NEW_TOKENS` | `-1` | Sinh đến khi mô hình tự kết thúc; đặt 32–4096 nếu muốn giới hạn mỗi phản hồi |
| `CHATBOT_BACKEND` | `auto` | Ưu tiên llama.cpp khi có binary và GGUF; dùng `transformers` để chọn cách chạy PyTorch |
| `CHATBOT_LLAMA_SERVER` | `.runtime/llama-bin/llama-server.exe` trên Windows | Đường dẫn binary llama.cpp |
| `CHATBOT_GGUF_PATH` | `models/xanhnon-f16.gguf` | File GGUF chuyển đổi từ gói mô hình |
| `CHATBOT_PRELOAD` | `1` | Nạp mô hình ở nền khi khởi động; đặt `0` để nạp khi hỏi lần đầu |

Ví dụ (PowerShell): `$env:DB_SERVER = ".\SQLEXPRESS"; python app.py`

## Cách các phần nối với nhau

| Trên giao diện | Endpoint |
|---|---|
| Danh sách địa điểm | `GET /api/diadiem` |
| Thẻ AQI, PM2.5, PM10, nhiệt độ, độ ẩm, tiếng ồn, tư vấn và dự đoán Random Forest | `GET /api/capnhat` |
| Biểu đồ xu hướng PM2.5 | `GET /api/dulieu/lichsu?limit=12` |
| Lịch sử cảnh báo | `GET /api/canhbao?limit=8` |
| Lớp màu AQI theo vùng bản đồ | `GET /api/bando/khongkhi?location=hanoi` |
| Trò chuyện với Xanh Non | `POST /api/chat` |
| Tạo và lưu báo cáo | `POST /api/baocao` |
| Lịch sử báo cáo | `GET /api/baocao?limit=10&offset=0` |
| Mở báo cáo đã lưu | `GET /api/baocao/<id>` |

Ngoài ra backend còn có `GET /api/dulieu/moinhat` và `GET /api/phantich` (giao diện hiện chưa dùng).

Các API đọc dữ liệu/báo cáo nhận `?location=<MaDiaDiem>`, ví dụ `/api/capnhat?location=tphcm`. API chat và tạo báo cáo nhận trường `"location"` trong JSON. Bỏ trường này thì dùng Hà Nội để giữ tương thích; mã không thuộc danh sách trả HTTP 400.

- `/api/capnhat` gọi API môi trường, lưu vào 3 bảng `NguonDL`, `CanhBao`, `PhanTichAI` rồi trả kết quả.
  Mỗi địa điểm có bộ nhớ đệm 10 phút riêng. Các yêu cầu đồng thời cho cùng địa điểm dùng chung một lần cập nhật. Khi khởi động lại, ứng dụng có thể dùng lại snapshot vừa lưu trong SQL Server.
- Trường `DuDoanRF` trong phản hồi `/api/capnhat` chứa `ChatLuongKhongKhi` và `MucTiengOn` khi `TrangThai` là `ok`. Nếu thiếu một trong 5 chỉ số (`PM25`, `PM10`, `NhietDo`, `DoAm`, `TiengOn`), `TrangThai` là `thieu_du_lieu`; nếu không nạp/chạy được mô hình thì là `loi_mo_hinh`. Khi đó API vẫn trả dữ liệu và phân tích US AQI. Toàn bộ phản hồi, gồm dự đoán RF, AQI, các khí, thời gian nguồn và metadata tiếng ồn, được lưu vào `NguonDL.ChiTiet` dạng JSON Unicode.
- Giao diện tự làm mới mỗi 10 phút.

## Lưu ý

- Chỉ số AQI là **US AQI** (theo Open-Meteo).
- Tiếng ồn là tổng hợp theo năng lượng từ các ô NoiseCapture quanh địa điểm đang chọn, có trọng số theo số lần đo; không phải số đo trực tiếp theo thời gian thực. Giao diện hiển thị thời gian đo gần nhất của dữ liệu nguồn khi có.
- Thời tiết và không khí lấy theo tọa độ tham chiếu trong danh mục. Hà Nội mặc định giữ tọa độ cũ (21.0285, 105.8542) và vùng tiếng ồn Cầu Giấy.
- Mở thẳng file `index.html` vẫn gọi được backend (tại `127.0.0.1:5000`), nhưng nên truy cập qua `http://localhost:5000`.

## Chọn địa điểm và lưu database

Bộ chọn có **86 lựa chọn**: 9 thành phố tham chiếu (Hà Nội, TP.HCM, Đà Nẵng, Hải Phòng, Cần Thơ, Huế, Nha Trang, Đà Lạt, Vũng Tàu) và 77 khu vực trong [NoiseCapture Vietnam](https://data.noise-planet.org/dump/Vietnam.zip), gồm 16 khu vực thuộc nhóm Hà Nội của bộ dữ liệu. Tọa độ các thành phố bổ sung lấy từ [Open-Meteo Geocoding / GeoNames](https://open-meteo.com/en/docs/geocoding-api). Tọa độ các khu vực lấy từ tâm ô có nhiều lần đo nhất trong file nguồn, nhằm chọn một vị trí có dữ liệu thực tế; không đại diện cho toàn bộ địa giới.

Ô tìm kiếm hỗ trợ tiếng Việt có dấu hoặc không dấu. Địa điểm được nhớ trong `localStorage`; biểu đồ, cảnh báo và báo cáo chỉ đọc các bản ghi có cùng `MaDiaDiem`. Hội thoại trong trang được tách theo địa điểm; bộ chọn tạm khóa khi chatbot đang trả lời để giữ ngữ cảnh của câu đang chạy.

Tên khu vực NoiseCapture giữ nguyên theo bộ dữ liệu, có thể là tên hành chính cũ. Không khí ở Việt Nam sử dụng mô hình CAMS Global theo ô lưới khoảng 45 km; các nơi gần nhau có thể nhận cùng chỉ số, theo [tài liệu chất lượng không khí Open-Meteo](https://open-meteo.com/en/docs/air-quality-api). Một địa điểm không có ô tiếng ồn trong bán kính được trả `TiengOn: null`; không lấy tiếng ồn Hà Nội hay địa điểm khác để điền vào, và RF báo thiếu dữ liệu khi cần.

`location_schema.sql` tự chạy một lần khi cần: tạo bảng `dbo.DiaDiem` chứa mã, tên, nhóm, tọa độ và toàn bộ metadata JSON của danh mục; thêm `MaDiaDiem` và `ChiTiet` vào `NguonDL`. Bản ghi cũ có nguồn chính xác `Open-Meteo Hà Nội` được gắn `hanoi`; các nguồn khác không được tự gán. Báo cáo được lưu cùng mã địa điểm; các báo cáo tạo trước bộ chọn được giữ và gắn Hà Nội. Có thể chạy `location_schema.sql` rồi `report_schema.sql` trong SSMS nếu tài khoản ứng dụng không có quyền thay đổi schema.

## Bản đồ theo địa điểm

Bản đồ phía dưới bộ chọn tự cập nhật khi đổi địa điểm và khi tải lại trang với địa điểm đã nhớ. Mặc định bật lớp màu chất lượng không khí theo vùng, thang US AQI 6 mức, có thời gian nguồn và độ phân giải. Có thể bật/tắt lớp màu, chỉnh độ đậm, xem toàn màn hình và bấm nền bản đồ để xem AQI ước tính tại vị trí đó.

Dấu xanh là tọa độ tham chiếu thời tiết/không khí. Khi tắt lớp màu, nếu tọa độ tiếng ồn khác tọa độ này thì bản đồ có thêm dấu cam và chú thích riêng; Hà Nội có thêm vị trí tham chiếu Cầu Giấy. Những dấu này không biểu thị toàn bộ địa giới hoặc phạm vi ô nhiễm.

Có thể kéo, phóng to/thu nhỏ, bấm dấu để xem tên/tọa độ, trở về địa điểm đã chọn hoặc mở OpenStreetMap ở tab mới. Tọa độ dùng danh mục `locations.json` và metadata đã lưu trong SQL Server; thao tác kéo/zoom không đổi địa điểm giám sát.

Thư viện [Leaflet 1.9.4](https://leafletjs.com/download.html) được lưu trong `static/vendor/leaflet/` cùng giấy phép BSD 2-Clause. Nền bản đồ tải từ OpenStreetMap bằng trình duyệt, có ghi nguồn và dùng cache trình duyệt theo [chính sách tile OpenStreetMap](https://operations.osmfoundation.org/policies/tiles/). Nền bản đồ cần Internet; nếu tải lỗi, tên/tọa độ và dấu vị trí vẫn hiển thị, kèm nút thử tải lại. Không cần khóa API.

Lớp màu dùng dữ liệu **Open-Meteo / CAMS Global**, không phải AccuWeather. API nhiều tọa độ và lưới mô hình 0,4° (~45 km) được mô tả trong [tài liệu Open-Meteo](https://open-meteo.com/en/docs/air-quality-api). Backend lấy mẫu theo vùng đang xem, chọn ô gần nhất, tối đa 196 điểm mỗi lượt; khi xem vùng rộng thì tăng bước lấy mẫu và ghi rõ trên giao diện. Màu được nội suy song tuyến tính giữa các mẫu AQI; góc thiếu dữ liệu không được thay bằng 0 hay nội suy bù. Các màu chuyển liên tục theo thang AQI, không mô tả từng đường phố hoặc trạm đo trực tiếp.

`GET /api/bando/khongkhi?location=hanoi&south=20&west=103&north=22&east=109` trả lưới AQI, PM2.5, tọa độ và thời gian nguồn. Bỏ phạm vi thì dùng vùng quanh địa điểm đã chọn. Phạm vi hỗ trợ Việt Nam và vùng lân cận; vùng ngoài phạm vi trả lưới rỗng. Giao diện tải lại khi kéo/zoom, đổi nơi và mỗi 10 phút ở tab đang mở; phản hồi cũ bị bỏ qua nếu đã đổi vùng.

`air_map_schema.sql` tự tạo `dbo.MauBanDoKhongKhi` để lưu mã/tọa độ điểm mẫu, AQI, PM2.5, thời gian nguồn, thời gian lấy và JSON nguồn đầy đủ. Điểm mẫu được dùng lại trong cùng giờ Việt Nam, kể cả sau khởi động lại; giờ mới lấy mẫu mới. Các mẫu này lưu riêng với dữ liệu giám sát `NguonDL` và báo cáo. Nếu nguồn hoặc SQL lỗi, giao diện hiển thị lỗi và nút thử lại; không tô màu giả cho vùng thiếu.

## Giới hạn của mô hình Random Forest

`train_environment_rf.py` tạo nhãn không khí từ ngưỡng PM2.5 (`≤12`, `≤35.4`, `≤150`, `>150` µg/m³) và nhãn tiếng ồn từ ngưỡng (`<55`, `<70`, `≥70` dBA). Đây là nhãn minh họa, không phải dữ liệu được chuyên gia gán nhãn. Mô hình học từ dữ liệu cảm biến iSCAPE ở châu Âu, còn ứng dụng dự đoán bằng dữ liệu Open-Meteo và NoiseCapture ở Việt Nam. Các nguồn và vị trí đo khác nhau nên kết quả chỉ mang tính tham khảo; không dùng như AQI chính thức hoặc tư vấn sức khỏe. File metadata đánh giá chưa được cung cấp cùng mô hình gốc.

Để tái huấn luyện, chạy `python train_environment_rf.py`. Script sẽ tải các CSV iSCAPE về `iscape_data/` và ghi đè `environment_rf.joblib`, đồng thời tạo `environment_rf_metadata.json` chứa thông tin tập dữ liệu và báo cáo thử nghiệm. Cần kết nối Internet và nên sao lưu mô hình trước khi chạy.

## Chatbot Xanh Non

Gói `xanhnon-model.zip` đã được giải nén vào `models/xanhnon-qwen2.5-0.5b-vietnamese/`, gồm `model.safetensors`, cấu hình, tokenizer và giấy phép đi kèm. Các tệp phải nằm cùng thư mục. Hai tệp trọng số lớn (`model.safetensors` và `models/xanhnon-f16.gguf`) được lưu bằng Git LFS. Sau khi clone, cài Git LFS và chạy `git lfs pull` để tải đủ mô hình.

Chatbot ưu tiên llama.cpp trên CPU và sử dụng mẫu hội thoại của tokenizer trong gói ZIP. Câu hỏi và trọng số được xử lý trên máy; không gọi dịch vụ chatbot bên ngoài và không tải thêm mô hình. Internet vẫn cần cho các API môi trường hiện có. Khi thiếu bản GGUF hoặc binary, chế độ `auto` dùng PyTorch/Transformers với trọng số safetensors gốc.

Mô hình được nạp trước ở nền khi chạy `app.py`; giao diện hiển thị trạng thái khởi động/sẵn sàng. File safetensors gốc được chuyển sang GGUF F16 bằng bộ chuyển đổi chính thức của llama.cpp; không thay bằng mô hình khác. Binary CPU Windows b11471 và giấy phép đi kèm nằm trong `.runtime/llama-bin/`. Flask tự mở một tiến trình llama.cpp ẩn, chỉ lắng nghe ở `127.0.0.1` trên cổng trống; tiến trình được đóng khi dừng ứng dụng. Log nằm tại `.runtime/xanhnon-server.log`.

Phản hồi được hiển thị từng đoạn ngay khi mô hình sinh chữ. Trong phép thử trên máy này, llama.cpp đạt khoảng 10 token/giây, so với khoảng 2 token/giây của PyTorch float32. Khi kiểm tra trên giao diện với dữ liệu môi trường thực tế, hai câu ngắn có chữ đầu tiên sau khoảng 1,5–4,7 giây và hoàn tất sau 6–18 giây; câu hỏi dài và lịch sử dài vẫn cần thêm thời gian. PyTorch vẫn dùng float32 trên CPU hoặc float16 trên CUDA khi chọn backend `transformers`; các cách INT8 từng làm mô hình trả lời lệch chủ đề đã được bỏ khỏi cấu hình.

Chatbot không bị ép trả lời trong 2–3 câu. Mặc định `CHATBOT_MAX_NEW_TOKENS=-1`: phản hồi tiếp tục cho đến khi mô hình sinh tín hiệu kết thúc (EOS), không dừng ở mốc 2048 token và không cần bấm Viết tiếp. llama.cpp bật `--context-shift` để tiếp tục sinh khi cửa sổ ngữ cảnh đầy; giữ đầu vào và phần trả lời gần nhất. Cách chạy này dựa trên [tài liệu server llama.cpp b11471](https://github.com/ggml-org/llama.cpp/blob/b11471/tools/server/README.md). PyTorch tự nối các khối sinh văn bản đến EOS, giữ đầu vào cùng các token mới nhất trong giới hạn ngữ cảnh của mô hình. Nếu chủ động cấu hình giới hạn 32–4096 token, nút **Viết tiếp** vẫn có thể dùng khi phản hồi bị cắt.

Ngữ cảnh đầu vào tối đa 8192 token; ứng dụng bỏ các lượt cũ nhất khi cần. Với phản hồi rất dài, giao diện giữ toàn bộ nội dung hiển thị và gửi tối đa 32768 ký tự cuối trong lịch sử mỗi phản hồi. Giao diện và kết nối sinh văn bản với llama.cpp không tự cắt phản hồi theo thời gian. Nút **Dừng trả lời** chỉ dừng khi người dùng bấm, giữ phần đã nhận và cho phép viết tiếp. PyTorch không còn cắt phản hồi sau 60 giây.

Khi chuyển dự án sang máy Windows khác, chạy `git lfs pull` để lấy `models/xanhnon-f16.gguf`; binary trong `.runtime/llama-bin/` đã có trong Git để dùng chế độ CPU nhanh. Chỉ log, dữ liệu tải về và kết quả kiểm thử trong `.runtime/` được bỏ qua. Máy khác nền tảng cần binary llama.cpp phù hợp, đặt bằng `CHATBOT_LLAMA_SERVER`, hoặc dùng backend `transformers`.

Để tạo lại GGUF từ đúng trọng số gốc (bộ chuyển đổi b11471 đã có trong `.runtime/llama-converter/`):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-convert.txt
$env:USE_TF = '0'
.\.venv\Scripts\python.exe .runtime\llama-converter\convert_hf_to_gguf.py models\xanhnon-qwen2.5-0.5b-vietnamese --outfile models\xanhnon-f16.gguf --outtype f16 --model-name XanhNon
```

`POST /api/chat` nhận JSON:

```json
{
  "message": "PM2.5 là gì?",
  "location": "hanoi",
  "history": [
    {"role": "user", "content": "Chào bạn"},
    {"role": "assistant", "content": "Chào bạn!"}
  ]
}
```

Phản hồi JSON có `reply` và `truncated` (phản hồi chưa kết thúc tự nhiên). Thêm `"stream": true` để nhận `text/event-stream`: các sự kiện `status`, `delta` chứa đoạn chữ, `done` chứa toàn bộ phản hồi, hoặc `error`. `GET /api/chat/status` trả trạng thái `cold`, `loading`, `ready` hoặc `error`. Nếu mất kết nối trong lúc trả lời, ứng dụng dừng phần sinh văn bản còn lại. Câu hỏi tối đa 8000 ký tự; lịch sử tối đa 4 lượt hỏi đáp, với vai trò `user` và `assistant` xen kẽ, mỗi mục tối đa 32768 ký tự. Yêu cầu JSON tối đa 2 MiB. Hội thoại lưu trong bộ nhớ của trang và được xóa khi tải lại trang hoặc chọn **Cuộc trò chuyện mới**. Không lưu hội thoại vào SQL Server.

Ngữ cảnh chatbot lấy từ kết quả `/api/capnhat` gần nhất của server cho địa điểm đang chọn, gồm thời gian, số đo và phân loại AQI trên bảng giám sát. Nếu chưa cập nhật dữ liệu, chatbot nhận thông tin rằng chưa có số đo. Mô hình có thể trả lời sai; cần đối chiếu số liệu thực tế khi dùng câu trả lời. Khi một câu hỏi đang được xử lý, yêu cầu khác nhận HTTP 429; dữ liệu đầu vào sai nhận 400 và thiếu mô hình/thư viện nhận 503.

Kiểm tra phản hồi trực tiếp, JSON, xử lý bận và hủy khi mất kết nối: `.\.venv\Scripts\python.exe -m unittest discover -s tests`.

Cách chạy dựa trên tài liệu Qwen về [llama.cpp và chuyển đổi GGUF](https://qwen.readthedocs.io/en/v2.5/run_locally/llama.cpp.html), [Transformers](https://qwen.readthedocs.io/en/v2.5/inference/chat.html), và [binary chính thức llama.cpp b11471](https://github.com/ggml-org/llama.cpp/releases/tag/b11471).

## Kiểm thử

Chạy kiểm thử Python và kiểm tra phép nội suy/thang màu JavaScript:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node tests/test_air_overlay.cjs
```

Các kịch bản trình duyệt nằm trong `tests/browser/`, dữ liệu mẫu cố định nằm trong `tests/fixtures/`. Để chạy, cần ứng dụng tại `http://127.0.0.1:5000`, Microsoft Edge và thư viện tùy chọn:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tests/browser/check_air_map.py
.\.venv\Scripts\python.exe tests/browser/check_map.py
.\.venv\Scripts\python.exe tests/browser/check_locations.py
```

Có thể đặt `TEST_BASE_URL` để dùng địa chỉ khác. Kết quả ảnh được ghi vào `.runtime/test-results/`; import các kịch bản không tự mở trình duyệt. Hai kiểm thử bản đồ dùng nền và API AQI thật, thay phản hồi chỉ số/báo cáo để không tạo thêm bản ghi giám sát. Kiểm thử địa điểm đọc dữ liệu và báo cáo đã lưu, sau đó giả lập phản hồi đến muộn và hội thoại để kiểm tra cách tách ngữ cảnh; cần có báo cáo TP.HCM đã lưu để kiểm tra xuất CSV.

Chi tiết kết quả lần chạy gần nhất nằm trong `TEST_REPORT.md`.

## Báo cáo phục vụ quy hoạch và xử lý sự cố

Ở mục **Báo cáo**, chọn 24 giờ, 7 ngày hoặc 30 ngày rồi bấm **Tạo & lưu báo cáo**. Chức năng đọc `NguonDL` và `CanhBao` trong kỳ của địa điểm đang chọn, tính thống kê 5 chỉ số, tỷ lệ bản ghi có cảnh báo, diễn biến PM2.5 theo giờ/ngày và đề xuất dựa trên ngưỡng vận hành đang dùng. Các giá trị thiếu không được thay bằng 0; không lấy trung bình số học tiếng ồn dBA. Đây là phân tích theo các bản ghi đã lưu, không phải chuỗi đo liên tục hoặc đánh giá vi phạm quy chuẩn.

Bảng `dbo.BaoCaoMT` được tạo tự động khi sử dụng API báo cáo lần đầu bằng `report_schema.sql`; dữ liệu trong các bảng hiện có được giữ nguyên. Có thể chạy file SQL này trực tiếp trong database `GiamsatMT` nếu tài khoản ứng dụng không có quyền tạo bảng. Bảng chứa mã báo cáo, mã địa điểm, kỳ báo cáo, thời điểm tạo, số bản ghi, số cảnh báo và nội dung JSON Unicode (`NVARCHAR(MAX)`). Nội dung lưu cả dữ liệu nguồn trong kỳ, cảnh báo, thống kê, diễn biến, đề xuất và ghi chú để mở lại đúng phiên bản đã tạo.

`POST /api/baocao` nhận `{"days": 1}`, `{"days": 7}` hoặc `{"days": 30}` và trả báo cáo đã lưu với HTTP 201. `GET /api/baocao?limit=10&offset=0` trả danh sách mới nhất; `limit` tối đa 50, `offset` dùng để phân trang. `GET /api/baocao/<id>` đọc nguyên nội dung đã lưu, không tính lại từ số liệu mới. Tải lại trang tự mở báo cáo gần nhất; chỉ thao tác **Tạo & lưu báo cáo** mới tạo bản báo cáo mới.

**Tải dữ liệu CSV** xuất đúng các bản ghi trong báo cáo đang mở, kèm mã báo cáo, mã/tên địa điểm, tọa độ tham chiếu, thời gian kỳ và số cảnh báo gắn với mỗi bản ghi. File có UTF-8 BOM để mở tiếng Việt trong Excel. **In / Lưu PDF** mở hộp thoại in của trình duyệt; chọn lưu PDF để xuất bản báo cáo đầy đủ. Chế độ in chỉ hiển thị báo cáo đang mở. Lịch sử có nút **Mở** và **Xem thêm báo cáo**; chức năng tạo báo cáo không gọi hoặc gián đoạn quá trình sinh câu trả lời của chatbot.
