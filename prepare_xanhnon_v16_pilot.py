"""Freeze a small, evidence-consistent 4B pilot instead of repeating v15 data."""
from collections import Counter
from copy import deepcopy
from datetime import datetime
import argparse
import json
from pathlib import Path

from chat_answer_checks import semantic_violations
from chat_briefing_v16 import PROFILE, briefing, compact_messages
from prepare_xanhnon_4b_corrections import build, CONFIRMATION
from prepare_xanhnon_correction_data import history, validate_records
from prepare_xanhnon_data import stable_id
from sensor_training_data import ROOT, digest, save_json


SOURCE = 'reviewed_v16_signal_pilot'
EXPECTED = {
    'speaker_presence': {'đáp lại lời gọi trợ lý'},
    'topic_clarification': {'hỏi rõ chủ đề'},
    'particle_unit': {'phân biệt tên hạt, nồng độ và chỉ số'},
    'ask_activity_time': {'hỏi thời điểm định hoạt động'},
    'explain_own_question': {'giải thích lý do hỏi thời điểm'},
    'selected_location': {'đọc đúng số thời tiết hiện tại'},
    'noise_without_internal_ids': {'giảm tiếp xúc tiếng ồn', 'đưa biện pháp cụ thể'},
    'brief_acknowledgment': {'giao tiếp thanks'},
}


def confirmation_cases():
    """New wording, fixed before this pilot; concepts have been used for development."""
    return [
        {'id': 'signal_presence', 'question': 'Bạn vẫn còn ở đây nghe mình nói chứ, Xanh Non?',
         'required_any': [['mình'], ['đây', 'nghe']], 'forbidden': ['bạn đang ở đây']},
        {'id': 'signal_topic', 'question': 'Xem tình hình ngày tới giúp mình một chút nhé.',
         'required_any': [['thời tiết'], ['không khí']]},
        {'id': 'signal_unit', 'question': 'Mình nhầm tên PM2.5 với đơn vị µg/m³, phân biệt giúp nhé.',
         'required_any': [['hạt', 'bụi'], ['nồng độ'], ['đơn vị']]},
        {'id': 'signal_why', 'question': 'Vì sao bạn cần biết thời điểm mình đi ra ngoài?',
         'history': history('Mình sắp xếp một buổi đi bộ.', 'Bạn định đi ngày nào, vào mấy giờ?'),
         'required_any': [['số đo', 'số liệu', 'dữ liệu', 'dự báo'], ['thời điểm', 'giờ', 'lúc', 'ngày']]},
        {'id': 'signal_reading', 'question': 'Xem giúp nhiệt độ và độ ẩm hiện tại của khu vực được chọn.',
         'required_any': [['Hà Nội'], ['22.6', '22,6'], ['68']],
         'readings': {'NhietDo': 22.6, 'DoAm': 68}},
        {'id': 'signal_hypothesis', 'question': 'Thế mai có nên tập ngoài trời theo giả định đó?',
         'history': history('Giả sử Hà Nội ngày mai US AQI 186.', 'Mình sẽ dùng tình huống giả định đó.'),
         'required_any': [['giả định', 'giả sử', 'ví dụ'], ['186'], ['Xấu'], ['giảm', 'hạn chế']],
         'time_scope': 'tomorrow'},
        {'id': 'signal_missing', 'question': 'US AQI chưa tải được, liệu có chắc buổi chạy lúc này ổn không?',
         'readings': {'US_AQI': None},
         'required_any': [['chưa', 'không đủ', 'thiếu']], 'forbidden': ['AQI 175', 'AQI 0']},
        {'id': 'signal_noise', 'question': 'Tập quen tai bằng cách ở lại chỗ ồn thật lâu có nên không?',
         'required_any': [['không', 'đừng'], ['giảm', 'rút ngắn'], ['xa']],
         'check_noise_duration': True},
    ]


