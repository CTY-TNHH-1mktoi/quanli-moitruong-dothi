from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, MagicMock

from daily_train_xanhnon import run_training
from training_resume import resume_plan, order_hash, save_trainer_state, restore_trainer_state


class ResumeTests(unittest.TestCase):
    def fixture(self, folder):
        checkpoint = Path(folder) / 'step-0088'
        checkpoint.mkdir()
        rows = [{'id': str(i)} for i in range(336)] * 2
        previous = {'mode': 'lora_training', 'steps_completed': 88, 'steps_planned': 168,
                    'baseline_validation_loss': 1.299, 'manifest_sha256': 'frozen',
                    'data_dir': str(Path(folder) / 'data'), 'data': {'train': {'encoded_rows': 336}},
                    'max_length': 768,
                    'configuration': {'epochs': 2, 'accumulation': 4, 'seed': 42, 'learning_rate': .00003}}
        (checkpoint / 'progress.json').write_text(json.dumps(previous), encoding='utf-8')
        (checkpoint / 'adapter_config.json').write_text('{}', encoding='utf-8')
        (checkpoint / 'adapter_model.safetensors').write_bytes(b'fixture')
        return checkpoint, previous, rows

    def test_recovery_reconstructs_only_the_remaining_data_after_step_88(self):
        with TemporaryDirectory() as folder:
            checkpoint, report, rows = self.fixture(folder)
            _, result = resume_plan(checkpoint, report, rows, 168, allow_optimizer_reset=True)
            self.assertEqual(result['steps_remaining'], 80)
            self.assertEqual(len(rows[result['checkpoint_step'] * 4:]), 320)
            self.assertEqual(rows[result['checkpoint_step'] * 4]['id'], '16')
            self.assertTrue(result['optimizer_reinitialized'])
            self.assertFalse(result['exact_trajectory_resume'])
            with self.assertRaisesRegex(ValueError, 'allow-optimizer-reset'):
                resume_plan(checkpoint, report, rows, 168)

    def test_changed_data_configuration_or_record_order_is_rejected(self):
        with TemporaryDirectory() as folder:
            checkpoint, report, rows = self.fixture(folder)
            for changed in ({**report, 'manifest_sha256': 'changed'},
                            {**report, 'configuration': {**report['configuration'], 'epochs': 3}}):
                with self.assertRaises(ValueError):
                    resume_plan(checkpoint, changed, rows, 168, allow_optimizer_reset=True)
            saved = {**report, 'training_order_sha256': order_hash(rows)}
            (checkpoint / 'progress.json').write_text(json.dumps(saved), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'row order'):
                resume_plan(checkpoint, report, list(reversed(rows)), 168, allow_optimizer_reset=True)

    def test_peft_serialization_can_reorder_the_same_target_modules(self):
        with TemporaryDirectory() as folder:
            checkpoint, report, rows = self.fixture(folder)
            saved = deepcopy(report)
            saved['configuration']['target_modules'] = ['q_proj', 'v_proj']
            (checkpoint / 'progress.json').write_text(json.dumps(saved), encoding='utf-8')
            report['configuration']['target_modules'] = ['v_proj', 'q_proj']
            resume_plan(checkpoint, report, rows, 168, allow_optimizer_reset=True)

    def test_resume_rejects_changed_quantization_or_base_weights(self):
        with TemporaryDirectory() as folder:
            checkpoint, report, rows = self.fixture(folder)
            saved = deepcopy(report)
            saved['configuration'].update(quantization='nf4', base_model_sha256='original',
                                          base_model_revision='pinned')
            (checkpoint / 'progress.json').write_text(json.dumps(saved), encoding='utf-8')
            for key in ('quantization', 'base_model_sha256', 'base_model_revision'):
                changed = deepcopy(saved)
                changed['configuration'][key] = 'different'
                with self.assertRaisesRegex(ValueError, key):
                    resume_plan(checkpoint, changed, rows, 168, allow_optimizer_reset=True)

    def test_saved_optimizer_and_rng_reproduce_the_next_real_update(self):
        import torch
        torch.manual_seed(5)
        torch.set_num_threads(2)
        def model():
            return torch.nn.Sequential(torch.nn.Linear(3, 4), torch.nn.Dropout(.25), torch.nn.Linear(4, 1))
        def step(net, optimizer):
            optimizer.zero_grad(set_to_none=True)
            loss = net(torch.ones(2, 3)).square().mean()
            loss.backward()
            optimizer.step()
        first = model()
        optimizer = torch.optim.AdamW(first.parameters(), lr=.001)
        scaler = torch.amp.GradScaler('cuda', enabled=False)
        step(first, optimizer)
        weights = deepcopy(first.state_dict())
        with TemporaryDirectory() as folder:
            checkpoint = Path(folder)
            save_trainer_state(checkpoint / 'trainer-state.pt', optimizer, scaler, 1, [.4], 0, 'same-order')
            step(first, optimizer)
            restored = model()
            restored.load_state_dict(weights)
            other = torch.optim.AdamW(restored.parameters(), lr=.001)
            losses, offset = restore_trainer_state(checkpoint, other, scaler, 1, 'same-order')
            self.assertEqual((losses, offset), ([.4], 0))
            step(restored, other)
            for key, value in first.state_dict().items():
                torch.testing.assert_close(value, restored.state_dict()[key], rtol=0, atol=0)

    def test_extended_timeout_is_passed_to_the_owned_training_process(self):
        process = MagicMock()
        process.wait.return_value = 0
        with patch('daily_train_xanhnon.subprocess.Popen', return_value=process):
            self.assertEqual(run_training(['python', 'train.py'], None, timeout_seconds=86400), 0)
        process.wait.assert_called_once_with(timeout=86400)


if __name__ == '__main__':
    unittest.main()
