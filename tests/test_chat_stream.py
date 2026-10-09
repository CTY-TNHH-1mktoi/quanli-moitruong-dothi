import json
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import app as backend
import chatbot


class ChatStreamTests(unittest.TestCase):
    def setUp(self):
        self.client = backend.app.test_client()
        self.question = {"message": "Xin chào", "history": [], "stream": True}

    def tearDown(self):
        # Do not let an unfinished worker leak into the next test.
        self.assertTrue(chatbot._generation_lock.acquire(timeout=2))
        chatbot._generation_lock.release()

    @staticmethod
    def events(response):
        return [json.loads(line[6:]) for line in response.get_data(as_text=True).splitlines()
                if line.startswith("data: ")]

    @staticmethod
    def answer(message, history, snapshot, on_text=None, cancelled=None):
        if on_text:
            on_text("Xin ")
            on_text("chào 🌱")
        return {"reply": "Xin chào 🌱", "truncated": False}

    def test_stream_preserves_vietnamese_and_finishes_once(self):
        with patch.object(chatbot, "_generate", self.answer):
            response = self.client.post("/api/chat", json=self.question, buffered=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")
        events = self.events(response)
        self.assertEqual("".join(e["text"] for e in events if e["type"] == "delta"), "Xin chào 🌱")
        self.assertEqual(sum(e["type"] == "done" for e in events), 1)
        self.assertEqual(events[-1]["reply"], "Xin chào 🌱")

    def test_json_clients_still_receive_the_complete_reply(self):
        with patch.object(chatbot, "_generate", self.answer):
            response = self.client.post("/api/chat", json={"message": "Xin chào"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["reply"], "Xin chào 🌱")

    def test_followup_accepts_a_long_vietnamese_reply_in_history(self):
        previous_reply = "Nội dung chi tiết 🌱. " * 1000
        question = "Hãy phân tích thêm. " * 100
        history = [
            {"role": "user", "content": "Giải thích chi tiết."},
            {"role": "assistant", "content": previous_reply},
        ]
        with patch.object(chatbot, "_generate", side_effect=self.answer) as generate:
            response = self.client.post("/api/chat", json={"message": question, "history": history})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate.call_args.args[0], question.strip())
        self.assertEqual(generate.call_args.args[1][-1]["content"], previous_reply.strip())

    def test_stream_retains_truncation_flag_for_continuation(self):
        with patch.object(chatbot, "_generate", return_value={"reply": "Phần đầu…", "truncated": True}):
            response = self.client.post("/api/chat", json=self.question, buffered=True)
        final = self.events(response)[-1]
        self.assertEqual(final["type"], "done")
        self.assertEqual(final["reply"], "Phần đầu…")
        self.assertTrue(final["truncated"])

    def test_transformers_continues_the_same_reply_until_eos(self):
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
                return "".join({105: "a", 106: "b", 107: "c"}.get(int(token), "") for token in tokens)

        class Model:
            config = SimpleNamespace(max_position_embeddings=4096)
            generation_config = SimpleNamespace(eos_token_id=[99])

            def __init__(self):
                self.prompts = []

            def generate(self, input_ids, **kwargs):
                self.prompts.append(input_ids[0].tolist())
                new_tokens = [105, 106] if len(self.prompts) == 1 else [107, 99]
                return torch.cat((input_ids, torch.tensor([new_tokens])), dim=1)

        model = Model()
        runtime = (torch, Tokenizer(), model, "cpu")
        with patch.object(chatbot, "_load_runtime", return_value=runtime), patch.object(chatbot, "MAX_NEW_TOKENS", -1):
            result = chatbot.generate_reply("Viết đầy đủ", [])
        self.assertEqual(result, {"reply": "abc", "truncated": False})
        self.assertEqual(model.prompts, [[10, 11], [10, 11, 105, 106]])

    def test_busy_request_is_rejected_and_disconnect_cancels_worker(self):
        stopped = Event()

        def wait_until_closed(message, history, snapshot, on_text=None, cancelled=None):
            self.assertTrue(cancelled.wait(timeout=3))
            stopped.set()
            return {"reply": "Đã dừng", "truncated": True}

        with patch.object(chatbot, "_generate", wait_until_closed):
            response = self.client.post("/api/chat", json=self.question, buffered=False)
            busy = self.client.post("/api/chat", json=self.question)
            self.assertEqual(busy.status_code, 429)
            response.close()
            self.assertTrue(stopped.wait(timeout=2))

    def test_worker_error_ends_the_stream_with_an_error_event(self):
        with self.assertLogs("chatbot", level="ERROR"):
            with patch.object(chatbot, "_generate", side_effect=RuntimeError("test failure")):
                response = self.client.post("/api/chat", json=self.question, buffered=True)
        events = self.events(response)
        self.assertEqual(events[-1]["type"], "error")
        self.assertNotIn("test failure", events[-1]["loi"])


if __name__ == "__main__":
    unittest.main()
