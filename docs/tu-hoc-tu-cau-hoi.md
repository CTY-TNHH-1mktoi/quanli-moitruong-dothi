# Tự tích lũy câu hỏi mới trong Xanh Non

Theo yêu cầu ngày 21/10/2026, khung chat tự nhận diện câu hỏi mới phù hợp trong lúc trò chuyện. Người dùng không cần đánh giá Hữu ích để kích hoạt việc tích lũy câu hỏi. Đánh giá bằng tin nhắn vẫn hoạt động riêng theo [Học từ góp ý](hoc-tu-gop-y.md).

## Luồng hoạt động

1. Lọc câu xã giao, câu ngoài phạm vi, mẫu đã có, câu hỏi thuộc tập đánh giá và những dấu hiệu thông tin nhạy cảm thông dụng. Câu nối tiếp được gắn với câu hỏi có chủ đề trước đó; lời cảm ơn không làm mất ngữ cảnh.
2. Lưu câu hỏi mới cùng câu hỏi trước đó nếu cần để hiểu ý. Không lưu câu trả lời tự sinh của mô hình vào kho này. Không tạo hồ sơ cá nhân.
3. Với cách hỏi mới mà bộ xử lý kiến thức đã xác định rõ chủ đề, lấy đáp án đúng nguyên bản hoặc phần phù hợp từ tài liệu đã kiểm tra trong `data/xanhnon/knowledge.json`. Tài liệu phải có nguồn chuyên môn chính thức. Không dùng điểm tương đồng mơ hồ làm bằng chứng câu trả lời đúng.
4. Ghi nhớ quan hệ giữa cách hỏi, ngữ cảnh và tài liệu nguồn. Lần hỏi lại có thể dùng trực tiếp nội dung nguồn; không cần chờ train xong. Nguồn thay đổi làm vô hiệu bản ghi cũ cho đến khi kiểm tra lại.
5. Tác vụ train theo giờ tự nhận các mẫu đủ điều kiện ở nguồn `environment_chat_learning`, kết hợp dữ liệu cũ và bản sửa đã duyệt. Bộ dữ liệu được đóng riêng thành snapshot; số lần hỏi lại không làm train lặp cùng dữ liệu. Câu hỏi đánh giá vẫn được giữ riêng.
6. Tạo adapter thử nghiệm, kiểm tra validation và chất lượng câu trả lời trước khi có thể áp dụng. Mô hình đang phục vụ và dữ liệu của lượt đang train không bị sửa giữa chừng.

Việc ghi nhớ cách hỏi và việc thay đổi trọng số là hai bước khác nhau. Một câu hỏi chưa từng gặp không tự cung cấp đáp án đúng. Phiên bản này tự học cách hỏi trên kiến thức đã kiểm tra; chưa tự tìm và duyệt kiến thức mới trên toàn bộ Internet.

## Các trạng thái

| Trạng thái | Ý nghĩa |
| --- | --- |
| `learned` | Đã gắn cách hỏi mới với đáp án và tài liệu nguồn hợp lệ; đủ điều kiện tạo mẫu train. |
| `needs_source` | Chưa xác định được đáp án có nguồn phù hợp. Lưu câu hỏi để bổ sung kiến thức, chưa tạo đáp án học. |
| `needs_data` | Có số liệu, thời gian hiện tại, giả định số hoặc yêu cầu dự báo; tiếp tục đi qua luồng đọc dữ liệu của ứng dụng. Không học thuộc số đó làm sự thật hiện tại. |
| `needs_review` | Câu hỏi có nguồn phù hợp nhưng quá dài cho giới hạn mẫu tự động; cần rút gọn hoặc kiểm tra riêng. |

Những câu ở trạng thái chưa đủ điều kiện vẫn được chuyển cho luồng trả lời bình thường. Câu trả lời do mô hình tự sinh không được dùng để tự chứng minh rồi huấn luyện lại. Khi kho nguồn được bổ sung, tác vụ theo giờ tự kiểm tra lại các câu hỏi có phiên bản nguồn cũ.

## Lưu trữ và cấu hình

- Kho câu hỏi mặc định: `.runtime/xanhnon-learning/questions.sqlite3`, ngoài thư mục web và bị Git bỏ qua.
- Chỉ lưu văn bản câu hỏi phù hợp và câu hỏi trước đó cần để hiểu ngữ cảnh. Không lấy nội dung câu trả lời cũ của chatbot làm ngữ cảnh huấn luyện.
- Bộ lọc nhận diện các dấu hiệu phổ biến như email, điện thoại, giấy tờ, mật khẩu, khóa truy cập và tọa độ. Đây là bộ lọc theo mẫu, không phải xác nhận ẩn danh tuyệt đối.
- `XANHNON_AUTO_LEARN=0` tắt việc tiếp nhận, dùng lại mẫu và cung cấp mẫu tự học cho các lần chuẩn bị dữ liệu tiếp theo. Áp dụng cấu hình cho cả ứng dụng và tác vụ Windows, rồi khởi động lại các tiến trình liên quan.
- `XANHNON_LEARNING_DB` đặt đường dẫn khác cho kho câu hỏi. Ứng dụng và tác vụ train cần dùng cùng cấu hình.
- Khung chat gửi `learn_from_chat: true` trong `POST /api/chat`; công cụ gọi API trực tiếp có thể gửi cờ này để bật tích lũy cho yêu cầu đó.

Xem thống kê tại máy:

```powershell
.\.venv\Scripts\python.exe learn_chat_questions.py
```

Xem câu hỏi đang thiếu nguồn, hoặc kiểm tra lại sau khi bổ sung kho kiến thức đã xác minh:

```powershell
.\.venv\Scripts\python.exe learn_chat_questions.py --pending
.\.venv\Scripts\python.exe learn_chat_questions.py --recheck
```

Các lệnh này không nạp trọng số LLM, không tự tìm kiếm web và không bắt đầu train. Quy trình chuẩn bị snapshot giữ nguyên các điều kiện RAM, đĩa và hàng đợi hiện có; không chạy thêm một mô hình train khi lượt trước đang hoạt động.
