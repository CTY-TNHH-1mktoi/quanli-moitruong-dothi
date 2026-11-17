"""Measure visible-token and completion latency while retaining one local model.

Uses synthetic development scenarios. CPU and GPU use the same 4096-token
runtime context, settings and prompts. Never changes the active application.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
from threading import Timer
import time
import traceback
from zoneinfo import ZoneInfo

from native_chatbot import NativeChatbot
from sensor_training_data import digest, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--hardware', type=Path, required=True)
    parser.add_argument('--reference-review', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'status.json').exists():
        parser.error('Warm chat benchmark already exists')
    state = {'model_activated': False, 'context_tokens': 4096, 'input_limit': 2048,
             'synthetic_contexts': True, 'measurement': 'Local inference HTTP, excluding application routing/UI'}

    def update(**values):
        state.update(values, checked_at=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat())
        save_json(output / 'status.json', state)

    try:
        update(status='preparing')
        from evaluate_xanhnon import evaluation_cases, messages_for, assess
        hardware = json.loads((args.hardware / 'results.json').read_text(encoding='utf-8'))
        model = Path(hardware['model'])
        if digest(model) != hardware['model_sha256']:
            raise ValueError('The benchmark model changed')
        binary = args.hardware / 'runtime/llama-server.exe'
        cases, fingerprint = evaluation_cases(args.reference_review / 'extra-cases.json')
        by_id = {case['id']: case for case in cases}
        selected = [by_id[name] for name in ('current_weather', 'unseen_weather', 'dust_without_filter_followup')]
        results = {}
        for backend, layers in [('cpu', 0), ('vulkan', 99)]:
            update(status='loading_model', phase=backend, completed_cases=0)
            started = time.monotonic()
            runtime = NativeChatbot(binary, model, 2, 2048, 192, gpu_layers=layers,
                                    log_path=output / (backend + '-server.log'))
            startup = time.monotonic() - started
            records = []
            try:
                for index, case in enumerate(selected):
                    first_visible = [None]

                    def receive(text):
                        if text.strip() and first_visible[0] is None:
                            first_visible[0] = time.monotonic()

                    update(status='benchmarking', phase=backend, case_id=case['id'])
                    began = time.monotonic()
                    timer = Timer(120, runtime.close)
                    timer.daemon = True
                    timer.start()
                    try:
                        result = runtime.generate(messages_for(case, 'grounded-v15'), 192, on_text=receive)
                    finally:
                        timer.cancel()
                    elapsed = time.monotonic() - began
                    row = assess(case, result, elapsed)
                    row['first_visible_seconds'] = round(first_visible[0] - began, 3) if first_visible[0] else None
                    row['case_position'] = index + 1
                    records.append(row)
                    save_json(output / (backend + '-partial.json'), records)
                    update(completed_cases=len(records), first_visible_seconds=row['first_visible_seconds'], completion_seconds=row['seconds'])
            finally:
                runtime.close()
            results[backend] = {'startup_seconds': round(startup, 3), 'gpu_layers': layers,
                                'same_process_for_all_cases': True, 'cases': records}
        save_json(output / 'results.json', {'model': str(model), 'model_sha256': hardware['model_sha256'],
                  'cases_sha256': fingerprint, 'context_tokens': 4096, 'threads': 2,
                  'native_runtime_sha256': digest(Path(__file__).with_name('native_chatbot.py')),
                  'runtime': str(binary), 'results': results, 'model_activated': False,
                  'limitations': ['Three synthetic development scenarios, one pass per backend.',
                                  'Context is 4096, unlike the older reload-per-case trial at 10240.',
                                  'Measures inference HTTP only; application routing and browser rendering are excluded.']})
        update(status='completed', phase='benchmark_finished')
    except Exception as error:
        update(status='failed', error=str(error))
        (output / 'error.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
