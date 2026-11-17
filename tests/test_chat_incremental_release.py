import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app as backend
import chatbot
import chat_knowledge as knowledge
from chat_learning import ConversationLearner
from evaluate_xanhnon import assess, evaluation_cases
from location_catalog import get_location


class IncrementalReleaseTests(unittest.TestCase):
    def test_fixed_consultation_cases_work_without_waiting_for_the_trainer(self):
        for case in evaluation_cases(Path('data/xanhnon/eval_consultation.json'))[0]:
            snapshot = {'DiaDiem':get_location('hanoi'), 'ThoiGian':'2026-10-19T09:00:00',
                        'DuLieu':{'US_AQI':175, 'PM25':45.4, 'PM10':60, 'NhietDo':24.8,
                                  'DoAm':95, 'TiengOn':74.99, **case.get('readings', {})}}
            with self.subTest(case=case['id']), patch.object(chatbot, '_load_runtime', side_effect=AssertionError('Use verified source/data')):
                reply = chatbot.generate_reply(case['question'], case.get('history', []), snapshot)
                assessment = assess(case, reply, 0)
                self.assertTrue(assessment['passed'], assessment)

    def test_new_phrasings_use_facts_and_current_readings_remain_current(self):
        with patch.object(chatbot, '_load_runtime', side_effect=AssertionError('No model required')):
            self.assertIn('chỉ số', chatbot.generate_reply('Bạn giải thích AQI thật dễ hiểu với.', [])['reply'])
            history=[{'role':'user','content':'Bạn giải thích AQI thật dễ hiểu với.'},
                     {'role':'assistant','content':'AQI là chỉ số chất lượng không khí.'}]
            self.assertIn('151–200',chatbot.generate_reply('Giải thích chi tiết',history)['reply'])
            self.assertIn('công trường', chatbot.generate_reply('Bụi PM10 có nguồn gốc từ đâu vậy?', [])['reply'])
            self.assertNotIn('µg/m³', chatbot.generate_reply('PM2.5 có đường kính nhỏ cỡ nào, có vào phổi được không?', [])['reply'])
            self.assertIn('nồng độ', chatbot.generate_reply('PM2.5 bằng 61 có đồng nghĩa AQI bằng 61 không?', [])['reply'])
            snapshot={'DiaDiem':get_location('hanoi'), 'DuLieu':{'US_AQI':83}}
            answer=chatbot.generate_reply('Còn AQI Hà Nội lúc này thì sao?', [], snapshot)['reply']
            self.assertIn('83', answer)
            self.assertNotIn('175', answer)

    def test_verified_details_do_not_need_a_fuzzy_index_or_current_database(self):
        with patch.object(knowledge, '_index', side_effect=AssertionError('Keep verified answers light')), \
                patch.object(chatbot, '_load_runtime', side_effect=AssertionError('No model needed')):
            for message in ['Giải thích chi tiết AQI', 'Giải thích chi tiết PM2.5 ảnh hưởng sức khỏe thế nào?']:
                self.assertFalse(chatbot.needs_environment_data(message))
                self.assertFalse(chatbot.generate_reply(message, [])['truncated'])

    def test_automatic_learning_json_and_stream_share_the_verified_reply(self):
        with tempfile.TemporaryDirectory() as directory:
            learner=ConversationLearner(Path(directory)/'learning.sqlite3')
            body={'message':'Bạn giải thích AQI thật dễ hiểu với.', 'learn_from_chat':True}
            with patch.object(backend, 'conversation_learner', learner), \
                    patch.object(backend, 'chat_snapshot', side_effect=AssertionError('No readings needed')):
                client=backend.app.test_client()
                reply=client.post('/api/chat',json=body)
                streamed=client.post('/api/chat',json={**body,'stream':True},buffered=True)
            self.assertEqual(reply.status_code,200)
            events=[json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines() if line.startswith('data: ')]
            self.assertEqual(events[-1],{'type':'done',**reply.get_json()})
            self.assertIn('chỉ số',reply.get_json()['reply'])


if __name__ == '__main__':
    unittest.main()
