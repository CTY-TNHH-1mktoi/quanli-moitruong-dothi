# Quản lý môi trường đô thị

Kho mã nguồn của dự án **Quản lý môi trường đô thị** thuộc tổ chức CTY-TNHH-1mktoi.

## Trạng thái

Dự án đang được khởi tạo. Tài liệu về phạm vi, kiến trúc, cách cài đặt và cách chạy sẽ được bổ sung khi mã nguồn được đưa vào kho.

## Phân quyền và nhánh làm việc

| Vai trò | Tài khoản GitHub | Nhánh làm việc |
| --- | --- | --- |
| Owner, quản trị viên | `trxyan` | Duyệt và hợp nhất pull request vào `main` |
| Thành viên | `247480201033-code` | `member/247480201033-code` |
| Thành viên | `tadangduong1504-art` | `member/tadangduong1504-art` |

Mỗi thành viên đẩy commit lên nhánh của mình và mở pull request vào `main`. Owner xem xét, phê duyệt và quyết định có hợp nhất pull request hay không. Không đẩy trực tiếp hoặc force push lên `main`.

## Bắt đầu

```bash
git clone https://github.com/CTY-TNHH-1mktoi/quanli-moitruong-dothi.git
cd quanli-moitruong-dothi
git switch --track origin/member/<github-username>
```

Thay `<github-username>` bằng tên tài khoản GitHub của bạn.
