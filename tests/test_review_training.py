from collections import Counter
import json
from pathlib import Path
import re
import tempfile
import unittest

from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_data import make_record, stable_id, normalize
from prepare_xanhnon_review_data import corrective_records
from queue_sensor_training import validate_prepared_dataset
from sensor_training_data import digest, ROOT, save_json
from train_xanhnon import load_data


class ReviewTrainingTests(unittest.TestCase):
    def test_reviewed_examples_cover_failures_without_copying_evaluation_questions(self):
        knowledge = json.loads((ROOT / "data/xanhnon/knowledge.json").read_text(encoding="utf-8"))
        records = corrective_records(knowledge)
        self.assertEqual(Counter(split for split, _ in records), {"train": 54, "validation": 18})
        cases, _ = evaluation_cases(ROOT / "data/xanhnon/eval_consultation.json")
        held_out_questions = {case["question"] for case in cases}
        pair_splits = {}
        for split, record in records:
            self.assertTrue(record["synthetic_context"])
            self.assertTrue(set(record["source_ids"]) <= set(knowledge["sources"]))
            for message in record["messages"]:
                if message["role"] == "user":
                    self.assertNotIn(message["content"], held_out_questions)
            for index in range(1,len(record["messages"]),2):
                key=stable_id(normalize(json.dumps(record["messages"][index:index+2],ensure_ascii=False,sort_keys=True)))
                self.assertIn(pair_splits.get(key,split),[split])
                pair_splits[key]=split
            if record["topic"] == "fresh_over_history":
                value = re.search(r"US_AQI (\d+)", record["messages"][-2]["content"])[1]
                self.assertIn("AQI " + value, record["messages"][-1]["content"])
            if record["topic"] == "no_filter":
                self.assertIn("khăn ẩm", record["messages"][-1]["content"])
                self.assertIn("Nếu đã có", record["messages"][-1]["content"])
        for split in ("train", "validation"):
            counts = Counter(record["topic"] for part,record in records if part == split)
            self.assertEqual(len(counts), 9)
            self.assertEqual(set(counts.values()), {6 if split == "train" else 2})

    def test_prepared_batch_integrity_is_checked_before_queueing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hashes = {}
            for name in ("train.jsonl", "validation.jsonl"):
                path = root/name
                path.write_text("fixture",encoding="utf-8")
                hashes[name] = digest(path)
            save_json(root/"manifest.json", {"artifacts_sha256":hashes})
            validate_prepared_dataset(root)
            (root/"train.jsonl").write_text("modified",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"changed"):
                validate_prepared_dataset(root)

    def test_complete_dialogue_rule_prevents_losing_the_constraint_followup(self):
        class Tokenizer:
            def apply_chat_template(self, messages, **kwargs):
                tokens = []
                for message in messages:
                    tokens.extend([1 if message["role"] == "assistant" else 2, 3])
                return tokens + ([1] if kwargs.get("add_generation_prompt") else [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hashes = {}
            for split in ("train","validation"):
                record = make_record([{"role":"user","content":"Bụi trong nhà"},{"role":"assistant","content":"Có thể dùng máy lọc"},
                                      {"role":"user","content":"Chưa có máy lọc"},{"role":"assistant","content":"Lau bằng khăn ẩm"}],"review",split)
                path = root/(split+".jsonl")
                path.write_text(json.dumps(record,ensure_ascii=False)+"\n",encoding="utf-8")
                hashes[path.name]=digest(path)
            save_json(root/"manifest.json",{"artifacts_sha256":hashes})
            rows,_=load_data(Tokenizer(),6,data_dir=root)
            self.assertEqual(rows["train"][0]["messages_used"],3)
            save_json(root/"manifest.json",{"artifacts_sha256":hashes,"require_complete_dialogues":True})
            with self.assertRaisesRegex(ValueError,"No usable train"):
                load_data(Tokenizer(),6,data_dir=root)


if __name__=="__main__":
    unittest.main()
