from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import patch

import app as backend
import chat_air_data as air
import chatbot
from chat_scope import OUT_OF_SCOPE_REPLY
from location_catalog import get_location


class TopicClarificationTests(unittest.TestCase):
    now = datetime(2026, 10, 21, 10, tzinfo=air.VN_TIME)
    prompt = "Bạn muốn xem thời tiết hay chất lượng không khí ngày mai?"
    snapshot = {"DiaDiem": get_location("hanoi"),
                "DuLieu": {"NhietDo": 99, "DoAm": 99, "US_AQI": 12}}

    @staticmethod
    def data():
        start = datetime(2026, 10, 21)
        return {"hourly": {"time": [(start + timedelta(hours=i)).isoformat() for i in range(96)],
                           "temperature_2m": [99]*24 + [23]*12 + [30]*12 + [19]*48,
                           "relative_humidity_2m": [99]*24 + [60]*12 + [80]*12 + [70]*48,
                           "us_aqi": [12]*24 + [160]*12 + [175]*12 + [65]*48}}

    def pending(self, context=None):
        return (context or []) + [{"role": "user", "content": "tư vấn mai thế nào"},
                                 {"role": "assistant", "content": self.prompt}]

    def test_missing_topic_asks_one_short_question_without_model_or_data(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Do not guess")), \
                patch.object(chatbot, "get_air_data", side_effect=AssertionError("No data needed")), \
                patch.object(chatbot, "get_weather_data", side_effect=AssertionError("No data needed")):
            for question in ["mai thế nào?", "tư vấn mai thế nào", "mai tnao bạn"]:
                with self.subTest(question=question):
                    result = chatbot.generate_reply(question, [], self.snapshot)
                    self.assertEqual(result, {"reply": self.prompt, "truncated": False})
                    self.assertFalse(chatbot.needs_environment_data(question))
                    self.assertFalse(chatbot.needs_air_data(question))

    def test_mixed_topics_ask_but_one_clear_topic_does_not(self):
        mixed = [{"role": "user", "content": "Thời tiết và không khí ở Đà Nẵng hôm nay thế nào?"},
                 {"role": "assistant", "content": "Đã xem cả hai chỉ số."}]
        self.assertEqual(chatbot.generate_reply("mai thế nào", mixed, self.snapshot)["reply"], self.prompt)
        self.assertFalse(chatbot.needs_environment_data("mai thế nào", mixed))
        self.assertFalse(chatbot.needs_air_data("mai thế nào", mixed))
        weather = [{"role": "user", "content": "Thời tiết hôm nay thế nào?"},
                   {"role": "assistant", "content": "27 độ."}]
        with patch.object(air, "local_now", return_value=self.now), \
                patch.object(chatbot, "get_weather_data", return_value=self.data()):
            reply = chatbot.generate_reply("mai thế nào", weather, self.snapshot)["reply"]
        self.assertIn("23–30 °C", reply)
        self.assertNotIn("Bạn muốn", reply)

    def test_choice_uses_original_day_and_selected_place_instead_of_current_readings(self):
        with patch.object(air, "local_now", return_value=self.now), \
                patch.object(chatbot, "get_weather_data", return_value=self.data()), \
                patch.object(chatbot, "get_air_data", return_value=self.data()), \
                patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use real forecast reader")):
            for choice, expected, excluded in [("thời tiết", "23–30 °C", "AQI"),
                                                ("mình chọn không khí nhé", "160–175", "°C"),
                                                ("mình muốn xem thời tiết nhé", "23–30 °C", "AQI"),
                                                ("AQI", "160–175", "°C"),
                                                ("nhiệt độ", "23–30 °C", "độ ẩm"),
                                                ("cái đầu", "23–30 °C", "AQI")]:
                with self.subTest(choice=choice):
                    reply = chatbot.generate_reply(choice, self.pending(), self.snapshot)["reply"]
                    self.assertIn("Hà Nội", reply)
                    self.assertIn("22/10", reply)
                    self.assertIn(expected, reply)
                    self.assertNotIn(excluded, reply)
                    self.assertNotIn("99", reply)
                    self.assertNotIn("Bạn muốn", reply)

    def test_mixed_context_choice_keeps_named_city_across_subsequent_time_change(self):
        context = [{"role": "user", "content": "Nhiệt độ và không khí ở Đà Nẵng hôm nay thế nào?"},
                   {"role": "assistant", "content": "Số liệu cũ 999."}]
        pending = self.pending(context)
        with patch.object(air, "local_now", return_value=self.now), \
                patch.object(chatbot, "get_weather_data", return_value=self.data()) as fetch, \
                patch.object(chatbot, "get_air_data", side_effect=AssertionError("Weather choice")):
            first = chatbot.generate_reply("thời tiết", pending, self.snapshot)["reply"]
            self.assertIn("Đà Nẵng", first)
            self.assertIn("23–30 °C", first)
            history = pending + [{"role": "user", "content": "thời tiết"},
                                 {"role": "assistant", "content": first}]
            second = chatbot.generate_reply("Còn ngày kia?", history, self.snapshot)["reply"]
        self.assertIn("Đà Nẵng", second)
        self.assertIn("23/10", second)
        self.assertIn("19 °C", second)
        self.assertNotIn("AQI", second)
        self.assertEqual(fetch.call_args.args[0]["MaDiaDiem"], "danang")

    def test_both_is_a_valid_choice_and_returns_both_topics_for_same_day(self):
        with patch.object(air, "local_now", return_value=self.now), \
                patch.object(chatbot, "get_weather_data", return_value=self.data()), \
                patch.object(chatbot, "get_air_data", return_value=self.data()):
            reply = chatbot.generate_reply("cả hai", self.pending(), self.snapshot)["reply"]
        self.assertIn("23–30 °C", reply)
        self.assertIn("160–175", reply)
        self.assertNotIn("99", reply)
        self.assertEqual(reply.count("22/10"), 2)
        self.assertFalse(chatbot.generate_reply("cả hai", [
            {"role": "user", "content": "hôm nay thế nào?"},
            {"role": "assistant", "content": "Bạn muốn xem thời tiết hay chất lượng không khí hôm nay?"}],
            self.snapshot)["truncated"])

    def test_full_new_question_overrides_pending_time_and_topic(self):
        with patch.object(air, "local_now", return_value=self.now), \
                patch.object(chatbot, "get_weather_data", return_value=self.data()) as fetch:
            reply = chatbot.generate_reply("Ngày kia thời tiết Đà Nẵng thế nào?", self.pending(), self.snapshot)["reply"]
        self.assertIn("23/10", reply)
        self.assertIn("Đà Nẵng", reply)
        self.assertIn("19 °C", reply)
        self.assertEqual(fetch.call_args.args[0]["MaDiaDiem"], "danang")

    def test_unrelated_requests_and_intervening_topics_stay_out_of_scope(self):
        switched = self.pending() + [{"role": "user", "content": "Viết code Python"},
                                     {"role": "assistant", "content": OUT_OF_SCOPE_REPLY}]
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("No environmental inference")), \
                patch.object(chatbot, "_conversation_reply", return_value={"reply": "Trả lời theo chủ đề mới.", "truncated": False}):
            for message, history in [("Viết code Python", self.pending()),
                                     ("mai nên đầu tư Bitcoin không", self.pending()),
                                     ("mai thế nào", switched)]:
                self.assertEqual(chatbot.generate_reply(message, history, self.snapshot)["reply"], "Trả lời theo chủ đề mới.")

    def test_social_turn_does_not_lose_pending_choice_and_unknown_choice_can_ask_again(self):
        history = self.pending()
        self.assertEqual(chatbot.generate_reply("mình chưa biết", history, self.snapshot)["reply"], self.prompt)
        history += [{"role": "user", "content": "mình chưa biết"},
                    {"role": "assistant", "content": self.prompt}]
        history += [{"role": "user", "content": "Cảm ơn nhé"},
                    {"role": "assistant", "content": "Không có gì nhé!"}]
        with patch.object(air, "local_now", return_value=self.now), \
                patch.object(chatbot, "get_weather_data", return_value=self.data()):
            reply = chatbot.generate_reply("thời tiết", history, self.snapshot)["reply"]
        self.assertIn("22/10", reply)
        self.assertIn("23–30 °C", reply)

    def test_json_and_stream_ask_without_sql_then_weather_choice_gets_forecast(self):
        with patch.object(backend, "query", side_effect=AssertionError("No SQL for clarification/weather")), \
                patch.object(chatbot, "_load_runtime", side_effect=AssertionError("No inference")), \
                patch.object(chatbot, "get_weather_data", return_value=self.data()), \
                patch.object(air, "local_now", return_value=self.now):
            client = backend.app.test_client()
            for body in [{"message": "mai thế nào"},
                         {"message": "mai thế nào", "history": [
                             {"role": "user", "content": "Thời tiết và không khí hôm nay thế nào?"},
                             {"role": "assistant", "content": "Đã xem hai chỉ số."}]},
                         {"message": "thời tiết", "history": self.pending()}]:
                body["location"] = "hanoi"
                complete = client.post("/api/chat", json=body)
                streamed = client.post("/api/chat", json={**body, "stream": True}, buffered=True)
                self.assertEqual(complete.status_code, 200)
                events = [json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines()
                          if line.startswith("data: ")]
                self.assertEqual(events[-1], {"type": "done", **complete.get_json()})
            self.assertIn("23–30 °C", complete.get_json()["reply"])


if __name__ == "__main__":
    unittest.main()
