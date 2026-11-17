"""Recover one interrupted queue job without overwriting its prior candidate.

Uses the same OS queue lock and frozen dataset, then records completion in the
existing queue/monitor format. Legacy weights-only recovery is explicit.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import traceback

import psutil

from daily_train_xanhnon import candidate_status, memory_ready, run_training
from queue_sensor_training import validate_prepared_dataset
from sensor_training_data import ROOT, digest, save_json
from training_state import training_in_progress


def recovery_command(checkpoint, previous, candidate, *, allow_optimizer_reset=False):
    config = previous['configuration']
    command = [str(ROOT / '.venv/Scripts/python.exe'), str(ROOT / 'train_xanhnon.py'),
               '--train', '--data-dir', previous['data_dir'], '--output', str(candidate),
               '--resume-from', str(checkpoint), '--epochs', str(config['epochs']),
               '--max-length', str(previous['max_length']), '--accumulation', str(config['accumulation']),
               '--last-layers', str(config['last_layers']), '--threads', '2',
               '--learning-rate', str(config['learning_rate']), '--checkpoint-every', '8', '--allow-cpu-paging']
    for key, flag in [('limit', '--limit'), ('validation_limit', '--validation-limit'), ('max_steps', '--max-steps')]:
        if config.get(key):
            command += [flag, str(config[key])]
    for source in config.get('train_sources', []):
        command += ['--train-source', source]
    if allow_optimizer_reset:
        command.append('--allow-optimizer-reset')
    return command


def recover(storage, checkpoint, max_hours, allow_optimizer_reset=False):
    storage, checkpoint = Path(storage).resolve(), Path(checkpoint).resolve()
    with (storage / 'sensor-queue.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = storage / 'sensor-queue.json'
        old = json.loads(path.read_text(encoding='utf-8'))
        if training_in_progress() or old.get('status') not in {'failed', 'incomplete'}:
            raise ValueError('Recover only an interrupted job with no active trainer')
        if checkpoint.parent.name != 'checkpoints' or checkpoint.parent.parent != Path(old['candidate']).resolve():
            raise ValueError('Checkpoint does not belong to the interrupted candidate')
        previous = json.loads((checkpoint / 'progress.json').read_text(encoding='utf-8'))
        if previous.get('mode') != 'lora_training' or not 0 < previous['steps_completed'] < previous['steps_planned']:
            raise ValueError('Choose an incomplete training checkpoint')
        for name in ('adapter_config.json', 'adapter_model.safetensors'):
            if not (checkpoint / name).is_file():
                raise ValueError('Incomplete checkpoint: ' + name)
        if not (checkpoint / 'trainer-state.pt').exists() and not allow_optimizer_reset:
            raise ValueError('This older checkpoint needs --allow-optimizer-reset')
        validate_prepared_dataset(Path(previous['data_dir']))
        if digest(Path(previous['data_dir']) / 'manifest.json') != previous['manifest_sha256']:
            raise ValueError('Checkpoint data manifest no longer matches')
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        archive = storage / ('sensor-queue-before-recovery-' + stamp + '.json')
        save_json(archive, old)
        candidate = storage / ('dialogue-candidate-recovery-' + stamp)
        command = recovery_command(checkpoint, previous, candidate, allow_optimizer_reset=allow_optimizer_reset)
        job = {**old, 'requested_at': datetime.now(timezone.utc).isoformat(),
               'status': 'waiting_for_resources', 'phase': 'recovering_interrupted_training',
               'candidate': str(candidate), 'source_adapter': str(checkpoint),
               'adapter_reason': 'recover_interrupted_job_from_verified_checkpoint',
               'resume_checkpoint': str(checkpoint), 'resume_step': previous['steps_completed'],
               'previous_candidate': old['candidate'], 'previous_queue_archive': str(archive),
               'optimizer_reinitialized': not (checkpoint / 'trainer-state.pt').exists(),
               'start_from_active_release': False,
               'max_training_hours': max_hours, 'command': command,
               'worker_pid': os.getpid(), 'worker_create_time': psutil.Process().create_time(),
               'checkpoint_sha256': {name: digest(checkpoint / name) for name in
                                     ('progress.json', 'adapter_config.json', 'adapter_model.safetensors')},
               'model_activated': False}
        for key in ('error', 'report', 'steps', 'trained_examples', 'baseline_validation_loss', 'candidate_validation_loss'):
            job.pop(key, None)

        def update(**values):
            job.update(values, updated_at=datetime.now(timezone.utc).isoformat())
            save_json(path, job)

        try:
            update()
            deadline = time.monotonic() + 4 * 3600
            while training_in_progress() or not memory_ready(allow_cpu_paging=True):
                if time.monotonic() > deadline:
                    raise TimeoutError('Recovery could not obtain training resources')
                time.sleep(30)
            update(status='training', phase='restoring_checkpoint')
            with (storage / 'sensor-training.log').open('a', encoding='utf-8') as log:
                result = run_training(command, log, timeout_seconds=max_hours * 3600)
            if result:
                raise RuntimeError('Recovered trainer exited with status ' + str(result))
            report_path = candidate / 'training_report.json'
            report = json.loads(report_path.read_text(encoding='utf-8'))
            status = candidate_status(report)
            if status != 'incomplete' and job.get('fingerprint'):
                trained_path = storage / 'sensor-trained-fingerprints.json'
                fingerprints = json.loads(trained_path.read_text(encoding='utf-8')) if trained_path.exists() else []
                if job['fingerprint'] not in fingerprints:
                    save_json(trained_path, fingerprints + [job['fingerprint']])
            update(status=status, phase='training_finished', report=str(report_path),
                   steps=report['steps'], trained_examples=report['trained_examples'],
                   baseline_validation_loss=report['baseline_validation_loss'],
                   candidate_validation_loss=report['candidate_validation_loss'])
        except Exception as error:
            update(status='failed', error=str(error))
            with (storage / 'sensor-queue-errors.log').open('a', encoding='utf-8') as log:
                traceback.print_exc(file=log)
        return job


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage', type=Path, default=Path('D:/XanhNon-auto-training'))
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--max-hours', type=int, default=24)
    parser.add_argument('--allow-optimizer-reset', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.max_hours <= 72:
        parser.error('--max-hours must be between 1 and 72')
    print(json.dumps(recover(args.storage, args.checkpoint, args.max_hours, args.allow_optimizer_reset), ensure_ascii=False))
