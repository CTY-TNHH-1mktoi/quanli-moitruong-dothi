"""Evaluate a prepared GGUF base trial after the owned v15 review finishes.

Uses the same 48 definitions, evidence profile, CLI settings and saved v2 baseline.
Writes a report only; never trains or activates a model.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from zoneinfo import ZoneInfo

from sensor_training_data import ROOT, digest, save_json


def validate_resume(previous, cases, rows, hashes, model_hash, binary_hash, case_hash):
    if previous.get('status') != 'failed' or previous.get('error') != 'Empty CLI generation':
        raise ValueError('Only the interrupted empty-generation review can be resumed')
    if (previous.get('model_sha256') != model_hash or previous.get('binary_sha256') != binary_hash
            or previous.get('cases_sha256') != case_hash or previous.get('prompt_profile') != 'grounded-v15'):
        raise ValueError('Resume model, binary, cases or profile changed')
    if not 0 <= len(rows) == previous.get('completed_cases') < len(cases):
        raise ValueError('Resume progress differs from the saved answer prefix')
    if [row['id'] for row in rows] != [case['id'] for case in cases[:len(rows)]]:
        raise ValueError('Saved answers must be the same ordered prefix')
    for name, expected in previous['application_sha256'].items():
        if name != 'evaluate_xanhnon_base_trial.py' and hashes.get(name) != expected:
            raise ValueError('Frozen evaluation dependency changed: ' + name)


def assess_stdout(case, stdout, elapsed):
    from evaluate_xanhnon import assess
    from review_xanhnon_offline import parse_completion
    try:
        result = parse_completion(stdout)
        empty = False
    except ValueError as error:
        if str(error) != 'Empty CLI generation':
            raise
        result, empty = {'reply': '', 'truncated': False}, True
    row = assess(case, result, elapsed)
    if empty:
        row['violations'].insert(0, 'empty_generation')
        row['passed'] = False
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--reference-review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume', action='store_true', help='Continue an archived empty-generation interruption')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    previous, saved_rows = None, []
    if args.resume:
        previous = json.loads((output / 'review-state.before-resume.json').read_text(encoding='utf-8'))
        if json.loads((output / 'review-state.json').read_text(encoding='utf-8')) != previous:
            parser.error('The archived failure was already resumed or its state changed')
        if digest(output / 'evaluator.before-resume.py') != previous['application_sha256']['evaluate_xanhnon_base_trial.py']:
            parser.error('Original evaluator archive does not match its recorded hash')
        if digest(output / 'answers.jsonl') != digest(output / 'answers.before-resume.jsonl'):
            parser.error('Original answer prefix changed or was already resumed')
        saved_rows = [json.loads(line) for line in (output / 'answers.jsonl').read_text(encoding='utf-8').splitlines()]
    elif (output / 'review-state.json').exists():
        parser.error('Trial evaluation already exists')
    state = {'model_activated': False, 'reviewer_pid': os.getpid(),
             'model_dir': str(args.model_dir.resolve()), 'runtime': 'llama_completion_cli'}

    def update(**values):
        state.update(values, checked_at=datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat())
        save_json(output / 'review-state.json', state)

    try:
        deadline = time.monotonic() + 4 * 3600
        while True:
            ready_path = args.model_dir / 'preparation-state.json'
            ready = json.loads(ready_path.read_text(encoding='utf-8')) if ready_path.exists() else {}
            review_path = args.reference_review / 'review-state.json'
            reference = json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
            if ready.get('status') == 'failed':
                raise RuntimeError('Model preparation failed: ' + str(ready.get('error')))
            if (ready.get('status') == 'ready_for_evaluation'
                    and reference.get('status') in {'rejected_answer_quality', 'awaiting_manual_answer_review',
                                                  'rejected_manual_answer_quality', 'failed'}):
                break
            update(status='waiting', phase='waiting_for_prepared_model_and_reference_review',
                   preparation_status=ready.get('status'), reference_status=reference.get('status'))
            if time.monotonic() > deadline:
                raise TimeoutError('Trial prerequisites were not ready within four hours')
            time.sleep(30)
        update(status='preparing', phase='checking_trial_inputs')
        os.environ.setdefault('USE_TF', '0')
        os.environ.setdefault('USE_FLAX', '0')
        import psutil
        from transformers import AutoTokenizer
        from evaluate_xanhnon import ASSESSMENT_VERSION, evaluation_cases, load_comparison, assess, messages_for, compare_answers
        from review_xanhnon_offline import parse_completion
        from training_state import training_in_progress
        profile = 'grounded-v15'
        scope = 'core_generation_without_deterministic_replies:grounded-v15:llama_completion_cli'
        extra_path = args.reference_review / 'extra-cases.json'
        cases, fingerprint = evaluation_cases(extra_path)
        baseline = load_comparison(args.reference_review / 'baseline-core.json', scope, cases)
        model = Path(ready['path'])
        if digest(model) != ready['sha256']:
            raise ValueError('Prepared model checksum changed')
        for name, expected in ready['tokenizer_artifacts_sha256'].items():
            if digest(args.model_dir / name) != expected:
                raise ValueError('Prepared tokenizer changed: ' + name)
        tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True, trust_remote_code=False)
        sys.path.insert(0, str(ROOT / '.runtime/llama-converter/gguf-py'))
        from gguf import GGUFReader
        reader = GGUFReader(str(model))
        # Use the actual GGUF template when a quantizer supplied a different formatting template.
        tokenizer.chat_template = reader.get_field('tokenizer.chat_template').contents()
        vocabulary = reader.get_field('tokenizer.ggml.tokens')
        # GGUF may include unused padding tokens from the model's embedding matrix.
        if len(vocabulary.data) < len(tokenizer):
            raise ValueError('GGUF vocabulary is smaller than the local tokenizer')
        sample_ids = {0, tokenizer.eos_token_id, tokenizer.convert_tokens_to_ids('<|im_start|>'),
                      *tokenizer.encode('AQI PM2.5 Ha Noi', add_special_tokens=False)}
        if any(vocabulary.contents(index) != tokenizer.convert_ids_to_tokens(index) for index in sample_ids):
            raise ValueError('GGUF and local tokenizer token IDs differ')
        del reader
        files = ['evaluate_xanhnon.py', 'evaluate_xanhnon_base_trial.py', 'review_xanhnon_offline.py',
                 'chat_answer_checks.py', 'chat_briefing.py', 'chat_briefing_v15.py',
                 'chat_knowledge.py', 'chat_scope.py', 'chat_output.py',
                 'data/xanhnon/knowledge.json', 'data/xanhnon/specialist_supplement.json']
        hashes = {name: digest(ROOT / name) for name in files}
        reference_hashes = reference.get('application_sha256', {})
        if any(hashes[name] != reference_hashes[name] for name in hashes if name in reference_hashes):
            raise ValueError('The reference was generated with different evaluation inputs')
        active_bytes = (ROOT / 'models/xanhnon-active.json').read_bytes()
        binary = ROOT / '.runtime/llama-bin/llama-completion.exe'
        binary_hash = digest(binary)
        if previous:
            validate_resume(previous, cases, saved_rows, hashes, ready['sha256'], binary_hash, fingerprint)
            for index, row in enumerate(saved_rows):
                stem = f'{index + 1:02d}-{cases[index]["id"]}'
                actual = assess_stdout(cases[index], (output / (stem + '.stdout.log')).read_text(encoding='utf-8'), row['seconds'])
                if any(actual[key] != row[key] for key in ('raw_reply', 'passed', 'violations', 'words')):
                    raise ValueError('Saved answer or assessment changed: ' + row['id'])
            update(resumed_cases=len(saved_rows), preserved_answers_sha256=digest(output / 'answers.before-resume.jsonl'),
                   original_evaluator_sha256=previous['application_sha256']['evaluate_xanhnon_base_trial.py'])
        update(model=str(model), cases_sha256=fingerprint, case_count=len(cases),
               application_sha256=hashes, binary_sha256=binary_hash,
               model_sha256=ready['sha256'], prompt_profile=profile)
        while training_in_progress() or psutil.virtual_memory().available < 4.5 * 1024**3:
            update(status='waiting_for_resources', phase='waiting_for_memory',
                   minimum_free_ram_gb=4.5, available_ram_gb=round(psutil.virtual_memory().available / 1024**3, 2))
            if time.monotonic() > deadline:
                raise TimeoutError('Not enough memory for the base trial')
            time.sleep(30)
        results = list(saved_rows)
        update(status='reviewing', phase='base_model_trial', completed_cases=len(results), passed_so_far=sum(r['passed'] for r in results))
        with (output / 'answers.jsonl').open('a' if previous else 'w', encoding='utf-8', buffering=1) as answers:
            for index in range(len(saved_rows), len(cases)):
                case = cases[index]
                stem = f'{index + 1:02d}-{case["id"]}'
                messages = messages_for(case, profile)
                tokens = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
                if len(tokens) > 8192:
                    raise ValueError('Case exceeds the reference input limit')
                prompt = output / (stem + '.prompt.txt')
                rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                reuse_empty = previous is not None and index == len(saved_rows)
                if reuse_empty:
                    if prompt.read_text(encoding='utf-8') != rendered:
                        raise ValueError('The interrupted prompt changed')
                    old_stdout = (output / (stem + '.stdout.log')).read_text(encoding='utf-8')
                    if assess_stdout(case, old_stdout, 0)['raw_reply']:
                        raise ValueError('The interrupted answer is no longer empty')
                else:
                    prompt.write_text(rendered, encoding='utf-8')
                command = [str(binary), '-m', str(model), '-f', str(prompt), '-t', '2', '-tb', '2',
                           '-c', '10240', '-b', '256', '-ub', '128', '-n', '192', '-ngl', '0',
                           '--temp', '0', '--top-k', '1', '--top-p', '1', '--repeat-penalty', '1.1',
                           '--repeat-last-n', '64', '--seed', '42', '--no-conversation',
                           '--no-display-prompt', '--no-escape', '--simple-io', '--special', '--perf', '--color', 'off']
                started = time.monotonic()
                if not reuse_empty:
                    with (output / (stem + '.stdout.log')).open('wb') as stdout, (output / (stem + '.stderr.log')).open('wb') as stderr:
                        process = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                                 timeout=180, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    if process.returncode:
                        raise RuntimeError(f'{stem} exited with code {process.returncode}')
                row = assess_stdout(case, (output / (stem + '.stdout.log')).read_text(encoding='utf-8'), time.monotonic() - started)
                if reuse_empty:
                    row['seconds'] = None
                    row['timing_note'] = 'Original empty generation retained as a failure; Python elapsed timing was not saved before interruption.'
                row['input_tokens'] = len(tokens)
                results.append(row)
                answers.write(json.dumps(row, ensure_ascii=False) + '\n')
                update(completed_cases=index + 1, passed_so_far=sum(r['passed'] for r in results), last_case=case['id'])
        if (any(digest(ROOT / name) != value for name, value in hashes.items())
                or digest(binary) != binary_hash or digest(model) != ready['sha256']
                or (ROOT / 'models/xanhnon-active.json').read_bytes() != active_bytes
                or evaluation_cases(extra_path)[1] != fingerprint):
            raise ValueError('Comparison inputs changed during the trial')
        comparison = compare_answers({r['id']: r for r in baseline['cases']}, results, baseline['average_words'])
        report = {'model': str(model), 'model_sha256': ready['sha256'], 'model_activated': False,
                  'evaluation_scope': scope, 'assessment_version': ASSESSMENT_VERSION,
                  'cases_sha256': fingerprint, 'case_count': len(cases), 'prompt_profile': profile,
                  'passed': sum(r['passed'] for r in results), 'comparison': comparison,
                  'average_words': round(sum(r['words'] for r in results) / len(results), 1),
                  'inference_threads': 2, 'cases': results,
                  'coverage': 'Development cases only; requires manual review and application verification.'}
        save_json(output / 'candidate-core.json', report)
        update(status='awaiting_manual_review', phase='review_finished', passed=report['passed'], comparison=comparison)
    except Exception as error:
        update(status='failed', error=str(error))
        (output / 'error.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
