# Tiêu chí phát triển và đánh giá Xanh Non

Theo yêu cầu ngày 19/10/2026, **cá nhân hóa để giai đoạn có đăng nhập**. Hiện không tạo hồ sơ cá nhân. Hội thoại giữ ngữ cảnh trong trang và tách theo địa điểm; không được tự động ghi lại khi trò chuyện. Từ 21/10/2026, người dùng có thể chủ động bấm **Hữu ích / Góp ý** để gửi riêng câu hỏi, câu trả lời và tối đa hai lượt trao đổi trước đó vào hàng chờ trên máy. Cơ chế học từ góp ý được mô tả tại [Học từ góp ý](hoc-tu-gop-y.md).

**Ưu tiên hiện tại:** giao tiếp tự nhiên, hiểu ngữ cảnh nhiều lượt, biết đặt câu hỏi tư vấn. Luồng kiểm tra chính: chào → yêu cầu tư vấn → chọn chạy bộ → hỏi thời điểm → trả lời “bây giờ” hoặc “sáng mai” → tư vấn dựa trên dữ liệu đúng thời điểm → cảm ơn. Bot không hỏi lại thời điểm nếu người dùng đã cung cấp.

Đợt cải tiến tiếp theo giữ tối đa 8 lượt hỏi đáp gần nhất, hiểu các câu ngắn như “giờ luôn”, “bây giờ luôn nhé”, “ý là sao?”, “chưa biết nữa”. Nếu người dùng chưa chốt giờ, bot đề nghị xem hiện tại rồi chờ đồng ý; “để sau nhé” được tôn trọng. Lời cảm ơn không làm mất chủ đề, yêu cầu “nói ngắn hơn” giữ căn cứ tư vấn và giảm phần diễn đạt.

| Tiêu chí áp dụng | Trọng số ban đầu | Điều kiện kiểm tra |
| --- | ---: | --- |
| Hiểu tiếng Việt | 15% | Có dấu/không dấu, cách nói tự nhiên, viết tắt, câu thiếu chủ ngữ; hiểu “clkk hnay tn?” và “mai không khí thế nào”. |
| Hiểu ngữ cảnh | 15% | “Còn mai?” tiếp nối câu AQI; một chủ đề mới không được kế thừa chủ đề cũ; không dùng khẳng định sai của bot làm dữ liệu. |
| Chính xác | 15% | Đúng số liệu, địa điểm, thời gian và đơn vị; phân biệt hiện tại với dự báo; không lấy nhiệt độ để suy ra ô nhiễm. |
| Giao tiếp tự nhiên | 10% | Chào hỏi, cảm ơn, tạm biệt, gọi bot, thừa nhận chưa hiểu; câu trả lời ngắn, không chép chỉ dẫn nội bộ. |
| Biết hỏi lại | 10% | Hỏi rõ nhu cầu khi người dùng chỉ nói “tư vấn giúp tôi”; hỏi thời điểm cụ thể nếu yêu cầu vượt khoảng dự báo có thể tra. |
| Giải thích đề xuất | 5% | Khuyến nghị ngoài trời nêu căn cứ AQI và mức ô nhiễm; không áp dụng số hiện tại cho ngày mai. |
| Tốc độ | 5% | Dữ liệu thường dùng có cache 10 phút; câu xã giao và câu số liệu trực tiếp không chờ mô hình; có SSE và nút dừng. Đo riêng lúc nguồn API lỗi/chậm. |
| Xử lý lỗi | 5% | Nói rõ phần chưa lấy được; không phủ nhận toàn bộ dữ liệu khi chỉ thiếu dự báo; câu ngoài phạm vi dùng lời giới thiệu theo yêu cầu. |
| An toàn, bảo mật | 5% | Không kê thuốc/chẩn đoán từ AQI; kiểm tra JSON và lịch sử; câu truy vấn CSDL có tham số; không gửi hội thoại ra dịch vụ LLM bên ngoài. |

Trọng số còn lại là **85%** sau khi bỏ cá nhân hóa. Nếu quy đổi điểm về 100, dùng `tổng điểm có trọng số / 85 × 100`. Đây là mục tiêu kiểm tra, không phải tuyên bố chatbot đã đạt điểm chuyên gia.

## Dữ liệu tư vấn

Kho kiến thức có 26 chủ đề, bao gồm 6 nhóm biện pháp thực hành với nguồn EPA, NIH/NIDCD và CDC: giảm bụi vào nhà, phòng ẩm mốc, giảm tiếp xúc tiếng ồn, giảm rác, dùng máy lọc và điều chỉnh hoạt động khi nóng. Câu hỏi thực hành rõ nghĩa được trả lời bằng các biện pháp đã kiểm tra, không chỉ bằng câu dẫn hứa liệt kê. Nếu mô hình vẫn kết thúc ngay sau một câu dẫn ở chủ đề khác, phản hồi được đánh dấu chưa hoàn chỉnh để giữ khả năng viết tiếp.

