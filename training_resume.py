"""Validate checkpoint lineage and recover the original deterministic row order.

Older checkpoints have weights only. Recovery from those checkpoints requires
an explicit optimizer reset and records that the trajectory is not exact.
"""
import hashlib
import json
import math
from pathlib import Path


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def order_hash(rows):
    return hashlib.sha256(json.dumps([r['id'] for r in rows], separators=(',', ':')).encode()).hexdigest()


def resume_plan(checkpoint, report, rows, total_steps, *, allow_optimizer_reset=False):
    checkpoint = Path(checkpoint).resolve()
    previous = json.loads((checkpoint / 'progress.json').read_text(encoding='utf-8'))
    for name in ('adapter_config.json', 'adapter_model.safetensors'):
        if not (checkpoint / name).is_file():
            raise ValueError('Incomplete checkpoint: ' + name)
    step = previous.get('steps_completed')
    if (previous.get('mode') != 'lora_training' or isinstance(step, bool)
            or not isinstance(step, int) or not 0 < step < total_steps
            or previous.get('steps_planned') != total_steps):
        raise ValueError('Checkpoint does not belong to this incomplete training plan')
    if (previous.get('manifest_sha256') != report['manifest_sha256']
            or Path(previous['data_dir']).resolve() != Path(report['data_dir']).resolve()
            or previous.get('data') != report['data']):
        raise ValueError('Checkpoint dataset or encoded data differs from this run')
    keys = ('limit', 'validation_limit', 'max_steps', 'epochs', 'accumulation',
            'learning_rate', 'seed', 'last_layers', 'lora_rank', 'lora_alpha',
            'target_modules', 'effective_layers', 'train_sources',
            'quantization', 'base_model_sha256', 'base_model_revision')
    for key in keys:
        old_value, new_value = previous['configuration'].get(key), report['configuration'].get(key)
        if key in {'target_modules', 'effective_layers'} and old_value is not None and new_value is not None:
            old_value, new_value = set(old_value), set(new_value)
        if old_value != new_value:
            raise ValueError('Checkpoint training configuration changed: ' + key)
    if previous.get('max_length') != report['max_length']:
        raise ValueError('Checkpoint context length changed')
    fingerprint = order_hash(rows)
    if previous.get('training_order_sha256') and previous['training_order_sha256'] != fingerprint:
        raise ValueError('Checkpoint row order changed')
    baseline = previous.get('baseline_validation_loss')
    if isinstance(baseline, bool) or not isinstance(baseline, (int, float)) or not math.isfinite(baseline):
        raise ValueError('Checkpoint has no valid original baseline validation loss')
    state_path = checkpoint / 'trainer-state.pt'
    if not state_path.exists() and not allow_optimizer_reset:
        raise ValueError('Weights-only checkpoint requires --allow-optimizer-reset')
    metadata = {
        'checkpoint': str(checkpoint), 'checkpoint_step': step,
        'steps_remaining': total_steps-step, 'optimizer_state_available': state_path.exists(),
        'exact_trajectory_resume': state_path.exists(),
        'optimizer_reinitialized': not state_path.exists(),
        'training_order_sha256': fingerprint,
        'old_checkpoint_lacks_explicit_order_hash': not bool(previous.get('training_order_sha256')),
        'order_reconstructed_from_same_frozen_data_and_seed': True,
        'checkpoint_sha256': {name: file_hash(checkpoint / name) for name in
                              ('progress.json', 'adapter_config.json', 'adapter_model.safetensors')},
    }
    if state_path.exists():
        metadata['checkpoint_sha256']['trainer-state.pt'] = file_hash(state_path)
    return previous, metadata


def save_trainer_state(path, optimizer, scaler, steps, losses, loss_offset, fingerprint):
    import torch
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    state = {'schema_version': 1, 'steps_completed': steps,
             'optimizer': optimizer.state_dict(), 'scaler': scaler.state_dict(),
             'torch_rng': torch.get_rng_state(),
             'cuda_rng': torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
             'losses': losses, 'loss_step_offset': loss_offset,
             'training_order_sha256': fingerprint}
    torch.save(state, temporary)
    temporary.replace(path)


def restore_trainer_state(checkpoint, optimizer, scaler, expected_step, fingerprint):
    import torch
    state = torch.load(Path(checkpoint) / 'trainer-state.pt', map_location='cpu', weights_only=True)
    if state['steps_completed'] != expected_step or state['training_order_sha256'] != fingerprint:
        raise ValueError('Optimizer state and adapter checkpoint do not match')
    optimizer.load_state_dict(state['optimizer'])
    scaler.load_state_dict(state['scaler'])
    torch.set_rng_state(state['torch_rng'])
    if state['cuda_rng'] and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(state['cuda_rng'])
    return state['losses'], state['loss_step_offset']
