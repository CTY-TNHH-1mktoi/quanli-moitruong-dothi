"""Expand a plain Qwen2 LoRA while preserving its initial inference function.

This creates a separate adapter experiment. It never changes base/active weights.
The existing update is zero-padded; newly targeted projections have zero B.
"""
import argparse
from copy import deepcopy
from datetime import datetime
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from sensor_training_data import ROOT, digest, save_json


TARGETS = ('q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj')


def projection_shapes(base):
    hidden, intermediate = base['hidden_size'], base['intermediate_size']
    kv = hidden // base['num_attention_heads'] * base['num_key_value_heads']
    return {'q_proj': (hidden, hidden), 'k_proj': (kv, hidden), 'v_proj': (kv, hidden),
            'o_proj': (hidden, hidden), 'gate_proj': (intermediate, hidden),
            'up_proj': (intermediate, hidden), 'down_proj': (hidden, intermediate)}


def expand_tensors(original, config, base, rank=16):
    import torch
    old_rank = config['r']
    if isinstance(rank, bool) or not isinstance(rank, int) or rank <= old_rank:
        raise ValueError('Expanded rank must exceed the original rank')
    if (base.get('model_type') != 'qwen2' or config.get('peft_type') != 'LORA'
            or config.get('bias') != 'none' or config.get('use_rslora') or config.get('use_dora')
            or config.get('rank_pattern') or config.get('alpha_pattern')
            or config.get('modules_to_save') or config.get('fan_in_fan_out')
            or config.get('lora_bias') or config.get('target_parameters')):
        raise ValueError('Only plain Qwen2 LoRA with uniform rank/scaling is supported')
    layers = config.get('layers_to_transform')
    if not layers or any(not 0 <= i < base['num_hidden_layers'] for i in layers):
        raise ValueError('Explicit original adapter layers are required')
    if not set(config['target_modules']) <= set(TARGETS):
        raise ValueError('Unsupported original projection')
    new_config = deepcopy(config)
    new_config.update(r=rank, lora_alpha=config['lora_alpha'] * rank / old_rank,
                      target_modules=list(TARGETS), inference_mode=True)
    old_scale = config['lora_alpha'] / old_rank
    new_scale = new_config['lora_alpha'] / rank
    generator = torch.Generator().manual_seed(42)
    expanded, consumed, maximum_error = {}, set(), 0.0
    for layer in layers:
        for target, (outputs, inputs) in projection_shapes(base).items():
            block = 'mlp' if target in {'gate_proj', 'up_proj', 'down_proj'} else 'self_attn'
            stem = f'base_model.model.model.layers.{layer}.{block}.{target}'
            ka, kb = stem + '.lora_A.weight', stem + '.lora_B.weight'
            a = torch.empty((rank, inputs), dtype=torch.float32)
            a.uniform_(-1 / math.sqrt(inputs), 1 / math.sqrt(inputs), generator=generator)
            b = torch.zeros((outputs, rank), dtype=torch.float32)
            if target in config['target_modules']:
                source_a, source_b = original[ka].float(), original[kb].float()
                if tuple(source_a.shape) != (old_rank, inputs) or tuple(source_b.shape) != (outputs, old_rank):
                    raise ValueError('Original tensor shape differs from the base config: ' + stem)
                a[:old_rank].copy_(source_a)
                b[:, :old_rank].copy_(source_b * (old_scale / new_scale))
                consumed.update((ka, kb))
                x = torch.randn((3, inputs), generator=generator)
                before = (x @ source_a.T) @ source_b.T * old_scale
                after = (x @ a.T) @ b.T * new_scale
                torch.testing.assert_close(after, before, rtol=1e-5, atol=1e-6)
                maximum_error = max(maximum_error, float((after - before).abs().max()))
            elif torch.count_nonzero(b):
                raise AssertionError('New projections must initially contribute zero')
            if not torch.isfinite(a).all() or not torch.isfinite(b).all():
                raise ValueError('Non-finite expanded adapter weights')
            expanded[ka], expanded[kb] = a.contiguous(), b.contiguous()
    if consumed != set(original):
        raise ValueError('Some original adapter tensors would be lost')
    proof = {'initial_function_preserved': True, 'existing_projection_updates_checked': len(consumed) // 2,
             'new_projection_updates_zero': True, 'maximum_sampled_update_error': maximum_error,
             'source_parameters': sum(t.numel() for t in original.values()),
             'expanded_parameters': sum(t.numel() for t in expanded.values()),
             'scope': 'Preserved scaling and zero-padded old updates; new projections have exactly zero B. Not evidence of post-training quality.'}
    return expanded, new_config, proof


