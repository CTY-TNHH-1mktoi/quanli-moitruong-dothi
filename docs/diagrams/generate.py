"""Generate the two project diagrams as editable SVG files."""

from html import escape
from pathlib import Path


OUT = Path(__file__).resolve().parent
INK = "#263238"
MUTED = "#52616b"
LINE = "#52616b"
PALE = "#f3f7f8"
GRID = "#edf1f2"


class SVG:
    def __init__(self, width, height, title, grid=False):
        self.width, self.height = width, height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
            f'<title>{escape(title)}</title>',
            '<rect width="100%" height="100%" fill="#ffffff"/>',
        ]
        if grid:
            self.parts += [
                '<defs><pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">'
                f'<path d="M 24 0 L 0 0 0 24" fill="none" stroke="{GRID}" stroke-width="1"/>'
                '</pattern></defs>',
                '<rect width="100%" height="100%" fill="url(#grid)"/>',
            ]

    def rect(self, x, y, w, h, fill="#ffffff", stroke=INK, sw=2.5, rx=0):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

    def line(self, x1, y1, x2, y2, dashed=False, sw=2.5, stroke=LINE):
        dash = ' stroke-dasharray="9 7"' if dashed else ""
        self.parts.append(
            f'<path d="M {x1} {y1} L {x2} {y2}" fill="none" stroke="{stroke}" '
            f'stroke-width="{sw}"{dash}/>'
        )

    def text(self, x, y, value, size=23, weight=400, anchor="start", fill=INK):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="Arial, Segoe UI, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
            f'fill="{fill}">{escape(value)}</text>'
        )

    def centered_lines(self, cx, cy, lines, size=23, weight=400, spacing=31):
        start = cy - (len(lines) - 1) * spacing / 2
        for i, value in enumerate(lines):
            self.text(cx, start + i * spacing + size * .35, value, size, weight, "middle")

    def save(self, name):
        (OUT / name).write_text("\n".join(self.parts + ["</svg>"]) + "\n", encoding="utf-8")


def function_diagram():
    s = SVG(2170, 1190, "Sơ đồ phân rã chức năng hệ thống giám sát môi trường đô thị", grid=True)
    s.rect(845, 68, 480, 136, PALE, sw=3)
    s.centered_lines(1085, 136, ["HỆ THỐNG GIÁM SÁT", "MÔI TRƯỜNG ĐÔ THỊ"], 29, 700, 39)

    columns = [
        ("Địa điểm & bản đồ", [
            ["Tìm và chọn địa điểm", "giám sát"],
            ["Xem vị trí tham chiếu", "trên bản đồ"],
            ["Xem lớp màu US AQI", "theo khu vực"],
            ["Kéo, thu phóng và", "tra cứu AQI trên bản đồ"],
        ]),
        ("Thu thập & theo dõi", [
            ["Lấy thời tiết, không khí", "từ Open-Meteo"],
            ["Tổng hợp tiếng ồn", "từ NoiseCapture"],
            ["Hiển thị AQI, bụi,", "nhiệt độ, độ ẩm, tiếng ồn"],
            ["Lưu số đo và xem", "xu hướng PM2.5"],
        ]),
        ("Cảnh báo & phân tích", [
            ["So sánh chỉ số", "với ngưỡng cảnh báo"],
            ["Ghi và tra cứu", "lịch sử cảnh báo"],
            ["Phân tích US AQI", "và đưa ra khuyến nghị"],
            ["Dự đoán bằng RF:", "không khí và tiếng ồn"],
        ]),
        ("Báo cáo môi trường", [
            ["Tạo báo cáo 24 giờ,", "7 ngày hoặc 30 ngày"],
            ["Thống kê chỉ số,", "xu hướng và đề xuất"],
            ["Lưu và mở", "lịch sử báo cáo"],
            ["Xuất CSV; in hoặc", "lưu báo cáo PDF"],
        ]),
        ("Chatbot Xanh Non", [
            ["Hỏi đáp về chỉ số", "và môi trường"],
            ["Dùng số đo mới nhất", "theo địa điểm đã chọn"],
            ["Trả lời dạng luồng;", "dừng hoặc viết tiếp"],
            ["Tạo cuộc", "trò chuyện mới"],
        ]),
    ]
    xs = [80, 495, 910, 1325, 1740]
    group_y, group_h = 324, 108
    child_ys = [505, 660, 815, 970]
    child_h = 105
    s.line(1085, 204, 1085, 271, sw=3)
    s.line(xs[0] + 175, 271, xs[-1] + 175, 271, sw=3)
    for x, (heading, children) in zip(xs, columns):
        cx = x + 175
        s.line(cx, 271, cx, group_y, sw=3)
        s.rect(x, group_y, 350, group_h, PALE, sw=2.7)
        s.centered_lines(cx, group_y + group_h / 2, [heading], 25, 700)
        rail_x = x + 24
        s.line(rail_x, group_y + group_h, rail_x, child_ys[-1] + child_h / 2)
        for y, lines in zip(child_ys, children):
            bx, bw = x + 50, 300
            s.line(rail_x, y + child_h / 2, bx, y + child_h / 2)
            s.rect(bx, y, bw, child_h)
            s.centered_lines(bx + bw / 2, y + child_h / 2, lines, 22, 400, 29)
    s.save("so-do-chuc-nang.svg")


