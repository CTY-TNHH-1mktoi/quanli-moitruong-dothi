from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')

from expand_xanhnon_adapter import expand, verify_expansion, expand_tensors
from queue_sensor_training import choose_training_adapter, prepared_training_configuration
from sensor_training_data import digest
from train_xanhnon import adapter_metadata


class AdapterExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        from peft import get_peft_model, LoraConfig
        from transformers import Qwen2Config, Qwen2ForCausalLM
        torch.set_num_threads(2)
        torch.manual_seed(31)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.base_path, cls.source, cls.expanded = cls.root / 'base', cls.root / 'active', cls.root / 'expanded'
        config = Qwen2Config(vocab_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
                            num_attention_heads=4, num_key_value_heads=2, attention_dropout=0)
        cls.base = Qwen2ForCausalLM(config).eval()
        config.save_pretrained(cls.base_path)
        config._name_or_path = str(cls.base_path)
        cls.original_model = get_peft_model(deepcopy(cls.base), LoraConfig(
            task_type='CAUSAL_LM', r=2, lora_alpha=4, lora_dropout=0,
            target_modules=['q_proj', 'v_proj'], layers_to_transform=[0, 1], bias='none')).eval()
        with torch.no_grad():
            for name, value in cls.original_model.named_parameters():
                if 'lora_B' in name:
                    value.normal_(std=.03)
        cls.original_model.save_pretrained(cls.source, safe_serialization=True, save_embedding_layers=False)
        cls.manifest = expand(cls.source, cls.base_path, cls.expanded, rank=4)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_real_peft_loader_preserves_logits_and_exposes_trainable_new_projections(self):
        import torch
        from peft import PeftModel
        from train_xanhnon import assistant_loss
        model = PeftModel.from_pretrained(deepcopy(self.base), self.expanded, is_trainable=True, local_files_only=True).eval()
        ids = torch.tensor([[1, 2, 3, 4, 5]])
        with torch.no_grad():
            before = self.original_model(ids).logits
            after = model(ids).logits
        torch.testing.assert_close(after, before, rtol=1e-5, atol=1e-6)
        model.train()
        inputs = {'input_ids': ids, 'attention_mask': torch.ones_like(ids),
                  'labels': torch.tensor([[-100, -100, -100, 4, 5]])}
        assistant_loss(model, inputs).backward()
        gradients = {name: parameter.grad for name, parameter in model.named_parameters() if 'lora_B' in name}
        self.assertEqual(len(gradients), 14)
        for name, gradient in gradients.items():
            self.assertIsNotNone(gradient, name)
            self.assertTrue(torch.isfinite(gradient).all(), name)
            self.assertGreater(gradient.abs().sum().item(), 0, name)
        self.assertGreater(self.manifest['proof']['expanded_parameters'], self.manifest['proof']['source_parameters'])

    def test_verified_expansion_starts_from_active_and_reports_effective_rank(self):
        fingerprint = digest(self.expanded / 'expansion-manifest.json')
        verify_expansion(self.expanded, self.source, fingerprint)
        job = {'start_from_active_release': True, 'capacity_adapter': str(self.expanded),
               'capacity_adapter_manifest_sha256': fingerprint}
        path, reason = choose_training_adapter(job, self.source)
        self.assertEqual(path, self.expanded)
        self.assertEqual(reason, 'expanded_active_adapter_capacity_experiment')
        self.assertEqual(adapter_metadata(path)['lora_rank'], 4)
        self.assertEqual(len(adapter_metadata(path)['target_modules']), 7)

    def test_modified_weights_or_changed_active_adapter_are_rejected(self):
        fingerprint = digest(self.expanded / 'expansion-manifest.json')
        with self.assertRaisesRegex(ValueError, 'current active'):
            verify_expansion(self.expanded, self.root / 'other-active', fingerprint)
        with self.assertRaisesRegex(ValueError, 'manifest changed'):
            verify_expansion(self.expanded, self.source, '0' * 64)
        original = digest
        def tampered(path):
            return '0' * 64 if Path(path) == self.expanded / 'adapter_model.safetensors' else original(path)
        with patch('expand_xanhnon_adapter.digest', side_effect=tampered):
            with self.assertRaisesRegex(ValueError, 'weights changed'):
                verify_expansion(self.expanded, self.source, fingerprint)

    def test_capacity_configuration_requires_both_artifact_hash_and_active_source(self):
        valid = {'start_from_active_release': True, 'capacity_adapter': str(self.expanded),
                 'capacity_adapter_manifest_sha256': digest(self.expanded / 'expansion-manifest.json')}
        self.assertEqual(prepared_training_configuration({'training_configuration': valid})['capacity_adapter'], str(self.expanded))
        for bad in ({**valid, 'start_from_active_release': False},
                    {**valid, 'capacity_adapter_manifest_sha256': None},
                    {**valid, 'capacity_adapter': 'relative/path'}):
            with self.assertRaises(ValueError):
                prepared_training_configuration({'training_configuration': bad})

    def test_expansion_does_not_replace_existing_output(self):
        with self.assertRaisesRegex(ValueError, 'new empty'):
            expand(self.source, self.base_path, self.expanded, rank=4)


if __name__ == '__main__':
    unittest.main()
