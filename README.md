# Quản lý môi trường đô thị

Kho mã nguồn của dự án **Quản lý môi trường đô thị** thuộc tổ chức CTY-TNHH-1mktoi.

## Trạng thái

Dự án đang được khởi tạo. Tài liệu về phạm vi, kiến trúc, cách cài đặt và cách chạy sẽ được bổ sung khi mã nguồn được đưa vào kho.

## Nhánh của thành viên

| Thành viên GitHub | Nhánh làm việc |
| --- | --- |
| `247480201033-code` | `member/247480201033-code` |
| `tadangduong1504-art` | `member/tadangduong1504-art` |

## Quy trình làm việc

- `main` là nhánh chính, dùng để lưu phiên bản đã được nhóm xem xét.
- Mỗi thành viên làm việc trên nhánh `member/<github-username>` của mình. Với công việc cụ thể, có thể tạo nhánh `feature/<github-username>/<ten-cong-viec>` từ nhánh của mình.
- Khi hoàn tất, mở pull request vào `main`, mô tả thay đổi và cách kiểm tra.
- Nhờ ít nhất một thành viên khác xem xét pull request trước khi hợp nhất.
- Không đẩy trực tiếp hoặc force push lên `main`.

## Bắt đầu

```bash
git clone https://github.com/CTY-TNHH-1mktoi/quanli-moitruong-dothi.git
cd quanli-moitruong-dothi
git switch --track origin/member/<github-username>
```

Thay `<github-username>` bằng tên tài khoản GitHub của bạn.
