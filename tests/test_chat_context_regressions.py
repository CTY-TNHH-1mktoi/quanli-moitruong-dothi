"""Reproduce conversational failures while model generation is unavailable."""
import json
import unittest
from unittest.mock import patch

import app as backend
import chatbot
from chat_knowledge import concept_answer
from chat_scope import OUT_OF_SCOPE_REPLY, is_environment_question
from location_catalog import get_location


class ContextRegressionTests(unittest.TestCase):
    snapshot = {'DiaDiem': get_location('hanoi'), 'DuLieu': {'US_AQI': 167}}

    def test_particle_definition_accepts_conversational_endings_without_loading_model(self):
        with patch.object(chatbot, '_load_runtime', side_effect=AssertionError('Use reviewed definition')):
            for question in ['PM2.5 là gì vậy bạn', 'Bạn giải thích PM2.5 là gì nhé', 'PM10 nghĩa là gì hả bạn']:
                with self.subTest(question=question):
                    result = chatbot.generate_reply(question, [], self.snapshot)
                    self.assertIn('micromet', result['reply'])
                    self.assertNotIn('167', result['reply'])
                    self.assertFalse(result['truncated'])

    def test_more_specific_explanation_inherits_concept_without_out_of_scope_fallback(self):
        history = [{'role': 'user', 'content': 'PM2.5 là gì?'},
                   {'role': 'assistant', 'content': 'PM2.5 là bụi mịn, hạt thường không quá 2,5 micromet.'}]
        with patch.object(chatbot, '_load_runtime', side_effect=AssertionError('Use reviewed concept')):
            for question in ['giải thích cụ thể hơn đi', 'bạn nói cụ thể thêm nhé']:
                with self.subTest(question=question):
                    self.assertTrue(is_environment_question(question, history))
                    reply = chatbot.generate_reply(question, history, self.snapshot)['reply']
                    self.assertIn('phổi', reply)
                    self.assertNotEqual(reply, OUT_OF_SCOPE_REPLY)
        self.assertFalse(is_environment_question('giải thích cụ thể hơn đi', []))
        unrelated = [{'role': 'user', 'content': 'Giải phương trình bậc hai'},
                     {'role': 'assistant', 'content': OUT_OF_SCOPE_REPLY}]
        self.assertFalse(is_environment_question('giải thích cụ thể hơn đi', unrelated))

    def test_short_action_followup_uses_dust_topic_instead_of_outdoor_activity(self):
        history = [{'role': 'user', 'content': 'Nhà sát đường lớn, bụi hay vào phòng.'},
                   {'role': 'assistant', 'content': 'Bạn có thể giảm nguồn bụi trong phòng.'}]
        with patch.object(chatbot, '_load_runtime', side_effect=AssertionError('Use reviewed measures')):
            for question in ['vậy mình làm gì bây giờ', 'thế tôi nên làm gì tiếp']:
                with self.subTest(question=question):
                    reply = chatbot.generate_reply(question, history, self.snapshot)['reply']
                    self.assertIn('khăn ẩm', reply)
                    self.assertNotIn('đọc sách', reply)
                    self.assertNotIn('167', reply)
            switched = history + [{'role': 'user', 'content': 'Viết code Python'},
                                  {'role': 'assistant', 'content': OUT_OF_SCOPE_REPLY}]
            with patch.object(chatbot, '_conversation_reply', return_value={'reply': 'Trả lời theo chủ đề mới.', 'truncated': False}):
                reply = chatbot.generate_reply('giải thích cụ thể hơn đi', switched, self.snapshot)['reply']
            self.assertEqual(reply, 'Trả lời theo chủ đề mới.')

    def test_particle_health_followup_does_not_require_live_concentration(self):
        history = [{'role': 'user', 'content': 'PM2.5 là gì?'},
                   {'role': 'assistant', 'content': 'Đó là bụi mịn.'}]
        with patch.object(chatbot, '_load_runtime', side_effect=AssertionError('Use reviewed particle facts')):
            result = chatbot.generate_reply('bụi này có nguy hiểm ko', history, self.snapshot)
        self.assertIn('phổi', result['reply'])
        self.assertFalse(result['truncated'])
        self.assertIsNone(concept_answer('PM2.5 là gì và cách chọn máy lọc như thế nào?'))

    def test_context_repair_works_for_json_and_stream_while_training(self):
        body = {'message': 'giải thích cụ thể hơn đi', 'history': [
            {'role': 'user', 'content': 'PM2.5 là gì?'},
            {'role': 'assistant', 'content': 'Đó là bụi mịn.'}]}
        with patch.object(chatbot, '_load_runtime', side_effect=AssertionError('No inference needed')), \
                patch.object(backend, 'chat_snapshot', return_value=self.snapshot):
            client = backend.app.test_client()
            complete = client.post('/api/chat', json=body)
            streamed = client.post('/api/chat', json={**body, 'stream': True}, buffered=True)
        self.assertEqual(complete.status_code, 200)
        events = [json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines() if line.startswith('data: ')]
        self.assertEqual(events[-1], {'type': 'done', **complete.get_json()})
        self.assertIn('phổi', complete.get_json()['reply'])


if __name__ == '__main__':
    unittest.main()
