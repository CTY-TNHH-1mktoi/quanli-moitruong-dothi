import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from daily_train_xanhnon import training_seed
from export_xanhnon import resolve_training_base


class RestoredTrainingSeedTests(unittest.TestCase):
    def test_existing_adapter_keeps_its_original_seed(self):
        self.assertEqual(training_seed({'adapter':Path('models/adapter')}),['--adapter',str(Path('models/adapter'))])

    def test_recovered_merge_requires_valid_hash_and_config(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            base=root/'models/xanhnon-style-v2-training-base'
            base.mkdir(parents=True)
            (base/'model.safetensors').write_bytes(b'weights')
            (base/'config.json').write_text('{}')
            proof=base/'recovery-training-base.json'
            proof.write_text(json.dumps({'sha256':hashlib.sha256(b'weights').hexdigest()}))
            self.assertEqual(training_seed({},root),['--model',str(base)])
            (base/'model.safetensors').write_bytes(b'corrupted')
            with self.assertRaisesRegex(ValueError,'checksum'):training_seed({},root)

    def test_missing_recovery_proof_is_never_treated_as_a_valid_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):training_seed({},Path(folder))

    def test_export_uses_the_recovered_base_in_adapter_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            adapter=root/'candidate'
            adapter.mkdir()
            base=root/'models/xanhnon-style-v2-training-base'
            base.mkdir(parents=True)
            config=adapter/'adapter_config.json'
            config.write_text(json.dumps({'base_model_name_or_path':str(base)}))
            self.assertEqual(resolve_training_base(adapter,root=root),base)
            config.write_text(json.dumps({'base_model_name_or_path':'C:/lost/unknown-training-base'}))
            with self.assertRaises(ValueError):resolve_training_base(adapter,root=root)

    def test_explicit_export_base_takes_precedence(self):
        self.assertEqual(resolve_training_base(Path('candidate'),Path('chosen')),Path('chosen'))
