import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import sensor_training_data as data


class TrainingStatusWriteTests(unittest.TestCase):
    def test_transient_windows_replace_lock_retries_without_truncating_target(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'status.json'
            path.write_text('{"state":"old"}', encoding='utf-8')
            replace = Path.replace
            attempts = []

            def transient(temporary, target):
                attempts.append(temporary)
                if len(attempts) < 3:
                    self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'state': 'old'})
                    raise PermissionError('Windows target is temporarily open')
                return replace(temporary, target)

            with patch.object(Path, 'replace', transient), patch.object(data.time, 'sleep'):
                data.save_json(path, {'state': 'new'})
            self.assertEqual(len(attempts), 3)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'state': 'new'})
            self.assertEqual(list(Path(directory).glob('*.new')), [])

    def test_permanent_failure_is_reported_and_keeps_previous_status(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'status.json'
            path.write_text('{"state":"old"}', encoding='utf-8')
            with patch.object(Path, 'replace', side_effect=PermissionError('locked')) as replace, \
                 patch.object(data.time, 'sleep'), self.assertRaises(PermissionError):
                data.save_json(path, {'state': 'new'})
            self.assertEqual(replace.call_count, 8)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'state': 'old'})
            self.assertEqual(list(Path(directory).glob('*.new')), [])

    def test_separate_writes_use_distinct_temporary_files(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'status.json'
            replace = Path.replace
            temporary_paths = []

            def record(temporary, target):
                temporary_paths.append(temporary)
                return replace(temporary, target)

            with patch.object(Path, 'replace', record):
                data.save_json(path, {'version': 1})
                data.save_json(path, {'version': 2})
            self.assertEqual(len(set(temporary_paths)), 2)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'version': 2})


if __name__ == '__main__':
    unittest.main()
