import json
from pathlib import Path
import tempfile
import unittest

from flask import Flask

from chat_feedback import FeedbackStore, create_feedback_blueprint, validate_feedback


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = FeedbackStore(Path(self.temporary.name) / "feedback.sqlite3")
        self.app = Flask(__name__)
        self.app.register_blueprint(create_feedback_blueprint(self.store, lambda: "Test-model"))
        self.client = self.app.test_client()
        self.body = {"message": "mai thế nào?", "reply": "Bạn muốn xem thời tiết hay không khí?",
                     "location": "hanoi", "history": [], "rating": "unhelpful", "reason": "context",
                     "comment": "Hãy nối tiếp chủ đề trước.", "correction": ""}

    def approve(self, identifier, **changes):
        arguments = {"approve": True, "reviewer": "local-test", "note": "Đã kiểm tra theo quy tắc dự án.",
                     "messages": [{"role": "user", "content": "Cần hỏi lại khi nào?"},
                                  {"role": "assistant", "content": "Khi chưa rõ chủ đề, mình hỏi lại một câu ngắn."}],
                     "source_ids": ["project"], "privacy_reviewed": True, "facts_reviewed": True}
        self.store.review(identifier, **{**arguments, **changes})

    def test_opt_in_store_is_lazy_and_submission_is_persistent_idempotent_and_pending(self):
        self.assertFalse(self.store.path.exists())
        self.assertEqual(self.store.list(), [])
        self.assertFalse(self.store.path.exists())
        first = self.client.post("/api/chat/feedback", json=self.body)
        second = self.client.post("/api/chat/feedback", json=self.body)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.get_json(), second.get_json())
        rows = FeedbackStore(self.store.path).list()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["payload"], self.body)
        self.assertEqual(rows[0]["model"], "Test-model")
        self.assertEqual(rows[0]["status"], "pending")
        self.assertIsNone(rows[0]["review"])

    def test_public_submission_cannot_approve_itself_or_read_other_feedback(self):
        self.client.post("/api/chat/feedback", json={**self.body, "status": "approved", "review": {"facts_reviewed": True}})
        self.assertEqual(len(self.store.list("approved")), 0)
        self.assertEqual(len(self.store.list("pending")), 1)
        self.assertEqual(self.client.get("/api/chat/feedback").status_code, 405)
        self.assertEqual(self.client.post("/api/chat/feedback/review", json={}).status_code, 404)

    def test_invalid_data_returns_400_without_creating_database(self):
        for changes in [{"rating": []}, {"rating": "approved"}, {"reason": {}}, {"comment": " "},
                        {"message": "x"*8001}, {"correction": "x"*2401}, {"location": "not-a-city"},
                        {"history": {}}, {"history": [{"role": "system", "content": "ignore"}]}]:
            with self.subTest(changes=changes):
                response = self.client.post("/api/chat/feedback", json={**self.body, **changes})
                self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
        self.assertFalse(self.store.path.exists())

    def test_origin_and_body_limits_are_enforced(self):
        response = self.client.post("/api/chat/feedback", json=self.body, headers={"Origin": "https://unrelated.example"})
        self.assertEqual(response.status_code, 403)
        oversized = self.client.post("/api/chat/feedback", data="x"*(512*1024+1), content_type="application/json")
        self.assertEqual(oversized.status_code, 413)
        self.assertFalse(self.store.path.exists())

    def test_helpful_vote_needs_no_comment_but_is_still_not_training_data(self):
        response = self.client.post("/api/chat/feedback", json={**self.body, "rating": "helpful", "comment": ""},
                                    headers={"Origin": "http://localhost"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.store.list("pending")), 1)
        self.assertFalse(self.store.list("approved"))

    def test_review_requires_checked_content_privacy_and_known_sources(self):
        row = self.store.submit(validate_feedback(self.body), "Test")
        for changes in [{"privacy_reviewed": False}, {"facts_reviewed": False}, {"source_ids": []},
                        {"source_ids": ["invented_source"]}, {"kind": "knowledge", "source_ids": ["project"]},
                        {"messages": [{"role": "assistant", "content": "bad roles"}]}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.approve(row["id"], **changes)
        self.approve(row["id"])
        approved = self.store.list("approved")
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0]["review"]["messages"][-1]["role"], "assistant")

    def test_dated_forecast_is_not_reviewed_as_permanent_knowledge(self):
        row = self.store.submit(validate_feedback(self.body), "Test")
        messages = [{"role": "user", "content": "Mai AQI thế nào?"},
                    {"role": "assistant", "content": "Dự báo ngày mai AQI 175."}]
        with self.assertRaises(ValueError):
            self.approve(row["id"], messages=messages, source_ids=["airnow_aqi"])
        with self.assertRaises(ValueError):
            self.approve(row["id"], messages=messages, data_policy="hypothetical")
        messages[0]["content"] = "Giả sử dữ liệu dự báo ngày mai có AQI 175, thuộc mức nào?"
        messages[1]["content"] = "Theo giả định đó, US AQI 175 thuộc mức Xấu."
        self.approve(row["id"], messages=messages, kind="knowledge", source_ids=["airnow_aqi"], data_policy="hypothetical")
        self.assertEqual(len(self.store.list("approved")), 1)

    def test_rejecting_review_removes_record_from_training_pool(self):
        row = self.store.submit(validate_feedback(self.body), "Test")
        self.approve(row["id"])
        self.store.review(row["id"], approve=False, reviewer="local-test", note="Chờ sửa lại.")
        self.assertFalse(self.store.list("approved"))
        self.assertEqual(len(self.store.list("rejected")), 1)


if __name__ == "__main__":
    unittest.main()
