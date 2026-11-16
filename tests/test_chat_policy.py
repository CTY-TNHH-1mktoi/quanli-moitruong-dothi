"""Regression coverage for concise, grounded Xanh Non responses."""

import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import chatbot
from location_catalog import get_location


class ChatGroundingTests(unittest.TestCase):
    @staticmethod
    def snapshot(**readings):
        return {
            "DiaDiem": get_location("tphcm"),
            "ThoiGian": "2026-10-14T09:30:00",
            "DuLieu": readings,
            # An old saved label must not override the current measurements.
            "PhanTich": {"KetQua": "NHAN_CU_KHONG_DUOC_DUNG"},
        }

    def test_missing_aqi_does_not_inherit_an_old_label_or_infer_aqi_from_pm25(self):
        context = chatbot._dashboard_context(self.snapshot(PM25=200))
        self.assertIn("PM2.5: 200", context)
        self.assertIn("US AQI: chưa có dữ liệu", context)
        self.assertNotIn("Mức US AQI:", context)
        self.assertNotIn("NHAN_CU_KHONG_DUOC_DUNG", context)

    def test_invalid_aqi_is_missing_and_never_produces_activity_guidance(self):
        for invalid in [None, True, False, -1, float("nan"), float("inf"), "175"]:
            with self.subTest(aqi=invalid):
                context = chatbot._dashboard_context(self.snapshot(US_AQI=invalid, PM25=45))
                self.assertIn("US AQI: chưa có dữ liệu", context)
                self.assertNotIn("Mức US AQI:", context)
                self.assertNotIn("NHAN_CU_KHONG_DUOC_DUNG", context)

    def test_zero_is_a_valid_aqi_and_has_good_air_guidance(self):
        context = chatbot._dashboard_context(self.snapshot(US_AQI=0))
        self.assertIn("US AQI: 0", context)
        self.assertIn("Mức US AQI: Tốt", context)
        self.assertIn("hoạt động ngoài trời bình thường", context)

    def test_aqi_boundary_categories_use_current_numeric_readings(self):
        expected = {
            50: "Tốt", 51: "Trung bình", 100: "Trung bình", 101: "Kém",
            150: "Kém", 151: "Xấu", 200: "Xấu", 201: "Rất xấu",
            300: "Rất xấu", 301: "Nguy hại",
        }
        for aqi, category in expected.items():
            with self.subTest(aqi=aqi):
                context = chatbot._dashboard_context(self.snapshot(US_AQI=aqi))
                self.assertIn(f"Mức US AQI: {category}.", context)
                self.assertNotIn("NHAN_CU_KHONG_DUOC_DUNG", context)

    def test_bad_air_guidance_reduces_exertion_instead_of_recommending_exercise(self):
        context = chatbot._dashboard_context(self.snapshot(US_AQI=175))
        self.assertIn("giảm hoạt động ngoài trời kéo dài hoặc gắng sức", context)
        self.assertIn("nhóm nhạy cảm", context)
        self.assertNotIn("Tập thể dục thường xuyên", context)

    def test_negative_temperature_is_valid_but_invalid_pollution_is_missing(self):
        context = chatbot._dashboard_context(self.snapshot(NhietDo=-5, PM25=-2, TiengOn=float("nan")))
        self.assertIn("Nhiệt độ: -5", context)
        self.assertIn("PM2.5: chưa có dữ liệu", context)
        self.assertIn("Tiếng ồn: chưa có dữ liệu", context)
        self.assertNotIn("NoiseCapture", context)


