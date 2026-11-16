import unittest
from unittest.mock import patch

import app as backend
import chatbot


class ConsultationWhyTests(unittest.TestCase):
    history=[{'role':'user','content':'Tôi muốn chạy bộ ngoài trời, bạn tư vấn giúp.'},
             {'role':'assistant','content':'Bạn định vận động hôm nay hay vào thời điểm nào khác?'}]

    def test_question_about_our_time_request_is_answered_directly(self):
        for question in ['Bạn hỏi giờ mình đi để làm gì nhỉ?',
                         'Lý do bạn muốn biết lúc tôi đi tập là gì?',
                         'Bạn hỏi mốc giờ hoạt động để phục vụ việc gì?',
                         'Tại sao cần hỏi thời gian mình tập?']:
            with self.subTest(question=question),patch.object(chatbot,'_load_runtime',side_effect=AssertionError('No inference')):
                reply=chatbot.generate_reply(question,self.history)['reply']
                self.assertIn('số đo hoặc dự báo',reply)
                self.assertIn('thời điểm',reply)

    def test_new_environment_question_is_not_mistaken_for_a_question_about_our_request(self):
        self.assertIsNone(chatbot._consultation_reply('Vì sao AQI hôm nay tăng?',self.history))

    def test_api_does_not_query_sql_when_explaining_our_own_question(self):
        with (patch.object(backend,'query',side_effect=AssertionError('No SQL')),
              patch.object(chatbot,'_load_runtime',side_effect=AssertionError('No inference'))):
            response=backend.app.test_client().post('/api/chat',json={
                'message':'Bạn hỏi mốc giờ hoạt động để phục vụ việc gì?', 'history':self.history})
        self.assertEqual(response.status_code,200)
        self.assertIn('số đo hoặc dự báo',response.get_json()['reply'])


if __name__=='__main__':unittest.main()
