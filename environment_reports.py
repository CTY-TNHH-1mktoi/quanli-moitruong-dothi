"""Saved environmental reports built from recorded measurements and alerts."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
from threading import Lock

from flask import Blueprint, jsonify, request
import pyodbc
from location_catalog import DEFAULT_LOCATION, get_location


# Operational thresholds already used by app.build_alerts; not legal limits.
METRICS = (
    ("PM25", "PM2.5", "µg/m³", 35.5, 55.5),
    ("PM10", "PM10", "µg/m³", 100, 154),
    ("NhietDo", "Nhiệt độ", "°C", 35, 38),
    ("DoAm", "Độ ẩm", "%", 85, 95),
    ("TiengOn", "Tiếng ồn", "dBA", 70, 85),
)


def finite_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def build_report(rows, alerts, days, now, location=None):
    """A reproducible snapshot; missing data never becomes a zero reading."""
    start = now - timedelta(days=days)
    location = location or get_location()
    rows = sorted(rows, key=lambda row: (row["ThoiGian"], row["Manguon"]))
    rows = [{**row, **{field: finite_number(row.get(field)) for field, *_ in METRICS}} for row in rows]
    # Keep alerts tied to the same measurements, even if data changes between reads.
    ids = {row["Manguon"] for row in rows}
    alerts = [alert for alert in alerts if alert["Manguon"] in ids]
    alerts = sorted(alerts, key=lambda alert: (alert["ThoiGian"], alert["Macanhbao"]), reverse=True)
    high_count = sum(alert.get("MucDo") == "Cao" for alert in alerts)
    alert_ids = {alert["Manguon"] for alert in alerts}
    count = len(rows)
    sources = Counter(row["TenNguon"] for row in rows)
    metrics = []
    for field, name, unit, mid, high in METRICS:
        measured = [(row[field], row["ThoiGian"]) for row in rows if row[field] is not None]
        values = [value for value, _ in measured]
        noise = field == "TiengOn"
        metrics.append({
            "Truong": field, "Ten": name, "DonVi": unit,
            "SoBanGhi": len(values), "SoThieu": count - len(values),
            "TrungBinh": round(sum(values) / len(values), 2) if values and not noise else None,
            "ThapNhat": min(values) if values else None,
            "CaoNhat": max(values) if values else None,
            "GanNhat": values[-1] if values else None,
            "ThoiGianGanNhat": measured[-1][1] if measured else None,
            "ThayDoi": round(values[-1] - values[0], 2) if len(values) >= 2 and not noise else None,
            "NguongLuuY": mid, "NguongCao": high,
            "VuotNguongLuuY": sum(value >= mid for value in values),
            "VuotNguongCao": sum(value >= high for value in values),
            "TyLeNguongLuuY": round(100 * sum(value >= mid for value in values) / len(values), 1) if values else None,
            "LoaiDuLieu": "tong_hop_khu_vuc" if noise else "ban_ghi",
        })

    groups = defaultdict(list)
    for row in rows:
        # Hourly groups for 24h, daily groups for the longer reports.
        bucket = row["ThoiGian"][:13] + ":00:00" if days == 1 else row["ThoiGian"][:10] + "T00:00:00"
        groups[bucket].append(row)
    trend = []
    for timestamp, group in sorted(groups.items()):
        values = [row["PM25"] for row in group if row["PM25"] is not None]
        trend.append({
            "ThoiGian": timestamp, "SoBanGhi": len(group), "SoBanGhiPM25": len(values),
            "TrungBinhPM25": round(sum(values) / len(values), 2) if values else None,
            "CaoNhatPM25": max(values) if values else None,
        })

    by_type = defaultdict(list)
    for alert in alerts:
        by_type[alert["LoaiCanhBao"]].append(alert)
    breakdown = sorted([
        {"LoaiCanhBao": name, "SoCanhBao": len(items),
         "SoCanhBaoCao": sum(item.get("MucDo") == "Cao" for item in items),
         "GanNhat": items[0]["ThoiGian"]}
        for name, items in by_type.items()
    ], key=lambda item: (-item["SoCanhBaoCao"], -item["SoCanhBao"], item["LoaiCanhBao"]))

    planning, response = [], []
    def advice(target, title, text, evidence, priority="Theo dõi"):
        target.append({"TieuDe": title, "NoiDung": text, "CanCu": evidence, "MucDo": priority})

    for metric in metrics:
        if not metric["VuotNguongLuuY"]:
            continue
        field = metric["Truong"]
        evidence = (f"{metric['VuotNguongLuuY']}/{metric['SoBanGhi']} bản ghi {metric['Ten']} "
                    f"đạt ngưỡng lưu ý {metric['NguongLuuY']} {metric['DonVi']}; "
                    f"cao nhất {metric['CaoNhat']:g} {metric['DonVi']}.")
        priority = "Cao" if metric["VuotNguongCao"] else "Theo dõi"
        if field in {"PM25", "PM10"}:
            advice(planning, f"Kiểm soát nguồn bụi {metric['Ten']}",
                   "Bổ sung điểm đo tại tuyến giao thông và khu vực xây dựng; rà soát vệ sinh đường, che phủ vật liệu và tổ chức vận chuyển để giảm phát tán bụi.", evidence, priority)
            advice(response, f"Xác minh cảnh báo {metric['Ten']}",
                   "Kiểm tra lại tại hiện trường bằng thiết bị phù hợp; xác định thời điểm, vị trí và nguồn phát tán trước khi lập phương án xử lý. Đối chiếu số đo sau xử lý để đánh giá thay đổi.", evidence, priority)
        elif field == "TiengOn":
            advice(planning, "Khảo sát tiếng ồn trước khi bố trí công trình",
                   f"Khảo sát theo vị trí và thời điểm quanh {location['TenKhuVucTiengOn']}; xem xét khoảng cách giữa nguồn ồn với khu ở và bố trí giải pháp giảm truyền âm sau khảo sát.",
                   evidence + " Đây là giá trị tổng hợp khu vực, không phải số đo tại một điểm.", priority)
            advice(response, "Đo kiểm tiếng ồn tại vị trí phản ánh",
                   "Xác định nguồn và thời gian phát sinh; đo lại tại vị trí bị ảnh hưởng. Không dùng dữ liệu NoiseCapture tổng hợp để xác nhận một sự cố đang diễn ra.", evidence, priority)
        elif field == "NhietDo":
            advice(planning, "Bổ sung không gian giảm tích nhiệt",
                   "Khảo sát các khu vực ít bóng râm; xem xét cây xanh, bề mặt thấm nước và điểm nghỉ có che nắng khi lập phương án không gian công cộng.", evidence, priority)
            advice(response, "Kiểm tra các điểm chịu nhiệt cao",
                   "Đối chiếu với số đo tại chỗ và rà soát điều kiện che nắng, thông gió tại khu vực được phản ánh; ghi nhận kết quả kiểm tra trong hồ sơ xử lý.", evidence, priority)
        else:
            advice(planning, "Rà soát thoát nước và thông gió",
                   "Khảo sát những nơi ẩm kéo dài và các điểm thoát nước kém; đối chiếu với số đo tại công trình trước khi lựa chọn giải pháp.", evidence, priority)
            advice(response, "Xác minh độ ẩm cao tại hiện trường",
                   "Kiểm tra thiết bị đo, điều kiện thông gió và dấu hiệu đọng nước tại khu vực phản ánh; theo dõi sau khi xử lý nguyên nhân.", evidence, priority)

    if not planning:
        advice(planning, "Bổ sung dữ liệu đại diện cho khu vực",
               "Duy trì thu thập theo lịch cố định và bổ sung điểm đo theo vị trí, giờ cao điểm, ngày trong tuần để có cơ sở so sánh khi lập quy hoạch.",
               f"Kỳ báo cáo có {count} bản ghi từ {len(sources)} nguồn.")
    if not response:
        advice(response, "Duy trì theo dõi và xác minh phản ánh",
               "Khi có phản ánh, ghi nhận vị trí, thời gian và đo lại tại chỗ; dữ liệu tổng hợp trong kỳ chưa đủ để xác nhận hoặc loại trừ một sự cố cụ thể.",
               f"Có {len(alerts)} cảnh báo đã lưu trong kỳ; {count} bản ghi môi trường.")

    notes = [
        f"Địa điểm: {location['Ten']} ({location['ViDo']}, {location['KinhDo']}). Không khí và thời tiết: mô hình Open-Meteo theo tọa độ tham chiếu. Tiếng ồn: NoiseCapture quanh {location['TenKhuVucTiengOn']}, không phải đo trực tiếp theo thời gian thực.",
        "Dữ liệu không khí theo ô lưới mô hình; các địa điểm gần nhau có thể nhận cùng giá trị. Tên khu vực NoiseCapture theo bộ dữ liệu nguồn, có thể là tên hành chính cũ.",
        "Trung bình là trung bình các bản ghi đã lưu, không phải trung bình liên tục theo thời gian. Các khoảng không có bản ghi không được nội suy.",
        "Tiếng ồn chỉ trình bày khoảng giá trị và giá trị gần nhất; không lấy trung bình số học dBA. Các bản ghi có thể lặp lại cùng dữ liệu tổng hợp.",
        "Ngưỡng lưu ý/cao là ngưỡng vận hành minh họa của hệ thống. Cảnh báo đã lưu không đồng nghĩa với sự cố được xác minh hoặc kết luận vi phạm quy chuẩn.",
        "Đề xuất được tạo từ số liệu và quy tắc của hệ thống; dữ liệu hiện có chưa xác định được điểm nóng theo vị trí hoặc quan hệ nguyên nhân.",
    ]
    if not count:
        notes.insert(0, "Không có bản ghi trong kỳ đã chọn; chưa có cơ sở đánh giá tình trạng môi trường.")
    elif count < 10:
        notes.insert(0, f"Chỉ có {count} bản ghi trong kỳ; cần bổ sung dữ liệu trước khi kết luận về xu hướng dài hạn.")
    priority = "Chưa có dữ liệu" if not count else "Cao" if high_count else "Theo dõi" if alerts else "Theo dõi định kỳ"
    summary = (f"Đã ghi nhận {count} bản ghi và {len(alerts)} cảnh báo trong kỳ, "
               f"trong đó {high_count} cảnh báo mức cao.") if count else "Chưa có dữ liệu trong kỳ báo cáo."
    return {
        "PhienBan": 2, "TieuDe": "Báo cáo phân tích môi trường", "SoNgay": days, "DiaDiem": location,
        "TuNgay": start.isoformat(), "DenNgay": now.isoformat(), "ThoiGianTao": now.isoformat(),
        "TongQuan": {
            "SoBanGhi": count, "SoCanhBao": len(alerts), "SoCanhBaoCao": high_count,
            "SoBanGhiCoCanhBao": len(alert_ids), "SoNguon": len(sources),
            "TyLeBanGhiCoCanhBao": round(100 * len(alert_ids) / count, 1) if count else None,
            "ThoiGianDau": rows[0]["ThoiGian"] if count else None,
            "ThoiGianCuoi": rows[-1]["ThoiGian"] if count else None,
            "MucUuTien": priority, "TomTat": summary,
        },
        "ChiSo": metrics, "XuHuong": trend, "CanhBaoTheoLoai": breakdown,
        "QuyHoach": planning, "XuLySuCo": response, "GhiChu": notes,
        "Nguon": [{"TenNguon": name, "SoBanGhi": total} for name, total in sorted(sources.items())],
        "DuLieu": rows, "CanhBao": alerts,
    }


class ReportRepository:
    def __init__(self, connection_factory, convert_rows, ensure_locations=None):
        self.connection_factory = connection_factory
        self.convert_rows = convert_rows
        self._schema_ready = False
        self._schema_lock = Lock()
        self.ensure_locations = ensure_locations or (lambda: None)

    def ensure_schema(self):
        if self._schema_ready:
            return
        with self._schema_lock:
            if not self._schema_ready:
                sql = Path(__file__).with_name("report_schema.sql").read_text(encoding="utf-8")
                self.ensure_locations()
                with self.connection_factory() as conn:
                    conn.cursor().execute(sql)
                    conn.commit()
                self._schema_ready = True

    def create(self, days, location_id=DEFAULT_LOCATION):
        location = get_location(location_id)
        self.ensure_schema()
        now = datetime.now()
        start = now - timedelta(days=days)
        with self.connection_factory() as conn:
            cur = conn.cursor()
            cur.execute("""SELECT Manguon, TenNguon, ThoiGian, PM25, PM10, NhietDo, DoAm, TiengOn, MaDiaDiem
                           FROM NguonDL WHERE ThoiGian >= ? AND ThoiGian <= ? AND MaDiaDiem = ?
                           ORDER BY ThoiGian, Manguon""", start, now, location_id)
            rows = self.convert_rows(cur)
            cur.execute("""SELECT c.Macanhbao, c.Manguon, c.LoaiCanhBao, c.MucDo, c.NoiDung, c.ThoiGian
                           FROM CanhBao c INNER JOIN NguonDL n ON n.Manguon = c.Manguon
                           WHERE n.ThoiGian >= ? AND n.ThoiGian <= ? AND n.MaDiaDiem = ?
                           ORDER BY c.ThoiGian DESC, c.Macanhbao DESC""", start, now, location_id)
            alerts = self.convert_rows(cur)
            report = build_report(rows, alerts, days, now, location)
            content = json.dumps(report, ensure_ascii=False, allow_nan=False)
            cur.execute("""INSERT INTO dbo.BaoCaoMT
                           (TieuDe, TuNgay, DenNgay, ThoiGianTao, SoNgay, SoBanGhi, SoCanhBao, NoiDung, MaDiaDiem)
                           OUTPUT INSERTED.MaBaoCao VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        report["TieuDe"], start, now, now, days, len(rows), len(report["CanhBao"]), content, location_id)
            report_id = cur.fetchone()[0]
            conn.commit()
        return {**report, "MaBaoCao": report_id}

    def list(self, limit, offset=0, location_id=DEFAULT_LOCATION):
        get_location(location_id)
        self.ensure_schema()
        with self.connection_factory() as conn:
            cur = conn.cursor()
            cur.execute("""SELECT MaBaoCao, TieuDe, TuNgay, DenNgay, ThoiGianTao,
                           SoNgay, SoBanGhi, SoCanhBao, MaDiaDiem FROM dbo.BaoCaoMT WHERE MaDiaDiem = ?
                           ORDER BY ThoiGianTao DESC, MaBaoCao DESC
                           OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""", location_id, offset, limit)
            return self.convert_rows(cur)

    def get(self, report_id, location_id=DEFAULT_LOCATION):
        location = get_location(location_id)
        self.ensure_schema()
        with self.connection_factory() as conn:
            cur = conn.cursor()
            cur.execute("SELECT NoiDung FROM dbo.BaoCaoMT WHERE MaBaoCao = ? AND MaDiaDiem = ?", report_id, location_id)
            row = cur.fetchone()
            return {"DiaDiem": location, **json.loads(row[0]), "MaBaoCao": report_id} if row else None


