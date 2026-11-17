from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import patch

import app as backend
import chat_air_data as air
import chatbot
from chat_scope import OUT_OF_SCOPE_REPLY
from location_catalog import get_location


class FollowupContextTests(unittest.TestCase):
    now = datetime(2026, 10, 21, 10, tzinfo=air.VN_TIME)
    place = get_location('noise-ba2df08c3226')

    @staticmethod
    def weather():
        start = datetime(2026, 10, 21)
        return {'hourly': {'time': [(start + timedelta(hours=i)).isoformat() for i in range(96)],
                           'temperature_2m': [99]*24 + [23]*12 + [30]*12 + [19]*48,
                           'relative_humidity_2m': [99]*24 + [60]*12 + [80]*12 + [70]*48}}

    @staticmethod
    def air_data():
        start = datetime(2026, 10, 21)
        return {'hourly': {'time': [(start + timedelta(hours=i)).isoformat() for i in range(96)],
                           'us_aqi': [12]*24 + [160]*12 + [175]*12 + [65]*48}}

    def snapshot(self):
        return {'DiaDiem': self.place, 'DuLieu': {'NhietDo': 27.3, 'DoAm': 83, 'US_AQI': 75}}

    def test_screenshot_advice_followup_keeps_weather_and_selected_place(self):
        history = [{'role': 'user', 'content': 'Thời tiết hiện tại thế nào?'},
                   {'role': 'assistant', 'content': 'Ở Phúc Yên, Vĩnh Phúc hiện 27.3 °C, độ ẩm 83%.'}]
        with patch.object(air, 'local_now', return_value=self.now), \
                patch.object(chatbot, 'get_weather_data', return_value=self.weather()) as fetch, \
                patch.object(chatbot, 'get_air_data', side_effect=AssertionError('Weather topic must stay weather')), \
                patch.object(chatbot, '_load_runtime', side_effect=AssertionError('Use forecast data')):
            for question in ['tư vấn mai thế nào', 'mai thế nào', 'tư vấn cho mình mai thế nào nhé',
                             'vậy bạn xem giúp mình sáng mai ra sao', 'mai tnao bạn']:
                with self.subTest(question=question):
                    reply = chatbot.generate_reply(question, history, self.snapshot())['reply']
                    self.assertIn(self.place['Ten'], reply)
                    self.assertIn('22/10', reply)
                    self.assertIn('23', reply)
                    self.assertNotIn('27.3', reply)
                    self.assertNotIn('AQI', reply)
                    self.assertNotEqual(reply, OUT_OF_SCOPE_REPLY)
                    self.assertEqual(fetch.call_args.args[0]['MaDiaDiem'], self.place['MaDiaDiem'])
                    self.assertFalse(chatbot.needs_environment_data(question, history))

    def test_air_followup_uses_tomorrow_and_preserves_explicit_city(self):
        history = [{'role': 'user', 'content': 'Hôm nay không khí ở Đà Nẵng thế nào?'},
                   {'role': 'assistant', 'content': 'AQI hiện tại là 12.'}]
        with patch.object(air, 'local_now', return_value=self.now), \
                patch.object(chatbot, 'get_air_data', return_value=self.air_data()) as fetch, \
                patch.object(chatbot, 'get_weather_data', side_effect=AssertionError('Air topic must stay air')), \
                patch.object(chatbot, '_load_runtime', side_effect=AssertionError('Use forecast data')):
            for question in ['mai thế nào', 'tư vấn mai thế nào', 'ngày mai có xấu hơn không?']:
                with self.subTest(question=question):
                    reply = chatbot.generate_reply(question, history, self.snapshot())['reply']
                    self.assertIn('Đà Nẵng', reply)
                    self.assertIn('22/10', reply)
                    self.assertIn('160–175', reply)
                    self.assertNotIn('12.', reply)
                    self.assertEqual(fetch.call_args.args[0]['MaDiaDiem'], 'danang')
                    self.assertTrue(chatbot.needs_air_data(question, history))

    def test_repeated_temporal_turns_keep_field_and_replace_previous_dates(self):
        history = [{'role': 'user', 'content': 'Nhiệt độ ở Đà Nẵng hôm nay bao nhiêu?'},
                   {'role': 'assistant', 'content': 'Hiện tại 27 độ.'},
                   {'role': 'user', 'content': 'Tư vấn mai thế nào?'},
                   {'role': 'assistant', 'content': 'Ngày mai 999 độ.'},
                   {'role': 'user', 'content': 'Cảm ơn bạn'},
                   {'role': 'assistant', 'content': 'Không có gì nhé.'}]
        with patch.object(air, 'local_now', return_value=self.now), \
                patch.object(chatbot, 'get_weather_data', return_value=self.weather()), \
                patch.object(chatbot, '_load_runtime', side_effect=AssertionError('Use forecast data')):
            reply = chatbot.generate_reply('Còn ngày kia thế nào?', history, self.snapshot())['reply']
        self.assertIn('Đà Nẵng', reply)
        self.assertIn('23/10', reply)
        self.assertIn('19 °C', reply)
        self.assertNotIn('độ ẩm', reply)
        self.assertNotIn('999', reply)
        resolved = chatbot._dialogue_question('Còn ngày kia thế nào?', history)
        self.assertNotIn('hom nay', chatbot._plain_question(resolved))
        self.assertNotIn('mai', chatbot._plain_question(resolved))

    def test_latest_explicit_subject_replaces_older_weather_context(self):
        history = [{'role': 'user', 'content': 'Thời tiết hôm nay ra sao?'},
                   {'role': 'assistant', 'content': 'Trời 27 độ.'},
                   {'role': 'user', 'content': 'Còn hôm nay không khí thế nào?'},
                   {'role': 'assistant', 'content': 'AQI 12.'}]
        with patch.object(air, 'local_now', return_value=self.now), \
                patch.object(chatbot, 'get_air_data', return_value=self.air_data()), \
                patch.object(chatbot, 'get_weather_data', side_effect=AssertionError('Use latest user topic')):
            reply = chatbot.generate_reply('Tư vấn ngày mai thế nào?', history, self.snapshot())['reply']
        self.assertIn('AQI', reply)
        self.assertIn('160–175', reply)
        self.assertNotIn('°C', reply)

    def test_unrelated_turn_and_new_unrelated_request_do_not_inherit_environment_topic(self):
        original = [{'role': 'user', 'content': 'Thời tiết hôm nay thế nào?'},
                    {'role': 'assistant', 'content': '27 độ.'}]
        switched = original + [{'role': 'user', 'content': 'Tư vấn mua Bitcoin'},
                               {'role': 'assistant', 'content': 'AQI 175.'}]
        with patch.object(chatbot, '_load_runtime', side_effect=AssertionError('No environmental inference')), \
                patch.object(chatbot, '_conversation_reply', return_value={'reply': 'Trả lời theo chủ đề mới.', 'truncated': False}), \
                patch.object(chatbot, 'get_weather_data', side_effect=AssertionError('Do not fetch')):
            for question, history in [('tư vấn mai thế nào', switched),
                                      ('mai nên đầu tư Bitcoin thế nào', original),
                                      ('tư vấn mai nấu món gì', original)]:
                with self.subTest(question=question):
                    self.assertEqual(chatbot.generate_reply(question, history, self.snapshot())['reply'], 'Trả lời theo chủ đề mới.')

    def test_followup_is_consistent_across_json_and_stream_without_sql(self):
        body = {'message': 'tư vấn mai thế nào', 'location': self.place['MaDiaDiem'], 'history': [
            {'role': 'user', 'content': 'Hôm nay thời tiết thế nào?'},
            {'role': 'assistant', 'content': 'Ở Phúc Yên, Vĩnh Phúc hiện 27.3 °C, độ ẩm 83%.'}]}
        with patch.object(air, 'local_now', return_value=self.now), \
                patch.object(chatbot, 'get_weather_data', return_value=self.weather()), \
                patch.object(backend, 'query', side_effect=AssertionError('Weather forecast does not need SQL')), \
                patch.object(chatbot, '_load_runtime', side_effect=AssertionError('No inference')):
            client = backend.app.test_client()
            complete = client.post('/api/chat', json=body)
            streamed = client.post('/api/chat', json={**body, 'stream': True}, buffered=True)
        self.assertEqual(complete.status_code, 200)
        self.assertIn('23–30 °C', complete.get_json()['reply'])
        self.assertIn(self.place['Ten'], complete.get_json()['reply'])
        events = [json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines() if line.startswith('data: ')]
        self.assertEqual(events[-1], {'type': 'done', **complete.get_json()})


if __name__ == '__main__':
    unittest.main()
