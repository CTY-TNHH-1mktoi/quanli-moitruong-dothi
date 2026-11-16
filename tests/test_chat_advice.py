"""Practical questions need concrete measures, not an introduction alone."""

import json
import unittest
from unittest.mock import patch

import app as backend
import chatbot
from chat_knowledge import advice_topic, practical_answer
from chat_output import has_dangling_intro


class PracticalAdviceTests(unittest.TestCase):
    def test_varied_questions_get_measures_from_reviewed_topics_without_a_model(self):
        cases = [
            ("Tôi sống gần đường lớn, làm thế nào để giảm bụi vào nhà?", "indoor_dust_actions", ["khăn ẩm", "cửa", "HEPA"]),
            ("Nhà sát đường, giúp mình hạn chế bụi trong phòng ngủ", "indoor_dust_actions", ["khăn ẩm", "cửa"]),
            ("Làm sao hạn chế PM2.5 vào nhà?", "indoor_dust_actions", ["HEPA", "bụi"]),
            ("Phòng ngủ ẩm quá, xử lý ra sao?", "humidity_actions", ["rò nước", "60%"]),
            ("Cách hạn chế nấm mốc trong nhà khi nồm ẩm?", "humidity_actions", ["lau khô", "trong nhà"]),
            ("Làm gì để giảm ảnh hưởng tiếng ồn quanh chỗ ở?", "noise_actions", ["khoảng cách", "thời gian", "nút tai"]),
            ("Giảm tiếng ồn", "noise_actions", ["âm lượng", "nút tai"]),
            ("Gợi ý cách giảm rác nhựa ở nhà", "waste_actions", ["dùng lại", "thu gom"]),
            ("Muốn bắt đầu phân loại rác sinh hoạt thì làm gì?", "waste_actions", ["tái chế", "địa phương"]),
            ("Cách chọn máy lọc không khí để giảm bụi mịn?", "filter_actions", ["CADR", "HEPA"]),
            ("Trời nắng gắt, làm sao tập thể dục cho hợp lý?", "heat_actions", ["bớt nóng", "nước"]),
            ("Trời nóng quá, nên làm gì khi phải đi bộ ngoài trời?", "heat_actions", ["râm mát", "nghỉ"]),
        ]
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use source-checked measures")):
            for question, topic, needed in cases:
                with self.subTest(question=question):
                    self.assertEqual(advice_topic(question), topic)
                    reply = chatbot.generate_reply(question, [], None)
                    for word in needed:
                        self.assertIn(word, reply["reply"])
                    self.assertFalse(reply["truncated"])
                    self.assertFalse(has_dangling_intro(reply["reply"]))
                    self.assertFalse(chatbot.needs_environment_data(question))
                    self.assertLessEqual(len(reply["reply"].split()), 85)

    def test_detail_has_actual_steps_and_default_does_not_repeat_the_user_as_self(self):
        question = "Tôi sống gần đường lớn, làm thế nào để giảm bụi vào nhà?"
        reply = chatbot.generate_reply(question + " Giải thích chi tiết nhé.", [], None)["reply"]
        self.assertIn("1. Hạn chế", reply)
        self.assertIn("4. Giảm", reply)
        self.assertNotIn("Tôi sống gần đường", reply)
        self.assertFalse(has_dangling_intro(reply))

    def test_missing_device_is_respected_in_short_followup_after_thanks(self):
        history = [{"role": "user", "content": "Cách giảm bụi trong nhà?"},
                   {"role": "assistant", "content": "Có thể dùng máy lọc."},
                   {"role": "user", "content": "Cảm ơn"}, {"role": "assistant", "content": "Không có gì"}]
        reply = chatbot.generate_reply("Thế mình chưa có máy lọc", history, None)["reply"]
        self.assertIn("khăn ẩm", reply)
        self.assertNotIn("dùng máy lọc", reply)
        unrelated = [{"role": "user", "content": "Viết code Python"}, {"role": "assistant", "content": "AQI là gì"}]
        self.assertIsNone(practical_answer("Mình chưa có máy lọc", unrelated))

    def test_measurements_definitions_clinical_and_mixed_questions_are_not_hijacked(self):
        for question in ["PM2.5 trong nhà hiện tại bao nhiêu?", "Bụi trong phòng là gì?",
                         "Tại sao lau ẩm giảm bụi trong nhà?", "Tôi khó thở, làm sao giảm bụi trong nhà?",
                         "Cách giảm bụi trong nhà và tiếng ồn?", "Viết câu mở đầu về cách giảm bụi trong nhà"]:
            with self.subTest(question=question):
                self.assertIsNone(practical_answer(question))

    def test_screenshot_json_and_stream_both_include_measures(self):
        client = backend.app.test_client()
        body = {"message": "Tôi sống gần đường lớn, làm thế nào để giảm bụi vào nhà?"}
        with patch.object(backend, "query", side_effect=AssertionError("Advice needs no live SQL")), \
                patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Reviewed advice")):
            complete = client.post("/api/chat", json=body)
            streamed = client.post("/api/chat", json={**body, "stream": True}, buffered=True)
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(streamed.status_code, 200)
        events = [json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines() if line.startswith("data: ")]
        self.assertIn("khăn ẩm", complete.get_json()["reply"])
        self.assertEqual(events[-1], {"type": "done", **complete.get_json()})
        self.assertEqual("".join(e["text"] for e in events if e["type"] == "delta"), complete.get_json()["reply"])

    def test_no_filter_constraint_supports_natural_variants_across_social_turns(self):
        history = [{"role": "user", "content": "Làm sao giảm bụi từ đường vào nhà?"},
                   {"role": "assistant", "content": "Có thể dùng máy lọc phù hợp."},
                   {"role": "user", "content": "Cảm ơn nhé"}, {"role": "assistant", "content": "Không có gì"}]
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use reviewed measures without a new filter")):
            for question in ["Chưa mua được máy lọc, còn cách nào làm ngay không?",
                             "Thế nếu chưa có máy lọc thì sao?",
                             "Nếu mình không dùng máy lọc không khí thì làm gì?",
                             "Mình chưa sắm được máy lọc, có cách nào khác không?"]:
                with self.subTest(question=question):
                    answer = chatbot.generate_reply(question, history, None)["reply"]
                    self.assertIn("khăn ẩm", answer)
                    self.assertNotIn("dùng máy lọc", answer)
        self.assertIsNone(practical_answer("Chưa mua được máy lọc, điều hòa thay được không?", history))

    def test_eos_after_an_intro_is_still_marked_unfinished_for_json_and_sse(self):
        prefix = "Để giảm bụi trong nhà, bạn có thể thực hiện các biện pháp sau:"
        with patch.object(chatbot, "_generate_raw", return_value={"reply": prefix, "truncated": False}):
            complete = chatbot.generate_reply("Cho mình gợi ý", [], None)
            stream = list(chatbot.stream_reply("Cho mình gợi ý", [], None))
        events = [json.loads(frame[6:]) for frame in stream if frame.startswith("data: ")]
        self.assertTrue(complete["truncated"])
        self.assertEqual(events[-1], {"type": "done", **complete})
        self.assertEqual("".join(e["text"] for e in events if e["type"] == "delta"), prefix)

    def test_completeness_guard_keeps_real_short_answers_and_lists(self):
        for prefix in ["Bạn có thể dùng các biện pháp sau:", "Một số cách như sau.",
                       "Bạn có thể làm các bước sau:\n1."]:
            self.assertTrue(has_dangling_intro(prefix), prefix)
        for complete in ["Độ ẩm hiện tại: 95%.", "Lau bụi bằng khăn ẩm.",
                         "Các biện pháp sau:\n1. Lau ẩm.\n2. Hạn chế nguồn bụi."]:
            self.assertFalse(has_dangling_intro(complete), complete)
