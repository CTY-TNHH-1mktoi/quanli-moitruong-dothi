"""
app.py - Backend giám sát môi trường theo địa điểm tại Việt Nam

Nhiệm vụ:
1. Nhận yêu cầu từ HTML/JS
2. Gọi API môi trường (Open-Meteo)
3. Làm việc với SQL Server (database GiamsatMT)
4. Trả dữ liệu JSON về cho HTML/JS

Cài thư viện:
    pip install -r requirements.txt

Chạy:
    python app.py   ->  mở http://localhost:5000
"""
import io
import json
import os
import time
import zipfile
from datetime import datetime
from decimal import Decimal
from threading import Lock

import pyodbc
import requests
from flask import Flask, Response, jsonify, request
from flask_cors import CORS

from environment_predictor import predict_environment
from environment_reports import create_report_blueprint
from air_quality_map import create_air_map_blueprint
from location_catalog import DEFAULT_LOCATION, LOCATIONS, LocationStore, get_location
from noise_data import NoiseData, aggregate_noise, read_cells
from chatbot import ChatbotBusy, generate_reply, runtime_status, stream_reply, validate_chat, warm_up_chatbot

# ---------------------------------------------------------------------------
# CẤU HÌNH (có thể đặt bằng biến môi trường, không cần sửa code)
# ---------------------------------------------------------------------------
# SQL Server chạy trên chính laptop. Xem tên server trong SSMS khi đăng nhập:
#   "localhost"  hoặc  ".\SQLEXPRESS"  hoặc  "TENMAY\SQLEXPRESS"
DB_SERVER = os.getenv("DB_SERVER", r"LAPTOP-2HSL339M")
DB_NAME = os.getenv("DB_NAME", "GiamsatMT")
DB_USER = os.getenv("DB_USER", "")          # để trống = dùng Windows Authentication
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
API_REFRESH_SECONDS = 600

last_api_time = 0
last_result = None
environment_cache = {}
environment_locks = {}
cache_lock = Lock()
noise_data = NoiseData()

# Tiếng ồn: chỉ tổng hợp ô NoiseCapture gần địa điểm đang chọn.
NOISE_RADIUS_KM = float(os.getenv("NOISE_RADIUS_KM", "2"))  # bán kính lấy dữ liệu quanh tâm

# Phục vụ index.html / script.js / style.css trong thư mục static/
# (không để static_folder="." vì sẽ lộ cả app.py ra trình duyệt)
app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)


# ---------------------------------------------------------------------------
# SQL SERVER
# ---------------------------------------------------------------------------
def get_conn():
    parts = [
        f"DRIVER={{{DB_DRIVER}}}",
        f"SERVER={DB_SERVER}",
        f"DATABASE={DB_NAME}",
        "TrustServerCertificate=yes",
    ]
    if DB_USER:
        parts += [f"UID={DB_USER}", f"PWD={DB_PASSWORD}"]
    else:
        parts.append("Trusted_Connection=yes")
    return pyodbc.connect(";".join(parts))


def rows_to_dicts(cursor):
    cols = [c[0] for c in cursor.description]
    out = []
    for row in cursor.fetchall():
        item = {}
        for col, val in zip(cols, row):
            if isinstance(val, Decimal):
                val = float(val)
            elif isinstance(val, datetime):
                val = val.isoformat()
            item[col] = val
        out.append(item)
    return out


def query(sql, params=()):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return rows_to_dicts(cur)


location_store = LocationStore(lambda: get_conn())
app.register_blueprint(create_report_blueprint(lambda: get_conn(), rows_to_dicts, location_store.ensure_schema))
app.register_blueprint(create_air_map_blueprint(lambda: get_conn()))


@app.errorhandler(ValueError)
def invalid_request(exc):
    return jsonify({"loi": str(exc)}), 400


@app.errorhandler(pyodbc.Error)
def database_error(exc):
    app.logger.exception("Không đọc hoặc lưu được dữ liệu địa điểm")
    return jsonify({"loi": "Không đọc hoặc lưu được dữ liệu trong SQL Server. Hãy thử lại."}), 503


@app.route("/api/diadiem")
def locations():
    location_store.ensure_schema()
    return jsonify({"MacDinh": DEFAULT_LOCATION, "DiaDiem": LOCATIONS})


