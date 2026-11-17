"""Measure CPU and Intel Vulkan throughput with a verified, separate runtime.

Synthetic llama-bench throughput excludes model startup and is not app latency.
Does not alter the active model, GPU drivers, system settings or application.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import time
import traceback
import zipfile
from zoneinfo import ZoneInfo

from sensor_training_data import digest, download, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prepared-model', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'status.json').exists():
        parser.error('Benchmark already exists')
    state = {'model_activated': False, 'worker_pid': os.getpid(),
             'measurement': 'Synthetic warm prompt/generation throughput; excludes startup and HTTP/UI latency'}

    def update(**values):
        state.update(values, checked_at=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat())
        save_json(output / 'status.json', state)

    try:
        update(status='preparing_runtime')
        entry = {'key': 'llama-b11471-bin-win-vulkan-x64.zip', 'size': 33378802,
                 'checksum': 'sha256:db253941698fdb946a5ff25df17f39a150ec536adc937eb5b9aad79bbe0e4fe1',
                 'url': 'https://github.com/ggml-org/llama.cpp/releases/download/b11471/llama-b11471-bin-win-vulkan-x64.zip'}
        archive, _ = download(entry, output / entry['key'])
        runtime = output / 'runtime'
        runtime.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                if not (runtime / item.filename).resolve().is_relative_to(runtime):
                    raise ValueError('Runtime archive contains a path outside its directory')
            bundle.extractall(runtime)
        binaries = list(runtime.rglob('llama-bench.exe'))
        if len(binaries) != 1:
            raise ValueError('Expected exactly one benchmark executable')
        binary = binaries[0]
        detected = subprocess.run([str(binary), '--list-devices'], capture_output=True, timeout=30,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (output / 'devices.stdout.log').write_bytes(detected.stdout)
        (output / 'devices.stderr.log').write_bytes(detected.stderr)
        if detected.returncode or b'Intel' not in detected.stdout + detected.stderr:
            raise RuntimeError('The trial runtime did not identify the Intel GPU')
        ready = json.loads((args.prepared_model / 'preparation-state.json').read_text(encoding='utf-8'))
        model = Path(ready['path'])
        if ready['status'] != 'ready_for_evaluation' or digest(model) != ready['sha256']:
            raise ValueError('Prepared model is not verified')
        import psutil
        deadline = time.monotonic() + 3600
        while psutil.virtual_memory().available < 4.5 * 1024**3:
            update(status='waiting_for_memory', available_ram_gb=round(psutil.virtual_memory().available / 1024**3, 2))
            if time.monotonic() > deadline:
                raise TimeoutError('Not enough free memory for the hardware benchmark')
            time.sleep(30)
        results = {}
        for name, layers in [('cpu', '0'), ('vulkan', '99')]:
            update(status='benchmarking', phase=name)
            command = [str(binary), '-m', str(model), '-p', '256', '-n', '64', '-r', '2',
                       '-t', '2', '-ngl', layers, '-o', 'json']
            with (output / (name + '.json')).open('wb') as stdout, (output / (name + '.stderr.log')).open('wb') as stderr:
                completed = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                           timeout=480, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if completed.returncode:
                raise RuntimeError(f'{name} benchmark failed with code {completed.returncode}')
            results[name] = json.loads((output / (name + '.json')).read_text(encoding='utf-8'))
        save_json(output / 'results.json', {'model': str(model), 'model_sha256': ready['sha256'],
                  'runtime_sha256': entry['checksum'].split(':', 1)[1], 'threads': 2, 'repetitions': 2,
                  'measurement': state['measurement'], 'results': results, 'model_activated': False})
        update(status='completed', phase='benchmark_finished')
    except Exception as error:
        update(status='failed', error=str(error))
        (output / 'error.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