def revised_rows(storage):
    partitions = build(storage)
    # Previous why examples had a clarification task paired with an explanatory
    # answer. Replace their questions, preserving role history and split ownership.
    questions = {
        'train': ['Vì sao bạn cần biết giờ mình đi bộ?',
                  'Bạn hỏi thời điểm mình tập để làm gì vậy?',
                  'Tại sao bạn cần biết ngày giờ mình vận động?',
                  'Bạn muốn biết giờ mình đi vì sao?'],
        'validation': ['Vì sao bạn cần biết ngày mình đi?',
                       'Bạn hỏi thời điểm đi dạo để làm gì thế?'],
    }
    audit, revised = [], {'train': [], 'validation': []}
    for split, rows in partitions.items():
        why_index = 0
        for original in rows:
            row = deepcopy(original)
            turns = row['messages'][1:-2]
            if row['topic'] == 'explain_own_question':
                row['original_question'] = questions[split][why_index]
                why_index += 1
            question = row['original_question']
            evidence = briefing(question, turns, row.get('snapshot'))
            task = evidence['nhiem_vu']
            supported = task != 'hỏi rõ thông tin cần thiết'
            if row['topic'] in EXPECTED:
                supported = task in EXPECTED[row['topic']]
            audit.append({'parent_id': original['id'], 'split': split, 'topic': row['topic'],
                          'question': question, 'task': task, 'included': supported})
            if not supported:
                continue
            row['parent_record_id'] = original['id']
            row['source'] = SOURCE
            row['group_id'] = SOURCE + ':' + original['group_id']
            row['messages'] = compact_messages(question, turns, row.get('snapshot')) + [row['messages'][-1]]
            row['id'] = stable_id(row['group_id'] + json.dumps(row['messages'], ensure_ascii=False))[:20]
            row['prompt_profile'] = PROFILE
            row['review'] = 'v16 evidence/target alignment checked; source-backed rehearsal; synthetic numeric contexts'
            revised[split].append(row)
    return revised, audit


def prepare(output, storage):
    output, storage = Path(output), Path(storage)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new output directory')
    pool, audit = revised_rows(storage)
    # One example per topic: 8 dialogue corrections + 8 safety/context rehearsal.
    train = []
    for topic in sorted({r['topic'] for r in pool['train']}):
        train.append(next(r for r in pool['train'] if r['topic'] == topic))
    validation_topics = ['speaker_presence', 'particle_unit', 'selected_location', 'explain_own_question']
    validation = [next(r for r in pool['validation'] if r['topic'] == t) for t in validation_topics]
    if len(train) != 16:
        raise ValueError('Pilot must cover exactly sixteen reviewed topics')
    partitions = {'train': train, 'validation': validation}
    old = json.loads((storage/'qwen3-4b-profile16-review-20261024-patch2/cases.json').read_text(encoding='utf-8'))
    confirmation = confirmation_cases()
    validate_records(partitions, old + CONFIRMATION + confirmation)
    for rows in partitions.values():
        for row in rows:
            if semantic_violations(row['messages'][-1]['content']):
                raise ValueError('Invalid target: ' + row['id'])
            if 'source_ids' in row['messages'][-2]['content']:
                raise ValueError('Internal source IDs remain in the model input')
    # Freeze actual generation inputs before training. No answers are used as SFT.
    development = old[:16]
    cases = development + confirmation
    prompts = {}
    for case in cases:
        snapshot = {'DiaDiem': {'MaDiaDiem':'hanoi', 'Ten':'Hà Nội'},
                    'ThoiGian':'2026-10-19T09:00:00',
                    'DuLieu': {'US_AQI':175, 'PM25':45.4, 'PM10':60,
                               'NhietDo':24.8, 'DoAm':95, 'TiengOn':74.99,
                               **case.get('readings', {})}}
        prompts[case['id']] = compact_messages(case['question'], case.get('history', []), snapshot)
    output.mkdir(parents=True)
    for split, rows in partitions.items():
        (output/(split+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    save_json(output/'alignment-audit.json', audit)
    save_json(output/'cases.json', cases)
    save_json(output/'messages.json', prompts)
    save_json(output/'confirmation-cases.json', confirmation)
    save_json(output/'reviewed-pool.json', pool)
    manifest = {'built_at':datetime.now().astimezone().isoformat(), 'require_complete_dialogues':True,
        'required_train_sources':[SOURCE], 'required_train_topics':sorted(r['topic'] for r in train),
        'counts':{s:len(rows) for s,rows in partitions.items()},
        'topics':{s:dict(Counter(r['topic'] for r in rows)) for s,rows in partitions.items()},
        'prompt_profile':PROFILE, 'model_activated':False,
        'artifacts_sha256':{p.name:digest(p) for p in output.iterdir() if p.is_file()},
        'input_sha256':{name:digest(ROOT/name) for name in ['prepare_xanhnon_v16_pilot.py',
            'prepare_xanhnon_4b_corrections.py','chat_briefing.py','chat_briefing_v15.py','chat_briefing_v16.py','chat_scope.py']},
        'parent_manifest_sha256':digest(storage/'qwen3-4b-correction-data-20261024/manifest.json'),
        'limitations':['Small update-signal pilot; not a full coverage benchmark.',
            'Validation wording is new to this run; concepts and original rows were used in earlier training.',
            '24 answer cases = 16 development + 8 newly authored wording; related concepts are not independent.',
            'Higher learning rate is experimental; never auto-deploy from a lower training loss.']}
    save_json(output/'manifest.json',manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--storage', type=Path, default=Path('D:/XanhNon-auto-training'))
    args = parser.parse_args()
    print(json.dumps(prepare(args.output,args.storage),ensure_ascii=False,indent=2))