class ChatAnswerStyleTests(unittest.TestCase):
    def test_ordinary_questions_stay_brief(self):
        for question in ["Anh Đạt có nên ra ngoài không?", "AQI là gì?", "Ở đây đang bao nhiêu độ?"]:
            with self.subTest(question=question):
                self.assertFalse(chatbot._wants_detail(question, []))

    def test_explicit_detail_requests_work_with_or_without_vietnamese_accents(self):
        for question in ["Giải thích chi tiết AQI", "Huong dan tung buoc", "So sánh hai chỉ số",
                         "Hãy phân tích sâu tác động của bụi mịn"]:
            with self.subTest(question=question):
                self.assertTrue(chatbot._wants_detail(question, []))

    def test_brief_or_negated_detail_request_overrides_detail_keywords(self):
        for question in ["So sánh ngắn gọn PM2.5 và PM10", "Không cần chi tiết, AQI là gì?",
                         "Giải thích chi tiết nhưng trả lời ngắn thôi",
                         "Không cần trả lời chi tiết, anh Đạt có nên ra ngoài không?"]:
            with self.subTest(question=question):
                self.assertFalse(chatbot._wants_detail(question, []))

    def test_continuation_preserves_the_original_style_across_multiple_turns(self):
        continuation = "Hãy viết tiếp câu trả lời trước từ chỗ đang dở, không lặp lại nội dung đã viết."
        for question, detailed in [("Giải thích chi tiết AQI", True), ("Đạt có nên ra ngoài?", False)]:
            history = [{"role": "user", "content": question}, {"role": "assistant", "content": "Phần đầu"}]
            history += [{"role": "user", "content": continuation}, {"role": "assistant", "content": "Phần tiếp"}]
            with self.subTest(question=question):
                self.assertEqual(chatbot._wants_detail(continuation, history), detailed)
        self.assertFalse(chatbot._wants_detail(continuation, []))

    def test_old_detail_request_does_not_expand_a_new_ordinary_question(self):
        history = [{"role": "user", "content": "Giải thích chi tiết"},
                   {"role": "assistant", "content": "Một bài dài"}]
        self.assertFalse(chatbot._wants_detail("Đạt có nên ra ngoài không?", history))


