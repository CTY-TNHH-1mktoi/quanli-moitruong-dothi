from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_data import make_record
from prepare_xanhnon_runtime_data import runtime_review_records, SIMULATION_NOTICE
from queue_sensor_training import enqueue, choose_training_adapter, training_command, prepared_training_configuration
from sensor_training_data import ROOT, digest, save_json
from train_xanhnon import encode_record


class RuntimeTrainingTests(unittest.TestCase):
    def test_real_prompt_context_has_reviewed_targets_and_holds_out_eval_questions(self):
        knowledge = json.loads((ROOT / "data/xanhnon/knowledge.json").read_text(encoding="utf-8"))
        records = runtime_review_records(knowledge)
        self.assertEqual(Counter(split for split, _ in records), {"train": 72, "validation": 24})
        cases, _ = evaluation_cases(ROOT / "data/xanhnon/eval_consultation.json")
        held_out = {case["question"] for case in cases}
        for split, row in records:
            self.assertNotIn(row["original_question"], held_out)
            self.assertTrue(row["supervise_last_assistant_only"])
            self.assertTrue(row["synthetic_context"])
            self.assertTrue(set(row["source_ids"]) <= set(knowledge["sources"]))
            self.assertIn("Địa điểm đang chọn:", row["messages"][0]["content"])
            self.assertIn(SIMULATION_NOTICE, row["messages"][-2]["content"])
            self.assertTrue(row["messages"][-2]["content"].endswith(row["original_question"]))
            answer = row["messages"][-1]["content"]
            if row["topic"] == "fresh_over_history":
                self.assertIn("AQI " + str(row["snapshot"]["DuLieu"]["US_AQI"]), answer)
            if row["topic"] == "no_filter":
                self.assertIn("khăn ẩm", answer)
                self.assertNotIn("máy hút bụi", answer)
            if row["topic"] == "noise_duration":
                self.assertIn("giảm thời gian", answer)
                self.assertNotIn("tăng khoảng cách và thời gian", answer)
            if row["topic"] in ("lung_direct", "lung_followup"):
                self.assertIn("phổi", answer)
        for split in ("train", "validation"):
            counts = Counter(row["topic"] for part, row in records if part == split)
            self.assertEqual(len(counts), 12)
            self.assertEqual(set(counts.values()), {6 if split == "train" else 2})

    def test_only_final_assistant_answer_is_supervised(self):
        class Tokenizer:
            def apply_chat_template(self, messages, **kwargs):
                tokens = []
                for message in messages:
                    tokens.extend([1 if message["role"] == "assistant" else 2, 3])
                return tokens + ([1] if kwargs.get("add_generation_prompt") else [])
        row = make_record([{"role": "user", "content": "Ví dụ cũ?"},
                           {"role": "assistant", "content": "Số liệu cũ."},
                           {"role": "user", "content": "Số liệu mới?"},
                           {"role": "assistant", "content": "Dùng số mới."}], "runtime", "one")
        all_turns = encode_record(Tokenizer(), row, 128)
        last = encode_record(Tokenizer(), {**row, "supervise_last_assistant_only": True}, 128)
        self.assertEqual(sum(v != -100 for v in all_turns["labels"]), 2)
        self.assertEqual(sum(v != -100 for v in last["labels"]), 1)
        self.assertTrue(all(v == -100 for v in last["labels"][:-1]))
        self.assertEqual(last["labels"][-1], 3)

    def test_prepared_job_preserves_context_length_and_resets_rejected_lineage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            after, data = root / "rejected", root / "data"
            save_json(after / "training_report.json", {"mode": "lora_candidate"})
            data.mkdir()
            hashes = {}
            for filename in ("train.jsonl", "validation.jsonl"):
                (data / filename).write_text("fixture", encoding="utf-8")
                hashes[filename] = digest(data / filename)
            save_json(data / "manifest.json", {"artifacts_sha256": hashes, "training_configuration":
                {"max_length": 1024, "epochs": 1, "learning_rate": 0.0001, "start_from_active_release": True}})
            job = enqueue(root, after, data)
            adapter, reason = choose_training_adapter(job, root / "active")
            self.assertEqual(adapter, root / "active")
            self.assertEqual(reason, "explicit_reviewed_reset_to_active_release")
            command = training_command(data, root / "candidate", adapter, job)
            self.assertEqual(command[command.index("--max-length") + 1], "1024")
            self.assertEqual(command[command.index("--adapter") + 1], str(root / "active"))
            for bad in (True, 0, 4096, "1024"):
                with self.assertRaises(ValueError):
                    prepared_training_configuration({"training_configuration": {"max_length": bad}})


if __name__ == "__main__":
    unittest.main()
