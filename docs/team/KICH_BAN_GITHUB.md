# Kịch bản làm việc và trình bày GitHub của nhóm

Chuẩn bị ngày 10/10/2026. Repository: [CTY-TNHH-1mktoi/quanli-moitruong-dothi](https://github.com/CTY-TNHH-1mktoi/quanli-moitruong-dothi).

**Theo yêu cầu mới, mỗi người chỉ chỉnh một file dự án.** Dùng [bộ lệnh terminal riêng](terminal/README.md): [Giang](terminal/GIANG.md), [Kiên](terminal/KIEN.md), [Dương](terminal/DUONG.md), [Nghĩa](terminal/NGHIA.md). Mỗi hướng dẫn có đầy đủ bước từ clone đến hai lần commit/push và tạo PR. Owner làm [bước chuẩn bị một lần](terminal/00_OWNER.md).

## 1. Điểm bắt đầu

Dự án đã có mã chạy được. Giang xác nhận là owner và ủy quyền trợ lý nhập bản nền, thực hiện phần `README.md` bằng tài khoản GitHub đã kết nối `trxyan`. Kiên, Dương và Nghĩa tự thực hiện thay đổi mới bằng tài khoản của mình. Commit và PR trên GitHub ghi nhận kết quả thực hiện; tài liệu này không giả định phần việc của thành viên đã hoàn thành.

Owner nhập bản nền hiện có và tài liệu hướng dẫn bằng một PR. Sau đó các thành viên thực hiện phần rà soát, tài liệu, kiểm thử và sửa lỗi tiếp theo bằng tài khoản của mình. Mỗi commit ghi đúng thay đổi mới; thời điểm commit là thời điểm thực hiện.

Owner của repository là `trxyan`, được giữ trong `CODEOWNERS`. Hai tài khoản được README trước đó ghi nhận là `247480201033-code` và `tadangduong1504-art`; nhóm cần xác nhận chúng ứng với ai trong bảng dưới đây. Tên người phụ trách trong tài liệu chưa tự gán thành assignee GitHub.

Owner hoàn tất PR bản nền trước khi nhóm bắt đầu. Thành viên chưa có quyền ghi cần được owner thêm quyền cộng tác và chấp nhận lời mời. Các nhánh thành viên theo quy ước hiện có `member/<github-username>`; owner quyết định hợp nhất vào `main`.

### Owner tự đưa bản nền lên GitHub

Trên máy có dự án hiện tại, chạy từng bước bằng PowerShell và dùng danh tính của chính người thực hiện:

```powershell
cd C:\Users\PC\OneDrive\Desktop\demoth1
$GitName = Read-Host 'Họ tên của người nhập bản nền'
$CommitEmail = Read-Host 'Email verified hoặc noreply từ Settings/Emails'
git config --local user.name "$GitName"
git config --local user.email "$CommitEmail"
git switch setup/team-workflow
git add .
git diff --cached --check
git diff --cached --stat
```

Đọc danh sách file trước khi commit và xử lý các lỗi định dạng do `git diff --cached --check` báo. Khoảng trắng dư trong `Demodatabase.sql` được dọn khi chuẩn bị bản nền; không chạy SQL hoặc thay đổi database. `.gitignore` bỏ qua `.venv/`, `models/`, `.runtime/`, `.env` và file dữ liệu SQL; mô hình RF nhỏ vẫn được đưa cùng mã nguồn.

Khi nội dung đã được kiểm tra, chính owner chạy:

```powershell
git commit -m "chore: nhap ban nen dashboard va huong dan lam viec nhom"
git push -u origin HEAD
```

Trên GitHub tạo PR từ `setup/team-workflow` vào `main`, điền thay đổi thực tế và kết quả kiểm tra. Thực hiện review/merge theo cấu hình repo; nếu yêu cầu review thì người review phải khác tác giả PR. Sau khi bản nền có trên `main`, owner tạo bốn issue theo bảng phân công, gán đúng tài khoản đã xác nhận và gửi link cho nhóm.

## 2. Phân công cụ thể

| Thành viên | Vai trò | Phần mã cần đọc | Đầu ra mới cần commit | Reviewer đề xuất |
|---|---|---|---|---|
| Nguyễn Trường Giang | Điều phối, phân tích yêu cầu | README, sơ đồ chức năng, tiêu chí nghiệm thu | Chỉ `README.md`: phân công và checklist nghiệm thu | Trần Trọng Nghĩa |
| Trịnh Trung Kiên | Backend, dữ liệu | `app.py` và các schema SQL | Chỉ `app.py`: endpoint health Flask/SQL | Nguyễn Trường Giang |
| Tạ Đăng Dương | Frontend, UI/UX | `static/`, các trạng thái UI | Chỉ `static/index.html`: menu điều hướng nhanh | Trịnh Trung Kiên |
| Trần Trọng Nghĩa | Mô hình, tích hợp AI | `chatbot.py`, metadata nguồn, cơ chế sinh | Chỉ `chatbot.py`: thời gian nguồn trong ngữ cảnh | Tạ Đăng Dương |

Các file trong `docs/team/templates/` là tài liệu tham khảo về yêu cầu/API/UI/AI. Trong đợt chia một file này, thành viên ghi kết quả kiểm chứng vào mô tả PR, không tạo thêm file kết quả hoặc sửa các module khác.

## 3. Mỗi thành viên chuẩn bị máy và nhánh

Đăng nhập GitHub bằng tài khoản cá nhân. Lấy email đã xác minh hoặc địa chỉ `noreply` chính xác tại **GitHub → Settings → Emails**. Email commit giúp GitHub liên kết commit với tài khoản; username đơn thuần không thay thế email. Xem [hướng dẫn email commit](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address).

Các lệnh dưới đây dùng PowerShell, thực hiện một lần trong bản clone mới:

```powershell
git clone https://github.com/CTY-TNHH-1mktoi/quanli-moitruong-dothi.git
cd quanli-moitruong-dothi
$GitHubUser = Read-Host 'Username GitHub của bạn'
$GitName = Read-Host 'Họ tên của bạn'
$CommitEmail = Read-Host 'Email verified hoặc noreply từ Settings/Emails'
git config --local user.name "$GitName"
git config --local user.email "$CommitEmail"
git fetch origin
$MemberBranch = "member/$GitHubUser"
git show-ref --verify --quiet "refs/remotes/origin/$MemberBranch"
if ($LASTEXITCODE -eq 0) {
    git switch --track "origin/$MemberBranch"
} else {
    git switch -c "$MemberBranch" origin/main
}
git merge origin/main
git status
```

Nếu đã có nhánh local, dùng `git switch "member/<username-của-bạn>"` thay cho bước tạo nhánh. Khi merge có xung đột, đọc và giải quyết từng file trước khi tiếp tục.

Clone Git có mã nguồn và mô hình RF nhỏ `environment_rf.joblib`. Bộ trọng số Xanh Non trong `models/` và binary trong `.runtime/llama-bin/` được chia sẻ riêng từ bản dự án đang chạy; README có cách đặt đúng thư mục. Máy thử ứng dụng cần SQL Server, ODBC 17 và cấu hình `DB_SERVER` của chính máy đó. Kiểm thử đơn vị dùng mock, không cần database thật hoặc chạy chatbot thật.

## 4. Thứ tự hai commit của mỗi người

| Thành viên | Commit 1 sau khi rà soát tài liệu | Commit 2 sau khi kiểm chứng |
|---|---|---|
| Giang | `docs: bo sung phan cong va pham vi du an` | `docs: hoan thien checklist nghiem thu theo vai tro` |
| Kiên | `feat: them endpoint health cho Flask` | `feat: kiem tra SQL va xu ly loi trong health endpoint` |
| Dương | `feat: them dieu huong nhanh den muc khong khi` | `feat: hoan thien dieu huong ban do bao cao va chatbot` |
| Nghĩa | `feat: bo sung thoi gian nguon khong khi va thoi tiet` | `feat: bo sung thoi gian nguon NoiseCapture cho chatbot` |

Đây là gợi ý thông điệp. Nếu có sửa mã, đặt thêm commit `fix(...)` mô tả đúng lỗi và cách sửa.

Ví dụ Kiên sửa đúng file được giao; xem nội dung thêm và lệnh kiểm tra đầy đủ trong `terminal/KIEN.md`:

```powershell
notepad .\app.py
# Thêm chức năng, lưu file và kiểm tra theo KIEN.md trước khi tiếp tục.
git add -- app.py
git diff --cached
git commit -m "feat: them endpoint health cho Flask"
git push -u origin HEAD
```

Giang chỉ stage `README.md`; Kiên chỉ stage `app.py`; Dương chỉ stage `static/index.html`; Nghĩa chỉ stage `chatbot.py`. Mỗi người kiểm tra `git diff --cached --name-only` trước khi commit. Kết quả thử thật hoặc mock được ghi đúng loại trong PR.

## 5. Kiểm chứng theo vai trò

| Người thực hiện | Lệnh / thao tác | Ghi nhận |
|---|---|---|
| Giang | Đối chiếu từng mã yêu cầu trong SRS với thao tác demo và kết quả của ba phần kỹ thuật | Đạt, chưa đạt hoặc chưa kiểm tra; issue lỗi nếu có |
| Kiên | `.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_locations.py -v`; chạy tương tự cho `test_environment_reports.py` và `test_air_quality_map.py` | Lệnh, số bài đạt/lỗi, ngày chạy; SQL thật chỉ ghi kết quả đã kiểm tra |
| Dương | `node tests/test_air_overlay.cjs`; chạy ba file `tests/browser/check_*.py` theo README | Desktop, 390 px, đổi địa điểm, lỗi mạng/thử lại, AQI, CSV, không trộn phản hồi cũ |
| Nghĩa | `.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_chat_stream.py -v`; thêm lượt thử RF/chatbot thật trên máy có đủ mô hình | Thiếu tiếng ồn, ngữ cảnh đúng nơi, phản hồi đến EOS; phân biệt mock với mô hình thật |

Ghi kết quả của lần chạy của mình; `TEST_REPORT.md` là bằng chứng của phiên trước, không thay cho lần kiểm chứng mới. Kiểm thử trình duyệt địa điểm cần có báo cáo TP.HCM đã lưu; nếu thiếu, tạo từ dữ liệu thật qua giao diện trước hoặc ghi rõ phần chưa chạy được.

## 6. Tạo PR, review và merge

1. Trên GitHub chọn **Pull requests → New pull request**: base `main`, compare `member/<username>`.
2. Điền mẫu PR: thay đổi thực tế, lệnh đã chạy, kết quả và hạn chế. Gắn `Closes #<issue-được-giao>`.
3. Mời reviewer theo bảng; các tài khoản phải có quyền phù hợp. Reviewer đọc **Files changed** và kiểm chứng bằng chứng. Góp ý vào vấn đề thực tế nếu tìm thấy; nếu đạt thì phê duyệt.
4. Tác giả sửa theo review, commit và push thêm vào cùng nhánh; PR tự cập nhật.
5. Owner kiểm tra rồi merge theo quy định repository. Tác giả không thể tự phê duyệt PR của chính mình; nếu quy tắc yêu cầu review, cần người khác đủ quyền.
6. Mỗi thành viên cập nhật sau khi merge: `git switch main`, `git pull --ff-only origin main`. Owner thống nhất khi nào kết thúc nhánh `member/` đang dùng cho đợt làm việc.

Quy trình này theo [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow).

## 7. Kịch bản buổi trình bày 35–45 phút

| Cảnh | Người / thời lượng | Thao tác trên màn hình | Lời trình bày gợi ý |
|---|---|---|---|
| 1. Chốt mục tiêu | Giang / 4 phút | Mở issue yêu cầu và SRS, chọn 3 tiêu chí chính | “Nhóm kiểm chứng lựa chọn địa điểm, tính nhất quán dữ liệu và báo cáo; đây là tiêu chí nghiệm thu của đợt này.” |
| 2. Luồng dữ liệu | Kiên / 7 phút | Mở PR backend, ERD, kết quả test; demo Hà Nội → TP.HCM | “Tôi đã rà soát hợp đồng API, cách lưu snapshot và lọc theo MaDiaDiem; đây là các trường hợp tôi đã kiểm tra.” |
| 3. Giao diện/bản đồ | Dương / 7 phút | Mở PR UI, thử AQI/độ đậm/toàn màn hình và màn hình 390 px | “Tôi kiểm tra thao tác chọn nơi, trạng thái lỗi và bản đồ; màu AQI là nội suy từ mô hình.” |
| 4. AI | Nghĩa / 7 phút | Mở model card và PR AI, thử RF thiếu tiếng ồn, hỏi chatbot về nơi đang chọn | “Tôi rà soát đầu vào và ngữ cảnh; RF là phân loại tham khảo, còn chatbot dùng mô hình cục bộ.” |
| 5. Review | Reviewer / 5 phút | Mở bình luận review, giải thích một điểm đã xác minh | “Tôi đã đối chiếu nội dung với diff và kết quả kiểm tra; kết luận review được ghi trong PR.” |
| 6. Hoàn tất | Owner + Giang / 5 phút | Mở PR đã merge, issue đã đóng, chạy demo tổng | “Các phần việc mới đã được hợp nhất; tiêu chí chưa kiểm tra hoặc hạn chế còn lại được ghi tại đây.” |

Các cảnh được lên lịch để nhóm làm việc thật; không cần tạo lỗi giả, commit rỗng hay đổi tác giả/ngày commit. Một người có thể hỗ trợ người khác, nhưng người đứng tên tự đọc, chỉnh, kiểm chứng và commit phần việc của mình.

## 8. Bộ bằng chứng nộp cuối

- Bốn issue và bốn PR do các thành viên thực hiện, có link đến commit thực tế.
- Bốn file đã thay đổi đúng phần việc, kèm kết quả kiểm chứng trong từng PR; các tài liệu mẫu vẫn là nguồn tham khảo.
- PR có review của người khác và quyết định merge của owner.
- Một ảnh demo tổng và danh sách tiêu chí đạt/chưa đạt; có thể xem lịch sử bằng `git log --all --graph --oneline --decorate`.
