import json
import unittest
from unittest.mock import patch

import app as backend
import chatbot
from chat_scope import social_intent


class ChatAttentionTests(unittest.TestCase):
    def test_attention_checks_get_a_brief_reply_without_a_model(self):
        for question in ['Xanh Non ơi, bạn nghe thấy mình chứ?',
                         'Nãy giờ bạn vẫn ở đây nghe mình nói chứ?',
                         'Bạn còn ở đây không?', 'Alo trợ lý, bạn có mặt không?']:
            with self.subTest(question=question),patch.object(chatbot,'_load_runtime',side_effect=AssertionError('No inference')):
                self.assertEqual(social_intent(question),'attention')
                self.assertEqual(chatbot.generate_reply(question,[])['reply'],'Mình đây, bạn muốn hỏi gì nào?')

    def test_attention_words_do_not_hide_environmental_or_health_questions(self):
        for question in ['Bạn nghe tiếng ồn thế nào?',
                         'Bạn còn ở đây không, giải thích PM2.5 giúp tôi.',
                         'Bạn nghe thấy mình khó thở vì bụi chứ?',
                         'Bạn thấy AQI hiện tại thế nào?']:
            self.assertIsNone(social_intent(question),question)

    def test_attention_turn_preserves_the_previous_weather_topic(self):
        turns=[{'role':'user','content':'Thời tiết Hà Nội hôm nay thế nào?'},
               {'role':'assistant','content':'Nhiệt độ là 24 °C.'},
               {'role':'user','content':'Xanh Non ơi, bạn nghe thấy mình chứ?'},
               {'role':'assistant','content':'Mình đây, bạn muốn hỏi gì nào?'}]
        question=chatbot._plain_question(chatbot._dialogue_question('Còn mai thế nào?',turns))
        self.assertIn('thoi tiet',question)
        self.assertIn('ha noi',question)
        self.assertNotIn('hom nay',question)

    def test_json_and_stream_use_the_same_brief_attention_reply_without_sql(self):
        body={'message':'Bạn còn ở đây không?','history':[],'learn_from_chat':False}
        with (patch.object(backend,'query',side_effect=AssertionError('No database')),
              patch.object(chatbot,'_load_runtime',side_effect=AssertionError('No model'))):
            client=backend.app.test_client()
            complete=client.post('/api/chat',json=body)
            streamed=client.post('/api/chat',json={**body,'stream':True},buffered=True)
        self.assertEqual(complete.status_code,200)
        events=[json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines() if line.startswith('data: ')]
        self.assertEqual(events[-1],{'type':'done',**complete.get_json()})


if __name__=='__main__':unittest.main()
