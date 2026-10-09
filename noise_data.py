"""Share one cached country dump, then calculate noise for each reference place."""
import json
import logging
import math
from pathlib import Path
from threading import Lock
import time
import zipfile

import requests


URL = "https://data.noise-planet.org/dump/Vietnam.zip"


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(h, 1)))


def geometry_center(geometry):
    coordinates = geometry.get("coordinates") or []
    if geometry.get("type") == "Point":
        return coordinates[1], coordinates[0]
    ring = coordinates[0][0] if geometry.get("type") == "MultiPolygon" else coordinates[0]
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return sum(point[1] for point in ring) / len(ring), sum(point[0] for point in ring) / len(ring)


def read_cells(archive):
    cells = []
    for name in archive.namelist():
        if not name.lower().endswith(".areas.geojson"):
            continue
        for feature in json.loads(archive.read(name)).get("features", []):
            properties = feature.get("properties") or {}
            value = properties.get("laeq", properties.get("LAeq"))
            if value is None or not feature.get("geometry"):
                continue
            try:
                lat, lon = geometry_center(feature["geometry"])
                value = float(value)
                weight = float(properties.get("measure_count", 1))
                if not all(math.isfinite(item) for item in (lat, lon, value, weight)) or weight <= 0 or abs(value) > 200:
                    continue
            except (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError):
                continue
            cells.append({"lat": lat, "lon": lon, "value": value, "weight": weight, "file": name,
                          "first": properties.get("first_measure_ISO_8601"),
                          "last": properties.get("last_measure_ISO_8601")})
    return cells


def aggregate_noise(cells, location, radius):
    lat = location.get("ViDoTiengOn", location["ViDo"])
    lon = location.get("KinhDoTiengOn", location["KinhDo"])
    selected = [cell for cell in cells
                if (not location.get("TepTiengOn") or cell["file"] == location["TepTiengOn"])
                and haversine_km(lat, lon, cell["lat"], cell["lon"]) <= radius]
    if not selected:
        return None
    weight = sum(cell["weight"] for cell in selected)
    energy = sum(cell["weight"] * 10 ** (cell["value"] / 10) for cell in selected)
    first = [cell["first"] for cell in selected if cell["first"]]
    last = [cell["last"] for cell in selected if cell["last"]]
    return {"TiengOn": round(10 * math.log10(energy / weight), 2),
            "SoO": len(selected), "SoLanDo": int(weight), "BanKinhKm": radius,
            "DoDauTien": min(first) if first else None, "DoGanNhat": max(last) if last else None,
            "KhuVuc": location["TenKhuVucTiengOn"],
            "Nguon": f"NoiseCapture tổng hợp quanh {location['TenKhuVucTiengOn']}; không phải đo trực tiếp theo thời gian thực"}


class NoiseData:
    def __init__(self):
        self.path = Path(__file__).resolve().parent / ".runtime" / "noise-vietnam.zip"
        self.lock = Lock()
        self.cells = None
        self.loaded_mtime = None
        self.last_attempt = 0

    def get(self, location, radius):
        with self.lock:
            now = time.time()
            mtime = self.path.stat().st_mtime if self.path.is_file() else 0
            if now - mtime >= 86400 and now - self.last_attempt >= 600:
                self.last_attempt = now
                try:
                    response = requests.get(URL, timeout=120)
                    response.raise_for_status()
                    import io
                    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                        read_cells(archive)  # Validate before replacing the last usable file.
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    temp = self.path.with_suffix(".tmp")
                    temp.write_bytes(response.content)
                    temp.replace(self.path)
                    mtime = self.path.stat().st_mtime
                except (requests.RequestException, zipfile.BadZipFile, ValueError, OSError):
                    logging.getLogger(__name__).exception("Không cập nhật được NoiseCapture; giữ dữ liệu hiện có")
            if not self.path.is_file():
                return None
            if self.cells is None or mtime != self.loaded_mtime:
                try:
                    with zipfile.ZipFile(self.path) as archive:
                        self.cells = read_cells(archive)
                    self.loaded_mtime = mtime
                except (zipfile.BadZipFile, ValueError, OSError):
                    logging.getLogger(__name__).exception("Không đọc được NoiseCapture")
                    return None
            cells = self.cells
        return aggregate_noise(cells, location, radius)
