# Học từ góp ý cho Xanh Non

## Cách sử dụng

Dưới câu trả lời hoàn chỉnh có hai nút:

- **Hữu ích:** ghi nhận câu trả lời đáp ứng nhu cầu.
- **Góp ý:** chọn vấn đề về ngữ cảnh, độ chính xác, cách diễn đạt, nội dung chưa đầy đủ hoặc vấn đề khác; nhập nhận xét ngắn. Có thể mở phần đề xuất câu trả lời nếu muốn.

Chỉ khi bấm gửi, ứng dụng mới lưu câu hỏi, câu trả lời, tối đa hai lượt trao đổi trước đó, địa điểm đang chọn, tên phiên bản mô hình và góp ý. Mở trang hay trò chuyện bình thường không tự ghi hội thoại vào kho góp ý. Đổi địa điểm khi yêu cầu lưu đang chạy vẫn giữ góp ý ở đúng địa điểm của câu trả lời đó. Nếu lưu thất bại, biểu mẫu giữ nội dung để gửi lại.

Kho mặc định là `.runtime/xanhnon-feedback/feedback.sqlite3`, được bỏ qua bởi Git và nằm ngoài thư mục web. Có thể đặt `XANHNON_FEEDBACK_DB` trước khi khởi động ứng dụng và tác vụ train để cùng dùng một đường dẫn khác. API nhận góp ý là `POST /api/chat/feedback`; không cung cấp API liệt kê hoặc duyệt góp ý.

## Từ góp ý thành dữ liệu học

1. Mọi góp ý mới đều ở trạng thái `pending`, kể cả đánh giá Hữu ích.
2. Người kiểm tra xem yêu cầu, ngữ cảnh và câu trả lời, rồi viết lại hội thoại đã sửa và loại bỏ dữ liệu riêng tư. Kiến thức môi trường phải đối chiếu với nguồn chuyên môn trong kho kiến thức; hội thoại/hỏi lại có thể dùng quy tắc dự án.
3. Góp ý được duyệt bằng công cụ tại máy. Một nhận xét hoặc câu trả lời đề xuất của người dùng không tự trở thành đáp án đúng. Các con số quan trắc/dự báo thật phải được viết lại thành tình huống giả định rõ ràng khi dùng để luyện, không học thuộc thành thông tin hiện tại.
4. Khi máy rảnh và hàng đợi train trước đã kết thúc, tác vụ theo giờ ghép các bản sửa đã duyệt vào một snapshot riêng. Góp ý chưa duyệt hoặc bị loại không thay đổi dữ liệu train hay fingerprint.
5. Loại dữ liệu trùng, giữ riêng câu hỏi validation/evaluation, giữ nguyên tập validation và chỉ học câu trả lời cuối đã sửa. Các hội thoại quá dài không được cắt ngầm để học câu trả lời cũ ở giữa hội thoại.
6. Train một adapter thử nghiệm riêng. Validation loss giảm đưa bản thử sang trạng thái chờ đánh giá câu trả lời, không tự kích hoạt. Cần kiểm tra tính đúng đắn, ngữ cảnh, hỏi lại và các ca hồi quy trước khi thay bản đang dùng.

Đây là cơ chế tích lũy và học từ bản sửa đã kiểm tra. Bấm đánh giá không làm trọng số đổi ngay, và số lượt thích không phải bằng chứng câu trả lời chính xác.

## Kiểm tra và duyệt tại máy

Xem góp ý đang chờ:

```powershell
.\.venv\Scripts\python.exe review_chat_feedback.py --status pending
```

Tạo một file JSON chứa hội thoại đã kiểm tra, theo thứ tự user/assistant. Không đưa system prompt, lời góp ý chưa xác minh hay số đo cũ vào đáp án. Ví dụ hội thoại ngắn về cách hỏi lại:

```json
[
  {"role": "user", "content": "Nếu chưa rõ mình đang hỏi về chỉ số nào thì sao?"},
  {"role": "assistant", "content": "Mình sẽ hỏi lại một câu ngắn để biết bạn muốn xem chỉ số nào."}
]
```

Duyệt một bản sửa về hội thoại, với ID lấy từ danh sách góp ý:

```powershell
.\.venv\Scripts\python.exe review_chat_feedback.py --id 1 --approve --reviewer "Nguoi kiem tra" --note "Da doi chieu quy tac hoi lai va loai thong tin rieng tu" --messages-file "D:\XanhNon-auto-training\reviewed-feedback-messages.json" --source project --privacy-reviewed --facts-reviewed
```

Với kiến thức môi trường, dùng `--kind knowledge` cùng nguồn chuyên môn hợp lệ, ví dụ `--source epa_pm` hoặc `--source airnow_aqi`. Không duyệt kiến thức chỉ với nguồn `project`. Với tình huống số liệu giả định, thêm `--data-policy hypothetical` và ghi rõ giả định trong câu hỏi.

Loại một góp ý khỏi dữ liệu học của các lần chuẩn bị sau:

```powershell
.\.venv\Scripts\python.exe review_chat_feedback.py --id 1 --reject --reviewer "Nguoi kiem tra" --note "Chua du can cu de dung lam du lieu hoc"
```

Kiểm tra tác vụ train, không bắt đầu huấn luyện:

```powershell
.\.venv\Scripts\python.exe daily_train_xanhnon.py --check
```

Khi có dữ liệu phản hồi đã duyệt và không bị loại do trùng/holdout, lệnh chuẩn bị dữ liệu dưới `D:\XanhNon-auto-training\feedback-data` và hiển thị đường dẫn, fingerprint, số mẫu được nhận/bỏ qua. Nếu đang train hoặc còn hàng đợi, nó chờ. Lần train có nguồn feedback dùng ngữ cảnh 1024 token, giữ 2 luồng CPU và các điều kiện RAM/đĩa hiện có. Bản đang phục vụ tiếp tục dùng mô hình đã kích hoạt trước đó.
