import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import export_xanhnon


class ExportStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name).resolve()
        self.root = self.base / 'project'
        self.adapter = self.root / 'adapter'
        self.adapter.mkdir(parents=True)
        (self.adapter / 'training_report.json').write_text(
            json.dumps({'mode': 'lora_candidate', 'steps': 58}), encoding='utf-8')
        self.archive = self.base / 'archive'
        self.archive.mkdir()

    def invoke(self, target, extra=(), free=4 * 2**30):
        arguments = ['export_xanhnon.py', '--adapter', str(self.adapter),
                     '--gguf', str(target), '--merged', str(self.archive / 'merged'), *extra]
        error = io.StringIO()
        with patch.object(export_xanhnon, 'ROOT', self.root), \
             patch('sys.argv', arguments), \
             patch.object(export_xanhnon.shutil, 'disk_usage', return_value=SimpleNamespace(free=free)) as disk, \
             patch.object(export_xanhnon.importlib.util, 'find_spec', return_value=None), \
             contextlib.redirect_stderr(error), self.assertRaises(SystemExit) as stopped:
            export_xanhnon.main()
        self.assertEqual(stopped.exception.code, 2)
        return error.getvalue(), disk

    def test_archive_export_checks_destination_volume_before_model_loading(self):
        error, disk = self.invoke(self.archive / 'candidate.gguf')
        self.assertIn('sentencepiece is required', error)
        self.assertEqual([call.args[0] for call in disk.call_args_list], [self.archive, self.archive])

    def test_archive_export_still_requires_available_space(self):
        error, _ = self.invoke(self.archive / 'candidate.gguf', free=2 * 2**30)
        self.assertIn('at least 3 GiB', error)
        self.assertIn(str(self.archive), error)

    def test_external_artifact_cannot_be_activated(self):
        error, disk = self.invoke(self.archive / 'candidate.gguf', ['--activate'])
        self.assertIn('Activation requires a GGUF inside models', error)
        disk.assert_not_called()

    def test_original_model_remains_protected(self):
        error, disk = self.invoke(self.root / 'models/xanhnon-f16.gguf')
        self.assertIn('preserve the original model', error)
        disk.assert_not_called()

    def test_existing_archive_cannot_be_overwritten(self):
        target = self.archive / 'candidate.gguf'
        target.write_bytes(b'preserve')
        error, disk = self.invoke(target)
        self.assertIn('destination already exists', error)
        self.assertEqual(target.read_bytes(), b'preserve')
        disk.assert_not_called()


if __name__ == '__main__':
    unittest.main()