# ---------------------------------------------------------------------------
# TIẾNG ỒN (Noise-Planet / NoiseCapture)
# ---------------------------------------------------------------------------
def compute_noise(zip_bytes, location=None):
    """Tổng hợp LAeq theo năng lượng, chỉ dùng ô thuộc địa điểm được chọn."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        return aggregate_noise(read_cells(archive), location or get_location(), NOISE_RADIUS_KM)


def get_noise(location=None):
    """Dùng chung bộ dữ liệu đã tải, lọc riêng cho từng địa điểm."""
    return noise_data.get(location or get_location(), NOISE_RADIUS_KM)


# ---------------------------------------------------------------------------
# GỌI API MÔI TRƯỜNG
# ---------------------------------------------------------------------------
def fetch_environment(location=None):
    location = location or get_location()
    weather = requests.get(
        WEATHER_URL,
        params={
            "latitude": location["ViDo"],
            "longitude": location["KinhDo"],
            "timezone": "Asia/Ho_Chi_Minh",
            "current": "temperature_2m,relative_humidity_2m",
        },
        timeout=15,
    )
    weather.raise_for_status()
    air = requests.get(
        AIR_URL,
        params={
            "latitude": location["ViDo"],
            "longitude": location["KinhDo"],
            "timezone": "Asia/Ho_Chi_Minh",
            "current": "pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,"
                       "sulphur_dioxide,ozone,us_aqi",
        },
        timeout=15,
    )
    air.raise_for_status()
    w, a = weather.json()["current"], air.json()["current"]
    noise = get_noise(location)
    return {
        "NhietDo": w.get("temperature_2m"),
        "DoAm": w.get("relative_humidity_2m"),
        "PM25": a.get("pm2_5"),
        "PM10": a.get("pm10"),
        "CO": a.get("carbon_monoxide"),
        "NO2": a.get("nitrogen_dioxide"),
        "SO2": a.get("sulphur_dioxide"),
        "O3": a.get("ozone"),
        "US_AQI": a.get("us_aqi"),
        "TiengOn": noise["TiengOn"] if noise else None,  # Open-Meteo không có tiếng ồn -> lấy từ Noise-Planet
        "TiengOn_ChiTiet": noise,  # metadata được lưu trong NguonDL.ChiTiet
        "ThoiGianNguonThoiTiet": w.get("time"),
        "ThoiGianNguonKhongKhi": a.get("time"),
    }


# ---------------------------------------------------------------------------
# LOGIC CẢNH BÁO & PHÂN TÍCH (theo ngưỡng)
# ---------------------------------------------------------------------------
def build_alerts(d):
    """Trả về danh sách (LoaiCanhBao, MucDo, NoiDung)."""
    alerts = []

    def check(value, name, unit, mid, high):
        if value is None:
            return
        if value >= high:
            alerts.append((name, "Cao", f"{name} = {value} {unit}, vượt ngưỡng nguy hiểm ({high})"))
        elif value >= mid:
            alerts.append((name, "Trung bình", f"{name} = {value} {unit}, vượt ngưỡng lưu ý ({mid})"))

    check(d["PM25"], "PM2.5", "µg/m³", 35.5, 55.5)
    check(d["PM10"], "PM10", "µg/m³", 100, 154)
    check(d["NhietDo"], "Nhiệt độ", "°C", 35, 38)
    check(d["DoAm"], "Độ ẩm", "%", 85, 95)
    if d["TiengOn"] is not None:
        check(d["TiengOn"], "Tiếng ồn", "dB", 70, 85)
    return alerts


def build_analysis(d):
    """Trả về (KetQua, NhanXet, KhuyenNghi) dựa trên US AQI (hoặc PM2.5)."""
    aqi = d.get("US_AQI")
    if aqi is None:
        pm = d.get("PM25") or 0
        aqi = 25 if pm < 12 else 75 if pm < 35.5 else 125 if pm < 55.5 else 175 if pm < 150 else 250

    if aqi <= 50:
        return ("Tốt", f"Chất lượng không khí tốt (AQI {aqi}).",
                "Có thể hoạt động ngoài trời bình thường.")
    if aqi <= 100:
        return ("Trung bình", f"Chất lượng không khí ở mức chấp nhận được (AQI {aqi}).",
                "Người nhạy cảm nên hạn chế ở ngoài trời quá lâu.")
    if aqi <= 150:
        return ("Kém", f"Không khí kém, ảnh hưởng nhóm nhạy cảm (AQI {aqi}).",
                "Người già, trẻ em, người bệnh hô hấp nên hạn chế ra ngoài và đeo khẩu trang.")
    if aqi <= 200:
        return ("Xấu", f"Không khí xấu, có hại cho sức khỏe (AQI {aqi}).",
                "Đeo khẩu trang lọc bụi mịn, hạn chế hoạt động ngoài trời, đóng cửa sổ.")
    if aqi <= 300:
        return ("Rất xấu", f"Không khí rất xấu (AQI {aqi}).",
                "Hạn chế tối đa ra ngoài, dùng máy lọc không khí trong nhà.")
    return ("Nguy hại", f"Không khí ở mức nguy hại (AQI {aqi}).",
            "Ở trong nhà, tránh mọi hoạt động ngoài trời.")


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/capnhat", methods=["GET", "POST"])
def capnhat():
    """Gọi API môi trường -> lưu DB -> trả kết quả."""
    location = get_location(request.args.get("location"))
    location_store.ensure_schema()
    identifier = location["MaDiaDiem"]
    with cache_lock:
        lock = environment_locks.setdefault(identifier, Lock())
    with lock:
        cached = environment_cache.get(identifier)
        if cached and time.time() - cached["time"] < API_REFRESH_SECONDS:
            return jsonify(cached["result"])
        # Reuse a complete saved snapshot after a restart, only for this place.
        rows = query("""SELECT TOP 1 ChiTiet, ThoiGian FROM NguonDL
                        WHERE MaDiaDiem = ? AND ChiTiet IS NOT NULL
                        ORDER BY ThoiGian DESC, Manguon DESC""", (identifier,))
        if rows:
            timestamp = datetime.fromisoformat(rows[0]["ThoiGian"]).timestamp()
            if 0 <= time.time() - timestamp < API_REFRESH_SECONDS:
                saved = json.loads(rows[0]["ChiTiet"])
                if saved.get("DiaDiem", {}).get("MaDiaDiem") == identifier:
                    environment_cache[identifier] = {"time": timestamp, "result": saved}
                    return jsonify(saved)
        return update_environment(location)


def update_environment(location):
    global last_api_time, last_result

    # Đủ 10 phút -> mới gọi API
    try:
        d = fetch_environment(location)
    except requests.RequestException as e:
        return jsonify({"loi": f"Không gọi được API môi trường: {e}"}), 502

    # Model labels are based on demo thresholds, separate from the US AQI analysis.
    # A missing/noisy model must not prevent the live readings from being saved.
    try:
        prediction = predict_environment(d)
    except Exception:
        app.logger.exception("Không chạy được mô hình Random Forest")
        prediction = {"TrangThai": "loi_mo_hinh"}

    now = datetime.now()
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO NguonDL (TenNguon, ThoiGian, PM25, PM10, NhietDo, DoAm, TiengOn, MaDiaDiem)
                   OUTPUT INSERTED.Manguon
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                f"Open-Meteo {location['Ten']}"[:100], now, d["PM25"], d["PM10"], d["NhietDo"], d["DoAm"], d["TiengOn"], location["MaDiaDiem"],
            )
            manguon = cur.fetchone()[0]

            alerts = build_alerts(d)
            for loai, mucdo, noidung in alerts:
                cur.execute(
                    """INSERT INTO CanhBao (Manguon, LoaiCanhBao, MucDo, NoiDung, ThoiGian)
                       VALUES (?, ?, ?, ?, ?)""",
                    manguon, loai, mucdo, noidung, now,
                )

            ketqua, nhanxet, khuyennghi = build_analysis(d)
            cur.execute(
                """INSERT INTO PhanTichAI (Manguon, KetQua, NhanXet, KhuyenNghi, ThoiGian)
                   VALUES (?, ?, ?, ?, ?)""",
                manguon, ketqua, nhanxet, khuyennghi, now,
            )
            result = {
                "Manguon": manguon, "ThoiGian": now.isoformat(), "DiaDiem": location,
                "DuLieu": d, "DuDoanRF": prediction,
                "CanhBao": [{"LoaiCanhBao": a, "MucDo": b, "NoiDung": c} for a, b, c in alerts],
                "PhanTich": {"KetQua": ketqua, "NhanXet": nhanxet, "KhuyenNghi": khuyennghi},
            }
            cur.execute("UPDATE NguonDL SET ChiTiet = ? WHERE Manguon = ?",
                        json.dumps(result, ensure_ascii=False, allow_nan=False), manguon)
            conn.commit()
    except pyodbc.Error as exc:
        return database_error(exc)

    timestamp = now.timestamp()
    environment_cache[location["MaDiaDiem"]] = {"time": timestamp, "result": result}
    if location["MaDiaDiem"] == DEFAULT_LOCATION:
        last_api_time, last_result = timestamp, result

    return jsonify(result)


@app.route("/api/dulieu/moinhat")
def dulieu_moinhat():
    location_store.ensure_schema()
    location = get_location(request.args.get("location"))
    rows = query("SELECT TOP 1 * FROM NguonDL WHERE MaDiaDiem = ? ORDER BY ThoiGian DESC, Manguon DESC", (location["MaDiaDiem"],))
    return jsonify(rows[0] if rows else {})


@app.route("/api/dulieu/lichsu")
def dulieu_lichsu():
    """Dữ liệu cho biểu đồ, thứ tự cũ -> mới. Ví dụ: /api/dulieu/lichsu?limit=12"""
    limit = min(max(request.args.get("limit", 12, type=int), 1), 500)
    location_store.ensure_schema()
    location = get_location(request.args.get("location"))
    rows = query("SELECT TOP (?) * FROM NguonDL WHERE MaDiaDiem = ? ORDER BY ThoiGian DESC, Manguon DESC", (limit, location["MaDiaDiem"]))
    return jsonify(list(reversed(rows)))


@app.route("/api/canhbao")
def canhbao():
    limit = min(max(request.args.get("limit", 20, type=int), 1), 200)
    location_store.ensure_schema()
    location = get_location(request.args.get("location"))
    return jsonify(query("""SELECT TOP (?) c.* FROM CanhBao c JOIN NguonDL n ON n.Manguon=c.Manguon
                            WHERE n.MaDiaDiem=? ORDER BY c.ThoiGian DESC, c.Macanhbao DESC""", (limit, location["MaDiaDiem"])))


@app.route("/api/phantich")
def phantich():
    limit = min(max(request.args.get("limit", 1, type=int), 1), 50)
    location_store.ensure_schema()
    location = get_location(request.args.get("location"))
    return jsonify(query("""SELECT TOP (?) p.* FROM PhanTichAI p JOIN NguonDL n ON n.Manguon=p.Manguon
                            WHERE n.MaDiaDiem=? ORDER BY p.ThoiGian DESC, p.Maphantich DESC""", (limit, location["MaDiaDiem"])))


@app.route("/api/chat", methods=["POST"])
def chat():
    if request.content_length is not None and request.content_length > 2 * 1024 * 1024:
        return jsonify({"loi": "Nội dung hội thoại quá dài."}), 413
    try:
        body = request.get_json(silent=True)
        message, history = validate_chat(body)
        location = get_location(body.get("location"))
        cached = environment_cache.get(location["MaDiaDiem"], {})
        snapshot = cached.get("result") or (last_result if location["MaDiaDiem"] == DEFAULT_LOCATION else None)
        snapshot = snapshot or {"DiaDiem": location, "DuLieu": {}}
        if body.get("stream") is True:
            return Response(
                stream_reply(message, history, snapshot), mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        return jsonify(generate_reply(message, history, snapshot))
    except ValueError as exc:
        return jsonify({"loi": str(exc)}), 400
    except ChatbotBusy as exc:
        return jsonify({"loi": str(exc)}), 429
    except (FileNotFoundError, ImportError):
        app.logger.exception("Chưa đủ tệp hoặc thư viện cho chatbot Xanh Non")
        return jsonify({"loi": "Chưa tải được Xanh Non. Hãy kiểm tra thư mục mô hình và cài requirements.txt."}), 503
    except Exception:
        app.logger.exception("Không tạo được câu trả lời từ Xanh Non")
        return jsonify({"loi": "Xanh Non chưa tạo được câu trả lời. Hãy thử lại."}), 500


@app.route("/api/chat/status")
def chat_status():
    return jsonify(runtime_status())


if __name__ == "__main__":
    # A reloader would unload the resident chatbot whenever source files change.
    if os.getenv("CHATBOT_PRELOAD", "1") == "1":
        warm_up_chatbot()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