class ChatGenerationPolicyTests(unittest.TestCase):
    def setUp(self):
        # Exercise generation budgets only after the verified-answer route declines.
        source_route = patch.object(chatbot, "concept_answer", return_value=None)
        source_route.start()
        self.addCleanup(source_route.stop)

    @staticmethod
    def native_runtime():
        runtime = chatbot.NativeChatbot.__new__(chatbot.NativeChatbot)
        runtime.generate = Mock(return_value={"reply": "Có thể ra ngoài.", "truncated": False})
        return runtime

    def test_native_backend_receives_short_or_detail_budget(self):
        runtime = self.native_runtime()
        with patch.object(chatbot, "_load_runtime", return_value=runtime), \
                patch.object(chatbot, "MAX_NEW_TOKENS", 256), \
                patch.object(chatbot, "DETAIL_MAX_NEW_TOKENS", 768):
            for question, expected in [("Tại sao bảng giám sát chậm cập nhật?", 256), ("Giải thích chi tiết AQI", 768)]:
                with self.subTest(question=question):
                    chatbot._generate(question, [], None)
                    self.assertEqual(runtime.generate.call_args.args[1], expected)

    def test_explicit_unlimited_override_is_preserved_for_both_styles(self):
        runtime = self.native_runtime()
        with patch.object(chatbot, "_load_runtime", return_value=runtime), \
                patch.object(chatbot, "MAX_NEW_TOKENS", -1):
            for question in ["Tại sao bảng giám sát chậm cập nhật?", "Giải thích chi tiết AQI"]:
                with self.subTest(question=question):
                    chatbot._generate(question, [], None)
                    self.assertEqual(runtime.generate.call_args.args[1], -1)

    def test_detailed_budget_never_reduces_a_larger_configured_budget(self):
        runtime = self.native_runtime()
        with patch.object(chatbot, "_load_runtime", return_value=runtime), \
                patch.object(chatbot, "MAX_NEW_TOKENS", 1024), \
                patch.object(chatbot, "DETAIL_MAX_NEW_TOKENS", 768):
            chatbot._generate("Giải thích chi tiết AQI", [], None)
        self.assertEqual(runtime.generate.call_args.args[1], 1024)

    def test_new_snapshot_and_original_question_are_in_the_latest_turn(self):
        runtime = self.native_runtime()
        history = [{"role": "user", "content": "Hà Nội có AQI 999?"},
                   {"role": "assistant", "content": "Dữ liệu cũ: Hà Nội 999."}]
        snapshot = {"DiaDiem": get_location("tphcm"), "DuLieu": {"US_AQI": 175}}
        question = "Giải thích chi tiết: anh Đạt có nên ra ngoài không?"
        with patch.object(chatbot, "_load_runtime", return_value=runtime):
            chatbot._generate(question, history, snapshot)
        messages = runtime.generate.call_args.args[0]
        self.assertEqual(messages[1:3], history)
        self.assertIn("Hồ Chí Minh", messages[-1]["content"])
        self.assertIn("US AQI: 175", messages[-1]["content"])
        self.assertNotIn("999", messages[-1]["content"])
        self.assertTrue(messages[-1]["content"].endswith(question))

    def test_transformers_uses_request_budget_and_keeps_truncation_semantics(self):
        import torch

        class Inputs(dict):
            def to(self, device):
                return self

        class Tokenizer:
            pad_token_id = 0

            def apply_chat_template(self, messages, **kwargs):
                ids = torch.tensor([[10, 11]])
                return Inputs(input_ids=ids, attention_mask=torch.ones_like(ids))

            def decode(self, tokens, **kwargs):
                return "Có thể ra ngoài."

        class Model:
            config = SimpleNamespace(max_position_embeddings=8192)
            generation_config = SimpleNamespace(eos_token_id=[99])

            def __init__(self, ending):
                self.ending = ending
                self.budgets = []

            def generate(self, input_ids, max_new_tokens, **kwargs):
                self.budgets.append(max_new_tokens)
                return torch.cat((input_ids, torch.tensor([[105, self.ending]])), dim=1)

        with patch.object(chatbot, "MAX_NEW_TOKENS", 256), \
                patch.object(chatbot, "DETAIL_MAX_NEW_TOKENS", 768):
            for question, budget, ending, truncated in [
                ("Tại sao bảng giám sát chậm cập nhật?", 256, 99, False),
                ("Giải thích chi tiết AQI", 768, 99, False),
                ("Tại sao bảng giám sát chậm cập nhật?", 256, 106, True),
            ]:
                with self.subTest(question=question, ending=ending):
                    model = Model(ending)
                    runtime = (torch, Tokenizer(), model, "cpu")
                    with patch.object(chatbot, "_load_runtime", return_value=runtime):
                        result = chatbot._generate(question, [], None)
                    self.assertEqual(model.budgets, [budget])
                    self.assertEqual(result["truncated"], truncated)