def expand(source, base_dir, output, rank=16):
    from safetensors.torch import load_file, save_file
    source, base_dir, output = Path(source).resolve(), Path(base_dir).resolve(), Path(output).resolve()
    if output == source or (output.exists() and any(output.iterdir())):
        raise ValueError('Use a new empty adapter directory')
    source_hashes = {name: digest(source / name) for name in ('adapter_config.json', 'adapter_model.safetensors')}
    base_hash = digest(base_dir / 'config.json')
    config = json.loads((source / 'adapter_config.json').read_text(encoding='utf-8'))
    base = json.loads((base_dir / 'config.json').read_text(encoding='utf-8'))
    weights, config, proof = expand_tensors(load_file(source / 'adapter_model.safetensors'), config, base, rank)
    config['base_model_name_or_path'] = str(base_dir)
    output.mkdir(parents=True, exist_ok=True)
    save_file(weights, output / 'adapter_model.safetensors', metadata={'format': 'pt'})
    save_json(output / 'adapter_config.json', config)
    if any(digest(source / name) != expected for name, expected in source_hashes.items()):
        raise RuntimeError('Source adapter changed during expansion')
    manifest = {'schema_version': 1, 'built_at': datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(),
                'source_adapter': str(source), 'source_sha256': source_hashes,
                'base_model': str(base_dir), 'base_config_sha256': base_hash,
                'proof': proof, 'rank': config['r'], 'alpha': config['lora_alpha'],
                'target_modules': config['target_modules'], 'layers': config['layers_to_transform'],
                'artifacts_sha256': {name: digest(output / name) for name in source_hashes},
                'recipe_sha256': digest(Path(__file__)), 'model_activated': False,
                'method_reference': 'https://huggingface.co/docs/peft/v0.17.0/developer_guides/lora',
                'note': 'Capacity hypothesis only; keep the same dataset/LR/epoch as v10 for a bounded comparison.'}
    save_json(output / 'expansion-manifest.json', manifest)
    return manifest


def verify_expansion(directory, active_adapter, expected_hash):
    directory, active_adapter = Path(directory).resolve(), Path(active_adapter).resolve()
    path = directory / 'expansion-manifest.json'
    if digest(path) != expected_hash:
        raise ValueError('Expanded adapter manifest changed')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1 or Path(manifest['source_adapter']).resolve() != active_adapter:
        raise ValueError('Expansion does not start from the current active adapter')
    if not manifest['proof'].get('initial_function_preserved') or not manifest['proof'].get('new_projection_updates_zero'):
        raise ValueError('Adapter expansion has no initial-function verification')
    for name in ('adapter_config.json', 'adapter_model.safetensors'):
        if digest(directory / name) != manifest['artifacts_sha256'][name] or digest(active_adapter / name) != manifest['source_sha256'][name]:
            raise ValueError('Expanded or source adapter weights changed')
    if digest(Path(manifest['base_model']) / 'config.json') != manifest['base_config_sha256']:
        raise ValueError('Expansion base configuration changed')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--base', type=Path, default=ROOT / 'models/xanhnon-qwen2.5-0.5b-vietnamese')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rank', type=int, default=16)
    args = parser.parse_args()
    result = expand(args.source, args.base, args.output, args.rank)
    print(json.dumps({'proof': result['proof'], 'rank': result['rank'], 'target_modules': result['target_modules']}))
