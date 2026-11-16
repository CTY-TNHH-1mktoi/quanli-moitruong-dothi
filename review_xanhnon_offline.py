"""Compare a completed export through llama-completion, without local HTTP.

Keeps raw prompts, stdout, stderr and a fresh baseline under a separate review.
Never changes the application's active release or its runtime.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
from zoneinfo import ZoneInfo

from sensor_training_data import ROOT, digest, save_json


def tokenizer_files(directory):
    """Fingerprint both supported local layouts, including added token metadata."""
    directory = Path(directory)
    if not (directory / 'tokenizer_config.json').is_file():
        raise FileNotFoundError('Missing local tokenizer_config.json')
    if not (directory / 'tokenizer.json').is_file() and not all(
            (directory / name).is_file() for name in ('vocab.json', 'merges.txt')):
        raise FileNotFoundError('Tokenizer needs tokenizer.json or both vocab.json and merges.txt')
    names = ('tokenizer_config.json', 'tokenizer.json', 'vocab.json', 'merges.txt',
             'special_tokens_map.json', 'added_tokens.json', 'chat_template.jinja')
    return [directory / name for name in names if (directory / name).is_file()]


def parse_completion(stdout):
    """Remove only the Qwen end marker and the CLI's terminal decoration."""
    match = re.search(r'<\|(?:im_end|endoftext)\|>\s*(?:\[end of text\])?\s*\Z', stdout)
    reply = (stdout[:match.start()] if match else stdout).strip()
    if not reply:
        raise ValueError('Empty CLI generation')
    return {'reply': reply, 'truncated': match is None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior-review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--training-snapshot', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'review-state.json').exists():
        parser.error('Review already exists; inspect it instead of duplicating it')
    state = {'model_activated': False, 'runtime': 'llama_completion_cli',
             'reviewer_pid': os.getpid(), 'prior_review': str(args.prior_review.resolve())}

    def update(**values):
        state.update(values, checked_at=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat())
        save_json(output / 'review-state.json', state)

    try:
        update(status='preparing', phase='checking_export_and_frozen_inputs')
        tokenizer_path = ROOT / 'models/xanhnon-qwen2.5-0.5b-vietnamese'
        tokenizer_inputs = tokenizer_files(tokenizer_path)
        import psutil
        from transformers import AutoTokenizer
        from evaluate_xanhnon import ASSESSMENT_VERSION, assess, compare_answers, messages_for
        from review_xanhnon_after_training import review_cases
        from training_state import training_in_progress

        prior = json.loads((args.prior_review / 'review-state.json').read_text(encoding='utf-8'))
        candidate = Path(prior['candidate'])
        training = json.loads((candidate / 'training_report.json').read_text(encoding='utf-8'))
        snapshot = json.loads(args.training_snapshot.read_text(encoding='utf-8'))
        if (not training.get('selected_data_pass_completed')
                or training['steps'] != snapshot['expected_steps']
                or Path(snapshot['candidate']).resolve() != candidate.resolve()):
            raise ValueError('Training is incomplete or the snapshot belongs to another candidate')
        profile = prior['prompt_profile']
        if profile != 'grounded-v15':
            raise ValueError('This offline review currently supports only the frozen v15 profile')
        manifest = json.loads((Path(training['data_dir']) / 'manifest.json').read_text(encoding='utf-8'))
        if (digest(Path(training['data_dir']) / 'manifest.json') != training['manifest_sha256']
                or manifest['prompt_profile'] != profile
                or manifest['input_sha256']['prompt_profile_recipe'] != digest(ROOT / 'chat_briefing_v15.py')
                or manifest['input_sha256']['base_prompt_profile_recipe'] != digest(ROOT / 'chat_briefing.py')):
            raise ValueError('Frozen training profile changed')
        cases, case_hash, coverage = review_cases(args.prior_review / 'extra-cases.json', True)
        if case_hash != prior['cases_sha256']:
            raise ValueError('Cases differ from the interrupted review')
        save_json(output / 'extra-cases.json', json.loads((args.prior_review / 'extra-cases.json').read_text(encoding='utf-8')))
        gguf = args.prior_review / 'candidate-f16.gguf'
        exported = json.loads((args.prior_review / 'export.stdout.log').read_text(encoding='utf-8').strip().splitlines()[-1])
        update(phase='checking_candidate_export_hash')
        if Path(exported['gguf']).resolve() != gguf.resolve() or digest(gguf) != exported['sha256']:
            raise ValueError('Completed export does not match its saved hash')
        active_path = ROOT / 'models/xanhnon-active.json'
        active_bytes = active_path.read_bytes()
        active = json.loads(active_bytes)
        baseline_model = ROOT / active['gguf']
        update(phase='checking_baseline_model_hash')
        if digest(baseline_model) != active['gguf_sha256']:
            raise ValueError('Active baseline model hash changed')
        binary = ROOT / '.runtime/llama-bin/llama-completion.exe'
        update(phase='checking_tokenizer_templates')
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
        sys.path.insert(0, str(ROOT / '.runtime/llama-converter/gguf-py'))
        from gguf import GGUFReader
        for model in (baseline_model, gguf):
            reader = GGUFReader(str(model))
            if reader.get_field('tokenizer.chat_template').contents() != tokenizer.chat_template:
                raise ValueError('GGUF and tokenizer chat templates differ')
            del reader
        files = ['evaluate_xanhnon.py', 'chat_answer_checks.py', 'chat_briefing_v15.py',
                 'chat_briefing.py', 'chat_knowledge.py', 'chat_scope.py', 'chat_output.py',
                 'data/xanhnon/knowledge.json', 'data/xanhnon/specialist_supplement.json',
                 'review_xanhnon_offline.py']
        files += [path.relative_to(ROOT).as_posix() for path in tokenizer_inputs]
        hashes = {name: digest(ROOT / name) for name in files}
        binary_hash = digest(binary)
        scope = 'core_generation_without_deterministic_replies:grounded-v15:llama_completion_cli'
        update(candidate=str(candidate), candidate_gguf=str(gguf), cases_sha256=case_hash,
               coverage=coverage, case_count=len(cases), prompt_profile=profile,
               application_sha256=hashes, binary_sha256=binary_hash,
               assessment_version=ASSESSMENT_VERSION, steps=training['steps'],
               baseline_validation_loss=training['baseline_validation_loss'],
               candidate_validation_loss=training['candidate_validation_loss'])
        save_json(output / 'active-before.json', active)
        deadline = time.monotonic() + 3600
        while training_in_progress() or psutil.virtual_memory().available < 3 * 1024**3:
            update(status='waiting_for_resources', phase='waiting_for_memory')
            if time.monotonic() > deadline:
                raise TimeoutError('Not enough memory for offline review')
            time.sleep(30)
        reports = {}
        for label, model in [('baseline', baseline_model), ('candidate', gguf)]:
            results = []
            update(status='reviewing', phase=label, completed_cases=0)
            with (output / (label + '-answers.jsonl')).open('w', encoding='utf-8', buffering=1) as answers:
                for index, case in enumerate(cases):
                    stem = f'{label}-{index + 1:02d}-{case["id"]}'
                    messages = messages_for(case, profile)
                    tokens = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
                    if len(tokens) > 8192:
                        raise ValueError('Case exceeds the original evaluation input limit')
                    prompt = output / (stem + '.prompt.txt')
                    prompt.write_text(tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True), encoding='utf-8')
                    command = [str(binary), '-m', str(model), '-f', str(prompt), '-t', '2', '-tb', '2',
                               '-c', '10240', '-b', '256', '-ub', '128', '-n', '192', '-ngl', '0',
                               '--temp', '0', '--top-k', '1', '--top-p', '1', '--repeat-penalty', '1.1',
                               '--repeat-last-n', '64', '--seed', '42', '--no-conversation',
                               '--no-display-prompt', '--no-escape', '--simple-io', '--special',
                               '--perf', '--color', 'off']
                    started = time.monotonic()
                    with (output / (stem + '.stdout.log')).open('wb') as stdout, (output / (stem + '.stderr.log')).open('wb') as stderr:
                        completed = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                                   timeout=120, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    if completed.returncode:
                        raise RuntimeError(f'{stem} exited with code {completed.returncode}')
                    result = parse_completion((output / (stem + '.stdout.log')).read_text(encoding='utf-8'))
                    record = assess(case, result, time.monotonic() - started)
                    record['input_tokens'] = len(tokens)
                    results.append(record)
                    answers.write(json.dumps(record, ensure_ascii=False) + '\n')
                    update(completed_cases=index + 1, passed_so_far=sum(r['passed'] for r in results), last_case=case['id'])
            report = {'model': str(model), 'evaluation_scope': scope, 'prompt_profile': profile,
                      'assessment_version': ASSESSMENT_VERSION, 'cases_sha256': case_hash,
                      'inference_threads': 2, 'case_count': len(results),
                      'passed': sum(r['passed'] for r in results),
                      'average_words': round(sum(r['words'] for r in results) / len(results), 1),
                      'cases': results}
            if label == 'candidate':
                report['comparison'] = compare_answers({r['id']: r for r in reports['baseline']['cases']}, results,
                                                       reports['baseline']['average_words'])
            save_json(output / (label + '-core.json'), report)
            reports[label] = report
        if (active_path.read_bytes() != active_bytes or digest(binary) != binary_hash
                or any(digest(ROOT / name) != value for name, value in hashes.items())
                or review_cases(args.prior_review / 'extra-cases.json', True)[1] != case_hash
                or digest(gguf) != exported['sha256']):
            raise ValueError('Comparison inputs changed during review')
        report = reports['candidate']
        comparison = report['comparison']
        eligible = comparison['eligible_for_manual_review'] and comparison['candidate_passed'] > comparison['baseline_passed']
        decision = 'awaiting_manual_answer_review' if eligible else 'rejected_answer_quality'
        result = {**state, 'decision': decision, 'candidate_gguf_sha256': exported['sha256'],
                  'passed': report['passed'], 'comparison': comparison,
                  'evaluation_scope': scope, 'active_release_preserved': True,
                  'requires_strict_pass_count_gain': True,
                  'limitation': 'Offline CLI comparison; app HTTP integration remains unverified.'}
        save_json(output / 'release-decision.json', result)
        snapshot['completion_review'] = {**result, 'report_directory': str(output)}
        save_json(args.training_snapshot, snapshot)
        update(status=decision, phase='review_finished', passed=report['passed'], comparison=comparison)
    except Exception as error:
        update(status='failed', error=str(error))
        (output / 'error.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