def create_report_blueprint(connection_factory, convert_rows, ensure_locations=None):
    blueprint = Blueprint("reports", __name__)
    repository = ReportRepository(connection_factory, convert_rows, ensure_locations)

    @blueprint.errorhandler(ValueError)
    def invalid_location(exc):
        return jsonify({"loi": str(exc)}), 400

    @blueprint.errorhandler(pyodbc.Error)
    def database_error(exc):
        from flask import current_app
        current_app.logger.exception("Không đọc/lưu được báo cáo môi trường")
        return jsonify({"loi": "Không đọc hoặc lưu được báo cáo trong SQL Server. Hãy thử lại."}), 503

    @blueprint.route("/api/baocao", methods=["POST"])
    def create():
        body = request.get_json(silent=True)
        days = body.get("days") if isinstance(body, dict) else None
        if isinstance(days, bool) or not isinstance(days, int) or days not in {1, 7, 30}:
            return jsonify({"loi": "Chọn kỳ báo cáo 1, 7 hoặc 30 ngày."}), 400
        location = get_location(body.get("location"))
        return jsonify(repository.create(days, location["MaDiaDiem"])), 201

    @blueprint.route("/api/baocao", methods=["GET"])
    def history():
        limit = min(max(request.args.get("limit", 10, type=int), 1), 50)
        offset = min(max(request.args.get("offset", 0, type=int), 0), 1000000)
        location = get_location(request.args.get("location"))
        return jsonify(repository.list(limit, offset, location["MaDiaDiem"]))

    @blueprint.route("/api/baocao/<int:report_id>")
    def detail(report_id):
        location = get_location(request.args.get("location"))
        report = repository.get(report_id, location["MaDiaDiem"])
        return jsonify(report) if report else (jsonify({"loi": "Không tìm thấy báo cáo đã lưu."}), 404)

    return blueprint
