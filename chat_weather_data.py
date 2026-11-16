"""Read-only hourly weather forecasts for the selected place and Vietnam dates."""
from datetime import datetime
import math
from threading import Lock
import time

import requests

import chat_air_data as air


WEATHER_URL = 'https://api.open-meteo.com/v1/forecast'
VARIABLES = {'NhietDo': 'temperature_2m', 'DoAm': 'relative_humidity_2m'}
_cache = {}
_lock = Lock()


class WeatherDataUnavailable(Exception):
    pass


def get_weather_data(location):
    key = (location['MaDiaDiem'], location['ViDo'], location['KinhDo'], air.local_now().date())
    with _lock:
        cached = _cache.get(key)
        if cached and 0 <= time.monotonic() - cached[0] < 600:
            return cached[1]
    try:
        response = requests.get(WEATHER_URL, params={
            'latitude': location['ViDo'], 'longitude': location['KinhDo'],
            'timezone': 'Asia/Ho_Chi_Minh', 'forecast_days': 5,
            'temperature_unit': 'celsius', 'hourly': ','.join(VARIABLES.values()),
        }, timeout=10)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get('error') or payload.get('utc_offset_seconds') != 25200:
            raise ValueError('Wrong forecast shape or timezone')
        hourly, units = payload.get('hourly'), payload.get('hourly_units')
        if not isinstance(hourly, dict) or not isinstance(units, dict) or not isinstance(hourly.get('time'), list):
            raise ValueError('Missing hourly weather')
        for variable, unit in [('temperature_2m', '°C'), ('relative_humidity_2m', '%')]:
            if units.get(variable) != unit or not isinstance(hourly.get(variable), list) or len(hourly[variable]) != len(hourly['time']):
                raise ValueError('Weather arrays or units do not match')
        result = {'MaDiaDiem': location['MaDiaDiem'], 'LayLuc': air.local_now().isoformat(), 'hourly': hourly}
    except (requests.RequestException, ValueError, TypeError, KeyError) as error:
        raise WeatherDataUnavailable('Chưa lấy được dự báo thời tiết từ Open-Meteo.') from error
    with _lock:
        for previous in list(_cache):
            if previous[-1] != key[-1]:
                _cache.pop(previous)
        _cache[key] = (time.monotonic(), result)
    return result


def forecast_weather(data, window, fields):
    if not window:
        return {}
    start, end = window
    expected = int((end - start).total_seconds() // 3600)
    if expected <= 0:
        return {}
    hourly = data.get('hourly', {})
    times = hourly.get('time', [])
    selected = {}
    for index, stamp in enumerate(times):
        try:
            moment = datetime.fromisoformat(stamp)
            moment = moment.replace(tzinfo=air.VN_TIME) if moment.tzinfo is None else moment.astimezone(air.VN_TIME)
        except (ValueError, TypeError):
            continue
        if start <= moment < end:
            if moment in selected or moment.minute or moment.second:
                return {}
            selected[moment] = index
    if len(selected) != expected:
        return {}
    values = {}
    for field in fields:
        series = hourly.get(VARIABLES[field], [])
        values[field] = []
        for index in selected.values():
            value = series[index] if index < len(series) else None
            if (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
                    or (field == 'DoAm' and not 0 <= value <= 100)):
                return {}
            values[field].append(value)
    return values
