"""Freeze a same-data, same-LR/epoch capacity experiment without claiming new data."""
import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

from expand_xanhnon_adapter import verify_expansion
from model_release import read_release
from queue_sensor_training import validate_prepared_dataset
from sensor_training_data import ROOT, digest, save_json


def prepare(source, adapter, output):
    source, adapter, output = Path(source).resolve(), Path(adapter).resolve(), Path(output).resolve()
    if source == output or (output.exists() and any(output.iterdir())):
        raise ValueError('Use a new empty dataset directory')
    old = validate_prepared_dataset(source)
    adapter_hash = digest(adapter / 'expansion-manifest.json')
    expansion = verify_expansion(adapter, read_release(ROOT)['adapter'], adapter_hash)
    manifest = deepcopy(old)
    manifest.update(built_at=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(),
                    new_dialogue_counts={'train': 0, 'validation': 0}, model_activated=False)
    manifest['training_configuration'].update(capacity_adapter=str(adapter),
                                             capacity_adapter_manifest_sha256=adapter_hash)
    manifest['input_sha256'].update(source_dataset_manifest=digest(source / 'manifest.json'),
                                   capacity_recipe=digest(Path(__file__)),
                                   adapter_expansion=digest(ROOT / 'expand_xanhnon_adapter.py'))
    manifest['experiment'] = {
        'name': 'capacity-v11', 'hypothesis': 'More trainable projections/rank may correct errors that did not improve with narrow q/v LoRA.',
        'source_dataset': str(source), 'new_training_records': 0,
        'intentional_same_data_replay': True, 'same_learning_rate_and_epoch_as_v10': True,
        'source_parameters': expansion['proof']['source_parameters'],
        'expanded_parameters': expansion['proof']['expanded_parameters'],
        'start_from_rejected_v10': False,
        'evaluation_role': 'All 36 previous generation cases are now development regression cases, not unseen confirmation.',
    }
    manifest['limitations'] += [
        'This is an explicit same-data architecture experiment, not a new or larger dataset.',
        'More trainable parameters may help or harm; generation comparison is required.',
        'Repeated use of all 36 generation cases cannot establish generalization to unseen questions.',
    ]
    output.mkdir(parents=True, exist_ok=True)
    for name in ('train.jsonl', 'validation.jsonl', 'LICENSE-APACHE-2.0.txt', 'NOTICE.md'):
        shutil.copy2(source / name, output / name)
    for name, expected in manifest['artifacts_sha256'].items():
        if digest(output / name) != expected:
            raise RuntimeError('Frozen dataset copy differs from the original')
    save_json(output / 'manifest.json', manifest)
    (output / 'EXPERIMENT.md').write_text(
        '# v11 capacity experiment\n\nReuses the exact 120 training and 20 validation records from v10. '
        'No samples were relabeled as newly collected data. LR, epoch and context length stay the same. '
        'The separate starting adapter preserves active v2 updates and adds trainable projections/rank. '
        'All previous 36 evaluation questions are development cases. No weights are automatically activated.\n', encoding='utf-8')
    validate_prepared_dataset(output)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.adapter, args.output)
    print(json.dumps({'configuration': result['training_configuration'], 'experiment': result['experiment']}, ensure_ascii=False))
