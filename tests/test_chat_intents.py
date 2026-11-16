"""Natural requests should route by intent without losing scope/data boundaries."""

import json
import unittest
from unittest.mock import patch

import app as backend
import chatbot
from chat_scope import OUT_OF_SCOPE_REPLY, assistant_help_intent, is_environment_question
from location_catalog import get_location


class NaturalIntentTests(unittest.TestCase):
    @staticmethod
    def snapshot(aqi):
        return {"DiaDiem": get_location("hanoi"), "DuLieu": {"US_AQI": aqi, "NhietDo": 25, "DoAm": 80}}

    def test_help_requests_recognize_roles_and_different_question_forms(self):
        questions = {
            "giới thiệu về chức năng": "features",
            "Giới thiệu các tính năng chính của ứng dụng này nhé": "features",
            "Cho mình biết chức năng của ứng dụng": "features",
            "App này có những chức năng gì?": "features",
            "Bạn có thể giúp được mình những gì?": "capabilities",
            "Bạn hỗ trợ những chuyện gì?": "capabilities",
            "Bạn biết làm những công việc nào?": "capabilities",
            "Tôi có thể hỏi bạn về những nội dung gì?": "capabilities",
            "Mình có thể nhờ bạn giúp những việc gì?": "capabilities",
            "Bạn ơi, bạn có những chức năng gì vậy?": "capabilities",
            "Bạn là ai?": "identity",
            "Hãy giới thiệu về bản thân đi": "identity",
            "Hướng dẫn cách sử dụng app này": "guide",
            "Ứng dụng này dùng thế nào nhỉ?": "guide",
            "Mình nên bắt đầu từ đâu?": "guide",
        }
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Explain actual capabilities directly")):
            for question, intent in questions.items():
                with self.subTest(question=question):
                    self.assertEqual(assistant_help_intent(question), intent)
                    self.assertTrue(is_environment_question(question))
                    result = chatbot.generate_reply(question, [], self.snapshot(None))
                    self.assertNotEqual(result["reply"], OUT_OF_SCOPE_REPLY)
                    self.assertIn("chỉ số", result["reply"])
                    self.assertFalse(result["truncated"])

    def test_implicit_daily_activity_requests_use_real_aqi(self):
        questions = ["hôm nay phù hợp cho hoạt động nào", "Hôm nay mình nên làm gì?",
                     "Có hoạt động nào thích hợp lúc này không?", "Gợi ý vài hoạt động cho mình nhé",
                     "Hnay nên tập gì bạn?", "Bạn đề xuất hoạt động nào bây giờ?"]
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use actual AQI for these requests")):
            for question in questions:
                with self.subTest(question=question):
                    self.assertTrue(is_environment_question(question))
                    self.assertEqual(chatbot._requested_fields(question), ("US_AQI",))
                    good = chatbot.generate_reply(question, [], self.snapshot(42))["reply"]
                    bad = chatbot.generate_reply(question, [], self.snapshot(175))["reply"]
                    self.assertIn("42 (Tốt)", good)
                    self.assertIn("đi bộ", good)
                    self.assertIn("175 (Xấu)", bad)
                    self.assertIn("trong nhà", bad)
                    self.assertNotEqual(good, bad)

    def test_casual_outdoor_questions_are_not_rejected(self):
        for question in ["Đi dạo ổn không?", "Đi bộ một vòng được chứ?", "Đạp xe dc ko bạn?",
                         "Ra ngoài một chút được không nhỉ?", "Mình định đi picnic hôm nay"]:
            with self.subTest(question=question), patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use AQI")):
                self.assertTrue(is_environment_question(question))
                self.assertIn("42 (Tốt)", chatbot.generate_reply(question, [], self.snapshot(42))["reply"])

    def test_missing_data_and_future_or_other_place_do_not_become_positive_advice(self):
        question = "Hôm nay phù hợp cho hoạt động nào?"
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Missing AQI has a direct reply")):
            reply = chatbot.generate_reply(question, [], self.snapshot(None))["reply"]
            self.assertIn("chưa đủ dữ liệu", reply)
            self.assertNotIn("có thể ra ngoài", reply)
        for question in ["Cuối tuần phù hợp hoạt động nào?", "Ngày mai nên tập gì?",
                         "Ở Đà Nẵng hôm nay nên làm gì?", "Tôi bị hen thì hôm nay nên tập gì?"]:
            with self.subTest(question=question):
                self.assertTrue(is_environment_question(question))
                self.assertIsNone(chatbot._grounded_reply(question, [], self.snapshot(42)))

    def test_activity_explanations_are_not_mistaken_for_current_advice(self):
        for question in ["Lợi ích của đi bộ là gì?", "Cách tập thể dục ngoài trời?",
                         "Tác dụng của đi dạo là gì?", "Nên đi chơi ở đâu?"]:
            with self.subTest(question=question):
                self.assertTrue(is_environment_question(question))
                self.assertIsNone(chatbot._grounded_reply(question, [], self.snapshot(42)))

    def test_activity_followup_uses_latest_user_topic(self):
        history = [{"role": "user", "content": "AQI hiện tại thế nào?"},
                   {"role": "assistant", "content": "US AQI 175."}]
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use current data")):
            reply = chatbot.generate_reply("Vậy mình nên làm gì?", history, self.snapshot(42))["reply"]
        self.assertIn("42 (Tốt)", reply)
        self.assertNotIn("175", reply)

    def test_other_subjects_do_not_turn_into_help_or_activity_advice(self):
        for question in ["Giới thiệu chức năng của máy giặt", "Bạn giúp mình nấu món gì?",
                         "Hôm nay nên đầu tư Bitcoin hay chứng khoán?",
                         "Hoạt động kinh doanh nào phù hợp hôm nay?", "Bạn viết code Python được không?",
                         "Hôm nay nên nấu món gì?", "Đội nào vô địch World Cup?"]:
            with self.subTest(question=question), patch.object(chatbot, "_load_runtime", side_effect=AssertionError("No environmental inference")), \
                    patch.object(chatbot, "_conversation_reply", return_value={"reply": "Trả lời theo chủ đề mới.", "truncated": False}):
                self.assertIsNone(assistant_help_intent(question))
                self.assertEqual(chatbot.generate_reply(question, [], self.snapshot(42))["reply"], "Trả lời theo chủ đề mới.")

    def test_screenshot_questions_work_in_both_json_and_stream(self):
        client = backend.app.test_client()
        history = [{"role": "user", "content": "giới thiệu về chức năng"},
                   {"role": "assistant", "content": OUT_OF_SCOPE_REPLY}]
        with patch.object(backend, "environment_cache", {"hanoi": {"result": self.snapshot(175)}}), \
                patch.object(chatbot, "_load_runtime", side_effect=AssertionError("No model needed")):
            for question in ["giới thiệu về chức năng", "hôm nay phù hợp cho hoạt động nào"]:
                with self.subTest(question=question):
                    body = {"message": question, "history": history, "location": "hanoi"}
                    complete = client.post("/api/chat", json=body)
                    stream = client.post("/api/chat", json={**body, "stream": True}, buffered=True)
                    self.assertEqual(complete.status_code, 200)
                    self.assertEqual(stream.status_code, 200)
                    events = [json.loads(line[6:]) for line in stream.get_data(as_text=True).splitlines() if line.startswith("data: ")]
                    self.assertNotEqual(complete.get_json()["reply"], OUT_OF_SCOPE_REPLY)
                    self.assertEqual(events[-1]["reply"], complete.get_json()["reply"])


if __name__ == "__main__":
    unittest.main()
