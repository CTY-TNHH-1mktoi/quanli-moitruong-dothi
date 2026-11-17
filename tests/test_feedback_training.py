from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from chat_feedback import FeedbackStore, validate_feedback
import daily_train_xanhnon as daily
from feedback_training_data import prepare_feedback_dataset, fingerprint, digest, SOURCE
from prepare_xanhnon_data import make_record


class FeedbackTrainingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.base = self.root / "data/xanhnon"
        self.base.mkdir(parents=True)
        self.storage = self.root / "storage"
        self.store = FeedbackStore(self.root / "feedback.sqlite3")
        for name, question in [("train", "Một câu huấn luyện gốc?"), ("validation", "Một câu giữ riêng?")]:
            record = make_record([{"role": "user", "content": question}, {"role": "assistant", "content": "Trả lời gốc."}],
                                 "environment_style", name)
            (self.base / f"{name}.jsonl").write_text(json.dumps(record, ensure_ascii=False)+"\n", encoding="utf-8")
        (self.base / "manifest.json").write_text(json.dumps({"artifacts_sha256": {
            name: digest(self.base / name) for name in ["train.jsonl", "validation.jsonl"]}}), encoding="utf-8")
        (self.base / "eval_consultation.json").write_text(json.dumps([{"question": "Một câu đánh giá riêng?"}]), encoding="utf-8")

    def record(self, question="Bạn cần hỏi rõ điều gì nữa?", history=None):
        payload = validate_feedback({"message": question, "reply": "Trả lời chưa tốt.", "location": "hanoi",
                                     "rating": "unhelpful", "comment": "Cần nối đúng chủ đề.", "history": history or []})
        return self.store.submit(payload, "Test")["id"]

    def approve(self, identifier, question="Bạn cần hỏi rõ điều gì nữa?", history=None):
        messages = (history or []) + [{"role": "user", "content": question},
                                      {"role": "assistant", "content": "Bạn muốn xem thời tiết hay chất lượng không khí?"}]
        self.store.review(identifier, approve=True, reviewer="test", note="Đã kiểm tra.", messages=messages,
                          source_ids=["project"], facts_reviewed=True, privacy_reviewed=True)

    def test_pending_and_rejected_do_not_change_fingerprint_or_create_snapshot(self):
        identifier = self.record()
        for reject in [False, True]:
            if reject:
                self.store.review(identifier, approve=False, reviewer="test", note="Chưa dùng để học.")
            directory, key, summary = prepare_feedback_dataset(self.base, self.storage, self.store)
            self.assertEqual(directory, self.base)
            self.assertEqual(key, fingerprint(self.base))
            self.assertEqual(summary["included"], 0)
        self.assertFalse(self.storage.exists())

    def test_approved_correction_creates_reproducible_snapshot_and_keeps_base_and_holdout(self):
        before = {name: digest(self.base / name) for name in ["train.jsonl", "validation.jsonl", "manifest.json"]}
        self.approve(self.record())
        directory, key, summary = prepare_feedback_dataset(self.base, self.storage, self.store)
        again, same_key, _ = prepare_feedback_dataset(self.base, self.storage, self.store)
        self.assertEqual((directory, key), (again, same_key))
        self.assertEqual(summary["included"], 1)
        self.assertEqual(before, {name: digest(self.base / name) for name in before})
        self.assertEqual(digest(directory / "validation.jsonl"), before["validation.jsonl"])
        records = [json.loads(line) for line in (directory / "train.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(records[-1]["source"], SOURCE)
        self.assertTrue(records[-1]["supervise_last_assistant_only"])
        self.assertNotIn("Trả lời chưa tốt.", records[-1]["messages"][-1]["content"])
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["require_complete_dialogues"])
        self.assertIn(SOURCE, manifest["required_train_sources"])

    def test_holdout_questions_and_duplicate_training_prompts_are_skipped(self):
        for question in ["Một câu giữ riêng?", "Một câu đánh giá riêng?", "Một câu huấn luyện gốc?"]:
            identifier = self.record(question)
            self.approve(identifier, question)
        directory, _, summary = prepare_feedback_dataset(self.base, self.storage, self.store)
        self.assertEqual(directory, self.base)
        self.assertEqual(summary["included"], 0)
        self.assertEqual(summary["skipped"]["duplicate_or_holdout_question"], 3)

    def test_same_followup_in_different_reviewed_contexts_remains_distinct(self):
        for subject in ["thời tiết", "chất lượng không khí"]:
            history = [{"role": "user", "content": f"Xem {subject} giúp mình nhé."},
                       {"role": "assistant", "content": "Bạn muốn xem ngày nào?"}]
            identifier = self.record("Mai thế nào?", history)
            self.approve(identifier, "Mai thế nào?", history)
        _, _, summary = prepare_feedback_dataset(self.base, self.storage, self.store)
        self.assertEqual(summary["included"], 2)

    def test_daily_check_selects_feedback_snapshot_without_starting_or_activating_model(self):
        self.approve(self.record())
        output = io.StringIO()
        with patch.object(daily, "ROOT", self.root), patch.object(daily, "STATE", self.root / "state.json"), \
                patch.object(daily, "training_in_progress", return_value=False), \
                patch.object(daily, "memory_ready", return_value=True), \
                patch.object(daily.shutil, "disk_usage", return_value=SimpleNamespace(free=10*2**30)), \
                patch.object(daily, "read_release", return_value={"adapter": self.root / "active-adapter"}), \
                patch.object(daily, "prepare_feedback_dataset", side_effect=lambda base, storage: prepare_feedback_dataset(base, storage, self.store)), \
                patch.object(daily, "run_training", side_effect=AssertionError("Check must not train")), \
                patch("sys.argv", ["daily_train_xanhnon.py", "--storage", str(self.storage), "--check"]), redirect_stdout(output):
            daily.main()
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "ready")
        self.assertFalse(result["model_activated"])
        self.assertEqual(result["feedback"]["included"], 1)
        command = result["command"]
        self.assertIn(SOURCE, command)
        self.assertEqual(command[command.index("--max-length") + 1], "1024")
        self.assertEqual(Path(command[command.index("--data-dir") + 1]), Path(result["data_dir"]))
        self.assertFalse((self.root / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