def entity(s, x, y, w, title, fields, row_h=37):
    header_h, pad = 72, 21
    h = header_h + pad * 2 + row_h * len(fields)
    s.rect(x, y, w, h, "#ffffff", sw=2.6)
    s.line(x, y + header_h, x + w, y + header_h, sw=2.6, stroke=INK)
    s.text(x + w / 2, y + 47, title, 31, 700, "middle")
    for i, (name, kind) in enumerate(fields):
        fy = y + header_h + pad + (i + 1) * row_h - 8
        s.text(x + 28, fy, name, 23, 700 if kind == "PK" else 400)
        if kind == "PK":
            # Underline the primary key, as in the reference ERD.
            approx_width = min(len(name) * 13.5, w - 130)
            s.line(x + 28, fy + 4, x + 28 + approx_width, fy + 4, sw=1.4, stroke=INK)
    return h


def horizontal_relation(s, child_edge, parent_edge, y, label, dashed=False):
    """Connect a child on the left to a parent on the right."""
    s.line(child_edge, y, parent_edge, y, dashed=dashed)
    s.text((child_edge + parent_edge) / 2, y - 24, label, 19, 500, "middle", MUTED)
    # Crow's foot at the child; the open circle means participation is optional.
    s.line(child_edge + 24, y, child_edge, y - 15, stroke=INK)
    s.line(child_edge + 24, y, child_edge, y + 15, stroke=INK)
    s.parts.append(
        f'<circle cx="{child_edge + 37}" cy="{y}" r="8" fill="#ffffff" '
        f'stroke="{INK}" stroke-width="2.5"/>'
    )
    # A bar at the parent means exactly one.
    s.line(parent_edge - 21, y - 15, parent_edge - 21, y + 15, stroke=INK)


