# Trịnh Trung Kiên — hướng dẫn terminal từ đầu đến cuối

**Chỉ chỉnh và commit file `app.py`.** Các lệnh dùng PowerShell trên máy của chính bạn. Đọc từng bước, thực hiện thay đổi thật rồi chạy lệnh Git của bước đó.

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
git clone https://github.com/CTY-TNHH-1mktoi/quanli-moitruong-dothi.git quanli-moitruong-dothi-kien
if ($LASTEXITCODE -ne 0) { throw "Clone chưa thành công. Xem thông báo Git trước khi tiếp tục." }
Set-Location "quanli-moitruong-dothi-kien"
if (-not (Test-Path -LiteralPath 'app.py')) { throw 'Owner cần nhập bản nền đầy đủ vào main trước.' }
git status
git remote -v
```

## 2. Cấu hình tài khoản và vào nhánh của mình

Username là tài khoản của chính bạn; tên trong lệnh đã đặt theo phân công. Email phải lấy từ tài khoản đó.

```powershell
$GitHubUser = (Read-Host 'Username GitHub của bạn').Trim()
$CommitEmail = (Read-Host 'Email verified hoặc noreply của bạn').Trim()
git config --local user.name "Trịnh Trung Kiên"
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

Dự án dùng Python 3.13 đã kiểm tra. Tạo môi trường nếu clone mới chưa có:

```powershell
python --version
if (-not (Test-Path -LiteralPath .\.venv\Scripts\python.exe)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Cần cài xong thư viện trước khi kiểm tra." }
notepad .\app.py
```

Trong `app.py`, thêm endpoint sau ngay **trước** `if __name__ == "__main__":`. Đây là chức năng mới, bước đầu chỉ kiểm tra Flask:

```python
@app.route("/api/health")
def health():
    return jsonify({"UngDung": "Giam sat moi truong", "TrangThai": "ok"})
```

Lưu/đóng Notepad. Kiểm tra HTTP bằng test client, không khởi chạy server thật:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py
@'
import app as backend
response = backend.app.test_client().get("/api/health")
assert response.status_code == 200
assert response.get_json()["TrangThai"] == "ok"
print("Health Flask: OK")
'@ | .\.venv\Scripts\python.exe -
```

## 4. Commit và push lần thứ nhất
Đọc diff trước khi commit. Kết quả `git diff --cached --name-only` phải chỉ có `app.py`.

```powershell
git add -- "app.py"
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Sửa khoảng trắng/lỗi được báo rồi git add lại file." }
git diff --cached --name-only
git diff --cached
[void](Read-Host 'Đã đọc diff và xác nhận chỉ có file của mình? Nhấn Enter để tiếp tục')
git commit -m "feat: them endpoint health cho Flask"
if ($LASTEXITCODE -ne 0) { throw "Commit chưa thành công; xem thông báo rồi xử lý." }
git push -u origin HEAD
if ($LASTEXITCODE -ne 0) { throw "Push chưa thành công; xem phần xử lý lỗi ở cuối file." }
git log -1 --format="%h %an <%ae> %s"
git status
```


## 5. Lần sửa thứ hai: thêm kiểm tra SQL và lỗi kết nối

```powershell
notepad .\app.py
```

Thay toàn bộ hàm `health` vừa thêm bằng phiên bản sau; trong file chỉ giữ **một** route `/api/health`:

```python
@app.route("/api/health")
def health():
    connection = None
    try:
        connection = get_conn()
        connection.cursor().execute("SELECT 1").fetchone()
        return jsonify({
            "UngDung": "Giam sat moi truong",
            "TrangThai": "ok",
            "Database": "ok",
        })
    except pyodbc.Error:
        return jsonify({
            "UngDung": "Giam sat moi truong",
            "TrangThai": "loi",
            "Database": "khong_ket_noi",
        }), 503
    finally:
        if connection is not None:
            connection.close()
```

Dùng `get_conn`, `pyodbc`, `jsonify` đã có trong file. Lưu/đóng Notepad và kiểm chứng trường hợp thành công/lỗi bằng mock:

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py
@'
from unittest.mock import MagicMock, patch
import app as backend
connection = MagicMock()
connection.cursor.return_value.execute.return_value.fetchone.return_value = (1,)
client = backend.app.test_client()
with patch.object(backend, "get_conn", return_value=connection):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["Database"] == "ok"
connection.close.assert_called_once()
with patch.object(backend, "get_conn", side_effect=backend.pyodbc.Error("mock SQL error")):
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.get_json()["Database"] == "khong_ket_noi"
    assert "mock SQL error" not in response.get_data(as_text=True)
print("Health SQL: success/error/close OK (mock)")
'@ | .\.venv\Scripts\python.exe -
if ($LASTEXITCODE -ne 0) { throw "Sửa lỗi kiểm tra trước khi commit." }
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_locations.py -v
if ($LASTEXITCODE -ne 0) { throw "Kiểm thử địa điểm chưa đạt." }
```

Nếu máy có SQL thật, có thể kiểm tra thêm bằng hai terminal: terminal A đặt `DB_SERVER` đúng máy, `CHATBOT_PRELOAD=0` rồi chạy `.venv\Scripts\python.exe app.py`; terminal B gọi `Invoke-RestMethod http://127.0.0.1:5000/api/health`. Chỉ ghi “SQL thật đạt” khi đã làm bước này. Khi backend cũ đang chạy, thống nhất với người vận hành trước khi thay phiên chạy.
## 6. Commit và push lần thứ hai
Đọc diff trước khi commit. Kết quả `git diff --cached --name-only` phải chỉ có `app.py`.

```powershell
git add -- "app.py"
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Sửa khoảng trắng/lỗi được báo rồi git add lại file." }
git diff --cached --name-only
git diff --cached
[void](Read-Host 'Đã đọc diff và xác nhận chỉ có file của mình? Nhấn Enter để tiếp tục')
git commit -m "feat: kiem tra SQL va xu ly loi trong health endpoint"
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

- Tiêu đề PR: `Backend và dữ liệu: hoàn thiện app.py`.
- Mô tả hai thay đổi thật; ghi lệnh kiểm tra, kết quả của chính bạn và hạn chế chưa kiểm tra.
- **Files changed** phải chỉ có `app.py`. Nếu nhánh đã có các thay đổi cũ chưa merge, đối chiếu với owner trước khi mở PR cho đợt này.
- Nhờ một người khác review; owner quyết định merge theo quy định của repo. Quy trình tham khảo [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow).

Sau khi PR đã được merge, cập nhật bản local:

```powershell
git switch main
git pull --ff-only origin main
git log -4 --oneline -- "app.py"
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
