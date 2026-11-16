"""General conversation uses the model; environmental facts keep their own route."""

import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import app as backend
import chatbot
from chat_scope import OUT_OF_SCOPE_REPLY, is_environment_question
from native_chatbot import NativeChatbot


EXPECTED = "Bạn đang muốn trao đổi cụ thể về phần nào?"


class ConversationRuntime(NativeChatbot):
    def __init__(self, answer=EXPECTED):
        self.answer = answer
        self.messages = None

    def generate(self, messages, max_tokens, on_text=None, cancelled=None):
        self.messages = messages
        if on_text:
            # Exercise the same filter with a retired greeting split across chunks.
            for start in range(0, len(self.answer), 9):
                on_text(self.answer[start:start + 9])
        return {"reply": self.answer, "truncated": False}


class ChatScopeTests(unittest.TestCase):
    def test_unrelated_requests_use_model_without_dashboard_injection(self):
        questions = [
            "Viết code Python giúp tôi",
            "Bạn có biết nấu phở không?", "Có nên đầu tư Bitcoin không?",
            "Kể chuyện cười đi", "Giải phương trình x + 2 = 5",
            "Đội nào vô địch World Cup?", "Tôi bị đau bụng, uống thuốc gì?",
            "What is the capital of France?", "Giải thích chi tiết",
            "Có nên mua máy tính mới không?", "Môi trường lập trình Python là gì?",
        ]
        runtime = ConversationRuntime()
        with patch.object(chatbot, "_load_runtime", return_value=runtime) as load:
            for question in questions:
                with self.subTest(question=question):
                    result = chatbot.generate_reply(question, [], {"DuLieu": {"US_AQI": 987654}})
                    self.assertEqual(result, {"reply": EXPECTED, "truncated": False})
                    self.assertEqual(runtime.messages[-1], {"role": "user", "content": question})
                    self.assertNotIn("987654", json.dumps(runtime.messages, ensure_ascii=False))
                    self.assertNotIn("Dữ liệu bảng giám sát", json.dumps(runtime.messages, ensure_ascii=False))
        self.assertEqual(load.call_count, len(questions))

    def test_environment_weather_noise_and_application_questions_stay_in_scope(self):
        for question in ["AQI hiện tại bao nhiêu?", "PM2,5 là gì?", "Nhiệt độ đang 38 độ có nên ra ngoài?",
                         "Tác hại của tiếng ồn", "Phân loại rác thế nào?", "Tái chế chai nhựa thế nào?",
                         "Độ ẩm cao có ảnh hưởng gì?", "Cách trồng cây xanh ở đô thị",
                         "Vì sao hạt bụi nhỏ ảnh hưởng phổi?", "Anh Đạt có nên ra ngoài không?",
                         "Tại sao bảng giám sát chậm cập nhật?", "Địa điểm đang chọn là gì?",
                         "What is air pollution?", "Bộ lọc HEPA có tác dụng gì?",
                         "Mưa hình thành thế nào?", "Trời đang mưa không?", "CO là gì?"]:
            with self.subTest(question=question):
                self.assertTrue(is_environment_question(question))

    def test_all_current_knowledge_questions_stay_in_scope(self):
        path = Path(__file__).resolve().parents[1] / "data/xanhnon/knowledge.json"
        for document in json.loads(path.read_text(encoding="utf-8"))["documents"]:
            for question in document["questions"]:
                with self.subTest(question=question):
                    self.assertTrue(is_environment_question(question))

    def test_short_followup_inherits_environment_context(self):
        history = [{"role": "user", "content": "AQI là gì?"},
                   {"role": "assistant", "content": "AQI là chỉ số chất lượng không khí."}]
        for question in ["Giải thích chi tiết", "Nói rõ hơn", "Cho ví dụ", "Còn 150 thì sao?",
                         "Thế còn trẻ em thì sao?", "Nó có nguy hiểm không?",
                         "Nói dễ hiểu hơn một chút được không?", "Giúp mình phân tích thêm nhé",
                         "Thế còn với trẻ em thì sao bạn?", "Nó có thể đi sâu tới phổi không bạn?",
                         "Vậy mình cần chú ý gì?", "Cho mình ví dụ được không?",
                         "Hãy viết tiếp câu trả lời trước từ chỗ đang dở, không lặp lại nội dung đã viết."]:
            with self.subTest(question=question):
                self.assertTrue(is_environment_question(question, history))
        with patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Known follow-up uses verified facts")):
            result = chatbot.generate_reply("Giải thích chi tiết", history)
        self.assertIn("AQI là chỉ số", result["reply"])
        self.assertIn("151–200", result["reply"])
        self.assertNotEqual(result["reply"], OUT_OF_SCOPE_REPLY)

    def test_unrelated_new_topic_uses_conversation_despite_previous_environment_context(self):
        history = [{"role": "user", "content": "AQI là gì?"},
                   {"role": "assistant", "content": "AQI là chỉ số chất lượng không khí."}]
        with patch.object(chatbot, "_load_runtime", return_value=ConversationRuntime()):
            for question in ["Viết code Python", "Giải thích chi tiết về bóng đá", "Cho ví dụ về đầu tư chứng khoán",
                             "Giúp mình phân tích đầu tư Bitcoin nhé", "Nói dễ hiểu hơn về nấu ăn được không?"]:
                with self.subTest(question=question):
                    self.assertEqual(chatbot.generate_reply(question, history)["reply"], EXPECTED)

    def test_unrelated_turn_breaks_followup_context(self):
        history = [{"role": "user", "content": "AQI là gì?"}, {"role": "assistant", "content": "Chỉ số chất lượng không khí."},
                   {"role": "user", "content": "Viết code Python"}, {"role": "assistant", "content": EXPECTED}]
        self.assertFalse(is_environment_question("Giải thích chi tiết", history))
        # Assistant output alone must not create a new environment topic.
        history = [{"role": "user", "content": "Viết code Python"},
                   {"role": "assistant", "content": "AQI là chỉ số chất lượng không khí."}]
        self.assertFalse(is_environment_question("Nói rõ hơn", history))

    def test_json_and_stream_return_the_identical_unrelated_reply(self):
        client = backend.app.test_client()
        with patch.object(chatbot, "_load_runtime", return_value=ConversationRuntime()):
            complete = client.post("/api/chat", json={"message": "Có nên đầu tư Bitcoin không?"})
            streamed = client.post("/api/chat", json={"message": "Có nên đầu tư Bitcoin không?", "stream": True}, buffered=True)
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(streamed.status_code, 200)
        events = [json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines() if line.startswith("data: ")]
        self.assertEqual(complete.get_json(), {"reply": EXPECTED, "truncated": False})
        self.assertEqual("".join(event["text"] for event in events if event["type"] == "delta"), EXPECTED)
        self.assertEqual(sum(event["type"] == "done" for event in events), 1)
        self.assertEqual(events[-1], {"type": "done", "reply": EXPECTED, "truncated": False})

    def test_model_cannot_reintroduce_retired_greeting_in_json_or_stream(self):
        answer = OUT_OF_SCOPE_REPLY + ". Mình chưa rõ bạn muốn giải thích phần nào."
        runtime = ConversationRuntime(answer)
        with patch.object(chatbot, "_load_runtime", return_value=runtime):
            complete = chatbot.generate_reply("Giải thích chi tiết", [], None)
            events = [json.loads(frame[6:]) for frame in chatbot.stream_reply("Giải thích chi tiết", [], None)
                      if frame.startswith("data: ")]
        self.assertEqual(complete["reply"], "Mình chưa rõ bạn muốn giải thích phần nào.")
        self.assertEqual(events[-1]["reply"], complete["reply"])
        self.assertEqual("".join(e["text"] for e in events if e["type"] == "delta"), complete["reply"])
        self.assertNotIn(OUT_OF_SCOPE_REPLY, json.dumps(events, ensure_ascii=False))

    def test_general_conversation_works_with_each_prompt_profile(self):
        for profile in ["legacy", "grounded-v15", "grounded-v16"]:
            runtime = ConversationRuntime("Bạn muốn kể chuyện vui hay chuyện về cuộc sống?")
            with self.subTest(profile=profile), patch.object(chatbot, "MODEL_PROMPT_PROFILE", profile), \
                    patch.object(chatbot, "_load_runtime", return_value=runtime):
                reply = chatbot.generate_reply("Kể chuyện cười đi", [], None)["reply"]
                self.assertEqual(reply, runtime.answer)
                self.assertNotIn("Chứng cứ cho câu hỏi", runtime.messages[-1]["content"])


if __name__ == "__main__":
    unittest.main()
