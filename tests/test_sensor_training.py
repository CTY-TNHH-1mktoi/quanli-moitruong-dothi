from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sensor_training_data as data
from queue_sensor_training import dependency_ready, enqueue, source_adapter
from train_xanhnon import load_data


def observation(source, index=0, filename="device.csv", **values):
    parsed = {"values": values or {"pm25": 12.0, "pm10": 24.0, "temperature": 25.0, "humidity": 60.0, "noise": 62.0},
              "channels": {}, "timestamp": f"2018-01-01T{index:02d}:00:00Z", "station": None,
              "filename": filename, "source": source, "group": source + ":" + data.file_family(filename)}
    parsed["key"] = data.observation_key(parsed)
    return parsed


class SensorTrainingTests(unittest.TestCase):
    def setUp(self):
        self.knowledge = json.loads((data.ROOT / "data/xanhnon/knowledge.json").read_text(encoding="utf-8"))

    def test_beijing_missing_noise_and_rh_are_not_invented_from_dewpoint(self):
        row = data.parse_observation({"PM2.5": "17", "PM10": "29", "TEMP": "25", "DEWP": "21"})
        self.assertEqual(row["values"], {"pm25": 17.0, "pm10": 29.0, "temperature": 25.0})
        invalid = data.parse_observation({"TEMP": "nan", "HUM": "120", "NOISE_A": "inf"})
        self.assertIsNone(invalid)
        self.assertIsNone(data.parse_observation({"PM2.5": "70", "PM10": "10", "TEMP": "25"}))

    def test_real_sensor_aliases_and_duplicate_rows(self):
        parsed = data.parse_observation({"Temperature": "24", "Humidity": "64"})
        self.assertEqual(parsed["values"], {"temperature": 24, "humidity": 64})
        rows, counts = data.sample_csv(io.StringIO("Time,TEMP,HUM\n2018-01-01,25,55\n2018-01-02,25,55\n2018-01-03,26,56\n"), data.SOURCES[0], "kit.csv")
        self.assertEqual(len(rows), 2)
        self.assertEqual(counts["repeated_measurements"], 1)

    def test_author_processed_first_with_raw_fallback(self):
        plan = data.plan_files([{"key": "9.csv"}, {"key": "9_PROCESSED.csv"}, {"key": "description.yaml"}])
        self.assertEqual([[item["key"] for item in group] for group in plan], [["9_PROCESSED.csv", "9.csv"]])

    def test_download_reuses_verified_file_under_a_different_name(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            old = directory / "already-present.csv"
            old.write_bytes(b"TEMP,HUM\n25,60\n")
            entry = {"key": "new-name.csv", "url": "https://example.invalid", "size": old.stat().st_size,
                     "checksum": "md5:" + hashlib.md5(old.read_bytes()).hexdigest()}
            with patch.object(data, "request", side_effect=AssertionError("must not download twice")):
                path, action = data.download(entry, directory / "new-name.csv", [old])
            self.assertEqual(path, old)
            self.assertEqual(action, "reused_verified_file")

    def test_collection_skips_identical_files_and_raw_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = b"Time,TEMP,HUM\n2018-01-01,25,55\n2018-01-02,26,56\n"
            source = data.SOURCES[0]
            path = root / source["id"] / "kit_PROCESSED.csv"
            path.parent.mkdir(parents=True)
            path.write_bytes(content)
            files = [{"key": name, "checksum": "md5:" + hashlib.md5(content).hexdigest(), "size": len(content),
                      "links": {"self": "https://example.invalid"}} for name in ("kit_PROCESSED.csv", "kit.csv", "other.csv")]
            data.save_json(root / "metadata/3570700.json", {"metadata": {"license": {"id": "cc-zero"}}, "files": files})
            with patch.object(data, "SOURCES", [source]), patch.object(data, "request", side_effect=AssertionError("unexpected download")):
                rows, reports = data.collect_sources(root)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(reports[0]["files"]), 1)
            self.assertEqual({row["reason"] for row in reports[0]["skipped"]}, {"author_processed_variant_already_usable", "identical_file_content"})

    def test_weather_reply_stays_on_topic_and_never_fills_missing_fields(self):
        row = observation("beijing_air", pm25=17, pm10=29, temperature=25)
        record = data.dialogue_record(row, 1, self.knowledge)
        answer = record["messages"][-1]["content"]
        self.assertIn("25 °C", answer)
        self.assertNotIn("PM", answer)
        self.assertNotIn("tiếng ồn", answer)
        self.assertIn("chưa có độ ẩm", answer)
        self.assertNotIn("0 %", answer)

    def test_controlled_tests_do_not_become_outdoor_health_or_advice_labels(self):
        row = observation("iscape_development", pm25=20, pm10=30, noise=65)
        for variant in range(8):
            record = data.dialogue_record(row, variant, self.knowledge)
            self.assertIn("Mẫu thử nghiệm", record["messages"][1]["content"])
            answer = record["messages"][-1]["content"]
            self.assertNotIn("máy lọc", answer)
            self.assertFalse(answer.endswith(": "))

    def test_dust_followup_has_complete_actions_and_sources(self):
        record = data.dialogue_record(observation("iscape_outdoor"), 7, self.knowledge)
        self.assertEqual(len(record["messages"]), 5)
        self.assertIn("khăn ẩm", record["messages"][2]["content"])
        self.assertGreater(len(record["messages"][-1]["content"].split()), 15)
        for source_id in record["source_ids"]:
            self.assertTrue(source_id == "iscape_outdoor" or source_id in self.knowledge["sources"])

    def test_isolated_dataset_dedup_split_and_manifest(self):
        rows = []
        for source_index, source in enumerate(data.SOURCES):
            for device in range(8):
                for index in range(8):
                    rows.append(observation(source["id"], index, f"device-{source_index}-{device}.csv",
                                            pm25=source_index * 40 + device * 3 + index, pm10=source_index * 40 + device * 3 + index + 20,
                                            temperature=20 + device, humidity=40 + index, noise=50 + device))
        # Two copies from another dataset: one identical vector, one incomplete same-origin copy.
        duplicate = {**rows[0], "source": "iscape_workshops", "group": "iscape_workshops:duplicate", "filename": "duplicate.csv"}
        inferior = {**rows[1], "values": {"temperature": rows[1]["values"]["temperature"], "humidity": rows[1]["values"]["humidity"]}}
        inferior["key"] = data.observation_key(inferior)
        original_hash = data.digest(data.ROOT / "data/xanhnon/manifest.json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            manifest = data.prepare_dataset(rows + [duplicate, inferior], data.SOURCES, path, per_source=12)
            partitions = {split: [json.loads(line) for line in (path / (split + ".jsonl")).read_text(encoding="utf-8").splitlines()]
                          for split in ("train", "validation")}
            self.assertFalse({row["group_id"] for row in partitions["train"]} & {row["group_id"] for row in partitions["validation"]})
            keys = [data.pair_key(row) for records in partitions.values() for row in records]
            self.assertEqual(len(keys), len(set(keys)))
            self.assertGreater(manifest["deduplication"]["duplicate_measurement_vector"], 0)
            self.assertGreater(manifest["deduplication"]["duplicate_or_inferior_copy_of_same_observation"], 0)
            self.assertEqual(set(manifest["new_sensor_counts"]["train"]), {"sensor_" + row["id"] for row in data.SOURCES})
            for filename, expected in manifest["artifacts_sha256"].items():
                self.assertEqual(data.digest(path / filename), expected)
        self.assertEqual(data.digest(data.ROOT / "data/xanhnon/manifest.json"), original_hash)

    def test_training_loader_reads_the_isolated_directory_and_checks_hashes(self):
        class Tokenizer:
            def apply_chat_template(self, messages, **kwargs):
                tokens = []
                for message in messages:
                    tokens.extend([1 if message["role"] == "assistant" else 2, 3])
                return tokens + ([1] if kwargs.get("add_generation_prompt") else [])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hashes = {}
            for split in ("train", "validation"):
                record = data.make_record([{"role": "user", "content": "Mẫu lịch sử"}, {"role": "assistant", "content": "Đọc số đo"}], "sensor_test", split)
                path = root / (split + ".jsonl")
                path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
                hashes[path.name] = data.digest(path)
            data.save_json(root / "manifest.json", {"artifacts_sha256": hashes})
            rows, stats = load_data(Tokenizer(), 512, data_dir=root)
            self.assertEqual(stats["train"]["encoded_rows"], 1)
            self.assertEqual(len(rows["validation"]), 1)
            data.save_json(root / "manifest.json", {"artifacts_sha256": hashes, "required_train_sources": ["missing_sensor_source"]})
            with self.assertRaisesRegex(ValueError, "Required sources"):
                load_data(Tokenizer(), 512, data_dir=root)
            (root / "train.jsonl").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manifest"):
                load_data(Tokenizer(), 512, data_dir=root)

    def test_source_entirely_duplicated_is_skipped_instead_of_retrained(self):
        samples = []
        for source in data.SOURCES:
            for index in range(8):
                samples.append(observation(source["id"], index, f"shared-{index}.csv", pm25=10 + index, pm10=30 + index, temperature=25))
        with tempfile.TemporaryDirectory() as directory:
            manifest = data.prepare_dataset(samples, data.SOURCES, directory, per_source=8)
            self.assertEqual(manifest["required_train_sources"], ["sensor_iscape_outdoor"])
            self.assertEqual(len(manifest["skipped_sources"]), 3)
            self.assertNotIn("sensor_beijing_air", manifest["counts"]["train"])

    def test_queue_waits_for_completion_and_does_not_enqueue_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            after = root / "previous"
            data.save_json(after / "progress.json", {"steps_completed": 4})
            self.assertFalse(dependency_ready(after))
            first = enqueue(root, after)
            self.assertEqual(enqueue(root, after)["requested_at"], first["requested_at"])
            report = {"mode": "lora_candidate", "selected_data_pass_completed": True, "steps": 4,
                      "baseline_validation_loss": 2.0, "candidate_validation_loss": 1.9}
            data.save_json(after / "training_report.json", report)
            (after / "adapter_model.safetensors").write_bytes(b"fixture")
            with patch("queue_sensor_training.training_in_progress", return_value=True):
                self.assertFalse(dependency_ready(after))
            with patch("queue_sensor_training.training_in_progress", return_value=False):
                self.assertTrue(dependency_ready(after))
            self.assertEqual(source_adapter(after, root / "active")[0], after)
            data.save_json(after / "training_report.json", {**report, "candidate_validation_loss": 2.2})
            self.assertEqual(source_adapter(after, root / "active")[0], root / "active")


if __name__ == "__main__":
    unittest.main()
