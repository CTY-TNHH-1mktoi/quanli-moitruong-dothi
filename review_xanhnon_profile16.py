"""Measure a candidate input profile against the same untrained 4B base.

Waits for the adapter comparison, reuses its frozen 56 baseline answers, and
adds eight prewritten confirmation scenarios. No training or deployment.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
from threading import Timer
import time
import traceback

from native_chatbot import NativeChatbot
from sensor_training_data import ROOT,digest,save_json


FRESH_CASES=[
 {'id':'profile16_first_person_plan','question':'Tôi đang tính đi dạo ở bờ hồ, tư vấn giúp tôi với.',
  'required_any':[['ngày nào','hôm nay','ngày mai','lúc nào','giờ','thời điểm']]},
 {'id':'profile16_evening_time','question':'Tôi muốn đi bộ tối nay, bạn xem điều kiện không khí giúp tôi.',
  'required_any':[['chưa có','chưa đủ','chưa được','thiếu']], 'forbidden':['US AQI 175','AQI là 175']},
 {'id':'profile16_selected_readings','question':'Cho mình đọc lại hai số nhiệt độ, độ ẩm ở khu vực đang xem nhé.',
  'readings':{'NhietDo':22.6,'DoAm':74},'required_any':[['Hà Nội'],['22.6','22,6'],['74'],['nhiệt độ'],['độ ẩm']],
  'forbidden':['24.8','95%']},
 {'id':'profile16_explain_request','question':'Lý do bạn muốn biết lúc tôi đi tập là gì?',
  'history':[{'role':'user','content':'Bạn tư vấn giúp buổi đạp xe ngoài trời của mình nhé.'},
             {'role':'assistant','content':'Bạn dự định vào ngày nào, khoảng mấy giờ?'}],
  'required_any':[['số liệu','số đo','dự báo','dữ liệu']]},
 {'id':'profile16_pm_unit','question':'Nói PM2.5 là đơn vị nồng độ còn µg/m³ là tên nhóm hạt thì mình hiểu ngược phải không?',
  'required_any':[['PM2.5'],['bụi','hạt'],['nồng độ'],['đơn vị']]},
 {'id':'profile16_presence','question':'Nãy giờ bạn vẫn ở đây nghe mình nói chứ?',
  'required_any':[['mình','tôi','tớ'],['đây','nghe','sẵn sàng']]},
 {'id':'profile16_no_filter_context','question':'Vậy nếu nhà mình chưa sắm được máy lọc thì nên ưu tiên việc nào?',
  'history':[{'role':'user','content':'Nhà bên đường của mình hay có bụi lọt vào khi xe chạy qua.'},
             {'role':'assistant','content':'Mình có thể gợi ý cách hạn chế bụi trong nhà.'}],
  'required_any':[['khép cửa','hạn chế mở cửa','đóng cửa','lau']], 'check_no_filter_actions':True},
 {'id':'profile16_unknown_aqi','question':'Mình muốn biết không khí lúc này có hợp để đạp xe không?',
  'readings':{'US_AQI':None},'required_any':[['chưa có','chưa đủ','thiếu']],
  'forbidden':['US AQI 175','AQI là 175','không khí tốt']},
]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse-fresh-baseline',type=Path,
                        help='Reuse all eight saved baseline replies; treat all 64 scenarios as development cases')
    args=parser.parse_args()
    reference,output=args.reference.resolve(),args.output.resolve()
    if output.exists() and any(output.iterdir()):parser.error('Choose a new empty output directory')
    output.mkdir(parents=True)
    state={'reviewer_pid':os.getpid(),'model_activated':False,'weights':'4B base without adapter',
           'development_cases':56,'new_confirmation_cases':8,'profile_before':'grounded-v15','profile_after':'grounded-v16'}
    if args.reuse_fresh_baseline:
        state.update(development_cases=64,new_confirmation_cases=0,previously_observed_confirmation_cases=8)
    def update(**values):
        state.update(values,checked_at=datetime.now().astimezone().isoformat())
        save_json(output/'review-state.json',state)
    try:
        # Freeze before any outputs on these new scenarios are generated.
        from evaluate_xanhnon import messages_for,compare_answers
        from chat_briefing_v16 import compact_messages
        from review_xanhnon_4b_lora import checked_answer
        from location_catalog import get_location
        from prepare_xanhnon_data import normalize
        save_json(output/'fresh-cases.json',FRESH_CASES)
        used=set()
        storage=reference.parent
        for name in ['meaning-v15-data-20261022-reviewed','qwen3-4b-correction-data-20261024']:
            for split in ['train','validation']:
                for line in (storage/name/(split+'.jsonl')).read_text(encoding='utf-8').splitlines():
                    row=json.loads(line)
                    used.add(normalize(row['original_question']))
                    used.update(normalize(m['content']) for m in row['messages'] if m['role']=='user')
        if any(normalize(c['question']) in used for c in FRESH_CASES):
            raise ValueError('New confirmation wording was already used for training')
        recipes=['chat_briefing_v16.py','chat_briefing_v15.py','chat_briefing.py','native_chatbot.py',
                 'review_xanhnon_profile16.py','review_xanhnon_4b_lora.py','evaluate_xanhnon.py','chat_answer_checks.py']
        hashes={}
        for name in recipes:
            path=output/'scripts'/name;path.parent.mkdir(exist_ok=True)
            shutil.copy2(ROOT/name,path);hashes[name]=digest(path)
        update(status='waiting',phase='waiting_for_adapter_review',script_sha256=hashes,
               fresh_cases_sha256=digest(output/'fresh-cases.json'))
        deadline=time.monotonic()+3600
        while True:
            prior=json.loads((reference/'review-state.json').read_text(encoding='utf-8'))
            if prior['status']=='failed':raise RuntimeError('Adapter review failed; inspect it before comparing profiles')
            if prior['status']=='awaiting_manual_review':break
            if time.monotonic()>deadline:raise TimeoutError('Adapter review did not finish within one hour')
            time.sleep(10)
        cases=json.loads((reference/'cases.json').read_text(encoding='utf-8'))
        previous=[json.loads(l) for l in (reference/'baseline-answers.jsonl').read_text(encoding='utf-8').splitlines()]
        if len(previous)!=56 or len(cases)!=56:raise ValueError('Incomplete baseline reference')
        cases+=FRESH_CASES
        if len({c['id'] for c in cases})!=64:raise ValueError('Duplicate case IDs')
        if args.reuse_fresh_baseline:
            saved_cases=json.loads(args.reuse_fresh_baseline.with_name('fresh-cases.json').read_text(encoding='utf-8'))
            saved=[json.loads(line) for line in args.reuse_fresh_baseline.read_text(encoding='utf-8').splitlines()]
            if saved_cases!=FRESH_CASES or [r['id'] for r in saved]!=[c['id'] for c in FRESH_CASES]:
                raise ValueError('Reuse requires exactly the same eight complete baseline scenarios')
            previous+=saved
            save_json(output/'reused-fresh-baseline.json',saved)
        model,binary=Path(prior['model']),storage/'qwen3-4b-hardware-20261023/runtime/llama-server.exe'
        if digest(model)!=prior['model_sha256'] or digest(binary)!=prior['binary_sha256']:
            raise ValueError('Baseline weights or binary changed')
        active=ROOT/'models/xanhnon-active.json';active_bytes=active.read_bytes()
        prompts={}
        for case in cases:
            snapshot={'DiaDiem':get_location('hanoi'),'ThoiGian':'2026-10-19T09:00:00',
                      'DuLieu':{'US_AQI':175,'PM25':45.4,'PM10':60,'NhietDo':24.8,'DoAm':95,'TiengOn':74.99,**case.get('readings',{})}}
            prompts[case['id']]=compact_messages(case['question'],case.get('history',[]),snapshot)
        save_json(output/'cases.json',cases);save_json(output/'messages-v16.json',prompts)
        total=64 if args.reuse_fresh_baseline else 72
        update(status='loading_model',phase='base_4b',model_sha256=prior['model_sha256'],
               reused_baseline_sha256=digest(reference/'baseline-answers.jsonl'),
               reused_fresh_baseline_sha256=digest(args.reuse_fresh_baseline) if args.reuse_fresh_baseline else None,
               messages_sha256=digest(output/'messages-v16.json'),completed_cases=0,total_cases=total)
        runtime=NativeChatbot(binary,model,2,2048,192,gpu_layers=99,log_path=output/'server.log')
        def generate(case,messages):
            started=time.monotonic();timer=Timer(180,runtime.close);timer.daemon=True;timer.start()
            try:
                try:result=runtime.generate(messages,192)
                except RuntimeError as error:
                    if str(error)!='The model returned an empty reply':raise
                    result={'reply':'','truncated':False}
            finally:timer.cancel()
            return checked_answer(case,result,time.monotonic()-started)
        try:
            if not args.reuse_fresh_baseline:
                with (output/'fresh-baseline-answers.jsonl').open('w',encoding='utf-8',buffering=1) as log:
                    for case in FRESH_CASES:
                        update(status='evaluating',phase='v15_fresh_baseline',case_id=case['id'])
                        row=generate(case,messages_for(case,'grounded-v15'));previous.append(row)
                        log.write(json.dumps(row,ensure_ascii=False)+'\n')
                        update(completed_cases=len(previous)-56)
            rows=[]
            order=cases
            if args.reuse_fresh_baseline:
                priority=['hypothetical_aqi','consultation_asks_time','particle_concentration_not_aqi',
                    'fourb_presence_new','fourb_location_new','fourb_topic_new','fourb_explain_new',
                    'profile16_evening_time','meaning_pm_not_humidity','dust_without_filter_followup']
                by_id={case['id']:case for case in cases}
                order=[by_id[key] for key in priority]+[case for case in cases if case['id'] not in priority]
            save_json(output/'evaluation-order.json',[case['id'] for case in order])
            with (output/'v16-answers.jsonl').open('w',encoding='utf-8',buffering=1) as log:
                for case in order:
                    update(status='evaluating',phase='v16',case_id=case['id'])
                    row=generate(case,prompts[case['id']]);rows.append(row)
                    log.write(json.dumps(row,ensure_ascii=False)+'\n')
                    update(completed_cases=(0 if args.reuse_fresh_baseline else 8)+len(rows),passed_so_far=sum(r['passed'] for r in rows))
        finally:runtime.close()
        if active.read_bytes()!=active_bytes:raise ValueError('Active release changed during review')
        before={r['id']:r for r in previous}
        comparison=compare_answers(before,rows,sum(r['words'] for r in previous)/64)
        save_json(output/'comparison.json',{'comparison':comparison,'before':previous,'after':rows,
            'model_activated':False,'limitations':['Development cases informed the new profile.',
                'All 64 cases are now development cases.' if args.reuse_fresh_baseline else 'Eight new phrasings frozen before evaluation; concepts remain related.',
                'Same untrained base model; this measures input preparation, not training quality.',
                '64 baseline replies reused.' if args.reuse_fresh_baseline else '56 baseline generations reused; 8 baseline and 64 revised-input generations are new.',
                'Manual review required; automatic scores are not expert accuracy.']})
        update(status='awaiting_manual_review',phase='comparison_finished',comparison=comparison)
    except Exception as error:
        update(status='failed',error=str(error))
        (output/'error.log').write_text(traceback.format_exc(),encoding='utf-8');raise


if __name__=='__main__':main()
