"""Read-only, location-scoped CAMS air data for conversations, with a short cache."""

from datetime import datetime, time as day_time, timedelta, timezone
import math
import re
from threading import Lock
import time

import requests

from chat_knowledge import normalized


AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
VN_TIME = timezone(timedelta(hours=7))
CACHE_SECONDS = 600
_cache = {}
_lock = Lock()


class AirDataUnavailable(Exception):
    pass


def local_now():
    return datetime.now(VN_TIME)


def number(value):
    return (value if isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0 else None)


def get_air_data(location):
    key = (location["MaDiaDiem"], location["ViDo"], location["KinhDo"], local_now().date())
    with _lock:
        entry = _cache.get(key)
        if entry and 0 <= time.monotonic() - entry[0] < CACHE_SECONDS:
            return entry[1]
    try:
        response = requests.get(AIR_URL, params={
            "latitude": location["ViDo"], "longitude": location["KinhDo"],
            "timezone": "Asia/Ho_Chi_Minh", "forecast_days": 5,
            "current": "us_aqi,pm2_5,pm10",
            "hourly": "us_aqi,pm2_5,pm10",
        }, timeout=10)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("error") or payload.get("utc_offset_seconds") != 25200:
            raise ValueError("Invalid air data or timezone")
        current = payload.get("current")
        hourly = payload.get("hourly")
        if not isinstance(current, dict) or not isinstance(hourly, dict):
            raise ValueError("Missing air data")
        if not isinstance(hourly.get("time"), list) or not isinstance(hourly.get("us_aqi"), list):
            raise ValueError("Missing hourly array")
        if len(hourly["time"]) != len(hourly["us_aqi"]):
            raise ValueError("Mismatched hourly array")
        result = {"MaDiaDiem": location["MaDiaDiem"], "LayLuc": local_now().isoformat(),
                  "current": current, "hourly": hourly}
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        raise AirDataUnavailable("Chưa lấy được dữ liệu không khí từ Open-Meteo/CAMS.") from exc
    with _lock:
        # Keep only this day's cache rather than retaining yesterday's entries.
        for previous in list(_cache):
            if previous[-1] != key[-1]:
                _cache.pop(previous)
        _cache[key] = (time.monotonic(), result)
    return result


def forecast_window(message, now=None):
    """Resolve a requested relative date/period in Vietnam local time."""
    now = (now or local_now()).astimezone(VN_TIME)
    question = normalized(message)
    date = now.date()
    if re.search(r"\bngay kia\b", question):
        date += timedelta(days=2)
    elif re.search(r"\bmai\b", question):
        date += timedelta(days=1)
    elif re.search(r"\bcuoi tuan\b", question):
        date += timedelta(days=(5 - date.weekday()) % 7)
        if re.search(r"\bcuoi tuan toi\b", question) and date == now.date():
            date += timedelta(days=7)
    elif re.search(r"\b(?:ngay|tuan|thang|nam) (?:sau|toi)\b", question):
        if re.search(r"\bngay (sau|toi)\b", question):
            date += timedelta(days=1)
        else:
            return None  # An unspecified week/month is not one forecast day.
    relative = re.search(r"\b(mot|hai|ba|\d+) (gio|phut|ngay) nua\b", question)
    if relative:
        count = int(relative[1]) if relative[1].isdigit() else {"mot": 1, "hai": 2, "ba": 3}[relative[1]]
        if count > 1000:
            return None
        if relative[2] == "ngay":
            date += timedelta(days=count)
        else:
            target = now + timedelta(**({"hours": count} if relative[2] == "gio" else {"minutes": count}))
            start = target.replace(minute=0, second=0, microsecond=0)
            return start, start + timedelta(hours=1)
    start = datetime.combine(date, day_time.min, VN_TIME)
    end = start + timedelta(days=1)
    from chat_time_context import explicit_clock,invalid_clock
    if invalid_clock(message):
        return None
    clock=explicit_clock(message)
    if clock is not None:
        # The provider supplies hourly values, not minute-resolution forecasts.
        start=start.replace(hour=clock[0])
        end=start+timedelta(hours=1)
        return (start,end) if end>now else None
    periods = {"sang": (5, 12), "trua": (11, 14), "chieu": (12, 18), "toi": (18, 24), "dem": (20, 24)}
    part = re.search(r"\b(sang|trua|chieu|toi|dem) (?:ngay )?(mai|nay)\b", question)
    if part:
        first, last = periods[part[1]]
        start += timedelta(hours=first)
        end = datetime.combine(date, day_time.min, VN_TIME) + timedelta(hours=last)
    if date == now.date():
        start = max(start, now.replace(minute=0, second=0, microsecond=0))
    return start, end


def forecast_aqi(data, window):
    if window is None:
        return []
    start, end = window
    points = []
    for stamp, value in zip(data["hourly"]["time"], data["hourly"]["us_aqi"]):
        try:
            moment = datetime.fromisoformat(stamp)
            moment = moment.replace(tzinfo=VN_TIME) if moment.tzinfo is None else moment.astimezone(VN_TIME)
        except (TypeError, ValueError):
            continue
        value = number(value)
        if value is not None and start <= moment < end:
            points.append((moment, value))
    # Don't summarize a partial day as if a whole-day forecast were available.
    expected = int((end - start).total_seconds() // 3600)
    if expected <= 0 or len({stamp for stamp, _ in points}) != expected:
        return []
    return sorted(points)
