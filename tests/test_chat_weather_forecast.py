from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import Mock, patch

import app as backend
import chat_air_data as air
import chat_weather_data as weather
import chatbot
from location_catalog import get_location


class WeatherForecastTests(unittest.TestCase):
    now = datetime(2026, 10, 21, 23, 50, tzinfo=air.VN_TIME)

    @staticmethod
    def data():
        start = datetime(2026, 10, 21)
        return {'utc_offset_seconds': 25200,
                'hourly_units': {'temperature_2m': '°C', 'relative_humidity_2m': '%'},
                'hourly': {'time': [(start + timedelta(hours=i)).isoformat() for i in range(72)],
                           'temperature_2m': [99]*24 + [20]*12 + [25]*12 + [15]*24,
                           'relative_humidity_2m': [99]*24 + [60]*12 + [80]*12 + [65]*24}}

    def test_user_question_uses_tomorrow_forecast_without_model_or_current_readings(self):
        with patch.object(air, 'local_now', return_value=self.now), \
                patch.object(chatbot, 'get_weather_data', return_value=self.data()), \
                patch.object(chatbot, '_load_runtime', side_effect=AssertionError('Forecast does not need model inference')):
            reply = chatbot.generate_reply('mai thời tiết thế nào', [], {'DiaDiem': get_location('hanoi'),
                'DuLieu': {'NhietDo': 99, 'DoAm': 99, 'US_AQI': 167}})['reply']
        for text in ['Hà Nội', '22/10', '20–25 °C', '60–80%', 'dự báo']:
            self.assertIn(text, reply)
        for text in ['99', '167', 'AQI', 'tiếng ồn', 'không có khả năng']:
            self.assertNotIn(text, reply)
        self.assertLess(len(reply.split()), 50)

    def test_weather_forecast_honors_single_fields_morning_and_negative_temperature(self):
        data = self.data()
        data['hourly']['temperature_2m'][24:48] = [-4]*24
        with patch.object(air, 'local_now', return_value=self.now), patch.object(chatbot, 'get_weather_data', return_value=data):
            temperature = chatbot.generate_reply('Sáng mai nhiệt độ bao nhiêu?', [], {})['reply']
            self.assertIn('-4 °C', temperature)
            self.assertIn('05:00–12:00', temperature)
            self.assertNotIn('độ ẩm', temperature)
            humidity = chatbot.generate_reply('Mai độ ẩm bao nhiêu?', [], {})['reply']
            self.assertIn('60–80%', humidity)
            self.assertNotIn('°C', humidity)

    def test_short_future_followup_keeps_weather_city_across_thanks(self):
        history = [{'role': 'user', 'content': 'Thời tiết Đà Nẵng hiện tại thế nào?'},
                   {'role': 'assistant', 'content': 'Đang xem.'},
                   {'role': 'user', 'content': 'Cảm ơn nhé'}, {'role': 'assistant', 'content': 'Không có gì'}]
        with patch.object(air, 'local_now', return_value=self.now), patch.object(chatbot, 'get_weather_data', return_value=self.data()) as fetch:
            reply = chatbot.generate_reply('Còn mai?', history, {'DiaDiem': get_location('hanoi')})['reply']
        self.assertIn('Đà Nẵng', reply)
        self.assertEqual(fetch.call_args.args[0]['MaDiaDiem'], 'danang')
        self.assertIsNone(chatbot._weather_forecast_topic('Còn mai?', [{'role': 'user', 'content': 'Viết code Python'}]))
        self.assertIsNone(chatbot._weather_forecast_topic('Mai không khí thế nào'))

    def test_provider_cache_is_scoped_by_place_and_local_day_and_requires_correct_units(self):
        response = Mock()
        response.json.return_value = self.data()
        with patch.object(weather, '_cache', {}), patch.object(air, 'local_now', return_value=self.now) as now, \
                patch.object(weather.requests, 'get', return_value=response) as fetch:
            weather.get_weather_data(get_location('hanoi'))
            weather.get_weather_data(get_location('hanoi'))
            self.assertEqual(fetch.call_count, 1)
            weather.get_weather_data(get_location('danang'))
            self.assertEqual(fetch.call_count, 2)
            now.return_value += timedelta(days=1)
            weather.get_weather_data(get_location('hanoi'))
            self.assertEqual(fetch.call_count, 3)
            params = fetch.call_args.kwargs['params']
            self.assertEqual(params['timezone'], 'Asia/Ho_Chi_Minh')
            self.assertEqual(params['temperature_unit'], 'celsius')
            self.assertEqual(params['forecast_days'], 5)
        for offset, unit in [(0, '°C'), (25200, '°F')]:
            bad = self.data()
            bad['utc_offset_seconds'] = offset
            bad['hourly_units']['temperature_2m'] = unit
            response.json.return_value = bad
            with patch.object(weather, '_cache', {}), patch.object(weather.requests, 'get', return_value=response):
                with self.assertRaises(weather.WeatherDataUnavailable):
                    weather.get_weather_data(get_location('hanoi'))

    def test_incomplete_invalid_or_duplicate_hours_do_not_become_full_day_forecasts(self):
        window = air.forecast_window('Mai thời tiết thế nào?', self.now)
        self.assertTrue(weather.forecast_weather(self.data(), window, ['NhietDo', 'DoAm']))
        for invalid in [None, True, float('nan'), float('inf'), '25']:
            data = self.data()
            data['hourly']['temperature_2m'][24] = invalid
            self.assertEqual(weather.forecast_weather(data, window, ['NhietDo']), {})
        for invalid in [-1, 101]:
            data = self.data()
            data['hourly']['relative_humidity_2m'][24] = invalid
            self.assertEqual(weather.forecast_weather(data, window, ['DoAm']), {})
        data = self.data()
        data['hourly']['time'][24] = data['hourly']['time'][25]
        self.assertEqual(weather.forecast_weather(data, window, ['NhietDo']), {})
        data['hourly']['time'] = data['hourly']['time'][:30]
        self.assertEqual(weather.forecast_weather(data, window, ['NhietDo']), {})

    def test_failed_forecast_does_not_invent_tomorrow_from_current_weather(self):
        with patch.object(air, 'local_now', return_value=self.now), \
                patch.object(chatbot, 'get_weather_data', side_effect=weather.WeatherDataUnavailable()), \
                patch.object(chatbot, '_load_runtime', side_effect=AssertionError('Do not guess forecast')):
            reply = chatbot.generate_reply('mai thời tiết thế nào', [], {'DuLieu': {'NhietDo': 99}})['reply']
        self.assertIn('chưa lấy được', reply)
        self.assertNotIn('99', reply)
        self.assertNotIn('không có khả năng', reply)

    def test_json_and_stream_work_while_training_without_sql_or_air_quality_requests(self):
        with patch.object(backend, 'query', side_effect=AssertionError('Weather forecast does not need SQL')), \
                patch.object(backend, 'get_air_data', side_effect=AssertionError('No AQI request')), \
                patch.object(chatbot, '_load_runtime', side_effect=AssertionError('No model')), \
                patch.object(chatbot, 'get_weather_data', return_value=self.data()), \
                patch.object(air, 'local_now', return_value=self.now):
            client = backend.app.test_client()
            body = {'message': 'mai thời tiết thế nào', 'location': 'hanoi'}
            complete = client.post('/api/chat', json=body)
            streamed = client.post('/api/chat', json={**body, 'stream': True}, buffered=True)
        self.assertEqual(complete.status_code, 200)
        self.assertIn('20–25 °C', complete.get_json()['reply'])
        events = [json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines() if line.startswith('data: ')]
        self.assertEqual(events[-1], {'type': 'done', **complete.get_json()})
        self.assertFalse(chatbot.needs_environment_data('mai thời tiết thế nào'))
        self.assertFalse(chatbot.needs_air_data('mai thời tiết thế nào'))


if __name__ == '__main__':
    unittest.main()
