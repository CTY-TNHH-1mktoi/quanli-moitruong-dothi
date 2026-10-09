# Trần Trọng Nghĩa — hướng dẫn terminal từ đầu đến cuối

**Chỉ chỉnh và commit file `chatbot.py`.** Các lệnh dùng PowerShell trên máy của chính bạn. Đọc từng bước, thực hiện thay đổi thật rồi chạy lệnh Git của bước đó.

## 0. Điều kiện trước khi bắt đầu

- Owner đã nhập đầy đủ dự án hiện có vào `main` theo `00_OWNER.md`, bao gồm các file phụ thuộc và `.gitignore`.
- Tài khoản GitHub của bạn đã được cấp quyền cộng tác và đã chấp nhận lời mời.
- Git đã có trên máy. Mở PowerShell và chạy `git --version`; nếu chưa có, cài từ [Git for Windows](https://git-scm.com/downloads/win), rồi mở lại PowerShell.
- Lấy email verified hoặc địa chỉ `noreply` chính xác tại GitHub → Settings → Emails. Xem [hướng dẫn chính thức](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address).

## 1. Clone về thư mục riêng

Chạy một lần. Nếu thư mục clone đã tồn tại, dùng bản clone đó, không clone đè.

```powershell
$GitWork = Join-Path $env:USERPROFILE 'git-nhom'
New-Item -ItemType Directory -Path $GitWork -Force | Out-Null
Set-Location $GitWork
git clone https://github.com/CTY-TNHH-1mktoi/quanli-moitruong-dothi.git quanli-moitruong-dothi-nghia
if ($LASTEXITCODE -ne 0) { throw "Clone chưa thành công. Xem thông báo Git trước khi tiếp tục." }
Set-Location "quanli-moitruong-dothi-nghia"
if (-not (Test-Path -LiteralPath 'chatbot.py')) { throw 'Owner cần nhập bản nền đầy đủ vào main trước.' }
git status
git remote -v
```

## 2. Cấu hình tài khoản và vào nhánh của mình

Username là tài khoản của chính bạn; tên trong lệnh đã đặt theo phân công. Email phải lấy từ tài khoản đó.

```powershell
$GitHubUser = (Read-Host 'Username GitHub của bạn').Trim()
$CommitEmail = (Read-Host 'Email verified hoặc noreply của bạn').Trim()
git config --local user.name "Trần Trọng Nghĩa"
git config --local user.email "$CommitEmail"
git config --local --get user.name
git config --local --get user.email
$MemberBranch = "member/$GitHubUser"
git check-ref-format --branch "$MemberBranch"
if ($LASTEXITCODE -ne 0) { throw "Username hoặc tên nhánh chưa hợp lệ." }
git fetch origin
if ($LASTEXITCODE -ne 0) { throw "Fetch chưa thành công." }
git show-ref --verify --quiet "refs/heads/$MemberBranch"
if ($LASTEXITCODE -eq 0) {
    git switch "$MemberBranch"
} else {
    git show-ref --verify --quiet "refs/remotes/origin/$MemberBranch"
    if ($LASTEXITCODE -eq 0) {
        git switch --track "origin/$MemberBranch"
    } else {
        git switch -c "$MemberBranch" origin/main
    }
}
if ($LASTEXITCODE -ne 0) { throw "Chưa chuyển được sang nhánh thành viên." }
git merge origin/main
if ($LASTEXITCODE -ne 0) { throw "Cần xử lý xung đột trước khi tiếp tục." }
git status
```

Các bước dưới đây tiếp tục trong cùng cửa sổ PowerShell để giữ biến `$MemberBranch`.
## 3. Chuẩn bị Python và lần sửa thứ nhất

```powershell
python --version
if (-not (Test-Path -LiteralPath .\.venv\Scripts\python.exe)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Cần cài xong thư viện trước khi kiểm tra." }
notepad .\chatbot.py
```

Tìm hàm `_dashboard_context(snapshot)`. Ngay trước dòng `analysis = snapshot.get("PhanTich", {})`, thêm phần sau với thụt dòng như code:

```python
    air_time = readings.get("ThoiGianNguonKhongKhi")
    weather_time = readings.get("ThoiGianNguonThoiTiet")
    if air_time:
        prompt += f"Thời gian dữ liệu không khí từ nguồn: {air_time}.\n"
    if weather_time:
        prompt += f"Thời gian dữ liệu thời tiết từ nguồn: {weather_time}.\n"
```

Hàm hiện có thời gian cập nhật snapshot; phần mới tách rõ thời gian dữ liệu nguồn. Giữ cách xử lý giá trị thiếu và chế độ sinh đến EOS.

Lưu/đóng Notepad và kiểm chứng bằng snapshot giả lập (không nạp LLM):

```powershell
.\.venv\Scripts\python.exe -m py_compile chatbot.py
@'
from chatbot import _dashboard_context
from location_catalog import get_location
snapshot = {
    "DiaDiem": get_location("tphcm"),
    "DuLieu": {
        "PM25": 20, "TiengOn": None,
        "ThoiGianNguonKhongKhi": "2026-10-10T09:00",
        "ThoiGianNguonThoiTiet": "2026-10-10T09:15",
    },
}
text = _dashboard_context(snapshot)
assert "Thành phố Hồ Chí Minh" in text
assert "2026-10-10T09:00" in text and "2026-10-10T09:15" in text
assert "Tiếng ồn: chưa có dữ liệu" in text
assert "Hà Nội" not in text
print("Source time and selected place: OK (mock)")
'@ | .\.venv\Scripts\python.exe -
if ($LASTEXITCODE -ne 0) { throw "Sửa lỗi trước khi commit." }
```

## 4. Commit và push lần thứ nhất
Đọc diff trước khi commit. Kết quả `git diff --cached --name-only` phải chỉ có `chatbot.py`.

```powershell
git add -- "chatbot.py"
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Sửa khoảng trắng/lỗi được báo rồi git add lại file." }
git diff --cached --name-only
git diff --cached
[void](Read-Host 'Đã đọc diff và xác nhận chỉ có file của mình? Nhấn Enter để tiếp tục')
git commit -m "feat: bo sung thoi gian nguon khong khi va thoi tiet"
if ($LASTEXITCODE -ne 0) { throw "Commit chưa thành công; xem thông báo rồi xử lý." }
git push -u origin HEAD
if ($LASTEXITCODE -ne 0) { throw "Push chưa thành công; xem phần xử lý lỗi ở cuối file." }
git log -1 --format="%h %an <%ae> %s"
git status
```


## 5. Lần sửa thứ hai: thời gian NoiseCapture

```powershell
notepad .\chatbot.py
```

Trong cùng hàm, thêm đoạn sau ngay sau phần thời gian nguồn vừa tạo và trước `analysis = ...`:

```python
    noise_detail = readings.get("TiengOn_ChiTiet") or {}
    noise_time = noise_detail.get("DoGanNhat")
    if readings.get("TiengOn") is not None and noise_time:
        prompt += f"Thời gian đo gần nhất trong nguồn NoiseCapture: {noise_time}.\n"
```

Giữ nguyên tên nguồn, khu vực đang chọn và câu chú thích tiếng ồn không phải đo trực tiếp. Lưu/đóng Notepad, rồi kiểm chứng cả có/thiếu nguồn:

```powershell
.\.venv\Scripts\python.exe -m py_compile chatbot.py
@'
from chatbot import _dashboard_context
from location_catalog import get_location
snapshot = {
    "DiaDiem": get_location("hanoi"),
    "DuLieu": {
        "TiengOn": 60,
        "TiengOn_ChiTiet": {"DoGanNhat": "2025-01-02T10:00:00Z"},
    },
}
text = _dashboard_context(snapshot)
assert "2025-01-02T10:00:00Z" in text
assert "không phải đo trực tiếp" in text
empty = _dashboard_context({"DiaDiem": get_location("tphcm"), "DuLieu": {"TiengOn": None}})
assert "2025-01-02T10:00:00Z" not in empty
assert "Thời gian dữ liệu không khí từ nguồn" not in empty
assert "Tiếng ồn: chưa có dữ liệu" in empty
print("Noise source and missing data: OK (mock)")
'@ | .\.venv\Scripts\python.exe -
if ($LASTEXITCODE -ne 0) { throw "Sửa lỗi kiểm tra trước khi commit." }
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_chat_stream.py -v
if ($LASTEXITCODE -ne 0) { throw "Kiểm thử streaming chưa đạt." }
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_locations.py -v
if ($LASTEXITCODE -ne 0) { throw "Kiểm thử ngữ cảnh theo địa điểm chưa đạt." }
```

Các bước trên kiểm tra mock/ngữ cảnh, chưa chứng minh chất lượng trả lời của LLM thật. Nếu kiểm tra thêm chatbot thật, dùng mô hình đã chia sẻ của nhóm và ghi kết quả đúng lần chạy của mình. Đợt này không thay giới hạn độ dài hoặc ngắt lượt sinh đang chạy.
## 6. Commit và push lần thứ hai
Đọc diff trước khi commit. Kết quả `git diff --cached --name-only` phải chỉ có `chatbot.py`.

```powershell
git add -- "chatbot.py"
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Sửa khoảng trắng/lỗi được báo rồi git add lại file." }
git diff --cached --name-only
git diff --cached
[void](Read-Host 'Đã đọc diff và xác nhận chỉ có file của mình? Nhấn Enter để tiếp tục')
git commit -m "feat: bo sung thoi gian nguon NoiseCapture cho chatbot"
if ($LASTEXITCODE -ne 0) { throw "Commit chưa thành công; xem thông báo rồi xử lý." }
git push -u origin HEAD
if ($LASTEXITCODE -ne 0) { throw "Push chưa thành công; xem phần xử lý lỗi ở cuối file." }
git log -1 --format="%h %an <%ae> %s"
git status
```


## 7. Mở PR và hoàn tất

Sau khi cả hai commit đã push thành công:

```powershell
$PullRequestUrl = "https://github.com/CTY-TNHH-1mktoi/quanli-moitruong-dothi/compare/main...${MemberBranch}?expand=1"
Start-Process -FilePath $PullRequestUrl
```

Trên trang vừa mở, kiểm tra **base: main**, **compare: nhánh của bạn**, rồi chọn **Create pull request**.

- Tiêu đề PR: `Ngữ cảnh chatbot: hoàn thiện chatbot.py`.
- Mô tả hai thay đổi thật; ghi lệnh kiểm tra, kết quả của chính bạn và hạn chế chưa kiểm tra.
- **Files changed** phải chỉ có `chatbot.py`. Nếu nhánh đã có các thay đổi cũ chưa merge, đối chiếu với owner trước khi mở PR cho đợt này.
- Nhờ một người khác review; owner quyết định merge theo quy định của repo. Quy trình tham khảo [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow).

Sau khi PR đã được merge, cập nhật bản local:

```powershell
git switch main
git pull --ff-only origin main
git log -4 --oneline -- "chatbot.py"
```

## 8. Lỗi thường gặp

- **`git` không nhận diện:** cài Git và mở lại PowerShell.
- **`nothing to commit`:** mở lại file, lưu thay đổi thực tế rồi `git add` đúng file. Kiểm tra `git diff`; nếu không có thay đổi thì không cần commit.
- **Push bị 403:** đăng nhập đúng GitHub, kiểm tra lời mời collaborator và quyền ghi nhánh với owner. Nhánh `member/<username>` phải đúng tài khoản của bạn.
- **Push bị `non-fast-forward`:** khi cây làm việc sạch, chạy các lệnh sau rồi giải quyết xung đột nếu Git báo:

```powershell
git fetch origin
git merge "origin/$MemberBranch"
# Nếu có xung đột: sửa file, git add file đã xử lý, rồi git commit.
git push origin HEAD
```

- **Terminal mới không có `$MemberBranch`:** chạy `$MemberBranch = git branch --show-current` trước khi mở link PR hoặc xử lý push.
- **PR có file khác:** dùng `git status`, `git diff --cached --name-only` và trao đổi với owner để tách đúng phần việc; không bỏ qua các thay đổi đang có.

Hai commit là hai giai đoạn thay đổi có ích. Bạn tự đọc, chỉnh và kiểm tra file mình phụ trách; không cần gửi log, thư mục `.venv/` hoặc trọng số Xanh Non vào commit.