class ChatGroundedReplyTests(unittest.TestCase):
    def tearDown(self):
        # stream_reply uses a worker; ensure it released the shared slot.
        self.assertTrue(chatbot._generation_lock.acquire(timeout=2))
        chatbot._generation_lock.release()

    @staticmethod
    def snapshot(aqi):
        return {
            "DiaDiem": get_location("tphcm"),
            "DuLieu": {"US_AQI": aqi, "PM25": 999},
            "PhanTich": {"KetQua": "Tốt", "KhuyenNghi": "Tập thể dục thường xuyên"},
        }

    def test_short_outdoor_answer_uses_valid_aqi_without_loading_a_model(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Model must not load")) as load:
            for aqi, conclusion in [(42, "có thể ra ngoài"), (175, "tránh vận động gắng sức"),
                                    (250, "hạn chế ra ngoài"), (301, "hạn chế ra ngoài")]:
                with self.subTest(aqi=aqi):
                    result = chatbot.generate_reply("a đạt có nên ra ngoài không", [], self.snapshot(aqi))
                    self.assertIn(conclusion, result["reply"])
                    self.assertIn(f"là {aqi}", result["reply"])
                    self.assertIn("Hồ Chí Minh", result["reply"])
                    self.assertFalse(result["truncated"])
                    self.assertTrue(result["reply"].endswith("."))
                    self.assertLessEqual(len(result["reply"].split()), 85)
                    for irrelevant in ["giữ ấm", "kính râm", "lây nhiễm", "Tập thể dục thường xuyên", "**"]:
                        self.assertNotIn(irrelevant, result["reply"])
            load.assert_not_called()

    def test_missing_or_invalid_aqi_cannot_give_positive_advice_from_pm25_or_saved_label(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Model must not load")):
            for aqi in [None, True, -1, float("nan"), float("inf"), "175"]:
                with self.subTest(aqi=aqi):
                    result = chatbot.generate_reply("Anh Đạt có nên ra ngoài không?", [], self.snapshot(aqi))
                    self.assertIn("chưa đủ dữ liệu", result["reply"])
                    self.assertNotIn("có thể ra ngoài", result["reply"])
                    self.assertNotIn("Tốt", result["reply"])
                    self.assertNotIn("999", result["reply"])
                    self.assertFalse(result["truncated"])

    def test_zero_aqi_is_reported_as_good_air(self):
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Model must not load")):
            result = chatbot.generate_reply("Anh Đạt có nên ra ngoài không?", [], self.snapshot(0))
        self.assertIn("là 0 (Tốt)", result["reply"])
        self.assertIn("có thể ra ngoài", result["reply"])
        self.assertNotIn("chưa đủ dữ liệu", result["reply"])

    def test_current_aqi_reply_ignores_old_city_history_and_saved_label(self):
        history = [{"role": "user", "content": "AQI Hà Nội là 999?"},
                   {"role": "assistant", "content": "Hà Nội rất nguy hiểm, AQI 999"}]
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Model must not load")):
            result = chatbot.generate_reply("AQI hiện tại bao nhiêu?", history, self.snapshot(175))
        self.assertIn("là 175 (Xấu)", result["reply"])
        self.assertIn("Hồ Chí Minh", result["reply"])
        self.assertNotIn("Hà Nội", result["reply"])
        self.assertNotIn("999", result["reply"])
        self.assertNotIn("(Tốt)", result["reply"])

    def test_grounded_stream_finishes_once_and_matches_complete_reply(self):
        snapshot = self.snapshot(175)
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Model must not load")):
            expected = chatbot.generate_reply("Anh Đạt có nên ra ngoài không?", [], snapshot)
            frames = list(chatbot.stream_reply("Anh Đạt có nên ra ngoài không?", [], snapshot))
        events = [json.loads(frame[6:]) for frame in frames if frame.startswith("data: ")]
        self.assertEqual(sum(event["type"] == "done" for event in events), 1)
        self.assertEqual("".join(event["text"] for event in events if event["type"] == "delta"), expected["reply"])
        self.assertEqual(events[-1], {"type": "done", **expected})
        self.assertFalse(events[-1]["truncated"])

    def test_weather_and_personal_medical_queries_are_not_answered_from_aqi_alone(self):
        for question in ["Trời đang mưa, có nên ra ngoài không?",
                         "Nhiệt độ đang 38 độ, có nên ra ngoài?",
                         "Tôi bị hen, có nên chạy bộ không?",
                         "Anh Đạt có nên ra ngoài khi đang đau ngực?"]:
            with self.subTest(question=question):
                self.assertIsNone(chatbot._grounded_reply(question, [], self.snapshot(42)))

    def test_aqi_definition_is_not_mistaken_for_a_current_air_assessment(self):
        runtime = chatbot.NativeChatbot.__new__(chatbot.NativeChatbot)
        runtime.generate = Mock(return_value={"reply": "AQI là chỉ số chất lượng không khí.", "truncated": False})
        with patch.object(chatbot, "_load_runtime", return_value=runtime):
            result = chatbot.generate_reply("AQI là gì?", [], self.snapshot(175))
        self.assertNotIn("là 175", result["reply"])
        self.assertNotIn("có thể ra ngoài", result["reply"])
        self.assertFalse(result["truncated"])

    def test_hypothetical_aqi_or_explicit_values_do_not_use_current_snapshot_advice(self):
        reply = chatbot._grounded_reply("Nếu AQI là 250 thì tôi có nên ra ngoài không?", [], self.snapshot(42))
        self.assertIn("250 thuộc mức Rất xấu", reply)
        self.assertNotIn("42", reply)
        for question in ["Giả sử không khí xấu, có nên ra ngoài?",
                         "AQI 250 thì có nên chạy bộ không?",
                         "AQI=250, tôi có nên ra ngoài không?"]:
            with self.subTest(question=question):
                self.assertIsNone(chatbot._grounded_reply(question, [], self.snapshot(42)))

    def test_past_or_future_questions_do_not_use_current_aqi_as_the_answer(self):
        for question in ["AQI hôm qua bao nhiêu?",
                         "Tuần sau tôi có nên ra ngoài không?",
                         "Một giờ nữa tôi có nên ra ngoài không?",
                         "AQI tháng trước như thế nào?"]:
            with self.subTest(question=question):
                self.assertIsNone(chatbot._grounded_reply(question, [], self.snapshot(42)))

    def test_another_explicit_city_does_not_inherit_selected_city_measurements(self):
        hanoi = {"DiaDiem": get_location("hanoi"), "DuLieu": {"US_AQI": 42}}
        with patch.object(chatbot, 'get_air_data', return_value={'current': {'us_aqi': 77}}) as fetch:
            for question, snapshot, place in [
                    ("AQI tại Hà Nội hiện tại bao nhiêu?", self.snapshot(42), 'hanoi'),
                    ("Ở Đà Nẵng hiện tại có nên ra ngoài không?", self.snapshot(42), 'danang'),
                    ("AQI Sài Gòn hiện tại bao nhiêu?", hanoi, 'tphcm')]:
                with self.subTest(question=question):
                    reply = chatbot._grounded_reply(question, [], snapshot)
                    self.assertIn('77', reply)
                    self.assertNotIn('42', reply)
                    self.assertEqual(fetch.call_args.args[0]['MaDiaDiem'], place)
        # An explicit name matching the selected city is still eligible.
        self.assertIsNotNone(chatbot._grounded_reply("AQI Thành phố Hồ Chí Minh hiện tại bao nhiêu?", [], self.snapshot(42)))

    def test_additional_symptoms_do_not_receive_a_simple_positive_outdoor_answer(self):
        for question in ["Đạt đang chóng mặt, có nên ra ngoài không?",
                         "Tôi đang buồn nôn, có nên ra ngoài không?",
                         "Tôi bị sốt có nên chạy bộ không?"]:
            with self.subTest(question=question):
                self.assertIsNone(chatbot._grounded_reply(question, [], self.snapshot(42)))

    def test_forecast_requests_do_not_claim_current_aqi_is_a_forecast(self):
        for question in ["Dự báo AQI ngày mai bao nhiêu?",
                         "Chiều nay tôi có nên ra ngoài không?",
                         "AQI tối nay như thế nào?"]:
            with self.subTest(question=question):
                self.assertIsNone(chatbot._grounded_reply(question, [], self.snapshot(42)))

    def test_indoor_activity_questions_do_not_receive_outdoor_guidance(self):
        for question in ["AQI xấu, có nên tập thể dục trong nhà không?",
                         "Có nên chạy bộ ở phòng tập không?"]:
            with self.subTest(question=question):
                self.assertIsNone(chatbot._grounded_reply(question, [], self.snapshot(42)))


if __name__ == "__main__":
    unittest.main()
