# Owner — chuẩn bị một lần trước khi bốn thành viên bắt đầu

Các lệnh trong file này dùng tài khoản của owner. Giang đã xác nhận là owner `trxyan` và ủy quyền trợ lý thực hiện bước chuẩn bị cùng phần `README.md`. Hướng dẫn được giữ để owner có thể tự thực hiện lại trên máy khác; kiểm tra lịch sử Git/PR trước khi chạy để tránh nhập bản nền lần nữa.

## 1. Chuẩn bị GitHub

- Dùng repository [quanli-moitruong-dothi](https://github.com/CTY-TNHH-1mktoi/quanli-moitruong-dothi).
- Xác nhận username của Giang, Kiên, Dương, Nghĩa; cấp quyền cộng tác, yêu cầu mọi người chấp nhận lời mời.
- Mã hiện có ở máy dự án cần được nhập đầy đủ vào `main` trước khi thành viên chỉnh một file trên bản clone. Các module phụ thuộc phải đi cùng bản nền.

## 2. Trên máy chứa dự án

```powershell
Set-Location "C:\Users\PC\OneDrive\Desktop\demoth1"
git status
git remote -v
$GitName = Read-Host 'Họ tên người nhập bản nền'
$CommitEmail = Read-Host 'Email verified hoặc noreply của tài khoản đó'
git config --local user.name "$GitName"
git config --local user.email "$CommitEmail"
git switch setup/team-workflow
notepad .\Demodatabase.sql
```

Trong file SQL, bỏ khoảng trắng dư cuối dòng `Create database` và các dòng trống dư cuối file; lưu rồi đóng Notepad. Đây là chỉnh định dạng, không chạy SQL hoặc tạo lại database.

```powershell
git add .
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Xử lý lỗi Git báo rồi git add lại file." }
git diff --cached --stat
git diff --cached --name-only
[void](Read-Host 'Đã kiểm tra file đưa lên, không có dữ liệu riêng hay thư viện cục bộ? Nhấn Enter')
git commit -m "chore: nhap ban nen dashboard va huong dan nhom"
if ($LASTEXITCODE -ne 0) { throw "Commit chưa thành công." }
git push -u origin HEAD
if ($LASTEXITCODE -ne 0) { throw "Push chưa thành công; kiểm tra đăng nhập/quyền ghi." }
Start-Process "https://github.com/CTY-TNHH-1mktoi/quanli-moitruong-dothi/compare/main...setup/team-workflow?expand=1"
```

Tạo PR và review/merge theo quy định hiện có của repo. Nếu rule cần review, reviewer phải khác tác giả PR. `.gitignore` bỏ qua `.venv/`, `models/`, `.runtime/`, `.env` và dữ liệu SQL; RF nhỏ đi cùng mã nguồn. Xanh Non/binary được chia sẻ riêng theo README.

## 3. Gửi đúng một hướng dẫn cho mỗi người

| Người | File hướng dẫn gửi | File duy nhất được giao |
|---|---|---|
| Giang | GIANG.md | README.md |
| Kiên | KIEN.md | app.py |
| Dương | DUONG.md | static/index.html |
| Nghĩa | NGHIA.md | chatbot.py |

Mỗi hướng dẫn có đủ clone → cấu hình danh tính → nhánh member → sửa cơ bản → commit/push → hoàn thiện cùng file → commit/push → PR.

## 4. Review và kết thúc

- Reviewer: Nghĩa xem Giang; Giang xem Kiên; Kiên xem Dương; Dương xem Nghĩa.
- Kiểm tra PR mỗi người chỉ thay file được giao, nội dung và kết quả kiểm tra đúng thực tế.
- Owner merge từng PR vào `main`. Nhóm cập nhật local bằng `git switch main` rồi `git pull --ff-only origin main`.
- Người thật tự chỉnh, kiểm chứng, commit và push; không đổi author hoặc ngày để tạo lịch sử cho người khác.
