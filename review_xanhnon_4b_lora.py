"""Compare the original 4B GGUF and its corrective LoRA, without deployment."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from threading import Timer
import time
import traceback

from native_chatbot import NativeChatbot
from sensor_training_data import ROOT, digest, save_json


def confirmation_rubrics(cases):
    rules = {
      'fourb_presence_new': {'required_any':[['mình','tôi','tớ'],['đây','nghe','sẵn sàng']]},
      'fourb_topic_new': {'required_any':[['thời tiết'],['không khí','AQI']]},
      'fourb_unit_new': {'required_any':[['PM2.5'],['bụi','hạt'],['nồng độ'],['đơn vị']]},
      'fourb_activity_new': {'required_any':[['khi nào','ngày nào','giờ','lúc nào','thời điểm']]},
      'fourb_explain_new': {'required_any':[['số liệu','số đo','dự báo','dữ liệu'],['thời điểm','thời gian','giờ','ngày','lúc']]},
      'fourb_location_new': {'required_any':[['Hà Nội'],['24.8','24,8'],['95'],['nhiệt độ'],['độ ẩm']]},
      'fourb_noise_new': {'required_any':[['không','đừng']], 'check_noise_duration':True},
      'fourb_ack_new': {},
    }
    return [{**case, **rules[case['id']]} for case in cases]


def checked_answer(case, result, elapsed):
    from evaluate_xanhnon import assess
    from chat_knowledge import normalized
    row = assess(case, result, elapsed)
    row['original_rubric_passed'] = row['passed']
    text = normalized(result['reply'])
    extra = []
    if not result['reply'].strip():
        extra.append('empty_generation')
    if result.get('truncated'):
        extra.append('truncated_generation')
    for marker in ('nidcd_noise','epa_pm','airnow_aqi','source_ids','nhiem_vu','chung_cu'):
        if marker in result['reply']:
            extra.append('internal_source_or_task_identifier_leak')
            break
    # The old rubric missed this exact quantity/unit confusion in the base trial.
    for match in re.finditer(r'\bpm25\s+(?:la|chinh la)\s+(?:mot\s+)?don vi\b',text):
        prefix=text[max(0,match.start()-45):match.start()]
        if not re.search(r'\b(?:khong(?: nen| duoc)?|dung)\s+(?:coi|goi|xem)\s*$',prefix):
            extra.append('PM25_incorrectly_called_a_unit')
            break
    if re.search(r'\bban (?:dang o day|chao ban roi)\b',text):
        extra.append('wrong_speaker_reference')
    if case['id']=='fourb_explain_new' and re.search(r'\bban hoi (?:gio|thoi gian|thoi diem) minh\b',text):
        extra.append('wrong_speaker_reference')
    if case['id'] in {'fourb_location_new','current_weather'} and re.search(r'\bban (?:dang )?o ha noi\b',text):
        extra.append('selected_location_assumed_to_be_user_location')
    row['additional_violations'] = extra
    row['violations'] += extra
    row['passed'] = not row['violations']
    row['truncated'] = bool(result.get('truncated'))
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storage',type=Path,default=Path('D:/XanhNon-auto-training'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--lora',type=Path,required=True)
    args=parser.parse_args()
    storage, output, candidate = args.storage.resolve(),args.output.resolve(),args.candidate.resolve()
    output.mkdir(parents=True,exist_ok=True)
    if (output/'review-state.json').exists():
        parser.error('Use a new review directory to preserve previous answers')
    state={'reviewer_pid':os.getpid(),'model_activated':False,'prompt_profile':'grounded-v15',
           'runtime':'resident_llama_cpp_vulkan','gpu_layers':99,'threads':2,'context_tokens':4096,
           'input_tokens':2048,'output_tokens':192,'temperature':0,'guard_version':1}

    def update(**values):
        state.update(values,checked_at=datetime.now().astimezone().isoformat())
        save_json(output/'review-state.json',state)

    try:
        update(status='preparing',phase='verifying_training_and_export')
        from evaluate_xanhnon import evaluation_cases,messages_for,compare_answers
        training=json.loads((candidate/'training_report.json').read_text(encoding='utf-8'))
        cycle=json.loads((storage/'qwen3-4b-lora-cycle-20261024/cycle-state.json').read_text(encoding='utf-8'))
        if (not training.get('full_dataset_pass_completed') or training.get('steps_completed')!=16
                or digest(candidate/'adapter_model.safetensors')!=cycle['adapter_sha256']):
            raise ValueError('Incomplete or changed trained adapter')
        preparation=json.loads((storage/'qwen3-4b-instruct-2507-trial/preparation-state.json').read_text(encoding='utf-8'))
        model=Path(preparation['path'])
        if digest(model)!=preparation['sha256']:
            raise ValueError('The inference base model changed')
        lora=args.lora.resolve()
        if lora.read_bytes()[:4]!=b'GGUF':
            raise ValueError('LoRA export is not GGUF')
        binary=storage/'qwen3-4b-hardware-20261023/runtime/llama-server.exe'
        cases,_=evaluation_cases(storage/'rehearsal-review-v14-answers-20261022/extra-cases.json')
        cases+=json.loads((ROOT/'data/xanhnon/eval_meaning_confirmation.json').read_text(encoding='utf-8'))
        new=confirmation_rubrics(json.loads((Path(training['data_dir'])/'confirmation-cases.json').read_text(encoding='utf-8')))
        cases+=new
        if len(cases)!=56 or len({c['id'] for c in cases})!=56:
            raise ValueError('Compare exactly 48 development and 8 new confirmation cases')
        prompts={case['id']:messages_for(case,'grounded-v15') for case in cases}
        save_json(output/'cases.json',cases)
        save_json(output/'messages.json',prompts)
        for name in ['native_chatbot.py','chat_briefing.py','chat_briefing_v15.py',
                     'evaluate_xanhnon.py','chat_answer_checks.py','review_xanhnon_4b_lora.py']:
            frozen=output/'scripts'/name
            frozen.parent.mkdir(exist_ok=True)
            shutil.copy2(ROOT/name,frozen)
        active=ROOT/'models/xanhnon-active.json'
        active_bytes=active.read_bytes()
        update(model=str(model),model_sha256=preparation['sha256'],lora=str(lora),lora_sha256=digest(lora),
            adapter_sha256=cycle['adapter_sha256'],binary_sha256=digest(binary),
            cases_sha256=digest(output/'cases.json'),messages_sha256=digest(output/'messages.json'),
            active_release_sha256=hashlib.sha256(active_bytes).hexdigest(),
            development_cases=48,new_confirmation_cases=8,
            limitation='Adapter trained on NF4 weights; this checks deployment on Q4_K_M. Raw model generation only; app routing is excluded.')
        all_rows={}
        for variant, adapter in [('baseline',None),('candidate',lora)]:
            update(status='loading_model',phase=variant,completed_cases=0,total_cases=56)
            runtime=NativeChatbot(binary,model,2,2048,192,gpu_layers=99,
                log_path=output/(variant+'-server.log'),lora_path=adapter)
            rows=[]
            try:
                with (output/(variant+'-answers.jsonl')).open('w',encoding='utf-8',buffering=1) as answers:
                    for case in cases:
                        update(status='evaluating',phase=variant,case_id=case['id'])
                        began=time.monotonic()
                        timer=Timer(180,runtime.close);timer.daemon=True;timer.start()
                        error=None
                        try:
                            result=runtime.generate(prompts[case['id']],192)
                        except RuntimeError as exc:
                            if str(exc)!='The model returned an empty reply':raise
                            result={'reply':'','truncated':False};error=str(exc)
                        finally:
                            timer.cancel()
                        row=checked_answer(case,result,time.monotonic()-began)
                        row['runtime_error']=error
                        rows.append(row)
                        answers.write(json.dumps(row,ensure_ascii=False)+'\n')
                        update(completed_cases=len(rows),passed_so_far=sum(r['passed'] for r in rows))
            finally:
                runtime.close()
            all_rows[variant]=rows
        before={row['id']:row for row in all_rows['baseline']}
        comparison=compare_answers(before,all_rows['candidate'],
            sum(r['words'] for r in all_rows['baseline'])/56)
        if active.read_bytes()!=active_bytes:
            raise ValueError('Active release changed during the review')
        save_json(output/'comparison.json',{'comparison':comparison,'results':all_rows,
            'evaluation_scope':'core_generation_without_deterministic_replies:grounded-v15:resident_vulkan',
            'development_cases':48,'new_confirmation_cases':8,'model_activated':False,
            'requires_manual_answer_review':True})
        update(status='awaiting_manual_review',phase='comparison_finished',comparison=comparison)
    except Exception as error:
        update(status='failed',error=str(error))
        (output/'error.log').write_text(traceback.format_exc(),encoding='utf-8')
        raise


if __name__=='__main__':
    main()
