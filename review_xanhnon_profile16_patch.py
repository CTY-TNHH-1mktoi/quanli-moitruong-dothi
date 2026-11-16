"""Evaluate only changed prompts and reuse byte-identical previously tested inputs."""
import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import time

from chat_briefing_v16 import compact_messages
from evaluate_xanhnon import compare_answers
from location_catalog import get_location
from native_chatbot import NativeChatbot
from review_xanhnon_4b_lora import checked_answer
from sensor_training_data import digest,save_json,ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    prior,output=args.prior.resolve(),args.output.resolve()
    if output.exists() and any(output.iterdir()):parser.error('Choose a new empty output directory')
    output.mkdir(parents=True)
    before=json.loads((prior/'comparison.json').read_text(encoding='utf-8'))
    cases=json.loads((prior/'cases.json').read_text(encoding='utf-8'))
    old=json.loads((prior/'messages-v16.json').read_text(encoding='utf-8'))
    state=json.loads((prior/'review-state.json').read_text(encoding='utf-8'))
    messages={}
    for case in cases:
        snapshot={'DiaDiem':get_location('hanoi'),'ThoiGian':'2026-10-19T09:00:00',
                  'DuLieu':{'US_AQI':175,'PM25':45.4,'PM10':60,'NhietDo':24.8,'DoAm':95,'TiengOn':74.99,**case.get('readings',{})}}
        messages[case['id']]=compact_messages(case['question'],case.get('history',[]),snapshot)
    changed=[c for c in cases if messages[c['id']]!=old[c['id']]]
    if len(changed)!=2:raise ValueError('Expected exactly two input corrections; do not reuse other results until inspected')
    save_json(output/'cases.json',cases);save_json(output/'messages.json',messages)
    for name in ['chat_briefing_v16.py','review_xanhnon_profile16_patch.py']:
        (output/name).write_bytes((ROOT/name).read_bytes())
    status={'status':'evaluating','model_activated':False,'development_cases':64,
            'new_generations':2,'reused_generations':62,'changed_case_ids':[c['id'] for c in changed],
            'prior_answers_sha256':digest(prior/'v16-answers.jsonl'),
            'messages_sha256':digest(output/'messages.json'),
            'input_recipe_sha256':digest(ROOT/'chat_briefing_v16.py')}
    save_json(output/'review-state.json',status)
    original=prior.parent/'qwen3-4b-lora-review-20261024/review-state.json'
    original=json.loads(original.read_text(encoding='utf-8'))
    model=Path(original['model'])
    if digest(model)!=original['model_sha256']:raise ValueError('Model changed')
    binary=prior.parent/'qwen3-4b-hardware-20261023/runtime/llama-server.exe'
    if digest(binary)!=original['binary_sha256']:raise ValueError('Binary changed')
    runtime=NativeChatbot(binary,model,2,2048,192,gpu_layers=99,log_path=output/'server.log')
    rows={r['id']:deepcopy(r) for r in before['after']}
    try:
        for case in changed:
            began=time.monotonic()
            result=runtime.generate(messages[case['id']],192)
            rows[case['id']]=checked_answer(case,result,time.monotonic()-began)
            print(json.dumps(rows[case['id']],ensure_ascii=False),flush=True)
    finally:runtime.close()
    ordered=[rows[c['id']] for c in cases]
    comparison=compare_answers({r['id']:r for r in before['before']},ordered,
                              sum(r['words'] for r in before['before'])/64)
    save_json(output/'comparison.json',{'comparison':comparison,'before':before['before'],'after':ordered,
        'reused_case_ids':[c['id'] for c in cases if c not in changed],
        'new_case_ids':[c['id'] for c in changed],
        'method':'62 outputs reused only when the complete input message array is identical; two changed prompts generated anew.',
        'limitations':['All 64 are development cases; no independent expert certification.',
                       'This is incremental verification, not a new 64-query run.'], 'model_activated':False})
    status.update(status='awaiting_manual_review',comparison=comparison,
                  checked_at=datetime.now().astimezone().isoformat())
    save_json(output/'review-state.json',status)


if __name__=='__main__':main()
