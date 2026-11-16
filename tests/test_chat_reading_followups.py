"""Reading changes must keep the requested place/time and use fresh source values."""
from contextlib import ExitStack
from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import patch

import app as backend
import chat_air_data as air
import chatbot
from chat_scope import is_time_followup
from location_catalog import get_location


class ReadingFollowupTests(unittest.TestCase):
    now = datetime(2026, 10, 24, 12, 30, tzinfo=air.VN_TIME)
    snapshot = {'DiaDiem': get_location('hanoi'),
                'DuLieu': {'NhietDo': 99, 'DoAm': 98, 'US_AQI': 12}}

    @staticmethod
    def pair(question, answer='Phản hồi cũ không đáng tin: 777.'):
        return [{'role': 'user', 'content': question}, {'role': 'assistant', 'content': answer}]

    def setUp(self):
        start = self.now.replace(hour=0, minute=0)
        self.data = {'LayLuc': self.now.isoformat(), 'current': {'us_aqi': 77}, 'hourly': {
            'time': [(start + timedelta(hours=i)).isoformat() for i in range(120)],
            'temperature_2m': [20 + i//24*3 + i%24/10 for i in range(120)],
            'relative_humidity_2m': [40 + i//24*10 + i%24 for i in range(120)],
            'us_aqi': [50 + i//24*100 + i%24 for i in range(120)]}}
        self.history = self.pair('Nhiệt độ Đà Nẵng ngày mai lúc 18h thế nào?')
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(air, 'local_now', return_value=self.now))
        self.stack.enter_context(patch.object(chatbot, 'local_now', return_value=self.now))
        self.weather = self.stack.enter_context(patch.object(chatbot, 'get_weather_data', return_value=self.data))
        self.air = self.stack.enter_context(patch.object(chatbot, 'get_air_data', return_value=self.data))
        self.stack.enter_context(patch.object(chatbot, '_load_runtime', side_effect=AssertionError('Use readings, not the model')))

    def reply(self, message, history=None):
        return chatbot.generate_reply(message, self.history if history is None else history, self.snapshot)['reply']

    def test_short_humidity_wordings_keep_city_day_hour_and_only_requested_field(self):
        for question in ('Còn độ ẩm?', 'Độ ẩm thì sao?', 'Vậy xem giúp mình độ ẩm nhé', 'humidity?'):
            with self.subTest(question=question):
                reply = self.reply(question)
                for expected in ('Đà Nẵng', '25/10', '18:00–19:00', '68%'):
                    self.assertIn(expected, reply)
                for unrelated in ('Hà Nội', '777', '98%', '°C', 'AQI'):
                    self.assertNotIn(unrelated, reply)
                self.assertEqual(self.weather.call_args.args[0]['MaDiaDiem'], 'danang')
                self.assertFalse(chatbot.needs_environment_data(question, self.history))
        self.air.assert_not_called()

    def test_topic_can_switch_between_weather_and_air_without_losing_time(self):
        reply = self.reply('Còn AQI thì sao?')
        for expected in ('Đà Nẵng', '25/10', '18:00–19:00', '168'):
            self.assertIn(expected, reply)
        self.assertNotIn('12.', reply)
        self.assertTrue(chatbot.needs_air_data('Còn AQI thì sao?', self.history))
        turns = self.history + self.pair('Còn AQI thì sao?', reply)
        weather = self.reply('Còn nhiệt độ và độ ẩm?', turns)
        self.assertIn('24.8 °C', weather)
        self.assertIn('68%', weather)
        self.assertNotIn('AQI', weather)

    def test_reading_change_composes_with_social_city_day_and_clock_changes(self):
        turns = self.history + self.pair('Cảm ơn bạn', 'Không có gì nhé!')
        for question, expected in (
            ('Còn độ ẩm?', ('Đà Nẵng', '25/10', '18:00–19:00', '68%')),
            ('Đổi sang 19h nhé', ('Đà Nẵng', '25/10', '19:00–20:00', '69%')),
            ('Vậy ngày kia?', ('Đà Nẵng', '26/10', '19:00–20:00', '79%')),
            ('Còn Hải Phòng?', ('Hải Phòng', '26/10', '19:00–20:00', '79%')),
            ('Vậy nhiệt độ?', ('Hải Phòng', '26/10', '19:00–20:00', '27.9 °C')),
        ):
            reply = self.reply(question, turns)
            for value in expected:
                self.assertIn(value, reply)
            turns += self.pair(question, reply)

    def test_explicit_day_and_place_override_old_context(self):
        reply = self.reply('Độ ẩm ngày kia thì sao?')
        self.assertIn('26/10', reply)
        self.assertIn('78%', reply)
        reply = self.reply('Còn độ ẩm Hải Phòng lúc 19h ngày kia?')
        for expected in ('Hải Phòng', '26/10', '19:00–20:00', '79%'):
            self.assertIn(expected, reply)
        self.assertEqual(self.weather.call_args.args[0]['MaDiaDiem'], 'haiphong')

    def test_current_resets_forecast_date_and_clock_but_keeps_city(self):
        reply = self.reply('Còn độ ẩm hiện tại?')
        self.assertIn('Đà Nẵng', reply)
        self.assertIn('12:00', reply)
        self.assertIn('52%', reply)
        self.assertNotIn('25/10', reply)
        self.assertNotIn('18:00', reply)
        self.assertNotIn('98%', reply)

    def test_clock_change_wordings_and_new_day_never_become_unrelated_or_keep_old_hour(self):
        for question in ('Đổi sang 19h nhé', 'Vậy 19h thì sao?', 'Chuyển sang 19:00 giúp mình'):
            with self.subTest(question=question):
                self.assertTrue(is_time_followup(question))
                reply = self.reply(question)
                self.assertIn('25/10', reply)
                self.assertIn('19:00–20:00', reply)
                self.assertIn('24.9 °C', reply)
                self.assertNotIn('18:00', reply)
        reply = self.reply('Đổi sang ngày kia lúc 20h nhé')
        self.assertIn('26/10', reply)
        self.assertIn('20:00–21:00', reply)
        self.assertFalse(is_time_followup('Đổi sang 19h rồi viết code Python'))

    def test_definition_hypothesis_unrelated_and_multiple_places_do_not_inherit(self):
        definition = 'Độ ẩm là gì?'
        resolved = chatbot._dialogue_question(definition, self.history)
        self.assertEqual(resolved, definition)
        self.assertEqual(chatbot._requested_fields(resolved, self.history), ())
        self.assertFalse(chatbot.needs_environment_data(definition, self.history))
        self.weather.assert_not_called()
        self.air.assert_not_called()
        question = 'Còn độ ẩm?'
        for prior in ('Viết code Python', 'Giả sử nhiệt độ Đà Nẵng ngày mai là 40 độ',
                      'AQI là gì?', 'AQI Hà Nội là 999?',
                      'Thời tiết Hà Nội và Đà Nẵng ngày mai?'):
            with self.subTest(prior=prior):
                turns = self.history + self.pair(prior)
                self.assertEqual(chatbot._dialogue_question(question, turns), question)

    def test_both_topics_and_clarification_choice_keep_the_same_explicit_hour(self):
        reply = self.reply('Còn thời tiết và AQI?')
        self.assertEqual(reply.count('18:00–19:00'), 2)
        self.assertIn('24.8 °C', reply)
        self.assertIn('68%', reply)
        self.assertIn('168', reply)
        turns = self.pair('Thời tiết và không khí Đà Nẵng ngày mai thế nào?')
        prompt = self.reply('Đổi sang 19h nhé', turns)
        self.assertIn('ngày mai lúc 19:00', prompt)
        turns += self.pair('Đổi sang 19h nhé', prompt)
        chosen = self.reply('cả hai', turns)
        self.assertEqual(chosen.count('19:00–20:00'), 2)
        self.assertIn('24.9 °C', chosen)
        self.assertIn('169', chosen)

    def test_unknown_day_is_clarified_instead_of_reading_current_weather(self):
        first = 'Độ ẩm Đà Nẵng lúc 18h bao nhiêu?'
        prompt = self.reply(first, [])
        self.assertIn('18:00 hôm nay hay ngày nào khác', prompt)
        self.weather.assert_not_called()
        reply = self.reply('ngày mai', self.pair(first, prompt))
        self.assertIn('25/10', reply)
        self.assertIn('18:00–19:00', reply)
        self.assertIn('68%', reply)
        topic_prompt = self.reply('18h', [])
        self.assertIn('lúc 18:00', topic_prompt)
        turns = self.pair('18h', topic_prompt)
        day_prompt = self.reply('độ ẩm', turns)
        self.assertIn('18:00 hôm nay hay ngày nào khác', day_prompt)
        turns += self.pair('độ ẩm', day_prompt)
        self.assertIn('18:00–19:00', self.reply('ngày mai', turns))

    def test_missing_new_field_does_not_use_old_answer_or_current_selected_values(self):
        self.weather.side_effect = chatbot.WeatherDataUnavailable()
        reply = self.reply('Còn độ ẩm?')
        self.assertIn('chưa lấy được', reply)
        self.assertIn('Đà Nẵng', reply)
        self.assertIn('ngày mai', reply)
        self.assertNotIn('777', reply)
        self.assertNotIn('98', reply)

    def test_json_and_sse_read_the_same_inherited_hour_without_sql(self):
        body = {'message': 'Còn độ ẩm?', 'history': self.history,
                'location': 'hanoi', 'learn_from_chat': False}
        with patch.object(backend, 'query', side_effect=AssertionError('No SQL for weather forecast')):
            client = backend.app.test_client()
            complete = client.post('/api/chat', json=body)
            streamed = client.post('/api/chat', json={**body, 'stream': True}, buffered=True)
        self.assertEqual(complete.status_code, 200)
        events = [json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines() if line.startswith('data: ')]
        self.assertEqual(events[-1], {'type': 'done', **complete.get_json()})
        self.assertIn('68%', complete.get_json()['reply'])


if __name__ == '__main__':
    unittest.main()
