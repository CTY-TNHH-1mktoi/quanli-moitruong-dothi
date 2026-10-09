# Lệnh terminal riêng cho bốn thành viên

Hướng dẫn PowerShell, chuẩn bị 10/10/2026. Đây là phương án mới: **mỗi thành viên chỉ chỉnh một file trong dự án**, làm hai bước từ cơ bản đến hoàn thiện.

Owner làm bước chuẩn bị một lần theo [00_OWNER.md](00_OWNER.md), sau đó gửi đúng file hướng dẫn cho từng thành viên.

| Người | File hướng dẫn đầy đủ | File chỉnh và commit |
|---|---|---|
| Nguyễn Trường Giang | [GIANG.md](GIANG.md) | README.md |
| Trịnh Trung Kiên | [KIEN.md](KIEN.md) | app.py |
| Tạ Đăng Dương | [DUONG.md](DUONG.md) | static/index.html |
| Trần Trọng Nghĩa | [NGHIA.md](NGHIA.md) | chatbot.py |

Giang (owner `trxyan`) đã ủy quyền trợ lý thực hiện phần chuẩn bị và phần `README.md` của mình. Kiên, Dương và Nghĩa tự chạy trên máy/tài khoản của mình. Những đoạn code mẫu cho ba thành viên là thay đổi được đề xuất, chưa được chèn vào mã ứng dụng trong bản nền. Kiểm tra lịch sử Git/PR trước khi chạy để không lặp lại phần đã hoàn thành.

Bốn nhánh dùng `member/<username>` theo quy định hiện có của repository. Hai tài khoản đã biết chưa được tự gán với tên người; từng người nhập username/email của chính mình ở bước cấu hình.
