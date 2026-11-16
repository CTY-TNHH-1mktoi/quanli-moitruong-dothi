"""Dialogue repair with broader rehearsal, without learning evaluation answers."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

from chat_answer_checks import semantic_violations
from chat_briefing_v16 import PROFILE, briefing, compact_messages
from prepare_xanhnon_correction_data import history, validate_records
from prepare_xanhnon_data import stable_id
from prepare_xanhnon_v16_pilot import revised_rows
from sensor_training_data import ROOT, digest, save_json


QUESTIONS = {
 'speaker_presence': [
  'Xanh Non à, bạn có nghe mình không vậy?',
  'Bạn có đang ở đây nghe mình tâm sự không?',
  'Này bạn Xanh Non, nghe thấy mình gọi chứ?',
  'Mình đang gọi Xanh Non, bạn còn ở đây không vậy?',
  'Trợ lý ơi, bạn nghe mình nói rõ chứ?',
  'Xanh Non, bạn có mặt để nghe mình hỏi chứ?',
  'Bạn Xanh Non có nghe thấy mình gọi bạn không?',
  'Mình muốn gọi Xanh Non, bạn đang ở đây đúng không?'],
 'explain_own_question': [
  'Bạn hỏi giờ mình ra ngoài để làm gì vậy?',
  'Vì sao bạn cần biết khi nào mình định chạy?',
  'Tại sao bạn cần biết mốc giờ đi dạo của mình?',
  'Bạn muốn biết thời điểm mình chạy để làm gì thế?',
  'Bạn hỏi ngày mình vận động vì sao vậy?',
  'Vì sao bạn cần biết giờ hẹn ra công viên?',
  'Bạn hỏi ngày giờ đi bộ của mình để làm gì thế?',
  'Tại sao bạn cần biết khi nào mình muốn ra ngoài?'],
 'missing_aqi': [
  'Chưa có US AQI ở điểm đang xem, bạn nhận xét buổi chạy hôm nay được không?',
  'Bảng thiếu AQI tại khu vực được chọn, có đủ căn cứ đánh giá buổi tập lúc này chưa?',
  'US AQI hiện đang trống ở điểm này, không khí đã phù hợp để đi dạo chưa?',
  'Ở địa điểm đang chọn không có AQI, mình có thể kết luận không khí tốt không?',
  'Chưa lấy được US AQI cho khu vực này, bạn kết luận điều kiện chạy bộ hiện tại thế nào?',
  'Ô US AQI của điểm đang chọn còn thiếu, hôm nay đánh giá hoạt động ngoài trời được chưa?',
  'Không có chỉ số AQI tại điểm đang xem, kết luận buổi tập an toàn được không?',
  'Bảng chưa có AQI cho địa điểm đang chọn, nói ngắn xem đã đánh giá không khí được chưa?'],
 'selected_location': [
  'Đọc giúp hai số nhiệt độ và độ ẩm hiện tại ở địa điểm được chọn nhé.',
  'Xem nhiệt độ với độ ẩm lúc này của khu vực đang chọn giúp mình.',
  'Cho biết nhiệt độ và độ ẩm hiện tại ở điểm đang xem, nói gọn nhé.',
  'Đọc nhiệt độ, độ ẩm đang có của khu vực được chọn trong một câu.',
  'Nhắc nhiệt độ và độ ẩm hiện tại của địa điểm mình đang xem trên bảng.',
  'Xem cho mình nhiệt độ và độ ẩm của điểm đang được chọn lúc này nhé.',
  'Đọc hai giá trị nhiệt độ và độ ẩm hiện tại ở khu vực đang xem nhé.',
  'Cho biết ngắn gọn nhiệt độ, độ ẩm ở địa điểm đang chọn lúc này.'],
}
LOCATIONS = [('hanoi','Hà Nội'),('hue','Huế'),('danang','Đà Nẵng'),('phucyen','Phúc Yên, Vĩnh Phúc'),
             ('haiphong','Hải Phòng'),('cantho','Cần Thơ'),('nhatrang','Nha Trang'),('dalat','Đà Lạt')]


def new_rows():
    result={'train':[],'validation':[]}
    audit=[]
    for topic,questions in QUESTIONS.items():
        for index,question in enumerate(questions):
            split='train' if index<6 else 'validation'
            code,name=LOCATIONS[index]
            temperature=round(19.4+index*1.3,1);humidity=51+index*5
            snapshot={'DiaDiem':{'MaDiaDiem':code,'Ten':name},
                      'DuLieu':{'US_AQI':None,'PM25':8.2+index,'NhietDo':temperature,'DoAm':humidity}}
            turns=[]
            if topic=='speaker_presence':
                answer=['Mình đây, bạn cứ nói nhé.','Mình đang nghe bạn đây.','Có mình đây, bạn hỏi nhé.'][index%3]
                expected={'đáp lại lời gọi trợ lý'}
            elif topic=='explain_own_question':
                previous_questions=[
                    'Mình muốn thu xếp một buổi đi bộ cùng gia đình.',
                    'Mình tính tham gia một buổi chạy cùng nhóm bạn.',
                    'Mình dự định rủ người quen ra công viên đi dạo.',
                    'Mình muốn tập chạy quanh khu dân cư vào dịp phù hợp.',
                    'Mình tính lên lịch vận động ngoài sân trường.',
                    'Mình muốn ra công viên vận động cùng đồng nghiệp.',
                    'Mình cần lên lịch đi bộ quanh hồ với người nhà.',
                    'Mình dự định thu xếp buổi tập ngoài trời với bạn cùng lớp.']
                turns=history(previous_questions[index],
                              'Bạn dự định vận động ngày nào, khoảng mấy giờ?')
                answer=['Mình hỏi để lấy số đo hoặc dự báo đúng lúc bạn định ra ngoài.',
                        'Có ngày giờ cụ thể, mình mới chọn được dữ liệu đúng thời điểm bạn muốn vận động.',
                        'Mình cần mốc giờ để xem số đo hoặc dự báo phù hợp với lúc bạn định đi.'][index%3]
                expected={'giải thích lý do hỏi thời điểm'}
            elif topic=='missing_aqi':
                answer=[f'Địa điểm đang chọn là {name}, nhưng chưa có US AQI hợp lệ nên mình chưa đánh giá được không khí cho buổi tập.',
                        f'Bảng đang thiếu US AQI của {name}, nên mình chưa kết luận được mức không khí hiện tại.',
                        f'Chưa có US AQI tại {name} để đánh giá buổi vận động. Ô trống không có nghĩa là không khí tốt.'][index%3]
                expected={'giải thích dữ liệu AQI bị thiếu','đọc hoặc tư vấn theo US AQI hiện tại'}
            else:
                answer=[f'Tại {name}, nhiệt độ hiện tại {temperature:g} °C, độ ẩm {humidity}%.',
                        f'Điểm đang chọn là {name}: nhiệt độ {temperature:g} °C, độ ẩm {humidity}%.'][index%2]
                expected={'đọc đúng số thời tiết hiện tại'}
            evidence=briefing(question,turns,snapshot)
            if evidence['nhiem_vu'] not in expected:
                raise ValueError('Evidence/task mismatch: '+question+' / '+evidence['nhiem_vu'])
            if topic=='missing_aqi' and 'dia_diem' not in evidence['chung_cu']:
                # This definition route supplies no location to the model.
                # Do not teach a named-place answer from a hidden snapshot.
                answer=['Ứng dụng chưa có US AQI hợp lệ nên mình chưa đánh giá được không khí cho buổi tập.',
                        'Bảng đang thiếu US AQI, nên mình chưa kết luận được mức không khí hiện tại.',
                        'Chưa có US AQI để đánh giá buổi vận động. Ô trống không có nghĩa là không khí tốt.'][index%3]
            group=f'v16_dialogue_repair:{topic}:{index}'
            messages=compact_messages(question,turns,snapshot)+[{'role':'assistant','content':answer}]
            row={'id':stable_id(group+json.dumps(messages,ensure_ascii=False))[:20], 'group_id':group,
                 'source':'v16_dialogue_repair','topic':topic,'original_question':question,'messages':messages,
                 'snapshot':snapshot,'synthetic_context':True,'supervise_last_assistant_only':True,
                 'source_ids':['project'],'prompt_profile':PROFILE,
                 'review':'Authored repair: direct response, no unsupported details, selected location is not user location.'}
            result[split].append(row)
            audit.append({'id':row['id'],'split':split,'topic':topic,'evidence':evidence,'target':answer})
    return result,audit


def confirmation_cases():
    return [
     {'id':'repair_presence_a','question':'Bạn còn ở đây để nghe mình nói chuyện chứ, Xanh Non?',
      'required_any':[['mình'],['đây','nghe']], 'reject_question_echo':True},
     {'id':'repair_presence_b','question':'Xanh Non, bạn nghe thấy mình đang gọi trợ lý chứ?',
      'required_any':[['mình'],['đây','nghe']], 'reject_question_echo':True},
     {'id':'repair_why_a','question':'Bạn hỏi khi nào mình đi dạo để làm gì thế?',
      'history':history('Mình muốn cân nhắc một buổi đi dạo ở công viên.', 'Bạn định đi vào ngày nào, khoảng mấy giờ?'),
      'required_any':[['số đo','dữ liệu','dự báo','số liệu'],['giờ','lúc','thời điểm','ngày']],
      'forbidden':['ánh sáng','trải nghiệm tốt nhất']},
     {'id':'repair_why_b','question':'Vì sao bạn cần biết giờ mình đi tập vậy nhỉ?',
      'history':history('Mình tính sắp xếp một buổi tập ngoài trời.', 'Bạn muốn tập ngày nào và lúc mấy giờ?'),
      'required_any':[['số đo','dữ liệu','dự báo','số liệu'],['giờ','lúc','thời điểm','ngày']],
      'forbidden':['ánh sáng','trải nghiệm tốt nhất']},
     {'id':'repair_missing_a','question':'US AQI ở điểm mình đang xem chưa có, lúc này có đủ dữ liệu nhận xét buổi tập không?',
      'readings':{'US_AQI':None},'required_any':[['chưa','thiếu','không đủ']],
      'selected_location_only':True,'no_retry_interval':True,'forbidden':['AQI 175','AQI 0']},
     {'id':'repair_missing_b','question':'Ở khu vực được chọn đang thiếu US AQI, liệu đã khẳng định được không khí phù hợp để chạy chưa?',
      'readings':{'US_AQI':None},'required_any':[['chưa','thiếu','không đủ']],
      'selected_location_only':True,'no_retry_interval':True,'forbidden':['AQI 175','AQI 0']},
     {'id':'repair_reading_a','question':'Đọc giúp mình nhiệt độ và độ ẩm đang có ở điểm được chọn trong một câu nhé.',
      'readings':{'NhietDo':21.7,'DoAm':73},'required_any':[['21.7','21,7'],['73']],
      'selected_location_only':True},
     {'id':'repair_followup_weather','question':'Vậy thời tiết mai trong bảng ví dụ ấy thì sao?',
      'history':history('Ví dụ dự báo Hà Nội ngày mai là 26.4 °C, độ ẩm 67%.', 'Mình sẽ dùng bảng ví dụ bạn vừa nêu.'),
      'required_any':[['26.4','26,4'],['67'],['ví dụ','minh họa']], 'time_scope':'tomorrow'},
    ]


def prepare(output,storage):
    output,storage=Path(output),Path(storage)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Choose a new empty data directory')
    partitions,audit=new_rows()
    pool,_=revised_rows(storage)
    excluded=set(QUESTIONS)
    for topic in sorted({r['topic'] for r in pool['train']}-excluded):
        rows=[r for r in pool['train'] if r['topic']==topic][:2]
        if len(rows)!=2:
            raise ValueError('Insufficient aligned rehearsal: '+topic)
        for original in rows:
            row=deepcopy(original)
            row['parent_record_id']=row['id'];row['source']='v16_checked_rehearsal'
            row['group_id']='repair_rehearsal:'+row['group_id'];row['id']=stable_id(row['group_id'])[:20]
            partitions['train'].append(row)
    if {s:len(rows) for s,rows in partitions.items()}!={'train':48,'validation':8}:
        raise ValueError('Expected 24 repair + 24 rehearsal, with 8 validation rows')
    old=json.loads((storage/'qwen3-4b-profile16-review-20261024-patch2/cases.json').read_text(encoding='utf-8'))
    pilot=json.loads((storage/'qwen3-4b-v16-signal-data-20261024/confirmation-cases.json').read_text(encoding='utf-8'))
    fresh=confirmation_cases()
    validate_records(partitions,old+pilot+fresh)
    for rows in partitions.values():
        for row in rows:
            if semantic_violations(row['messages'][-1]['content']):
                raise ValueError('Invalid authored target')
    # The 64 older cases are development, including the previously reviewed
    # 8 confirmation cases. Keep all 8 recent signal cases too (72 development).
    cases=old+pilot+fresh
    prompts={}
    for case in cases:
        snapshot={'DiaDiem':{'MaDiaDiem':'hanoi','Ten':'Hà Nội'},'ThoiGian':'2026-10-19T09:00:00',
                  'DuLieu':{'US_AQI':175,'PM25':45.4,'PM10':60,'NhietDo':24.8,'DoAm':95,
                            'TiengOn':74.99,**case.get('readings',{})}}
        prompts[case['id']]=compact_messages(case['question'],case.get('history',[]),snapshot)
    if len(cases)!=80 or len(prompts)!=80:
        raise ValueError('Expected 72 development + 8 new confirmation wordings')
    output.mkdir(parents=True)
    for split,rows in partitions.items():
        (output/(split+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    for name,value in [('alignment-audit.json',audit),('cases.json',cases),('messages.json',prompts),('confirmation-cases.json',fresh)]:
        save_json(output/name,value)
    manifest={'built_at':datetime.now().astimezone().isoformat(),'require_complete_dialogues':True,
       'counts':{s:len(rows) for s,rows in partitions.items()},'prompt_profile':PROFILE,
       'required_train_sources':['v16_dialogue_repair','v16_checked_rehearsal'],
       'required_train_topics':sorted({r['topic'] for r in partitions['train']}),
       'topics':{s:dict(Counter(r['topic'] for r in rows)) for s,rows in partitions.items()},
       'evaluation':{'development_cases':72,'new_confirmation_wordings':8},
       'artifacts_sha256':{p.name:digest(p) for p in output.iterdir() if p.is_file()},
       'input_sha256':{n:digest(ROOT/n) for n in ['prepare_xanhnon_v16_repair.py','prepare_xanhnon_v16_pilot.py',
           'chat_briefing.py','chat_briefing_v15.py','chat_briefing_v16.py','chat_scope.py']},
       'parent_manual_review_sha256':digest(storage/'qwen3-4b-v16-signal-cycle-20261024/answer-review/manual-answer-review.json'),
       'parent_data_manifest_sha256':digest(storage/'qwen3-4b-correction-data-20261024/manifest.json'),
       'sources':json.loads((storage/'qwen3-4b-correction-data-20261024/manifest.json').read_text(encoding='utf-8'))['sources'],
       'training_plan':{'start':'fresh_verified_nf4_base','learning_rate':0.0001,'epochs':1,'accumulation':4,
            'last_layers':4,'rank':8,'target_modules':['q_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']},
       'model_activated':False,'limitations':['Authored and source-backed rehearsal, not independent expert validation.',
         'Synthetic readings must not be represented as current observations.',
         'Eight new wordings cover known failure concepts; not a broad independent benchmark.',
         'Broader LoRA projections are an experimental change; quality must be measured before any deployment.']}
    save_json(output/'manifest.json',manifest)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--storage',type=Path,default=Path('D:/XanhNon-auto-training'))
    args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.storage),ensure_ascii=False,indent=2))