Bổ sung 30 mẫu huấn luyện `environment_advice`: 25 mẫu train và 5 mẫu validation, giữ nguyên phân chia của dữ liệu cũ. Tác vụ tự huấn luyện chọn cả `environment_style` và `environment_advice`; có dữ liệu mới nhưng chưa đủ 3 GiB RAM trống thì ghi nhận chờ, không tuyên bố đã train.

- Dữ liệu hiện tại: bộ nhớ ứng dụng, bản ghi SQL của đúng địa điểm, rồi truy vấn không khí chỉ đọc khi thiếu/cũ.
- Dự báo: Open-Meteo/CAMS, theo giờ, múi giờ Việt Nam, phạm vi 5 ngày. Khoảng thấp–cao của các giờ không được gọi là AQI trung bình cả ngày. Thiếu giờ hợp lệ thì không tóm tắt thành dự báo đủ ngày.
- Khuyến nghị: thang US AQI và hướng dẫn hoạt động EPA/AirNow, với nguồn ghi trong kho kiến thức. Không coi nồng độ PM là giá trị AQI.
- Nguồn chính: https://open-meteo.com/en/docs/air-quality-api ; https://www.airnow.gov/aqi/aqi-basics/ ; https://www.airnow.gov/sites/default/files/2023-03/air-quality-guide-for-particle-pollution_0.pdf

## Huấn luyện tự động trên máy

Đợt học tiếp từ bốn nguồn cảm biến và cơ chế bỏ trùng được mô tả tại [Huấn luyện dữ liệu cảm biến](huan-luyen-du-lieu-cam-bien.md). Hàng đợi chờ lượt đang chạy kết thúc; tác vụ theo giờ nhường lượt cho hàng đợi còn chờ.

Tác vụ Windows `XanhNon-Train-Reviewed-Data` kiểm tra mỗi giờ. Script `daily_train_xanhnon.py` đọc dữ liệu đã chuẩn bị và kiểm tra SHA-256 trong manifest. Khi chưa có dữ liệu mới so với lần train xong gần nhất, script ghi nhận bỏ qua, không train lặp liên tục.

Khi có bản sửa từ góp ý đã duyệt, tác vụ chuẩn bị một bộ dữ liệu riêng dưới `D:\XanhNon-auto-training\feedback-data`, thêm nguồn `environment_feedback` vào dữ liệu luyện và giữ nguyên tập validation. Câu hỏi trùng với holdout/evaluation được bỏ qua; ngữ cảnh khác nhau của cùng câu nối tiếp vẫn được giữ riêng. Chỉ câu trả lời cuối đã sửa được tính vào mục tiêu học. Lượt đang train và dữ liệu gốc không bị sửa giữa chừng. Bản thử vẫn chờ đánh giá câu trả lời trước khi có thể áp dụng.

Mỗi lần tối đa 128 mẫu đã chọn, một lượt qua tập đó, 2 luồng CPU, LoRA trên 8 lớp cuối. 24 mẫu validation được đánh giá trước và sau. Bản thử và nhật ký nằm tại `D:\XanhNon-auto-training`; bản đang chạy và trọng số gốc được giữ nguyên. Giảm validation loss chỉ đưa bản thử sang trạng thái chờ đánh giá câu trả lời; chưa đủ điều kiện để tự thay mô hình đang dùng.

Máy cần bật và tài khoản Windows này cần đăng nhập. Task không gọi ChatGPT nên không tiêu token ChatGPT; CPU/RAM và thời gian chạy vẫn được sử dụng. Sau lỗi, cùng dữ liệu được thử lại vào ngày sau. Những lần tự chạy tiếp theo cần ít nhất 3 GiB RAM trống và không bật chế độ cho phép paging khi thiếu RAM; thiếu tài nguyên thì chờ lần kiểm tra sau. Đợt chạy đầu được khởi tạo trước khi áp dụng giới hạn RAM này.

Khi chủ động chạy ngay trên máy ít RAM, có thể dùng `--allow-cpu-paging` cho riêng lượt gọi đó. Script chỉ cho phép nếu RAM trống cộng bộ nhớ ảo còn ít nhất 6 GiB; quá trình có thể chậm hơn. Cờ này không thay đổi cấu hình tác vụ theo giờ.

```powershell
# Xem trạng thái gần nhất
Get-Content D:\XanhNon-auto-training\latest-status.json
# Kiểm tra sẵn sàng, không train
.\.venv\Scripts\python.exe daily_train_xanhnon.py --check
# Chạy ngay với bộ nhớ ảo nếu đủ RAM + swap
.\.venv\Scripts\python.exe daily_train_xanhnon.py --allow-cpu-paging
# Tắt/bật lịch
Disable-ScheduledTask -TaskName XanhNon-Train-Reviewed-Data
Enable-ScheduledTask -TaskName XanhNon-Train-Reviewed-Data
```
