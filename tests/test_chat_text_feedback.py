import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import app as backend
import chatbot
from chat_feedback import FeedbackStore, is_helpful_message


class TextFeedbackTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = FeedbackStore(Path(temporary.name) / "feedback.sqlite3")
        self.client = backend.app.test_client()
        self.history = [{"role": "user", "content": "PM2.5 là gì?"},
                        {"role": "assistant", "content": "PM2.5 là bụi mịn, thường không quá 2,5 micromet."}]

    def post(self, message="hữu ích", history=None, **changes):
        with patch.object(backend, "feedback_store", self.store), \
                patch.object(backend, "chat_snapshot", side_effect=AssertionError("Feedback needs no data or model")), \
                patch.object(backend, "generate_reply", side_effect=AssertionError("No inference")), \
                patch.object(backend, "stream_reply", side_effect=AssertionError("No inference")):
            return self.client.post("/api/chat", json={"message": message, "location": "hanoi",
                "history": self.history if history is None else history, **changes}, buffered=True)

    def test_plain_helpful_saves_previous_answer_and_responds_without_model(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"reply": "Cảm ơn bạn, mình đã ghi nhận!", "truncated": False})
        rows = self.store.list()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["payload"]["rating"], "helpful")
        self.assertEqual(rows[0]["payload"]["message"], self.history[0]["content"])
        self.assertEqual(rows[0]["payload"]["reply"], self.history[1]["content"])
        self.assertEqual(rows[0]["status"], "pending")

    def test_natural_positive_phrases_do_not_match_negations_or_questions(self):
        for text in ["hữu ích", "huu ich", "rất hữu ích!", "hữu ích quá", "hữu ích, cảm ơn bạn",
                     "câu trả lời này rất hữu ích nhé"]:
            with self.subTest(text=text):
                self.assertTrue(is_helpful_message(text))
        for text in ["không hữu ích", "chưa hữu ích", "hữu ích là gì?", "câu này có hữu ích không?",
                     "Nếu hữu ích thì làm gì?", "thời tiết mai thế nào?"]:
            self.assertFalse(is_helpful_message(text), text)

    def test_stream_and_json_match_and_retry_does_not_duplicate_feedback(self):
        complete = self.post().get_json()
        response = self.post(stream=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")
        events = [json.loads(line[6:]) for line in response.get_data(as_text=True).splitlines() if line.startswith("data: ")]
        self.assertEqual(events[-1], {"type": "done", **complete})
        self.assertEqual("".join(event["text"] for event in events if event["type"] == "delta"), complete["reply"])
        self.assertEqual(len(self.store.list()), 1)

    def test_repeated_feedback_and_polite_turns_target_original_answer(self):
        self.post()
        history = self.history + [{"role": "user", "content": "hữu ích"},
            {"role": "assistant", "content": "Cảm ơn bạn, mình đã ghi nhận!"},
            {"role": "user", "content": "Cảm ơn"}, {"role": "assistant", "content": "Không có gì nhé!"}]
        self.assertEqual(self.post(history=history).status_code, 200)
        rows = self.store.list()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["payload"]["message"], "PM2.5 là gì?")

    def test_no_previous_answer_does_not_create_database_or_claim_saved(self):
        response = self.post(history=[])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["reply"], "Cảm ơn bạn nhé!")
        self.assertFalse(self.store.path.exists())

    def test_helpful_acknowledgement_preserves_topic_for_next_question(self):
        history = [{"role": "user", "content": "Thời tiết hôm nay thế nào?"},
                   {"role": "assistant", "content": "Đang xem thời tiết."},
                   {"role": "user", "content": "hữu ích"},
                   {"role": "assistant", "content": "Cảm ơn bạn, mình đã ghi nhận!"}]
        resolved = chatbot._plain_question(chatbot._dialogue_question("Còn mai?", history))
        self.assertIn("thoi tiet", resolved)
        self.assertIn("mai", resolved)
        self.assertNotIn("huu ich", resolved)

    def test_context_and_location_are_preserved(self):
        history = self.history * 3 + [{"role": "user", "content": "Còn PM10?"},
                                    {"role": "assistant", "content": "PM10 thường không quá 10 micromet."}]
        response = self.post(history=history, location="tphcm")
        self.assertEqual(response.status_code, 200)
        payload = self.store.list()[0]["payload"]
        self.assertEqual(payload["location"], "tphcm")
        self.assertEqual(payload["history"], history[-6:-2])
        self.assertEqual(payload["message"], "Còn PM10?")

    def test_failed_save_is_not_reported_as_success_and_can_be_retried(self):
        with patch.object(self.store, "submit", side_effect=sqlite3.OperationalError("busy")):
            result = self.post().get_json()
        self.assertIn("chưa lưu được", result["reply"])
        self.assertFalse(self.store.path.exists())
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(len(self.store.list()), 1)

    def test_cross_origin_feedback_is_rejected(self):
        with patch.object(backend, "feedback_store", self.store):
            response = self.client.post("/api/chat", json={"message": "hữu ích", "history": self.history},
                                        headers={"Origin": "https://unrelated.example"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.store.path.exists())


if __name__ == "__main__":
    unittest.main()
