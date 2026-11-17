"""Export a completed signal pilot and compare fixed raw generation inputs."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import requests
import shutil
import subprocess
import sys
from threading import Timer
import time

from native_chatbot import NativeChatbot
from review_xanhnon_4b_lora import checked_answer
from sensor_training_data import ROOT, digest, save_json


def check(case, result, elapsed):
    from chat_knowledge import normalized
    row = checked_answer(case,result,elapsed)
    text = normalized(result['reply'])
    question = normalized(case['question'])
    if len(question) >= 15 and text.startswith(question):
        row['violations'].append('question_echo_instead_of_direct_answer')
    if re.search(r'[\u3400-\u4dbf\u4e00-\u9fff]',result['reply']):
        row['violations'].append('unexpected_CJK_in_Vietnamese_reply')
    if (case.get('selected_location_only') or case['id'] in {'signal_reading','signal_missing','missing_aqi'}) and re.search(r'\bbạn (?:đang )?ở Hà Nội\b', result['reply'], re.I):
        row['violations'].append('selected_location_assumed_to_be_user_location')
    if case['id'] == 'signal_why' and 'anh sang' in text:
        row['violations'].append('light_not_present_in_supplied_time_explanation')
    if (case.get('no_retry_interval') or case['id'] == 'signal_missing') and re.search(r'\bsau (?:vai|may|\d+) (?:gio|tieng)\b',text):
        row['violations'].append('unsupported_retry_interval')
    if case['id'] == 'signal_hypothesis' and not re.search(r'giả (?:định|sử)|ví dụ',result['reply'],re.I):
        row['violations'].append('hypothesis_not_qualified')
    row['passed'] = not row['violations']
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('storage','candidate','data-dir','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    storage, candidate, data, output = args.storage.resolve(),args.candidate.resolve(),args.data_dir.resolve(),args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('Use an empty new review directory')
    output.mkdir(parents=True,exist_ok=True)
    state = {'model_activated':False,'prompt_profile':'grounded-v16','reviewer_pid':os.getpid(),
             'development_cases':16,'new_confirmation_wordings':8,'requires_manual_answer_review':True,
             'guard_revision':3,'review_script_sha256':digest(Path(__file__))}
    def update(**values):
        state.update(values,checked_at=datetime.now().astimezone().isoformat())
        save_json(output/'review-state.json',state)
    active = ROOT/'models/xanhnon-active.json'
    active_hash = digest(active)
    runtime = None
    try:
        report = json.loads((candidate/'training_report.json').read_text(encoding='utf-8'))
        manifest = json.loads((data/'manifest.json').read_text(encoding='utf-8'))
        scope = manifest.get('evaluation',{'development_cases':16,'new_confirmation_wordings':8})
        expected_total = scope['development_cases'] + scope['new_confirmation_wordings']
        state.update(scope,total_cases=expected_total)
        if (not report.get('full_dataset_pass_completed') or report['manifest_sha256'] != digest(data/'manifest.json')
                or manifest.get('prompt_profile') != 'grounded-v16'):
            raise ValueError('Incomplete training or changed dataset')
        for name, expected in manifest['artifacts_sha256'].items():
            if digest(data/name) != expected:
                raise ValueError('Frozen data changed: '+name)
        for name in ('cases.json','messages.json','confirmation-cases.json','manifest.json'):
            shutil.copy2(data/name,output/name)
        cases = json.loads((output/'cases.json').read_text(encoding='utf-8'))
        prompts = json.loads((output/'messages.json').read_text(encoding='utf-8'))
        if len(cases) != expected_total or len(prompts) != expected_total:
            raise ValueError('Answer cases do not match the frozen evaluation scope')
        preparation = json.loads((storage/'qwen3-4b-instruct-2507-trial/preparation-state.json').read_text(encoding='utf-8'))
        model = Path(preparation['path'])
        if digest(model) != preparation['sha256']:
            raise ValueError('Inference base changed')
        lora = output/'candidate-lora-f16.gguf'
        update(status='exporting',adapter_sha256=digest(candidate/'adapter_model.safetensors'),
            model_sha256=preparation['sha256'],active_release_sha256=active_hash)
        command = [sys.executable,'-u',str(ROOT/'.runtime/llama-converter/convert_lora_to_gguf.py'),
            '--base',str(storage/'qwen3-4b-instruct-2507-trial'),'--outfile',str(lora),'--outtype','f16',str(candidate)]
        with (output/'export.log').open('w',encoding='utf-8') as log:
            subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if lora.read_bytes()[:4] != b'GGUF':
            raise ValueError('Bad LoRA export')
        update(lora_sha256=digest(lora),binary_sha256=digest(storage/'qwen3-4b-hardware-20261023/runtime/llama-server.exe'))
        results = {}
        for variant, adapter in [('baseline',None),('candidate',lora)]:
            update(status='loading_model',phase=variant,completed_cases=0)
            runtime = NativeChatbot(storage/'qwen3-4b-hardware-20261023/runtime/llama-server.exe',
                model,2,2048,192,gpu_layers=99,log_path=output/(variant+'-server.log'),lora_path=adapter)
            results[variant] = []
            try:
                response=requests.get(runtime.base_url+'/lora-adapters',timeout=10)
                response.raise_for_status()
                adapters=response.json()
                if adapter and not any(Path(a['path']).resolve()==adapter.resolve() and a['scale']==1 for a in adapters):
                    raise ValueError('Server did not activate the requested LoRA at scale 1')
                if not adapter and adapters:
                    raise ValueError('Baseline unexpectedly has a LoRA adapter loaded')
                save_json(output/(variant+'-runtime-verification.json'),
                    {'pid':runtime.process.pid,'base_url':runtime.base_url,'adapters':adapters})
                with (output/(variant+'-answers.jsonl')).open('w',encoding='utf-8',buffering=1) as answers:
                    for case in cases:
                        update(status='evaluating',phase=variant,case_id=case['id'])
                        timer = Timer(180,runtime.close); timer.daemon=True; timer.start()
                        started = time.monotonic()
                        try:
                            result = runtime.generate(prompts[case['id']],192)
                        except RuntimeError as error:
                            if str(error) != 'The model returned an empty reply':
                                raise
                            result = {'reply':'','truncated':False}
                        finally:
                            timer.cancel()
                        row = check(case,result,time.monotonic()-started)
                        results[variant].append(row)
                        answers.write(json.dumps(row,ensure_ascii=False)+'\n')
                        update(completed_cases=len(results[variant]))
            finally:
                runtime.close(); runtime=None
        from evaluate_xanhnon import compare_answers
        before = {r['id']:r for r in results['baseline']}
        comparison = compare_answers(before,results['candidate'],sum(r['words'] for r in before.values())/len(before))
        changed = [r['id'] for r in results['candidate'] if r['raw_reply'] != before[r['id']]['raw_reply']]
        if digest(active) != active_hash:
            raise ValueError('Active release changed during comparison')
        decision = ('reject_no_measured_answer_change' if not changed else
                    'manual_review_required' if comparison['eligible_for_manual_review'] else 'reject_automatic_regression')
        save_json(output/'comparison.json',{'comparison':comparison,'changed_answers':changed,'results':results,
            'decision':decision,'model_activated':False,'requires_manual_answer_review':True})
        update(status='awaiting_manual_review',phase='comparison_finished',comparison=comparison,
            changed_answers=changed,decision=decision)
    except Exception as error:
        if runtime:
            runtime.close()
        update(status='failed',error=str(error))
        raise


if __name__ == '__main__':
    main()
