# Nguyễn Trường Giang — hướng dẫn terminal từ đầu đến cuối

**Chỉ chỉnh và commit file `README.md`.** Các lệnh dùng PowerShell trên máy của chính bạn. Đọc từng bước, thực hiện thay đổi thật rồi chạy lệnh Git của bước đó.

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
git clone https://github.com/CTY-TNHH-1mktoi/quanli-moitruong-dothi.git quanli-moitruong-dothi-giang
if ($LASTEXITCODE -ne 0) { throw "Clone chưa thành công. Xem thông báo Git trước khi tiếp tục." }
Set-Location "quanli-moitruong-dothi-giang"
if (-not (Test-Path -LiteralPath 'README.md')) { throw 'Owner cần nhập bản nền đầy đủ vào main trước.' }
git status
git remote -v
```

## 2. Cấu hình tài khoản và vào nhánh của mình

Username là tài khoản của chính bạn; tên trong lệnh đã đặt theo phân công. Email phải lấy từ tài khoản đó.

```powershell
$GitHubUser = (Read-Host 'Username GitHub của bạn').Trim()
$CommitEmail = (Read-Host 'Email verified hoặc noreply của bạn').Trim()
git config --local user.name "Nguyễn Trường Giang"
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
## 3. Lần sửa thứ nhất: bảng phân công và phạm vi

Mở đúng file:

```powershell
notepad .\README.md
```

Thêm một mục mới `## Phân công và phạm vi nghiệm thu` vào README. Rà soát rồi viết bảng sau theo phân công đã thống nhất:

```markdown
## Phân công và phạm vi nghiệm thu

| Thành viên | File phụ trách trong đợt này | Đầu ra |
|---|---|---|
| Nguyễn Trường Giang | README.md | Phạm vi, cách chạy và tiêu chí nghiệm thu |
| Trịnh Trung Kiên | app.py | API health của Flask và SQL |
| Tạ Đăng Dương | static/index.html | Điều hướng nhanh các mục dashboard |
| Trần Trọng Nghĩa | chatbot.py | Thời gian nguồn dữ liệu trong ngữ cảnh chatbot |

Phạm vi: dashboard theo địa điểm, lưu dữ liệu/báo cáo, bản đồ AQI và AI tham khảo.
Dữ liệu không khí là mô hình; tiếng ồn là dữ liệu tổng hợp, không phải cảm biến thời gian thực tại từng đường phố.
```

Lưu file và đóng Notepad. Kiểm tra:

```powershell
git diff -- README.md
```

## 4. Commit và push lần thứ nhất
Đọc diff trước khi commit. Kết quả `git diff --cached --name-only` phải chỉ có `README.md`.

```powershell
git add -- "README.md"
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Sửa khoảng trắng/lỗi được báo rồi git add lại file." }
git diff --cached --name-only
git diff --cached
[void](Read-Host 'Đã đọc diff và xác nhận chỉ có file của mình? Nhấn Enter để tiếp tục')
git commit -m "docs: bo sung phan cong va pham vi du an"
if ($LASTEXITCODE -ne 0) { throw "Commit chưa thành công; xem thông báo rồi xử lý." }
git push -u origin HEAD
if ($LASTEXITCODE -ne 0) { throw "Push chưa thành công; xem phần xử lý lỗi ở cuối file." }
git log -1 --format="%h %an <%ae> %s"
git status
```


## 5. Lần sửa thứ hai: checklist nghiệm thu

Mở lại README, thêm checklist cụ thể dưới mục vừa tạo. Đọc mã/tài liệu và hỏi kết quả kiểm tra của người phụ trách trước khi đánh dấu đạt:

```powershell
notepad .\README.md
```


```markdown
### Checklist nghiệm thu của đợt này

| Phần việc | Thao tác kiểm tra | Điều kiện đạt |
|---|---|---|
| Backend | GET /api/health khi SQL kết nối được | HTTP 200, Database là ok |
| Backend lỗi SQL | Kiểm thử giả lập kết nối SQL lỗi | HTTP 503, không lộ chi tiết kết nối |
| UI | Bấm các mục Không khí/Bản đồ/Báo cáo/Chatbot | Chuyển đúng mục, dùng được bằng Tab và Enter |
| UI nhỏ | Kiểm tra chiều rộng 390 px | Không tràn ngang |
| AI | Kiểm tra nguồn không khí/thời tiết và NoiseCapture | Có thời gian nguồn khi được cung cấp |
| AI thiếu nguồn | Thử snapshot không có thời gian nguồn | Không tự bịa thời gian hoặc số đo |

Ghi thời điểm, người kiểm tra và kết quả thực tế trong PR nghiệm thu.
Các mục chưa kiểm tra phải ghi rõ là chưa kiểm tra.
```

Lưu, đóng Notepad và rà soát thay đổi:

```powershell
git diff --check
git diff -- README.md
```

## 6. Commit và push lần thứ hai
Đọc diff trước khi commit. Kết quả `git diff --cached --name-only` phải chỉ có `README.md`.

```powershell
git add -- "README.md"
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Sửa khoảng trắng/lỗi được báo rồi git add lại file." }
git diff --cached --name-only
git diff --cached
[void](Read-Host 'Đã đọc diff và xác nhận chỉ có file của mình? Nhấn Enter để tiếp tục')
git commit -m "docs: hoan thien checklist nghiem thu theo vai tro"
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

- Tiêu đề PR: `Yêu cầu và hướng dẫn dự án: hoàn thiện README.md`.
- Mô tả hai thay đổi thật; ghi lệnh kiểm tra, kết quả của chính bạn và hạn chế chưa kiểm tra.
- **Files changed** phải chỉ có `README.md`. Nếu nhánh đã có các thay đổi cũ chưa merge, đối chiếu với owner trước khi mở PR cho đợt này.
- Nhờ một người khác review; owner quyết định merge theo quy định của repo. Quy trình tham khảo [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow).

Sau khi PR đã được merge, cập nhật bản local:

```powershell
git switch main
git pull --ff-only origin main
git log -4 --oneline -- "README.md"
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
