"""Reference places from the existing APIs and NoiseCapture Vietnam data."""
import json
from pathlib import Path
import re
from threading import Lock


ROOT = Path(__file__).resolve().parent
DEFAULT_LOCATION = "hanoi"
LOCATIONS = json.loads((ROOT / "locations.json").read_text(encoding="utf-8"))
LOCATION_MAP = {place["MaDiaDiem"]: place for place in LOCATIONS}


def get_location(identifier=None):
    identifier = DEFAULT_LOCATION if identifier is None else identifier
    if not isinstance(identifier, str) or identifier not in LOCATION_MAP:
        raise ValueError("Địa điểm không hợp lệ. Hãy chọn địa điểm trong danh sách.")
    return dict(LOCATION_MAP[identifier])


class LocationStore:
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory
        self.ready = False
        self.lock = Lock()

    def ensure_schema(self):
        if self.ready:
            return
        with self.lock:
            if self.ready:
                return
            sql = (ROOT / "location_schema.sql").read_text(encoding="utf-8")
            with self.connection_factory() as conn:
                cur = conn.cursor()
                for batch in re.split(r"(?im)^GO\s*$", sql):
                    if batch.strip():
                        cur.execute(batch)
                for place in LOCATIONS:
                    values = (place["Ten"], place["Nhom"], place["ViDo"], place["KinhDo"],
                              place.get("ViDoTiengOn", place["ViDo"]),
                              place.get("KinhDoTiengOn", place["KinhDo"]), place["TenKhuVucTiengOn"],
                              json.dumps(place, ensure_ascii=False, allow_nan=False))
                    cur.execute("""IF EXISTS (SELECT 1 FROM dbo.DiaDiem WHERE MaDiaDiem = ?)
                                   UPDATE dbo.DiaDiem SET Ten=?, Nhom=?, ViDo=?, KinhDo=?,
                                       ViDoTiengOn=?, KinhDoTiengOn=?, TenKhuVucTiengOn=?, ChiTiet=? WHERE MaDiaDiem=?
                                   ELSE INSERT INTO dbo.DiaDiem
                                       (MaDiaDiem, Ten, Nhom, ViDo, KinhDo, ViDoTiengOn, KinhDoTiengOn, TenKhuVucTiengOn, ChiTiet)
                                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                place["MaDiaDiem"], *values, place["MaDiaDiem"], place["MaDiaDiem"], *values)
                conn.commit()
            self.ready = True
