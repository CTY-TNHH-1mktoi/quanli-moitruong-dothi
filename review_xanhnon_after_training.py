"""Wait for one owned candidate, export to the archive, and compare real answers.

This one-shot reviewer never activates weights. Its state is written to --output.
"""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os
from pathlib import Path
import subprocess
import time
import traceback

import psutil

from sensor_training_data import ROOT, digest, save_json
from training_state import training_in_progress


def review_cases(path, all_development=False):
    from evaluate_xanhnon import evaluation_cases
    cases, fingerprint = evaluation_cases(path)
    legacy, _ = evaluation_cases(ROOT / 'data/xanhnon/eval_consultation.json')
    previous_extra = json.loads((ROOT / 'data/xanhnon/eval_balanced_extra.json').read_text(encoding='utf-8'))
    expected = {c['id'] for c in legacy + previous_extra}
    if not expected <= {c['id'] for c in cases}:
        raise ValueError('Keep all previous 28 development cases in both model comparisons')
    return cases, fingerprint, {'development_regression_cases': len(cases) if all_development else len(expected),
                                'additional_confirmation_cases': 0 if all_development else len(cases) - len(expected)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--training-snapshot', type=Path, required=True)
    parser.add_argument('--expected-steps', type=int, required=True)
    parser.add_argument('--wait-hours', type=int, default=8,
                        help='Maximum time to wait for training and review resources, including long interruptions')
    parser.add_argument('--name', default='XanhNon-Candidate', help='Export metadata label, not an activation request')
    parser.add_argument('--all-cases-development', action='store_true',
                        help='Previous confirmation cases already informed training decisions; report them as development cases')
    parser.add_argument('--prompt-profile', choices=['legacy', 'grounded-v12', 'grounded-v15'], default='legacy')
    args = parser.parse_args()
    if not 1 <= args.wait_hours <= 168:
        parser.error('--wait-hours must be between 1 and 168')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'review-state.json').exists():
        parser.error('Review already exists; inspect it instead of starting a duplicate')
    try:
        cases, case_hash, coverage = review_cases(output / 'extra-cases.json', args.all_cases_development)
    except ValueError as error:
        parser.error(str(error))
    state = {'candidate': str(args.candidate.resolve()), 'model_activated': False,
             'reviewer_pid': os.getpid(), 'reviewer_create_time': psutil.Process().create_time(),
             'coverage': coverage, 'cases_sha256': case_hash, 'prompt_profile': args.prompt_profile,
             'wait_hours': args.wait_hours}

    def update(**values):
        state.update(values, checked_at=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat())
        save_json(output / 'review-state.json', state)

    def run(name, arguments):
        update(phase=name)
        with (output / (name + '.stdout.log')).open('w', encoding='utf-8') as stdout, \
             (output / (name + '.stderr.log')).open('w', encoding='utf-8') as stderr:
            process = subprocess.Popen([str(ROOT / '.venv/Scripts/python.exe')] + arguments,
                cwd=ROOT, stdout=stdout, stderr=stderr,
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1'},
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            update(child_pid=process.pid, child_create_time=psutil.Process(process.pid).create_time())
            try:
                code = process.wait(timeout=20 * 60)
            except subprocess.TimeoutExpired:
                owned = psutil.Process(process.pid)
                for child in owned.children(recursive=True) + [owned]:
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                raise
            if code:
                raise RuntimeError(f'{name} exited with code {code}; inspect its stderr log')

    try:
        update(status='waiting_for_training', phase='waiting_for_completed_report')
        deadline = time.monotonic() + args.wait_hours * 3600
        report_path = args.candidate / 'training_report.json'
        while not report_path.exists():
            job = json.loads((args.candidate.parent / 'sensor-queue.json').read_text(encoding='utf-8'))
            if job.get('candidate') == str(args.candidate) and job.get('status') == 'failed':
                raise RuntimeError('Training failed: ' + str(job.get('error')))
            if time.monotonic() > deadline:
                raise TimeoutError(f'Training report was not produced within {args.wait_hours} hours')
            time.sleep(30)
        training = json.loads(report_path.read_text(encoding='utf-8'))
        if args.prompt_profile != 'legacy':
            manifest = json.loads((Path(training['data_dir']) / 'manifest.json').read_text(encoding='utf-8'))
            profile_recipe = ROOT / ('chat_briefing_v15.py' if args.prompt_profile == 'grounded-v15' else 'chat_briefing.py')
            if (manifest.get('prompt_profile') != args.prompt_profile
                    or manifest['input_sha256']['prompt_profile_recipe'] != digest(profile_recipe)):
                raise RuntimeError('Prompt profile differs from the frozen training batch')
            if args.prompt_profile == 'grounded-v15' and manifest['input_sha256']['base_prompt_profile_recipe'] != digest(ROOT / 'chat_briefing.py'):
                raise RuntimeError('Base prompt profile differs from the frozen training batch')
        if not training.get('selected_data_pass_completed') or training.get('steps') != args.expected_steps:
            raise RuntimeError('The candidate did not complete its planned training pass')
        update(status='waiting_for_resources', phase='waiting_for_export_resources', steps=training['steps'])
        while training_in_progress() or psutil.virtual_memory().available < 3 * 1024**3:
            if time.monotonic() > deadline:
                raise TimeoutError('Not enough resources to review the completed candidate')
            time.sleep(30)
        active_path = ROOT / 'models/xanhnon-active.json'
        original_active = active_path.read_bytes()
        release = json.loads(original_active)
        save_json(output / 'active-before.json', release)
        names = ['chatbot.py', 'chat_knowledge.py', 'chat_scope.py', 'chat_output.py',
                 'native_chatbot.py', 'evaluate_xanhnon.py', 'chat_answer_checks.py', 'data/xanhnon/knowledge.json']
        if args.prompt_profile != 'legacy':
            names += ['chat_briefing.py', 'data/xanhnon/specialist_supplement.json']
        if args.prompt_profile == 'grounded-v15':
            names += ['chat_briefing_v15.py']
        hashes = {name: digest(ROOT / name) for name in names}
        gguf = output / 'candidate-f16.gguf'
        merged = output.parent / (output.name + '-merged')
        if gguf.exists() or merged.exists():
            raise RuntimeError('Export artifacts already exist; inspect before retrying')
        update(status='reviewing', baseline_validation_loss=training.get('baseline_validation_loss'),
               candidate_validation_loss=training.get('candidate_validation_loss'),
               application_sha256=hashes, extra_cases_sha256=digest(output / 'extra-cases.json'))
        run('export', ['export_xanhnon.py', '--adapter', str(args.candidate), '--gguf', str(gguf),
                       '--merged', str(merged), '--name', args.name])
        extra = ['--extra-cases', str(output / 'extra-cases.json'), '--threads', '2', '--prompt-profile', args.prompt_profile]
        run('baseline', ['evaluate_xanhnon.py', '--model', str(ROOT / release['gguf']),
                         '--output', str(output / 'baseline-core.json')] + extra)
        run('candidate', ['evaluate_xanhnon.py', '--model', str(gguf),
                          '--output', str(output / 'candidate-core.json'),
                          '--compare', str(output / 'baseline-core.json')] + extra)
        answer_report = json.loads((output / 'candidate-core.json').read_text(encoding='utf-8'))
        _, current_case_hash, _ = review_cases(output / 'extra-cases.json', args.all_cases_development)
        if current_case_hash != case_hash or answer_report.get('cases_sha256') != case_hash:
            raise RuntimeError('Evaluation cases changed during review; generate a fresh comparison')
        if active_path.read_bytes() != original_active or any(digest(ROOT / name) != value for name, value in hashes.items()):
            raise RuntimeError('Application/release changed during comparison; a fresh comparison is required')
        comparison = answer_report['comparison']
        eligible = (comparison['eligible_for_manual_review'] and
                    comparison['candidate_passed'] > comparison['baseline_passed'])
        decision = 'awaiting_manual_answer_review' if eligible else 'rejected_answer_quality'
        result = {'checked_at': datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(),
                  'decision': decision, 'candidate': str(args.candidate), 'candidate_gguf': str(gguf),
                  'candidate_gguf_sha256': digest(gguf), 'model_activated': False,
                  'case_count': answer_report['case_count'], 'passed': answer_report['passed'],
                  'prompt_profile': args.prompt_profile,
                  'assessment_version': answer_report['assessment_version'], 'comparison': comparison,
                  'coverage': state['coverage'], 'requires_strict_pass_count_gain': True,
                  'active_release_preserved': True,
                  'scope': 'Raw native model generations, with existing app routing excluded.'}
        save_json(output / 'release-decision.json', result)
        snapshot = json.loads(args.training_snapshot.read_text(encoding='utf-8'))
        snapshot['completion_review'] = {**result, 'report_directory': str(output)}
        save_json(args.training_snapshot, snapshot)
        update(status=decision, phase='review_finished', passed=answer_report['passed'],
               case_count=answer_report['case_count'], comparison=comparison)
    except Exception as error:
        update(status='failed', error=str(error))
        (output / 'error.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
