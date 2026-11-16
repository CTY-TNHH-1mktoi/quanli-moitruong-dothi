from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

import chatbot
import chat_air_data as air
from chat_scope import OUT_OF_SCOPE_REPLY
from location_catalog import get_location


class ConsultationDialogueTests(unittest.TestCase):
    snapshot = {"DiaDiem": get_location("hanoi"), "DuLieu": {"US_AQI": 175}}

    def dialogue(self, messages):
        history, replies = [], []
        for question in messages:
            reply = chatbot.generate_reply(question, history, self.snapshot)["reply"]
            replies.append(reply)
            history += [{"role": "user", "content": question}, {"role": "assistant", "content": reply}]
        return history, replies

    def test_consultation_asks_for_missing_time_then_uses_current_readings(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("A clear consultation needs no guesswork")):
            history, replies = self.dialogue(["Chào bạn", "Tư vấn giúp tôi", "Mình muốn chạy bộ", "Bây giờ", "Cảm ơn"])
        self.assertIn("Bạn muốn", replies[1])
        self.assertIn("thời điểm nào", replies[2])
        self.assertIn("175 (Xấu)", replies[3])
        self.assertIn("giảm", replies[3])
        self.assertIn("Không có gì", replies[4])
        reply = chatbot.generate_reply("Còn hiện tại thì sao?", history, self.snapshot)["reply"]
        self.assertIn("175 (Xấu)", reply)

    def test_future_followup_keeps_activity_and_requests_correct_period(self):
        now = datetime(2026, 10, 19, 10, tzinfo=air.VN_TIME)
        start = now.replace(hour=0, tzinfo=None) + timedelta(days=1)
        data = {"hourly": {"time": [(start + timedelta(hours=i)).isoformat() for i in range(24)], "us_aqi": [175]*24}}
        with patch.object(chatbot, "get_air_data", return_value=data), patch.object(air, "local_now", return_value=now), \
                patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use forecast")):
            _, replies = self.dialogue(["Tư vấn giúp tôi", "Chạy bộ", "Sáng mai"])
        self.assertIn("thời điểm nào", replies[1])
        self.assertIn("05:00–11:00", replies[2])
        self.assertIn("175", replies[2])
        self.assertIn("giảm", replies[2])
        self.assertNotIn("mưa", replies[2])

    def test_does_not_reask_supplied_time_or_use_old_assistant_aqi(self):
        history = [{"role": "user", "content": "Tư vấn giúp tôi"},
                   {"role": "assistant", "content": "Bạn muốn tư vấn hoạt động ngoài trời? AQI 42."}]
        reply = chatbot.generate_reply("Mình muốn chạy bộ bây giờ", history, self.snapshot)["reply"]
        self.assertIn("175 (Xấu)", reply)
        self.assertNotIn("thời điểm nào", reply)
        self.assertNotIn("42", reply)

    def test_new_unrelated_topic_breaks_implicit_time_context(self):
        history, _ = self.dialogue(["Tư vấn giúp tôi", "Chạy bộ"])
        history += [{"role": "user", "content": "Viết code Python"}, {"role": "assistant", "content": OUT_OF_SCOPE_REPLY}]
        with patch.object(chatbot, "_conversation_reply", return_value={"reply": "Trả lời theo chủ đề mới.", "truncated": False}):
            self.assertEqual(chatbot.generate_reply("Bây giờ", history, self.snapshot)["reply"], "Trả lời theo chủ đề mới.")

    def test_casual_time_answers_keep_activity_without_repeating_a_question(self):
        history, _ = self.dialogue(["Tư vấn giúp tôi", "Chạy bộ"])
        for answer in ["Bây giờ luôn nhé", "Giờ luôn", "Ngay bây giờ", "Vậy hôm nay nhé"]:
            with self.subTest(answer=answer), patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use current AQI")):
                reply = chatbot.generate_reply(answer, history, self.snapshot)["reply"]
                self.assertIn("175 (Xấu)", reply)
                self.assertNotIn("thời điểm nào", reply)

    def test_uncertain_answer_gets_one_useful_question_then_confirmation_uses_aqi(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Clear dialogue needs no model")):
            history, replies = self.dialogue(["Tư vấn giúp tôi", "Mình tính đi bộ thôi", "Chưa biết nữa", "Được nhé"])
        self.assertIn("đi bộ", replies[1])
        self.assertIn("Bạn muốn xem luôn không?", replies[2])
        self.assertIn("175 (Xấu)", replies[3])
        self.assertFalse(chatbot.needs_environment_data("Mình tính đi bộ thôi", history[:2]))
        self.assertTrue(chatbot.needs_air_data("Được nhé", history[:-2]))

    def test_declining_a_suggested_check_does_not_invent_consent(self):
        history, _ = self.dialogue(["Tư vấn giúp tôi", "Đi dạo", "Chưa chốt"])
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Respect a short decline")):
            reply = chatbot.generate_reply("Để sau nhé", history, self.snapshot)["reply"]
        self.assertIn("khi nào bạn chốt", reply)
        self.assertNotIn("175", reply)

    def test_clarification_of_time_question_explains_the_question_in_place(self):
        history, _ = self.dialogue(["Tư vấn giúp tôi", "Chạy bộ"])
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Explain our own question")):
            reply = chatbot.generate_reply("Ý là sao?", history, self.snapshot)["reply"]
        self.assertIn("tập lúc nào", reply)
        self.assertIn("sáng mai", reply)
        self.assertNotIn("175", reply)

    def test_brief_followup_resolves_measurement_topic_after_thanks(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use current measurement")):
            _, replies = self.dialogue(["AQI hiện tại bao nhiêu?", "Cảm ơn", "Nói ngắn hơn chút"])
        self.assertIn("175 (Xấu)", replies[-1])
        self.assertLess(len(replies[-1].split()), 20)

    def test_brief_outdoor_followup_actually_shortens_advice(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Shorten verified advice")):
            _, replies = self.dialogue(["Có nên chạy bộ bây giờ không?", "Nói ngắn hơn chút"])
        self.assertIn("175 (Xấu)", replies[-1])
        self.assertLess(len(replies[-1].split()), len(replies[0].split()))
        self.assertIn("nhóm nhạy cảm", replies[-1])

    def test_current_time_replaces_old_forecast_period_instead_of_combining_them(self):
        history = [{"role": "user", "content": "Chiều nay tôi có nên chạy bộ không?"},
                   {"role": "assistant", "content": "Đang xem dự báo."}]
        with patch.object(chatbot, "get_air_data", side_effect=AssertionError("Current reply must not fetch a forecast")):
            reply = chatbot.generate_reply("Còn bây giờ luôn?", history, self.snapshot)["reply"]
        self.assertIn("175 (Xấu)", reply)

    def test_longer_consultation_survives_polite_and_clarifying_turns_at_api_boundary(self):
        import app as backend
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Keep user topic")):
            history, _ = self.dialogue(["Chào bạn", "Tư vấn giúp tôi", "Mình tính đi bộ thôi",
                                       "Ý là sao?", "Chưa biết nữa", "Được nhé", "Cảm ơn"])
        with patch.object(backend, "chat_snapshot", return_value=self.snapshot):
            response = backend.app.test_client().post("/api/chat", json={"message": "Nói ngắn hơn chút", "history": history})
        self.assertEqual(response.status_code, 200)
        self.assertIn("175 (Xấu)", response.get_json()["reply"])
        full = history + [{"role": "user", "content": "Cảm ơn"}, {"role": "assistant", "content": "Không có gì"}]
        chatbot.validate_chat({"message": "Còn bây giờ?", "history": full})
        with self.assertRaises(ValueError):
            chatbot.validate_chat({"message": "Còn bây giờ?", "history": full + full[:2]})
