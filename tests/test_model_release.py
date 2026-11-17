import json
from pathlib import Path
import tempfile
import unittest

from model_release import read_release


ROOT = Path(__file__).resolve().parents[1]


class ModelReleaseTests(unittest.TestCase):
    def make_release(self, folder):
        root = Path(folder).resolve()
        self.assertTrue(root.is_relative_to((ROOT / ".runtime").resolve()))
        models = root / "models"
        (models / "base").mkdir(parents=True)
        (models / "adapter").mkdir()
        (models / "base/model.safetensors").write_bytes(b"test")
        (models / "adapter/adapter_model.safetensors").write_bytes(b"test")
        (models / "adapter/adapter_config.json").write_text("{}", encoding="utf-8")
        (models / "candidate.gguf").write_bytes(b"test")
        data = {"version": 1, "name": "Test release", "base_model": "models/base",
                "adapter": "models/adapter", "gguf": "models/candidate.gguf"}
        manifest = models / "xanhnon-active.json"
        manifest.write_text(json.dumps(data), encoding="utf-8")
        return root, manifest, data

    def test_ready_release_resolves_local_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as folder:
            root, _, _ = self.make_release(folder)
            release = read_release(root)
            self.assertEqual(release["name"], "Test release")
            self.assertEqual(release["adapter"], root / "models/adapter")

    def test_incomplete_release_falls_back(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as folder:
            root, _, _ = self.make_release(folder)
            (root / "models/adapter/adapter_model.safetensors").unlink()
            with self.assertLogs("model_release", level="WARNING"):
                self.assertEqual(read_release(root), {})

    def test_paths_outside_models_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as folder:
            root, manifest, data = self.make_release(folder)
            data["gguf"] = "../elsewhere.gguf"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertLogs("model_release", level="WARNING"):
                self.assertEqual(read_release(root), {})

    def test_malformed_manifest_falls_back(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as folder:
            root, manifest, _ = self.make_release(folder)
            manifest.write_text("[]", encoding="utf-8")
            with self.assertLogs("model_release", level="WARNING"):
                self.assertEqual(read_release(root), {})


if __name__ == "__main__":
    unittest.main()
