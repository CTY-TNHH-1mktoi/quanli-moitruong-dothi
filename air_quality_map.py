"""Regional model samples for a georeferenced AQI overlay, cached in SQL."""
from datetime import datetime, timedelta, timezone
import json
import math
import logging
from pathlib import Path
from threading import Lock

import requests
from flask import Blueprint, jsonify, request, current_app
import pyodbc

from location_catalog import get_location

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
VN_TIME = timezone(timedelta(hours=7))
MAX_POINTS = 196
# Vietnam and nearby model cells, including the northern land border and coast.
COVERAGE = (6.0, 99.2, 25.6, 114.4)  # south, west, north, east


class AirMapUnavailable(Exception):
    pass


def finite_value(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def make_grid(bounds):
    if len(bounds) != 4 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in bounds):
        raise ValueError("Phạm vi bản đồ không hợp lệ.")
    south, west, north, east = bounds
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("Phạm vi bản đồ không hợp lệ.")
    south, west = max(south, COVERAGE[0]), max(west, COVERAGE[1])
    north, east = min(north, COVERAGE[2]), min(east, COVERAGE[3])
    if south >= north or west >= east:
        return [], [], .4
    step = .4
    while True:
        first_lat, last_lat = math.floor(south / step), math.ceil(north / step)
        first_lon, last_lon = math.floor(west / step), math.ceil(east / step)
        if (last_lat - first_lat + 1) * (last_lon - first_lon + 1) <= MAX_POINTS:
            break
        step *= 2
    return ([round(i * step, 6) for i in range(first_lat, last_lat + 1)],
            [round(i * step, 6) for i in range(first_lon, last_lon + 1)], step)


def point_key(lat, lon):
    return f"{lat:.6f}:{lon:.6f}"


def normalize_samples(points, payload, captured):
    items = payload if isinstance(payload, list) else [payload]
    if len(items) != len(points):
        raise AirMapUnavailable("Nguồn bản đồ trả thiếu điểm dữ liệu.")
    samples = []
    for index, ((lat, lon), item) in enumerate(zip(points, items)):
        if not isinstance(item, dict) or item.get("location_id", index) != index:
            raise AirMapUnavailable("Nguồn bản đồ trả vị trí dữ liệu không hợp lệ.")
        readings = item.get("current") or {}
        if not isinstance(readings, dict):
            raise AirMapUnavailable("Nguồn bản đồ trả chỉ số không hợp lệ.")
        timestamp = readings.get("time")
        try:
            source_time = datetime.fromisoformat(timestamp).isoformat() if timestamp else None
        except (ValueError, TypeError):
            source_time = None
        samples.append({"MaViTri": point_key(lat, lon), "ViDo": lat, "KinhDo": lon,
                        "ThoiGianLay": captured.isoformat(), "ThoiGianNguon": source_time,
                        "US_AQI": finite_value(readings.get("us_aqi")),
                        "PM25": finite_value(readings.get("pm2_5")),
                        "Nguon": "Open-Meteo / CAMS Global", "ChiTietNguon": item})
    return samples


