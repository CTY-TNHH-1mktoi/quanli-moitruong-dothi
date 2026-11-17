"""Future air questions must not invent a forecast or drift into rain."""

import json
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

import app as backend
import chatbot
import chat_air_data as air
from chat_scope import OUT_OF_SCOPE_REPLY
from location_catalog import get_location


class AirForecastScopeTests(unittest.TestCase):
    snapshot = {"DiaDiem": get_location("hanoi"),
                "DuLieu": {"US_AQI": 42, "NhietDo": 24.8, "DoAm": 95}}

    def test_future_air_phrasings_stay_on_topic_without_using_current_numbers(self):
        cases = [("mai không khí thế nào", "ngày mai"),
                 ("AQI mai bao nhiêu?", "ngày mai"),
                 ("Sáng mai bụi mịn có cao không?", "sáng mai"),
                 ("Không khí ngày kia tốt hơn không?", "ngày kia"),
                 ("Tối nay AQI thế nào?", "tối nay"),
                 ("Dự báo AQI tuần tới chi tiết", "tuần tới"),
                 ("Tháng tới không khí ra sao?", "tháng tới"),
                 ("Một giờ nữa có nên đi dạo không?", "một giờ nữa"),
                 ("Mai có nên chạy bộ không?", "ngày mai")]
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("No forecast to generate")):
            for question, period in cases:
                with self.subTest(question=question):
                    reply = chatbot.generate_reply(question, [], self.snapshot)["reply"]
                    self.assertIn("chưa có dự báo chất lượng không khí", reply)
                    self.assertIn(period, reply)
                    self.assertIn("Hà Nội", reply)
                    for unrelated in ["mưa", "42", "24.8", "95", "truy cập", "cập nhật bảng"]:
                        self.assertNotIn(unrelated, reply)
                    self.assertLess(len(reply.split()), 40)
                    self.assertEqual(chatbot._requested_fields(question), ())
                    self.assertIsNone(chatbot._grounded_reply(question, [], self.snapshot))

    def test_temporal_followups_inherit_only_the_latest_user_topic(self):
        history = [{"role": "user", "content": "AQI hiện tại thế nào?"},
                   {"role": "assistant", "content": "US AQI 42."}]
        now = datetime(2026, 10, 28, 10, tzinfo=air.VN_TIME)
        times = [(now.replace(hour=0) + timedelta(hours=n)).replace(tzinfo=None).isoformat(timespec="minutes")
                 for n in range(5 * 24)]
        forecast = {"MaDiaDiem": "hanoi", "hourly": {"time": times, "us_aqi": [77] * len(times)}}
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use forecast data")), \
                patch.object(air, "local_now", return_value=now), \
                patch.object(chatbot, "get_air_data", return_value=forecast) as fetch:
            for question in ["Còn mai?", "Thế ngày kia thì sao bạn?", "Vậy cuối tuần tới?"]:
                with self.subTest(question=question):
                    reply = chatbot.generate_reply(question, history, self.snapshot)["reply"]
                    self.assertIn("US AQI khoảng 77", reply)
                    self.assertNotIn("42", reply)
            previous_calls = fetch.call_count
            history += [{"role": "user", "content": "Viết code Python"},
                        {"role": "assistant", "content": "AQI là chỉ số môi trường."}]
            with patch.object(chatbot, "_conversation_reply", return_value={"reply": "Trả lời theo chủ đề mới.", "truncated": False}):
                self.assertEqual(chatbot.generate_reply("Còn mai?", history, self.snapshot)["reply"], "Trả lời theo chủ đề mới.")
                self.assertEqual(chatbot.generate_reply("Mai nấu món gì?", history[:2], self.snapshot)["reply"], "Trả lời theo chủ đề mới.")
            self.assertEqual(fetch.call_count, previous_calls)

    def test_weather_and_conceptual_or_hypothetical_questions_are_distinct(self):
        for question in ["Mai có mưa không?", "Thời tiết ngày mai thế nào?",
                         "Dự báo AQI là gì?", "Cách dự báo không khí ngày mai?",
                         "Giả sử AQI mai là 175 thì có nên ra ngoài?"]:
            with self.subTest(question=question):
                self.assertIsNone(chatbot._air_forecast_reply(question, [], self.snapshot))
        for question in ["Mai nhiệt độ bao nhiêu?", "Sáng mai thời tiết thế nào?",
                         "Độ ẩm tuần tới?", "Nhiệt độ hai giờ nữa?"]:
            with self.subTest(question=question):
                self.assertIsNone(chatbot._weather_reply(question, [], self.snapshot))
        self.assertIn("42 (Tốt)", chatbot.generate_reply("Không khí hiện tại thế nào?", [], self.snapshot)["reply"])
        self.assertEqual(chatbot.generate_reply("Nhiệt độ hiện tại bao nhiêu?", [], self.snapshot)["reply"],
                         "Ở Hà Nội hiện là 24.8 °C.")

    def test_forecast_does_not_relabel_another_city_as_selected_place(self):
        reply = chatbot.generate_reply("Mai không khí ở Đà Nẵng thế nào?", [], self.snapshot)["reply"]
        self.assertIn("chưa có dự báo", reply)
        self.assertNotIn("Hà Nội", reply)
        history = [{"role": "user", "content": "AQI Đà Nẵng bao nhiêu?"},
                   {"role": "assistant", "content": "Chưa có số liệu."}]
        self.assertNotIn("Hà Nội", chatbot.generate_reply("Còn mai?", history, self.snapshot)["reply"])

    def test_screenshot_json_and_stream_reply_match_even_with_bad_old_reply(self):
        client = backend.app.test_client()
        body = {"message": "mai không khí thế nào", "location": "hanoi",
                "history": [{"role": "user", "content": "mai có mưa không"},
                            {"role": "assistant", "content": "Tôi không thể truy cập dữ liệu giám sát."}]}
        with patch.object(backend, "environment_cache", {"hanoi": {"result": self.snapshot}}), \
                patch.object(chatbot, "_load_runtime", side_effect=AssertionError("No model needed")):
            complete = client.post("/api/chat", json=body)
            streamed = client.post("/api/chat", json={**body, "stream": True}, buffered=True)
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(streamed.status_code, 200)
        events = [json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines()
                  if line.startswith("data: ")]
        self.assertIn("chưa có dự báo chất lượng không khí ngày mai ở Hà Nội", complete.get_json()["reply"])
        self.assertEqual("".join(event["text"] for event in events if event["type"] == "delta"), complete.get_json()["reply"])
        self.assertEqual(events[-1], {"type": "done", **complete.get_json()})


if __name__ == "__main__":
    unittest.main()
