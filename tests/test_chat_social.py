import unittest
from unittest.mock import patch

import chatbot
from chat_scope import OUT_OF_SCOPE_REPLY, social_intent


class SocialTests(unittest.TestCase):
    def test_basic_social_turns_work_without_model_or_environment_data(self):
        cases = {"Xin chào": "Chào bạn", "Hi Xanh Non": "Chào bạn", "Cảm ơn bạn nhé": "Không có gì",
                 "Thanks": "Không có gì", "Tạm biệt": "Tạm biệt", "Mình hiểu rồi": "cứ nhắn",
                 "Bạn ơi": "Mình đây", "Bạn có đó không?": "Mình đây", "Mình chưa hiểu": "phần nào",
                 "Bạn nói sai rồi": "kiểm tra lại", "Tks": "Không có gì", "Tư vấn giúp tôi": "Bạn muốn"}
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Basic communication")):
            for question, expected in cases.items():
                with self.subTest(question=question):
                    reply = chatbot.generate_reply(question, [], None)["reply"]
                    self.assertIn(expected, reply)
                    self.assertNotEqual(reply, OUT_OF_SCOPE_REPLY)
                    self.assertFalse(chatbot.needs_environment_data(question))

    def test_politeness_does_not_swallow_a_real_question_or_open_unrelated_topics(self):
        for question in ["Chào bạn, AQI hiện tại thế nào?", "Cảm ơn, nhưng PM2.5 là gì?",
                         "Bạn ơi mai không khí thế nào?", "Hi, viết code Python"]:
            self.assertIsNone(social_intent(question))
        with patch.object(chatbot, "_conversation_reply", return_value={"reply": "Trả lời theo chủ đề mới.", "truncated": False}) as conversation:
            self.assertEqual(chatbot.generate_reply("Hi, viết code Python", [], None)["reply"], "Trả lời theo chủ đề mới.")
            conversation.assert_called_once()

    def test_abbreviated_subjectless_air_question_uses_actual_reading(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use actual data")):
            reply = chatbot.generate_reply("clkk hnay tn?", [], {"DuLieu": {"US_AQI": 95}})["reply"]
        self.assertIn("95 (Trung bình)", reply)