class AirMapRepository:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory
        self.ready = False
        self.lock = Lock()
        self.cache = {}

    def _ensure_schema(self):
        if self.ready:
            return
        with self.connection_factory() as conn:
            conn.cursor().execute(Path(__file__).with_name("air_map_schema.sql").read_text(encoding="utf-8"))
            conn.commit()
        self.ready = True

    def get_samples(self, points):
        if not points:
            return {}, None
        now = datetime.now(VN_TIME).replace(tzinfo=None)
        hour = now.replace(minute=0, second=0, microsecond=0)
        keys = [point_key(*point) for point in points]
        with self.lock:
            self._ensure_schema()
            # Reuse this hour's samples across places, pans and server restarts.
            self.cache = {key: value for key, value in self.cache.items()
                          if datetime.fromisoformat(value["ThoiGianLay"]) >= hour}
            unknown = [key for key in keys if key not in self.cache]
            if unknown:
                with self.connection_factory() as conn:
                    cur = conn.cursor()
                    placeholders = ",".join("?" for _ in unknown)
                    cur.execute(f"""WITH latest AS (
                        SELECT MaViTri, ChiTiet, ROW_NUMBER() OVER
                            (PARTITION BY MaViTri ORDER BY ThoiGianLay DESC, MaMau DESC) AS rn
                        FROM dbo.MauBanDoKhongKhi WHERE ThoiGianLay >= ? AND MaViTri IN ({placeholders})
                    ) SELECT MaViTri, ChiTiet FROM latest WHERE rn = 1""", hour, *unknown)
                    for key, content in cur.fetchall():
                        self.cache[key] = json.loads(content)
            missing = [point for point in points if point_key(*point) not in self.cache]
            warning = None
            if missing:
                try:
                    response = requests.get(AIR_URL, params={
                        "latitude": ",".join(str(point[0]) for point in missing),
                        "longitude": ",".join(str(point[1]) for point in missing),
                        "current": "us_aqi,pm2_5", "timezone": "Asia/Ho_Chi_Minh",
                        "domains": "cams_global", "cell_selection": "nearest",
                    }, timeout=(5, 25))
                    response.raise_for_status()
                    samples = normalize_samples(missing, response.json(), now)
                except (requests.RequestException, ValueError, AirMapUnavailable):
                    logging.getLogger(__name__).exception("Không tải đủ dữ liệu màu AQI")
                    samples = []
                    warning = "Chưa tải đủ dữ liệu chất lượng không khí; các vùng thiếu được để trống."
                    if not any(self.cache.get(key, {}).get("US_AQI") is not None for key in keys):
                        raise AirMapUnavailable("Chưa kết nối được nguồn dữ liệu chất lượng không khí. Hãy thử lại.")
                if samples:
                    with self.connection_factory() as conn:
                        cur = conn.cursor()
                        for sample in samples:
                            cur.execute("""INSERT INTO dbo.MauBanDoKhongKhi
                                (MaViTri, ViDo, KinhDo, ThoiGianLay, ThoiGianNguon, US_AQI, PM25, ChiTiet)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                sample["MaViTri"], sample["ViDo"], sample["KinhDo"], now,
                                sample["ThoiGianNguon"], sample["US_AQI"], sample["PM25"],
                                json.dumps(sample, ensure_ascii=False, allow_nan=False))
                        conn.commit()
                    self.cache.update({sample["MaViTri"]: sample for sample in samples})
            return {key: self.cache.get(key) for key in keys}, warning

    def grid(self, bounds, location):
        lats, lons, step = make_grid(bounds)
        samples, warning = self.get_samples([(lat, lon) for lat in lats for lon in lons])
        matrix = lambda field: [[(samples.get(point_key(lat, lon)) or {}).get(field) for lon in lons] for lat in lats]
        values = [sample for sample in samples.values() if sample and sample["US_AQI"] is not None]
        times = [sample["ThoiGianNguon"] for sample in values if sample["ThoiGianNguon"]]
        return {"DiaDiem": location, "ViDo": lats, "KinhDo": lons, "AQI": matrix("US_AQI"),
                "PM25": matrix("PM25"), "BuocLuoiDo": step, "SoDiem": len(values),
                "ThoiGianNguonDau": min(times) if times else None,
                "ThoiGianNguonCuoi": max(times) if times else None,
                "Nguon": "Open-Meteo / CAMS Global", "DoPhanGiaiMoHinhKm": 45,
                "CanhBao": warning,
                "PhamVi": [lats[0], lons[0], lats[-1], lons[-1]] if lats and lons else None}


def create_air_map_blueprint(connection_factory):
    blueprint = Blueprint("air_map", __name__)
    repository = AirMapRepository(connection_factory)

    @blueprint.route("/api/bando/khongkhi")
    def air_grid():
        location = get_location(request.args.get("location"))
        names = ("south", "west", "north", "east")
        if any(name in request.args for name in names):
            try:
                bounds = tuple(float(request.args[name]) for name in names)
            except (KeyError, TypeError, ValueError):
                raise ValueError("Phạm vi bản đồ không hợp lệ.")
        else:
            bounds = (location["ViDo"] - 1.6, location["KinhDo"] - 2.4,
                      location["ViDo"] + 1.6, location["KinhDo"] + 2.4)
        return jsonify(repository.grid(bounds, location))

    @blueprint.errorhandler(AirMapUnavailable)
    def source_error(exc):
        return jsonify({"loi": str(exc)}), 502

    @blueprint.errorhandler(ValueError)
    def invalid_request(exc):
        return jsonify({"loi": str(exc)}), 400

    @blueprint.errorhandler(pyodbc.Error)
    def storage_error(exc):
        current_app.logger.exception("Không đọc/lưu được dữ liệu bản đồ")
        return jsonify({"loi": "Chưa đọc hoặc lưu được dữ liệu bản đồ trong SQL Server."}), 503

    return blueprint
