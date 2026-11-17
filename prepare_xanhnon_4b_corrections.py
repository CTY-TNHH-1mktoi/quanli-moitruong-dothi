"""Build a bounded corrective SFT batch and freeze new confirmation questions."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import random

from chat_answer_checks import semantic_violations
from chat_briefing_v15 import PROFILE, compact_messages
from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_correction_data import history, validate_records
from prepare_xanhnon_data import stable_id
from sensor_training_data import ROOT, digest, save_json


SOURCE = 'qwen3_4b_reviewed_corrections'
QUESTIONS = {
 'speaker_presence': ['Alo Xanh Non, có nghe mình gọi không?', 'Bạn vẫn đang nghe mình chứ?',
  'Mình gọi trợ lý, bạn có mặt không?', 'Xanh Non còn trực ở đây chứ bạn?',
  'Ê trợ lý, đang nghe mình nói không?', 'Mình cần hỏi, bạn có đang ở đây chứ?'],
 'topic_clarification': ['Mình muốn biết ngày kế tiếp ra sao.', 'Tình hình ngày tới thế nào nhỉ?',
  'Nhờ bạn xem giúp hôm sau nhé.', 'Xem cho mình tình hình hôm tới được chứ?',
  'Cho mình hỏi sang hôm kế tiếp ra sao.', 'Hôm tiếp theo thì như nào vậy?'],
 'particle_unit': ['PM2.5 là đơn vị hay tên loại hạt?', 'Ký hiệu PM2.5 có phải đơn vị nồng độ không?',
  'Mình hiểu PM2.5 là một đơn vị đo, có đúng không?', 'Đơn vị µg/m³ và tên PM2.5 khác nhau thế nào?',
  'Gọi PM2.5 là đơn vị của số nồng độ có chuẩn không?', 'Vì sao không gọi PM2.5 là đơn vị đo bụi?'],
 'ask_activity_time': ['Giúp mình sắp xếp buổi đi dạo ngoài trời theo không khí nhé.',
  'Mình muốn tổ chức một buổi chạy ở công viên, bạn tư vấn nhé.',
  'Mình đang lên lịch đạp xe ngoài đường, nhờ bạn tư vấn môi trường.',
  'Nhờ Xanh Non cân nhắc điều kiện môi trường cho kế hoạch đi bộ.',
  'Mình lên kế hoạch tập ngoài công viên, cần bạn tư vấn môi trường.',
  'Bạn tư vấn giúp kế hoạch đi dạo ngoài trời của mình nha.'],
 'explain_own_question': ['Bạn cần mốc giờ ấy để chọn dữ liệu nào?', 'Mình nói giờ đi thì giúp bạn tư vấn ra sao?',
  'Lúc mình tập liên quan thế nào tới số liệu bạn dùng?', 'Sao lời tư vấn lại phụ thuộc vào giờ mình chọn?',
  'Biết ngày giờ mình đi thì bạn làm gì tiếp?', 'Giải thích vì sao bạn cần mốc thời gian mình vận động.'],
 'selected_location': ['Đọc gọn thời tiết tại địa điểm đang chọn giúp mình.',
  'Cho mình số nhiệt độ, độ ẩm của khu vực đang xem nhé.',
  'Nói ngắn hai số nhiệt độ và độ ẩm trên bảng đi.', 'Tóm tắt thời tiết của điểm được chọn trên ứng dụng.',
  'Khu vực mình chọn đang có nhiệt độ và độ ẩm bao nhiêu?', 'Nhắc hai thông số thời tiết ở điểm mình đang xem.'],
 'noise_without_internal_ids': ['Có nên cố nghe tiếng máy thật lâu cho quen không?',
  'Muốn quen tiếng công trường, mình nên đứng nghe lâu hơn à?',
  'Ở chỗ ồn thì tăng thời gian nghe có giúp tai quen không?',
  'Nghe nhạc lớn lâu hơn để quen tai có phải cách tốt không?',
  'Mình kéo dài lúc ở nơi ồn để tập quen tai được chứ?',
  'Có cần rèn tai bằng cách chịu tiếng lớn lâu hơn không?'],
 'brief_acknowledgment': ['Ừm mình hiểu cách bạn giải thích rồi nha.', 'Vậy là mình đã hiểu ý bạn rồi.',
  'Rõ ý rồi Xanh Non, cảm ơn nha.', 'Mình nắm được rồi, cảm ơn lời giải thích.',
  'Cách nói đó dễ hiểu, mình cảm ơn.', 'Thông tin vừa rồi giúp mình hiểu hơn rồi.'],
}
CONFIRMATION = [
 {'id':'fourb_presence_new','question':'Xanh Non ơi, bạn nghe thấy mình chứ?'},
 {'id':'fourb_topic_new','question':'Bạn cho mình biết hôm tới ra sao với.'},
 {'id':'fourb_unit_new','question':'Có đúng PM2.5 là đơn vị đo còn microgam trên mét khối là tên bụi?'},
 {'id':'fourb_activity_new','question':'Tư vấn giúp mình lên lịch một buổi vận động ngoài trời nha.'},
 {'id':'fourb_explain_new','question':'Bạn hỏi mốc giờ hoạt động để phục vụ việc gì?', 'history':history(
  'Mình lên kế hoạch đi bộ ngoài trời.', 'Bạn định đi vào ngày nào, khoảng mấy giờ?')},
 {'id':'fourb_location_new','question':'Đọc giúp mình nhiệt độ và độ ẩm của điểm đang được chọn nhé.'},
 {'id':'fourb_noise_new','question':'Để tai quen với tiếng lớn, mình nên cố ở lại nghe lâu hơn phải không?'},
 {'id':'fourb_ack_new','question':'Mình rõ rồi nha, cảm ơn câu giải thích của bạn.'},
]
REPLAY_TOPICS = ['missing_aqi', 'no_equipment', 'window_polarity', 'current_over_history',
                 'forecast_weather', 'forecast_air', 'pm_comparison', 'future_air_consultation']


def build(storage):
    storage = Path(storage)
    result = {'train': [], 'validation': []}
    for topic, questions in QUESTIONS.items():
        for index, question in enumerate(questions):
            turns = []
            snapshot = {'DiaDiem': {'MaDiaDiem':'hanoi','Ten':'Hà Nội'},
                        'DuLieu': {'NhietDo':round(18.2 + index * 1.7, 1), 'DoAm':52 + 6 * index}}
            source_ids = ['project']
            if topic == 'speaker_presence':
                answer = 'Mình đây, bạn cứ hỏi nhé.'
            elif topic == 'topic_clarification':
                answer = 'Bạn muốn xem thời tiết hay chất lượng không khí ngày tới?'
            elif topic == 'particle_unit':
                answer = 'PM2.5 là nhóm hạt bụi mịn, không phải đơn vị đo. µg/m³ là đơn vị nồng độ bụi; AQI là một chỉ số quy đổi.'
                source_ids = ['epa_pm', 'airnow_aqi']
            elif topic == 'ask_activity_time':
                answer = 'Bạn định vận động vào ngày nào, khoảng mấy giờ?'
            elif topic == 'explain_own_question':
                turns = history(QUESTIONS['ask_activity_time'][index], 'Bạn định vận động vào ngày nào, khoảng mấy giờ?')
                answer = 'Mình hỏi để xem số đo hoặc dự báo đúng thời điểm bạn định vận động.'
            elif topic == 'selected_location':
                values = snapshot['DuLieu']
                answer = f"Hà Nội hiện có nhiệt độ {values['NhietDo']:g} °C, độ ẩm {values['DoAm']}%."
            elif topic == 'noise_without_internal_ids':
                answer = 'Không nên cố chịu tiếng lớn để quen tai. Bạn nên giảm thời gian tiếp xúc, đứng xa nguồn ồn và dùng bảo vệ tai phù hợp khi cần.'
                source_ids = ['nidcd_noise']
            elif topic == 'brief_acknowledgment':
                answer = 'Không có gì nhé bạn.'
            messages = compact_messages(question, turns, snapshot) + [{'role':'assistant','content':answer}]
            group = f'{SOURCE}:{topic}:{index}'
            row = {'id':stable_id(group+json.dumps(messages,ensure_ascii=False))[:20],
                   'group_id':group,'source':SOURCE,'topic':topic,'original_question':question,
                   'messages':messages,'snapshot':snapshot,'source_ids':source_ids,
                   'synthetic_context':True,'prompt_profile':PROFILE,
                   'supervise_last_assistant_only':True,
                   'review':'authored corrections based on stored 4B failures; project dialogue policy and existing primary sources'}
            result['train' if index < 4 else 'validation'].append(row)
    parent = storage/'meaning-v15-data-20261022-reviewed'
    rows = [json.loads(line) for line in (parent/'train.jsonl').read_text(encoding='utf-8').splitlines()]
    for topic in REPLAY_TOPICS:
        selected = sorted((row for row in rows if row['topic'] == topic), key=lambda row:row['id'])[:4]
        if len(selected) != 4:
            raise ValueError('Insufficient checked rehearsal records: '+topic)
        for original in selected:
            row = deepcopy(original)
            row['parent_record_id'] = original['id']
            row['group_id'] = SOURCE+':replay:'+original['group_id']
            row['id'] = stable_id(row['group_id'])[:20]
            row['source'] = 'reviewed_v15_rehearsal'
            result['train'].append(row)
    return result


def prepare(output, storage):
    output, storage = Path(output), Path(storage)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Choose a new empty output directory')
    partitions = build(storage)
    extra = storage/'rehearsal-review-v14-answers-20261022/extra-cases.json'
    cases, _ = evaluation_cases(extra)
    fresh = json.loads((ROOT/'data/xanhnon/eval_meaning_confirmation.json').read_text(encoding='utf-8'))
    validate_records(partitions, cases + fresh + CONFIRMATION)
    knowledge_path = ROOT/'data/xanhnon/knowledge.json'
    supplement = ROOT/'data/xanhnon/specialist_supplement.json'
    sources = {**json.loads(knowledge_path.read_text(encoding='utf-8'))['sources'],
               **json.loads(supplement.read_text(encoding='utf-8'))['sources']}
    for rows in partitions.values():
        for row in rows:
            if semantic_violations(row['messages'][-1]['content']):
                raise ValueError('Unsafe/incorrect training target: '+row['id'])
            if not set(row['source_ids']) <= set(sources):
                raise ValueError('Unknown source ID')
    output.mkdir(parents=True,exist_ok=True)
    for split, rows in partitions.items():
        random.Random(42).shuffle(rows)
        (output/(split+'.jsonl')).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')
    save_json(output/'confirmation-cases.json',CONFIRMATION)
    manifest = {
        'built_at':datetime.now().astimezone().isoformat(),'require_complete_dialogues':True,
        'required_train_sources':[SOURCE,'reviewed_v15_rehearsal'],
        'required_train_topics':sorted(QUESTIONS),
        'counts':{s:len(rows) for s,rows in partitions.items()},
        'topics':{s:dict(Counter(r['topic'] for r in rows)) for s,rows in partitions.items()},
        'artifacts_sha256':{name:digest(output/name) for name in ['train.jsonl','validation.jsonl','confirmation-cases.json']},
        'input_sha256':{'recipe':digest(Path(__file__)),'knowledge':digest(knowledge_path),
            'specialist':digest(supplement),'rehearsal':digest(storage/'meaning-v15-data-20261022-reviewed/train.jsonl'),
            'reviewed_failures':digest(storage/'qwen3-4b-base-review-20261023-run2/manual-answer-review.json')},
        'sources':sources, 'model_activated':False,
        'limitations':['Authored corrections, not an independent expert review.',
            'Validation uses related concepts with different wording.',
            'Development and new confirmation questions excluded from SFT.',
            'A new adapter must pass output review before deployment.'],
    }
    save_json(output/'manifest.json',manifest)
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--storage',type=Path,default=Path('D:/XanhNon-auto-training'))
    args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.storage),ensure_ascii=False,indent=2))
