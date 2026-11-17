# Đợt học tiếp từ bốn bộ dữ liệu cảm biến

## Phạm vi

Đợt học được xếp sau ứng viên `candidate-20261019-135715` (121 mẫu hội thoại và biện pháp tư vấn). Worker chờ ứng viên đó hoàn tất và tiến trình train kết thúc rồi mới chuẩn bị bốn nguồn sau:

| Ưu tiên | Nguồn | Cách sử dụng cho Xanh Non |
| --- | --- | --- |
| 1 | [iSCAPE Outdoor Sensor Deployment Data](https://zenodo.org/records/3570700) | Đọc số đo được cung cấp, phân biệt dữ liệu lịch sử với hiện tại, tình huống tư vấn có nguồn. |
| 2 | [iSCAPE Citizen Science Workshops Data](https://zenodo.org/records/3570680) | Bổ sung tình huống từ các bản ghi khác; tái sử dụng file có sẵn khi checksum khớp. Project đã dùng nguồn này cho Random Forest; đó không phải một đợt học hội thoại của Xanh Non. |
| 3 | [iSCAPE Low Cost Sensor Development Data](https://zenodo.org/records/3570688) | Đọc và kiểm tra dữ liệu trong thử nghiệm cảm biến; không xem thử nghiệm có kiểm soát là hiện trạng ô nhiễm ngoài trời. Mỗi file có thể có các kênh khác nhau. |
| 4 | [Beijing Multi-Site Air Quality](https://archive.ics.uci.edu/dataset/501/beijingmultisiteairqualitydata) | Đọc PM và nhiệt độ, xử lý thiếu số đo. Không tự tạo tiếng ồn hoặc độ ẩm từ dữ liệu khác. |

Ba bản ghi Zenodo công bố giấy phép `cc-zero` trong metadata; nguồn UCI công bố CC BY 4.0. Metadata, checksum, URL và ghi nhận nguồn được lưu cùng dữ liệu chuẩn bị. Lời khuyên thực hành lấy từ `data/xanhnon/knowledge.json`, với nguồn EPA/AirNow, NIH/NIDCD và CDC đã kiểm tra; số đo cảm biến không tự sinh ra kiến thức tư vấn.

Đây là fine-tune hội thoại bằng **một phần dữ liệu đã chọn**, không phải train tất cả dòng CSV hay xây dựng mô hình dự báo. Những số đo lịch sử chỉ xuất hiện trong đầu vào của tình huống, không trở thành dữ liệu giám sát hiện tại của ứng dụng. Không gán AQI từ một giá trị PM đơn lẻ.

## Lọc trùng và chọn dữ liệu

- Kiểm tra MD5 phía nguồn và SHA-256 cục bộ; dùng lại file trùng nội dung, kể cả khác tên, nếu đã có trong cache.
- Cặp `_PROCESSED.csv` và bản gốc: thử bản tác giả đã xử lý trước; nếu không có mẫu hợp lệ thì mới thử bản gốc. Không khẳng định mọi bản processed đã được hiệu chuẩn.
- Loại file trùng checksum giữa các nguồn, số đo trùng sau chuẩn hóa và bản kém đầy đủ hơn của cùng bản ghi có thời điểm/định danh khớp.
- Loại NaN/vô hạn và giá trị ngoài giới hạn kiểm tra; không điền số đo thiếu bằng 0. Không lấy điểm sương thay cho độ ẩm tương đối.
- Lấy tối đa 64 vector khác nhau mỗi file bằng reservoir sampling, rồi chọn tối đa 40 tình huống mỗi nguồn; hạn chế các tình huống gần giống nhau. Nguồn hết dữ liệu mới sau lọc trùng hoặc không đủ bản ghi để tách kiểm tra được bỏ qua và ghi lý do. Nếu không còn mẫu cảm biến mới nào, bỏ qua lượt train; không chỉ train lại phần ôn cũ.
- Chia train/validation theo file bản ghi, không chia ngẫu nhiên các dòng liền kề trong cùng file. Validation vẫn dùng cùng khuôn câu hỏi nên không thay thế đánh giá câu trả lời độc lập.
- Giữ tối đa 48 mẫu cách diễn đạt và 16 mẫu tư vấn cũ để ôn lại. Phần ôn validation giữ tối đa 4 mẫu mỗi nguồn cũ.

## Chạy nối tiếp và trạng thái

`queue_sensor_training.py` ghi hàng đợi trên ổ D và dùng khóa hệ điều hành để tránh hai worker. Tác vụ train theo giờ nhường lượt khi hàng đợi này còn đang chờ hoặc chạy. Bộ dữ liệu mới lưu riêng; không sửa tập train/validation và manifest mà lượt train trước đang sử dụng.

Worker ưu tiên học tiếp adapter vừa train nếu lượt trước hoàn tất và validation loss giảm; nếu không, dùng adapter đang phát hành làm điểm xuất phát và ghi lý do. LoRA tiếp theo dùng 2 luồng CPU, 8 lớp cuối, một lượt dữ liệu, checkpoint mỗi 8 bước, cho phép paging khi còn đủ RAM + swap. Adapter và kết quả đánh giá được lưu riêng, chưa tự áp dụng vào chatbot.

```powershell
# Xem hàng đợi
Get-Content D:\XanhNon-auto-training\sensor-queue.json
# Nhật ký lọc và bản gốc đã kiểm tra
Get-Content D:\XanhNon-auto-training\sensor-sources\source-audit.json
# Tiến độ train sau khi bắt đầu
Get-Content D:\XanhNon-auto-training\sensor-training.log -Tail 10
# Khởi động lại worker của một job còn chờ (khóa ngăn chạy trùng)
.\.venv\Scripts\python.exe queue_sensor_training.py --work
```

Máy cần bật. Worker chạy độc lập với cửa sổ chat; nếu Windows khởi động lại, xem trạng thái và khởi động lại worker. Nếu lượt trước dừng hoặc lỗi, job ghi lỗi phụ thuộc; không chạy chồng hay giả báo hoàn tất.

## Theo dõi liên tục

`watch_xanhnon_training.py` kiểm tra mỗi 30 giây trên máy, xác minh PID và thời điểm tạo worker, đọc tiến độ train, dung lượng tải, CPU/I/O và lỗi. Cờ `needs_attention` được bật khi worker dừng bất thường, job lỗi hoặc không có hoạt động trong 15 phút. Bộ theo dõi ghi sự kiện khi trạng thái thay đổi, tự dừng khi job kết thúc hoặc sau tối đa 8 giờ. Việc kiểm tra dùng Python cục bộ, không gọi mô hình ngôn ngữ.

```powershell
# Trạng thái mới nhất, thời gian Việt Nam
Get-Content D:\XanhNon-auto-training\training-monitor-status.json
# Các thay đổi đáng chú ý
Get-Content D:\XanhNon-auto-training\training-monitor-events.jsonl -Tail 5
# Bật lại theo dõi nếu cần; khóa hệ điều hành ngăn hai bộ theo dõi chạy trùng
.\.venv\Scripts\python.exe watch_xanhnon_training.py --interval 30
```

## Kết quả ngày 19/10/2026 và lượt củng cố hội thoại

- Đợt 121 mẫu đã hoàn tất 31 bước: validation loss 2,29862 → 2,26761.
- Đợt bốn nguồn đã hoàn tất 48 bước trên 192 mẫu (128 tình huống mới, 64 mẫu ôn); 52 mẫu validation: loss 2,31346 → 2,15616. Đã quét 4.955.984 dòng nguồn để chọn một phần dữ liệu. Đây không phải huấn luyện trên toàn bộ các dòng đó.
- Bản thử `models/xanhnon-sensors-v3-f16.gguf` được xuất để đánh giá. Kiểm tra sinh trực tiếp trên 20 câu theo tiêu chí đã rà soát đạt 10/20, bản v2 đạt 9/20; bản mới vẫn xuất hiện lỗi dùng số AQI cũ trong lịch sử và nhầm PM/AQI. Vì có lỗi mới, bản thử chưa được áp dụng. Kết quả tự sinh và câu trả lời đã qua xử lý của ứng dụng là hai phạm vi đánh giá khác nhau.
- Bộ chấm bổ sung kiểm tra kích thước PM10, câu dẫn chưa có biện pháp, thời gian tiếp xúc tiếng ồn và điều kiện chưa có máy lọc. Một câu đã sai từ trước vẫn bị coi là thoái lui nếu bản mới đánh mất thêm số đo đúng. Các bản chấm lại giữ nguyên văn đầu ra và tham chiếu đến báo cáo gốc.
- Sửa định tuyến hội thoại cho các cách nói như “chưa mua được máy lọc”, “thế nếu chưa có máy lọc thì sao”, kể cả sau lời cảm ơn. Ứng dụng dùng hướng dẫn đã kiểm tra về lau ẩm và hạn chế nguồn bụi cho các câu này.

`prepare_xanhnon_review_data.py` tạo một bộ riêng tại `D:\XanhNon-auto-training\dialogue-correction-v4-data-20261019`:

| Nội dung | Train | Validation |
| --- | ---: | ---: |
| Mẫu mới, 9 nhóm lỗi/ngữ cảnh | 54 | 18 |
| Ôn cách diễn đạt và tư vấn | 64 | 20 |
| Ôn tình huống bốn nguồn cảm biến | 32 | 13 |
| **Tổng** | **150** | **51** |

Ba hội thoại ôn validation có cặp hỏi–đáp trùng tập học đã bị loại. Cả 150 mẫu train và 51 mẫu validation vừa giới hạn 512 token; các lượt hỏi–đáp được giữ trọn. Các bối cảnh số đo mới là giả định được ghi rõ, không phải dữ liệu giám sát hiện tại. Chín nhóm gồm kích thước bụi, phân loại AQI, dữ liệu mới so với lịch sử, không có máy lọc, thời gian tiếp xúc tiếng ồn, PM/AQI, hỏi thời điểm tư vấn, giải thích câu hỏi làm rõ và tiếp nối về bụi vào phổi.

Lượt củng cố học tiếp adapter vừa hoàn tất, learning rate `0.00005`, một lượt dữ liệu, 2 luồng CPU, checkpoint mỗi 8 bước. Hàng đợi dùng `--prepared-data` để kiểm tra manifest và chạy bộ đã chuẩn bị; không tải lại bốn nguồn. Lượt này đã hoàn tất **38/38 bước trên 150 mẫu**, validation loss trên 51 mẫu riêng giảm **2,26519 → 2,22497**, thời gian 2.594,5 giây. Không so trực tiếp loss này với lượt cảm biến vì hai tập validation khác nhau. Bản đang phát hành vẫn là v2 trong lúc đánh giá câu trả lời.

```powershell
# Chuẩn bị một bộ mới ở thư mục trống
.\.venv\Scripts\python.exe prepare_xanhnon_review_data.py --output D:\XanhNon-auto-training\new-reviewed-data
# Xếp bộ đã kiểm tra sau một ứng viên thực sự đã chạy
.\.venv\Scripts\python.exe queue_sensor_training.py --enqueue-after D:\XanhNon-auto-training\sensor-candidate-20261019-145040 --prepared-data D:\XanhNon-auto-training\new-reviewed-data
.\.venv\Scripts\python.exe queue_sensor_training.py --work
```

Báo cáo đối chiếu v3 nằm trong `D:\XanhNon-auto-training\sensor-review-v3`. Lượt củng cố v4 dùng thư mục `D:\XanhNon-auto-training\dialogue-review-v4`, chạy lại cả v2 và ứng viên trên cùng 20 câu, cùng mã xử lý hiện tại và 2 luồng CPU; log và trạng thái được ghi riêng. Loss giảm chưa chứng minh các lỗi tư vấn đã được sửa. `sensor-queue.json` ghi `awaiting_answer_evaluation` sau khi train xong; `training-monitor-status.json` lưu lần kiểm tra cuối khi worker kết thúc.

### Quyết định sau kiểm tra v4

- Đã sinh và đọc đủ 20 câu cho mỗi bản: v2 đạt 10/20, v4 đạt 10/20. Điểm v2 ở lần này khác lần trước do chạy lại với cùng mã định tuyến hiện tại; hai kết quả trong lần này dùng cùng đầu vào và tiêu chí. Đây là bộ kiểm tra giới hạn, không phải độ chính xác tổng quát của chatbot.
- V4 có lỗi mới ở bốn tình huống: giải thích PM2.5/phổi, so sánh PM2.5–PM10, ưu tiên AQI hiện tại hơn lịch sử và phân biệt nồng độ PM với AQI. Vẫn còn lỗi phân loại AQI giả định và câu tư vấn làm tăng thời gian ở nơi ồn. Không có trường hợp bị đánh dấu cắt ngắn hoặc chỉ còn câu dẫn, nhưng điều đó chưa đủ để chấp nhận bản mới.
- 44 kiểm thử ứng dụng về tư vấn thực hành, ngữ cảnh nhiều lượt, câu trả lời đúng trọng tâm và phạm vi hội thoại đều qua. Các kiểm thử này mô phỏng mô hình khi phù hợp; không dùng kết quả đó để khẳng định mô hình mới trả lời đúng.
- **Chưa áp dụng v4; giữ nguyên v2.** Quyết định và từng câu trả lời lỗi lưu trong `D:\XanhNon-auto-training\dialogue-review-v4\release-decision.json`. Không chạy thêm thử nghiệm phát hành kéo dài cho một ứng viên đã trượt kiểm tra sự thật và lỗi mới.
- Trước khi áp dụng bất kỳ ứng viên tiếp theo: không còn lỗi sự thật/tư vấn gây hại trong các câu đã rà soát, không thêm lỗi so với bản đang dùng, kiểm tra ứng viên thực qua đường xử lý của ứng dụng, rồi kiểm tra các cách hỏi khác nhau, nhiều lượt và tính đầy đủ của JSON/stream. Không tự áp dụng chỉ vì validation loss giảm.

### Lượt tiếp theo: ngữ cảnh ứng dụng v5

`prepare_xanhnon_runtime_data.py` chuẩn bị dữ liệu riêng tại `D:\XanhNon-auto-training\runtime-correction-v5-data-20261019`. Khác với các lượt hỏi–đáp ngắn trước, các mẫu mới dùng cấu trúc system prompt, số đo và kiến thức tham chiếu như khi ứng dụng gọi mô hình. Số đo giả lập được ghi rõ trong đầu vào. Với mẫu mới, chỉ câu trả lời cuối được tính loss; các câu trả lời cũ trong lịch sử được giữ làm ngữ cảnh và che khỏi nhãn học.

| Thành phần | Train | Validation |
| --- | ---: | ---: |
| Hội thoại theo ngữ cảnh ứng dụng, 12 nhóm | 72 | 24 |
| Ôn cách diễn đạt và tư vấn | 32 | 10 |
| Ôn bốn nguồn cảm biến | 16 | 6 |
| **Tổng** | **120** | **40** |

- Cả 160 hội thoại vừa giới hạn 1.024 token: dài nhất 909 token trong train, 892 trong validation. Không mất lượt hỏi–đáp cuối. Hai bản ghi ôn validation có cặp hỏi–đáp trùng tập học bị loại.
- Mẫu mới bổ sung giải thích PM2.5/phổi ngay ở lượt đầu, hỏi thời tiết đúng trọng tâm và thiếu AQI. Chín nhóm lỗi đã rà soát được ôn bằng đầu vào theo ứng dụng. Không chép nguyên câu hỏi của bộ đánh giá sinh câu trả lời vào mẫu mới.
- Điểm xuất phát được đặt rõ là adapter **v2 đang phát hành**, tránh kế thừa các lỗi mới đã phát hiện ở v4. Learning rate `0.0001`, một lượt dữ liệu, 2 luồng CPU, 8 lớp LoRA cuối, dự kiến **30 bước cập nhật**. Việc tăng ngữ cảnh làm lượt này nặng hơn lượt 512 token trước; chưa khẳng định chất lượng sẽ cải thiện trước khi kiểm tra đầu ra.
- 18 kiểm thử liên quan chuẩn bị dữ liệu, che nhãn học, cấu hình hàng đợi và nguồn cảm biến đã qua. Kết quả tokenizer nằm trong `tokenizer-preflight.json` của bộ dữ liệu mới. Sau huấn luyện vẫn cần so sánh câu trả lời riêng, chưa tự áp dụng.
- Hai GGUF thử v3/v4 không đạt yêu cầu được lưu bảo toàn trên D tại `D:\XanhNon-auto-training\archived-review-models-20261019` để có chỗ cho huấn luyện. SHA-256 được kiểm tra trước và sau chuyển; `archive-manifest.json` ghi đường dẫn cũ/mới. Bản v2 và mô hình gốc giữ nguyên.

### Kết quả v5 và lượt sửa tư vấn v6, ngày 21/10/2026

- V5 hoàn tất 30/30 bước trên 120 mẫu học và 40 mẫu validation; loss 2,06802 → 1,98583. Bản sinh trực tiếp đạt 12/20 theo bộ chấm cũ. Sau khi sửa bộ chấm để bắt câu định nghĩa bị thay bằng thông báo thiếu dữ liệu và khẳng định PM10 vô hại, chấm lại cùng đầu ra được **11/20**, bản v2 **10/20**. Đây là bộ hồi quy giới hạn, không phải độ chính xác tổng quát.
- V5 vẫn nhầm mức AQI giả định, dùng số cũ trong lịch sử và lẫn nồng độ bụi với AQI; có ba tình huống thêm lỗi so với v2. Không phát hành. Báo cáo và nguyên văn câu trả lời lưu tại `D:\XanhNon-auto-training\runtime-review-v5`. GGUF v5 được chuyển bảo toàn vào thư mục lưu các bản thử trên D, kiểm tra SHA-256 trước/sau; mô hình đang dùng vẫn là v2.
- `prepare_xanhnon_consultation_data.py` tạo bộ mới tại `D:\XanhNon-auto-training\consultation-v6-data-20261021-reviewed`: **132 mẫu học, 60 mẫu validation**. Trong đó có **60/20 mẫu mới**, **24/24 mẫu ôn ngữ cảnh v5**, **32/10 mẫu ôn cách diễn đạt và tư vấn**, **16/6 mẫu ôn bốn nguồn cảm biến**. Không tải lại hoặc học toàn bộ CSV cảm biến.
- Mười nhóm mới tập trung giải thích khái niệm đúng trọng tâm, kích thước và tác động của PM10, phân loại AQI, câu hỏi nối tiếp sau lời cảm ơn, chưa có thiết bị lọc, hỏi một câu làm rõ thời điểm, giải thích lý do hỏi, giới hạn suy luận nguồn ô nhiễm, ưu tiên số đo mới và phân biệt nồng độ với chỉ số. Không thêm đăng nhập hay cá nhân hóa.
- Đã sửa trùng cặp hỏi–đáp lịch sử giữa train/validation; giữ chặn lỗi khi dữ liệu bị trùng. **29 kiểm thử qua**, toàn bộ 192 hội thoại vừa 1.024 token; dài nhất 909 token ở train và 899 ở validation. Chỉ câu trả lời cuối của các mẫu mới được tính loss; câu hỏi đánh giá cố định được giữ riêng. Tài liệu chuyên môn tiếp tục dùng các nguồn EPA, AirNow và NIH/NIDCD đã kiểm tra trong manifest.
- Lượt v6 khởi động ngày 21/10/2026: ứng viên `D:\XanhNon-auto-training\dialogue-candidate-20261021-075257`, học từ adapter v2, một lượt dữ liệu, learning rate `0.00005`, 2 luồng CPU, 8 lớp LoRA cuối, **33 bước dự kiến**. Worker và bộ theo dõi chạy ẩn độc lập; trạng thái trực tiếp ở `sensor-queue.json` và `training-monitor-status.json`. Thư mục `consultation-review-v6-20261021` lưu kiểm thử và lần xác minh khởi động; không thay thế trạng thái trực tiếp.
- Chưa có kết luận chất lượng v6 trước khi học xong. Sau đó vẫn cần kiểm tra sự thật, lỗi mới, hội thoại thực qua ứng dụng và tính đầy đủ của JSON/stream trước khi áp dụng.
