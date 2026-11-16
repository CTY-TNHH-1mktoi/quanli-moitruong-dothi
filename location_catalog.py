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


def location_mentions(message):
    """Prefer a district's full name over an overlapping city substring."""
    from chat_knowledge import normalized
    text=normalized(message)
    matches=[]
    for place in LOCATIONS:
        aliases={normalized(place['Ten']),normalized(place['Ten'].split(',')[0])}
        if place['MaDiaDiem']=='tphcm':
            aliases.update({'tp hcm','tphcm','sai gon','ho chi minh'})
        for alias in aliases:
            if not alias:
                continue
            for match in re.finditer(r'\b'+re.escape(alias)+r'\b',text):
                matches.append((match.start(),match.end(),place))
    selected=[]
    for start,end,place in sorted(matches,key=lambda v: (-(v[1]-v[0]),v[0])):
        if not any(start<old_end and end>old_start for old_start,old_end,_ in selected):
            selected.append((start,end,place))
    return text,sorted(selected,key=lambda v:v[0])


def named_location(message):
    _,mentions=location_mentions(message)
    places={place['MaDiaDiem']:place for _,_,place in mentions}
    return dict(next(iter(places.values()))) if len(places)==1 else None


def location_followup(message):
    """A short change of place can inherit a topic; a new request cannot."""
    text,mentions=location_mentions(message)
    if len(mentions)!=1:
        return None
    start,end,place=mentions[0]
    remainder=' '.join((text[:start]+' '+text[end:]).split())
    if re.fullmatch(r'(?:(?:the|vay|con|o|tai|thi|sao|the nao|ra sao|nhe|nhi|ban|a|xem|giup minh|giup toi)\s*)*',remainder):
        return dict(place)
    return None


def without_locations(message):
    text,mentions=location_mentions(message)
    for start,end,_ in reversed(mentions):
        text=text[:start]+' '+text[end:]
    return ' '.join(text.split())


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
