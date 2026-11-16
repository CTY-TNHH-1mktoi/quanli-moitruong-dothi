import json
import unittest
from unittest.mock import patch

import app as backend
import chatbot


class ReviewedSafetyTests(unittest.TestCase):
    def test_supplied_aqi_categories_and_colors_do_not_use_a_live_value(self):
        cases=[(50,'Tốt','xanh lá'),(51,'Trung bình','vàng'),(100,'Trung bình','vàng'),
               (101,'Kém','cam'),(150,'Kém','cam'),(151,'Xấu','đỏ'),(175,'Xấu','đỏ'),
               (200,'Xấu','đỏ'),(201,'Rất xấu','tím'),(300,'Rất xấu','tím'),(301,'Nguy hại','nâu đỏ')]
        with patch.object(chatbot,'_load_runtime',side_effect=AssertionError('Use verified categories')):
            for value,label,color in cases:
                question=f'US AQI = {value} thuộc mức nào, màu gì?'
                with self.subTest(value=value):
                    self.assertFalse(chatbot.needs_environment_data(question))
                    reply=chatbot.generate_reply(question,[],{'DuLieu':{'US_AQI':7}})['reply']
                    self.assertIn(f'{value}',reply)
                    self.assertIn(label,reply)
                    self.assertIn(f'({color})',reply)
                    self.assertNotIn('hiện tại',reply)

    def test_other_scales_and_particle_concentrations_are_not_classified_as_us_aqi(self):
        self.assertIsNone(chatbot._provided_aqi_reply('VN AQI 175 thuộc mức nào?'))
        self.assertIsNone(chatbot._provided_aqi_reply('PM2.5 175 µg/m³ thuộc mức nào?'))
        self.assertIn('kiểm tra lại',chatbot._provided_aqi_reply('US AQI -10 thuộc mức nào?'))
        self.assertIn('kiểm tra lại',chatbot._provided_aqi_reply('US AQI 999 thuộc mức nào?'))

    def test_noise_duration_and_pm10_harm_use_existing_reviewed_sources(self):
        with patch.object(chatbot,'_load_runtime',side_effect=AssertionError('Use verified advice')):
            for question in ['Có nên tăng thời gian ở nơi ồn để quen tai không?',
                             'Nghe âm thanh lớn lâu để quen tai có được không?']:
                self.assertFalse(chatbot.needs_environment_data(question))
                reply=chatbot.generate_reply(question,[])['reply']
                self.assertIn('giảm thời gian',reply)
                self.assertNotIn('tăng thời gian',reply)
            reply=chatbot.generate_reply('PM10 là bụi vô hại đúng không?',[])['reply']
            self.assertIn('ảnh hưởng',reply)
            self.assertIn('hô hấp',reply)

    def test_json_and_stream_classify_supplied_aqi_without_database_or_model(self):
        client=backend.app.test_client()
        with patch.object(backend,'chat_snapshot',return_value=None), \
                patch.object(chatbot,'_load_runtime',side_effect=AssertionError('No model')):
            body={'message':'US AQI 175 thuộc mức nào?','history':[]}
            reply=client.post('/api/chat',json=body)
            streamed=client.post('/api/chat',json={**body,'stream':True},buffered=True)
        self.assertEqual(reply.status_code,200)
        events=[json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines() if line.startswith('data: ')]
        self.assertEqual(events[-1],{'type':'done',**reply.get_json()})
        self.assertIn('Xấu (đỏ)',reply.get_json()['reply'])


if __name__ == '__main__':
    unittest.main()