def erd_diagram():
    s = SVG(2150, 1470, "ERD các quan hệ dữ liệu chính của hệ thống giám sát môi trường đô thị")
    s.text(1075, 76, "ERD — CÁC QUAN HỆ DỮ LIỆU CHÍNH", 39, 700, "middle")

    report = [
        ("MaBaoCao", "PK"), ("MaDiaDiem", "logic"), ("TieuDe", ""),
        ("TuNgay", ""), ("DenNgay", ""), ("ThoiGianTao", ""),
        ("SoNgay", ""), ("SoBanGhi", ""), ("SoCanhBao", ""), ("NoiDung (JSON)", ""),
    ]
    place = [
        ("MaDiaDiem", "PK"), ("Ten", ""), ("Nhom", ""),
        ("ViDo", ""), ("KinhDo", ""), ("ViDoTiengOn", ""),
        ("KinhDoTiengOn", ""), ("TenKhuVucTiengOn", ""), ("ChiTiet (JSON)", ""),
    ]
    map_sample = [
        ("MaMau", "PK"), ("MaViTri", ""), ("ViDo", ""),
        ("KinhDo", ""), ("ThoiGianLay", ""), ("ThoiGianNguon", ""),
        ("US_AQI", ""), ("PM25", ""), ("ChiTiet (JSON)", ""),
    ]
    source = [
        ("Manguon", "PK"), ("MaDiaDiem", "logic"), ("TenNguon", ""),
        ("ThoiGian", ""), ("PM25", ""), ("PM10", ""),
        ("NhietDo", ""), ("DoAm", ""), ("TiengOn", ""),
        ("ChiTiet (JSON)", ""),
    ]
    alert = [
        ("Macanhbao", "PK"), ("Manguon", "FK"), ("LoaiCanhBao", ""),
        ("MucDo", ""), ("NoiDung", ""), ("ThoiGian", ""),
    ]
    analysis = [
        ("Maphantich", "PK"), ("Manguon", "FK"), ("KetQua", ""),
        ("NhanXet", ""), ("KhuyenNghi", ""), ("ThoiGian", ""),
    ]

    # Data relationships are behind the cards. Solid = SQL foreign key;
    # dashed = matching identifiers enforced by the application only.
    horizontal_relation(s, 650, 795, 390, "theo nơi", dashed=True)
    s.line(1075, 642, 1075, 765, dashed=True)
    s.text(1102, 700, "lưu số đo theo địa điểm", 19, 500, "start", MUTED)
    s.line(1060, 663, 1090, 663, stroke=INK)
    s.line(1075, 741, 1060, 765, stroke=INK)
    s.line(1075, 741, 1090, 765, stroke=INK)
    s.parts.append(f'<circle cx="1075" cy="727" r="8" fill="#ffffff" stroke="{INK}" stroke-width="2.5"/>')
    horizontal_relation(s, 650, 795, 1010, "phát sinh")
    s.line(1355, 1010, 1500, 1010)
    s.text(1427, 986, "phân tích", 19, 500, "middle", MUTED)
    s.line(1376, 995, 1376, 1025, stroke=INK)
    s.line(1476, 1010, 1500, 995, stroke=INK)
    s.line(1476, 1010, 1500, 1025, stroke=INK)
    s.parts.append(f'<circle cx="1463" cy="1010" r="8" fill="#ffffff" stroke="{INK}" stroke-width="2.5"/>')

    entity(s, 90, 195, 560, "BaoCaoMT", report)
    entity(s, 795, 195, 560, "DiaDiem", place)
    entity(s, 1500, 195, 560, "MauBanDoKhongKhi", map_sample)
    entity(s, 795, 765, 560, "NguonDL", source)
    entity(s, 90, 815, 560, "CanhBao", alert)
    entity(s, 1500, 815, 560, "PhanTichAI", analysis)

    s.text(1780, 670, "Mẫu AQI theo tọa độ; dùng lại theo giờ.", 20, 400, "middle", MUTED)
    s.text(1780, 702, "MaViTri không phải khóa đến DiaDiem.", 20, 400, "middle", MUTED)
    s.line(90, 1307, 2060, 1307, sw=1.5, stroke="#d7dfe2")
    s.line(145, 1363, 240, 1363)
    s.line(172, 1348, 172, 1378)
    s.text(255, 1371, "Một (bắt buộc)", 22, 400)
    s.line(680, 1363, 775, 1363)
    s.line(751, 1363, 775, 1348)
    s.line(751, 1363, 775, 1378)
    s.parts.append(f'<circle cx="738" cy="1363" r="8" fill="#ffffff" stroke="{INK}" stroke-width="2.5"/>')
    s.text(790, 1371, "Không hoặc nhiều (tùy chọn)", 22, 400)
    s.text(1570, 1371, "Khóa chính", 22, 400)
    s.line(1570, 1378, 1673, 1378, sw=1.6, stroke=INK)
    s.line(145, 1422, 235, 1422, dashed=True)
    s.text(255, 1430, "Nét đứt: liên kết logic theo MaDiaDiem, không khai báo khóa ngoại SQL.", 20, 400, fill=MUTED)
    s.text(1435, 1430, "NguonDL.MaDiaDiem có thể NULL.", 19, 400, fill=MUTED)
    s.save("so-do-erd.svg")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    function_diagram()
    erd_diagram()
