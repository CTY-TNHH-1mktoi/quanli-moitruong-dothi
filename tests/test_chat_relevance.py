"""Keep each answer focused without hiding missing data needed by the question."""

import json
from datetime import datetime
import unittest
from unittest.mock import Mock, patch

import app as backend
import chatbot
from chat_output import ReplyFilter, clean_reply
from location_catalog import get_location


EXTRA = "Không có thông tin cụ thể về chất lượng không khí trong câu hỏi của bạn."
EXPECTED_WEATHER = "Ở Hà Nội hiện 24.8 °C, độ ẩm 95%."


class AnswerRelevanceTests(unittest.TestCase):
    @staticmethod
    def snapshot(**changes):
        return {"DiaDiem": get_location("hanoi"), "ThoiGian": "2026-10-19T09:00:00",
                "DuLieu": {"NhietDo": 24.8, "DoAm": 95, "TiengOn": 74.99,
                           "US_AQI": 175, "PM25": 45.4, "PM10": 60, **changes}}

    def test_weather_facts_return_only_temperature_and_humidity(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Weather facts do not need a model")):
            for question in ["Thời tiết hiện tại ở Hà Nội thế nào?", "Thời tiết bây giờ thế nào?",
                             "Thời tiết Hà Nội hôm nay?"]:
                with self.subTest(question=question):
                    result = chatbot.generate_reply(question, [], self.snapshot())
                    self.assertEqual(result, {"reply": EXPECTED_WEATHER, "truncated": False})

    def test_individual_measurement_does_not_add_other_measurements(self):
        cases = [("Nhiệt độ hiện tại bao nhiêu?", "Ở Hà Nội hiện là 24.8 °C."),
                 ("Bây giờ bao nhiêu độ?", "Ở Hà Nội hiện là 24.8 °C."),
                 ("Độ ẩm hiện tại bao nhiêu?", "Độ ẩm ở Hà Nội hiện là 95%.")]
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("No model needed")):
            for question, expected in cases:
                with self.subTest(question=question):
                    self.assertEqual(chatbot.generate_reply(question, [], self.snapshot())["reply"], expected)

    def test_missing_aqi_does_not_add_a_warning_to_weather_answer(self):
        reply = chatbot.generate_reply("Thời tiết hiện tại ở Hà Nội thế nào?", [], self.snapshot(US_AQI=None))["reply"]
        self.assertEqual(reply, EXPECTED_WEATHER)
        self.assertNotIn("AQI", reply)

    def test_only_requested_missing_measurement_is_reported(self):
        reply = chatbot.generate_reply("Độ ẩm hiện tại bao nhiêu?", [], self.snapshot(DoAm=None))["reply"]
        self.assertEqual(reply, "Mình chưa có số đo độ ẩm ở Hà Nội.")
        self.assertEqual(chatbot.generate_reply("Thời tiết hiện tại thế nào?", [],
                                              self.snapshot(NhietDo=None, DoAm=None))["reply"],
                         "Mình chưa có số liệu thời tiết ở Hà Nội.")
        # An unreported field is not treated as zero or appended to a broad summary.
        reply = chatbot.generate_reply("Thời tiết hiện tại thế nào?", [], self.snapshot(DoAm=None))["reply"]
        self.assertEqual(reply, "Ở Hà Nội hiện 24.8 °C.")

    def test_numeric_validity_zero_and_negative_temperature_are_preserved(self):
        reply = chatbot.generate_reply("Thời tiết hiện tại thế nào?", [], self.snapshot(NhietDo=-5, DoAm=0))["reply"]
        self.assertEqual(reply, "Ở Hà Nội hiện -5 °C, độ ẩm 0%.")
        for invalid in [True, float("nan"), float("inf"), -1, 101, "95"]:
            with self.subTest(humidity=invalid):
                reply = chatbot.generate_reply("Độ ẩm hiện tại bao nhiêu?", [], self.snapshot(DoAm=invalid))["reply"]
                self.assertEqual(reply, "Mình chưa có số đo độ ẩm ở Hà Nội.")

    def test_forecast_hypothetical_and_causal_questions_do_not_receive_current_weather(self):
        for question in ["Thời tiết ngày mai thế nào?", "Thời tiết hôm qua thế nào?",
                         "Nếu nhiệt độ là 40 độ C thì sao?", "Vì sao độ ẩm cao?",
                         "Thời tiết hiện tại có mưa không?", "Thời tiết hôm nay có nên ra ngoài?"]:
            with self.subTest(question=question):
                self.assertIsNone(chatbot._weather_reply(question, [], self.snapshot()))

    def test_weather_never_inherits_measurements_from_another_city(self):
        snapshot = {**self.snapshot(), "DiaDiem": get_location("tphcm")}
        with patch.object(chatbot,'get_weather_data',side_effect=chatbot.WeatherDataUnavailable()):
            reply = chatbot.generate_reply("Thời tiết hiện tại ở Hà Nội thế nào?", [], snapshot)["reply"]
        self.assertIn("chưa có số liệu thời tiết", reply)
        self.assertNotIn("24.8", reply)

    def test_detailed_weather_prompt_does_not_receive_air_noise_or_unrelated_reference(self):
        runtime = chatbot.NativeChatbot.__new__(chatbot.NativeChatbot)
        runtime.generate = Mock(return_value={"reply": EXPECTED_WEATHER, "truncated": False})
        with patch.object(chatbot, "_load_runtime", return_value=runtime):
            chatbot.generate_reply("Giải thích chi tiết thời tiết hiện tại ở Hà Nội", [], self.snapshot())
        prompt = runtime.generate.call_args.args[0][-1]["content"]
        self.assertNotIn("AQI", runtime.generate.call_args.args[0][0]["content"])
        self.assertIn("Nhiệt độ: 24.8", prompt)
        self.assertIn("Độ ẩm: 95", prompt)
        for unrelated in ["US AQI", "PM2.5", "PM10", "Tiếng ồn", "NoiseCapture", "Cầu Giấy", "epa.gov"]:
            self.assertNotIn(unrelated, prompt)

    def test_explicit_multi_topic_question_keeps_all_requested_fields(self):
        fields = chatbot._requested_fields("Thời tiết, AQI và tiếng ồn hiện tại thế nào?")
        self.assertEqual(set(fields), {"NhietDo", "DoAm", "US_AQI", "TiengOn"})
        prompt = chatbot._dashboard_context(self.snapshot(), fields)
        self.assertIn("US AQI: 175", prompt)
        self.assertIn("Tiếng ồn: 74.99", prompt)
        self.assertIn("Nhiệt độ: 24.8", prompt)
        self.assertNotIn("PM2.5", prompt)

    def test_general_explanations_never_receive_current_measurements(self):
        for question in ["Bạn giải thích AQI dễ hiểu được không?", "PM2.5 nhỏ tới mức nào?",
                         "PM2.5 với PM10 khác nhau ở đâu?", "Bụi mịn từ đâu tới?",
                         "Ở trong phòng là hết lo bụi mịn rồi phải không?",
                         "Giả sử AQI lên 175 thì sao?"]:
            with self.subTest(question=question):
                context = chatbot._dashboard_context(self.snapshot(), chatbot._requested_fields(question))
                for reading in ["175", "45.4", "24.8", "NoiseCapture"]:
                    self.assertNotIn(reading, context)

    def test_conceptual_followup_keeps_topic_without_current_readings(self):
        history = [{"role": "user", "content": "PM2.5 là gì?"},
                   {"role": "assistant", "content": "Là bụi mịn."}]
        self.assertEqual(chatbot._requested_fields("Nó có thể đi sâu tới phổi không bạn?", history), ())

    def test_noise_context_has_its_own_source_and_no_unrelated_fields(self):
        prompt = chatbot._dashboard_context(self.snapshot(), chatbot._requested_fields("Tiếng ồn hiện tại bao nhiêu?"))
        self.assertIn("NoiseCapture", prompt)
        self.assertIn("74.99", prompt)
        for unrelated in ["Open-Meteo", "US AQI", "Nhiệt độ", "Độ ẩm", "PM2.5"]:
            self.assertNotIn(unrelated, prompt)

    def test_measurement_question_does_not_append_unsolicited_aqi_activity_advice(self):
        reply = chatbot.generate_reply("AQI hiện tại bao nhiêu?", [], self.snapshot())["reply"]
        self.assertIn("175 (Xấu)", reply)
        self.assertNotIn("hoạt động ngoài trời", reply)
        # Activity questions still need and retain missing-AQI notices.
        reply = chatbot.generate_reply("Có nên ra ngoài không?", [], self.snapshot(US_AQI=None))["reply"]
        self.assertIn("chưa đủ dữ liệu", reply)

    def test_hypothetical_aqi_uses_given_value_and_verified_category(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Verified AQI lookup needs no model")):
            for value, current, category in [(175, 42, "Xấu"), (42, 175, "Tốt")]:
                with self.subTest(value=value):
                    reply = chatbot.generate_reply(f"Giả sử US AQI lên {value} thì nên tập ngoài trời ra sao?", [],
                                                   self.snapshot(US_AQI=current))["reply"]
                    self.assertIn(f"US AQI {value} thuộc mức {category}", reply)
                    self.assertNotIn(str(current), reply)
        self.assertIsNone(chatbot._grounded_reply("Nếu AQI 175 và nhiệt độ 40 độ thì có nên ra ngoài?", [], self.snapshot()))

    def test_comparison_and_particle_followup_keep_needed_facts(self):
        history = [{"role": "user", "content": "PM2.5 là gì?"},
                   {"role": "assistant", "content": "Đó là bụi mịn."}]
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use reviewed facts")):
            comparison = chatbot.generate_reply("PM2.5 với PM10 khác nhau ở điểm chính nào? Nói ngắn thôi.", [], self.snapshot())["reply"]
            self.assertIn("2,5", comparison)
            self.assertIn("10 µm", comparison)
            followup = chatbot.generate_reply("Nó có thể đi sâu tới phổi không bạn?", history, self.snapshot())["reply"]
            self.assertIn("phổi", followup)
            self.assertNotIn("chẩn đoán", followup)

    def test_question_comment_is_removed_before_stream_deltas(self):
        for raw in [EXPECTED_WEATHER + " " + EXTRA, EXPECTED_WEATHER + "\n\n" + EXTRA,
                    EXPECTED_WEATHER + " Không có thông tin về PM2.5 trong câu hỏi của bạn."]:
            emitted = []
            output = ReplyFilter(emitted.append)
            for character in raw:
                output.feed(character)
            self.assertEqual(output.finish(), EXPECTED_WEATHER)
            self.assertEqual("".join(emitted), EXPECTED_WEATHER)
        warning = "Chưa có US AQI hợp lệ tại Hà Nội, nên mình chưa đủ dữ liệu để đánh giá không khí."
        self.assertEqual(clean_reply(warning), warning)

    def test_weather_json_and_stream_match(self):
        client = backend.app.test_client()
        cache = {"hanoi": {"result": {**self.snapshot(), "ThoiGian": datetime.now().isoformat()}}}
        with patch.object(backend, "environment_cache", cache), \
                patch.object(chatbot, "_load_runtime", side_effect=AssertionError("No model needed")):
            complete = client.post("/api/chat", json={"message": "Thời tiết hiện tại ở Hà Nội thế nào?"})
            streamed = client.post("/api/chat", json={"message": "Thời tiết hiện tại ở Hà Nội thế nào?", "stream": True}, buffered=True)
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(streamed.status_code, 200)
        events = [json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines() if line.startswith("data: ")]
        self.assertEqual(complete.get_json(), {"reply": EXPECTED_WEATHER, "truncated": False})
        self.assertEqual("".join(event["text"] for event in events if event["type"] == "delta"), EXPECTED_WEATHER)
        self.assertEqual(events[-1], {"type": "done", "reply": EXPECTED_WEATHER, "truncated": False})


if __name__ == "__main__":
    unittest.main()
