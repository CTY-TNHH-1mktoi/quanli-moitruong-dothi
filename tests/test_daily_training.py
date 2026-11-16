import unittest
from types import SimpleNamespace
from unittest.mock import patch
import json
from pathlib import Path
from daily_train_xanhnon import candidate_status, dataset_fingerprint, memory_ready


class DailyTrainingTests(unittest.TestCase):
    def test_paging_requires_explicit_opt_in_and_enough_combined_memory(self):
        with patch("daily_train_xanhnon.psutil.virtual_memory", return_value=SimpleNamespace(available=1 * 2**30)), \
                patch("daily_train_xanhnon.psutil.swap_memory", return_value=SimpleNamespace(free=5 * 2**30)):
            self.assertFalse(memory_ready())
            self.assertTrue(memory_ready(allow_cpu_paging=True))
        with patch("daily_train_xanhnon.psutil.virtual_memory", return_value=SimpleNamespace(available=1 * 2**30)), \
                patch("daily_train_xanhnon.psutil.swap_memory", return_value=SimpleNamespace(free=4 * 2**30)):
            self.assertFalse(memory_ready(allow_cpu_paging=True))

    def test_quality_gate_rejects_degraded_or_incomplete_training(self):
        report = {"steps": 2, "selected_data_pass_completed": True,
                  "baseline_validation_loss": 2.0, "candidate_validation_loss": 1.9}
        self.assertEqual(candidate_status(report), "awaiting_answer_evaluation")
        self.assertEqual(candidate_status({**report, "candidate_validation_loss": 2.1}), "rejected_validation")
        self.assertEqual(candidate_status({**report, "candidate_validation_loss": float("nan")}), "incomplete")
        self.assertEqual(candidate_status({**report, "selected_data_pass_completed": False}), "incomplete")

    def test_current_dataset_matches_prepared_manifest(self):
        self.assertEqual(len(dataset_fingerprint()), 64)

    def test_prepared_advice_examples_have_checked_sources_and_real_measures(self):
        root = Path(__file__).resolve().parents[1] / "data/xanhnon"
        advice = []
        for split in ["train", "validation"]:
            for line in (root / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                if record["source"] == "environment_advice":
                    advice.append(record)
                    self.assertEqual(record["review"], "source_checked_project_examples")
                    self.assertTrue(record["source_ids"])
                    self.assertGreater(len(record["messages"][-1]["content"].split()), 20)
        self.assertEqual(len(advice), 30)
