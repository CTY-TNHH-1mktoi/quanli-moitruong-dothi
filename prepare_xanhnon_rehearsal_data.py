"""v14: restore all unique v12/v13 examples and practice current-data reading.

Two epochs mean repeated presentations, not newly collected records. Retain
the earlier frozen input profile, source attribution and active-v2 starting
adapter. New targets are project-written, never copied from rejected answers.
"""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import random
import shutil
from zoneinfo import ZoneInfo

from chat_briefing import PROFILE, briefing, compact_messages
from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_correction_data import history, validate_records
from prepare_xanhnon_data import stable_id
from prepare_xanhnon_grounded_data import read_rows
from prepare_xanhnon_runtime_data import snapshot_for
from queue_sensor_training import validate_prepared_dataset
from sensor_training_data import ROOT, digest, save_json

STORAGE = Path('D:/XanhNon-auto-training')
SOURCE = 'environment_rehearsal_v14'
WEATHER_QUESTIONS = [
    'Đọc giúp nhiệt độ và độ ẩm hiện tại của khu vực nhé.',
    'Thời tiết ở địa điểm đang chọn hiện giờ ra sao?',
    'Cho mình hai số nhiệt độ và độ ẩm mới nhất.',
    'Mình muốn biết thời tiết lúc này, nói thật gọn.',
    'Thông số thời tiết tại đây hiện giờ thế nào nhỉ?',
]
MISSING_QUESTIONS = [
    'Không khí hôm nay có đủ tốt để mình đi dạo chưa?',
    'Mình tập thể dục ngoài trời hiện tại có phù hợp không?',
    'AQI hiện tại đang trống, vậy đã đánh giá không khí được chưa?',
    'Với dữ liệu không khí lúc này, mình ra ngoài chạy được chưa?',
    'Dữ liệu không khí hiện giờ đã đủ để tư vấn buổi đi bộ chưa?',
]
DUST_QUESTIONS = [
    'Phòng mình cạnh đường xe chạy, giảm bụi trong phòng thế nào cho gọn?',
    'Có cách nào hạn chế bụi từ xe ngoài đường bay vào nhà không?',
    'Nhà sát tuyến đường đông xe, bạn gợi ý cách giảm bụi nhé.',
    'Mình muốn bớt bụi vào phòng gần đường lớn, bắt đầu từ đâu?',
    'Cạnh nhà có nhiều xe tải, làm thế nào giảm bụi trong nhà?',
    'Bạn tư vấn ngắn cách hạn chế bụi lọt vào nhà cạnh đường.',
    'Muốn giảm bụi từ ngoài vào căn phòng sát đường thì làm gì?',
    'Phòng ở gần đường nhiều xe nên làm gì để bớt bụi?',
    'Nói ngắn các việc giúp nhà bên đường giảm bụi vào phòng.',
    'Ở sát đường giao thông, mình hạn chế bụi trong phòng bằng cách nào?',
]
GREETING_QUESTIONS = [
    'Chào Xanh Non, bạn giúp mình hỏi chút nhé.',
    'Alo trợ lý Xanh Non, mình hỏi nhờ được chứ?',
    'Hi Xanh Non ơi, cho mình hỏi thêm với.',
    'Chào bạn ơi, giúp mình tí được chứ?',
    'Chào Xanh Non nha, mình nhờ bạn tư vấn chút.',
    'Hello bạn ơi, mình muốn hỏi một câu nha.',
    'A lô Xanh Non, bạn trò chuyện với mình chút nhé.',
    'Chào bạn, sẵn sàng nghe mình hỏi chứ?',
    'Chào Xanh Non ơi, mình xin hỏi bạn một chút.',
    'Alo bạn, cho mình trao đổi một câu được không?',
]


def new_records():
    result = {'train': [], 'validation': []}

    def add(topic, index, question, answer, snapshot, turns=(), sources=('project',), validation=False):
        group = f'{SOURCE}:{topic}:{index}'
        messages = compact_messages(question, turns, snapshot) + [{'role': 'assistant', 'content': answer}]
        row = {'id': stable_id(group + json.dumps(messages, ensure_ascii=False))[:20],
               'group_id': group, 'source': SOURCE, 'topic': topic,
               'original_question': question, 'messages': messages, 'snapshot': snapshot,
               'source_ids': list(sources), 'synthetic_context': True,
               'supervise_last_assistant_only': True, 'prompt_profile': PROFILE,
               'mixture_component': 'dialogue' if topic == 'friendly_opening' else 'expertise',
               'novel_question_and_target': True,
               'review': 'project_authored_targets_from_checked_sources_and_explicit_synthetic_readings'}
        result['validation' if validation else 'train'].append(row)

    temperatures = [(11.6, 32.7), (5.2, 28.9), (21.4, 36.2), (14.7, 30.6), (9.3, 26.4)]
    humidities = [(48, 84), (36, 69), (55, 92), (43, 77), (51, 86)]
    for index, question in enumerate(WEATHER_QUESTIONS):
        for variant in range(2):
            snapshot = snapshot_for(index)
            temperature, humidity = temperatures[index][variant], humidities[index][variant]
            snapshot['DuLieu'].update(NhietDo=temperature, DoAm=humidity)
            answer = f'Hà Nội hiện {temperature} °C, độ ẩm {humidity}%.'
            add('current_weather_reading', index, question, answer, snapshot, validation=index == 4)
    for index, question in enumerate(MISSING_QUESTIONS):
        for variant in range(2):
            snapshot = snapshot_for(index)
            snapshot['DuLieu'].update(US_AQI=None, PM25=3 + index * 8 + variant * 15)
            old_aqi = 29 + index * 33 + variant * 12
            turns = history(f'Ví dụ cũ mình vừa xem có US AQI {old_aqi}.',
                            'Đây là thông tin của thời điểm cũ, không thay cho dữ liệu mới.')
            answer = 'Mình chưa có US AQI hiện tại nên chưa đủ dữ liệu để đánh giá không khí cho buổi tập. Không dùng chỉ số cũ hoặc lấy nguyên số PM2.5 thay cho AQI.'
            add('missing_current_aqi', index, question, answer, snapshot, turns,
                ('project', 'airnow_aqi'), validation=index == 4)
    for index, question in enumerate(DUST_QUESTIONS):
        answer = ('Bạn có thể hạn chế mở cửa phía đường khi ngoài trời nhiều bụi, lau bụi bằng khăn ẩm '
                  'và tránh khói thuốc trong nhà. Thông gió khi không khí ngoài trời sạch hơn.')
        add('concise_dust_actions', index, question, answer, snapshot_for(index % 8),
            sources=('epa_indoor_pm', 'epa_air_cleaners'), validation=index >= 8)
    for index, question in enumerate(GREETING_QUESTIONS):
        answer = ['Chào bạn! Mình đây, bạn cứ hỏi nhé.',
                  'Chào bạn, được chứ! Bạn cần mình hỗ trợ điều gì?'][index % 2]
        add('friendly_opening', index, question, answer, snapshot_for(index % 8), validation=index >= 8)
    return result


def records(storage=STORAGE):
    storage = Path(storage)
    result = new_records()
    for split in ('train', 'validation'):
        unique = {}
        for name in ('grounded-v12-data-20261022-reviewed', 'focused-v13-data-20261022-reviewed'):
            for row in read_rows(storage / name / (split + '.jsonl')):
                if row['id'] in unique and row != unique[row['id']]:
                    raise ValueError('Conflicting earlier record IDs')
                unique[row['id']] = row
        result[split] = [deepcopy(r) for r in unique.values()] + result[split]
    if len(result['train']) != 272 or len(result['validation']) != 39:
        raise ValueError('Unexpected deduplicated batch size')
    return result


def audit(partitions):
    for rows in partitions.values():
        for row in rows:
            if row['source'] != SOURCE:
                continue
            answer = row['messages'][-1]['content']
            evidence = briefing(row['original_question'], row['messages'][1:-2], row['snapshot'])
            if evidence['nhiem_vu'] == 'hỏi rõ thông tin cần thiết':
                raise ValueError('Teacher context does not support the target: ' + row['original_question'])
            if row['topic'] == 'current_weather_reading':
                values = evidence['chung_cu']
                if str(values.get('NhietDo')) not in answer or str(values.get('DoAm')) + '%' not in answer:
                    raise ValueError('Weather target disagrees with the supplied data')
            if row['topic'] == 'missing_current_aqi' and row['snapshot']['DuLieu']['US_AQI'] is not None:
                raise ValueError('Missing-AQI example has a current AQI')
            if len(answer.split()) > 85:
                raise ValueError('Answer too long')


def prepare(output, extra_cases, storage=STORAGE):
    output, storage = Path(output), Path(storage)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new empty output directory')
    recipe_hash, profile_hash = digest(Path(__file__)), digest(ROOT / 'chat_briefing.py')
    partitions = records(storage)
    audit(partitions)
    cases, case_hash = evaluation_cases(extra_cases)
    deduplication = validate_records(partitions, cases)
    parent = storage / 'focused-v13-data-20261022-reviewed'
    previous = json.loads((parent / 'manifest.json').read_text(encoding='utf-8'))
    sources = {s['id'] for s in previous['sources']}
    if any(not set(r['source_ids']) <= sources for rows in partitions.values() for r in rows):
        raise ValueError('Unknown source attribution')
    configuration = deepcopy(previous['training_configuration'])
    configuration['epochs'] = 2
    output.mkdir(parents=True, exist_ok=True)
    for split, rows in partitions.items():
        random.Random(44).shuffle(rows)
        (output / (split + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    if recipe_hash != digest(Path(__file__)) or profile_hash != digest(ROOT / 'chat_briefing.py'):
        raise RuntimeError('Recipe changed during preparation')
    input_hashes = {'recipe': recipe_hash, 'prompt_profile_recipe': profile_hash}
    for version, folder in [('v12', 'grounded-v12-data-20261022-reviewed'), ('v13', 'focused-v13-data-20261022-reviewed')]:
        for name in ('train.jsonl', 'validation.jsonl', 'manifest.json'):
            input_hashes[version + '_' + name] = digest(storage / folder / name)
    manifest = {'schema_version': 1, 'built_at': datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(),
        'require_complete_dialogues': True, 'seed': 44, 'prompt_profile': PROFILE,
        'counts': {s: dict(Counter(r['source'] for r in rows)) for s, rows in partitions.items()},
        'mixture_counts': {s: dict(Counter(r['mixture_component'] for r in rows)) for s, rows in partitions.items()},
        'new_dialogue_counts': {'train': 32, 'validation': 8},
        'reused_question_and_target_counts': {'train': 240, 'validation': 31},
        'required_train_sources': sorted({r['source'] for r in partitions['train']}),
        'required_train_topics': sorted({r['topic'] for r in partitions['train']}),
        'artifacts_sha256': {s + '.jsonl': digest(output / (s + '.jsonl')) for s in partitions},
        'sources': previous['sources'], 'rehearsal_sources': [], 'skipped_sources': [],
        'deduplication': {**deduplication, 'earlier_training_records_merged_once': 240,
                          'earlier_input_duplicates_removed': {'train': 80, 'validation': 20}},
        'training_configuration': configuration, 'input_sha256': input_hashes,
        'evaluation_cases_sha256': case_hash, 'model_activated': False,
        'planned_optimizer_steps': 136,
        'experiment': {'name': 'rehearsal-v14', 'starts_from_active_v2': True,
                       'continues_rejected_v13': False, 'all_v12_and_v13_records_restored': True,
                       'unique_training_rows': 272, 'training_presentations': 544},
        'review': {'targets_project_authored': True, 'independent_expert_certification': False},
        'limitations': ['Two epochs repeat the same 272 records; they are not 544 unique samples.',
                       'All 36 existing generation cases are development cases, not unseen confirmation.',
                       'Readings and forecasts are synthetic; do not represent current measurements.',
                       'Known evaluation failures informed topics, while exact questions and histories stay outside SFT.',
                       'Keyword-based evaluation still requires manual factual and naturalness review before release.']}
    save_json(output / 'manifest.json', manifest)
    shutil.copy2(parent / 'LICENSE-APACHE-2.0.txt', output / 'LICENSE-APACHE-2.0.txt')
    (output / 'NOTICE.md').write_text('# Rehearsal v14\n\n240 unique reused training records plus 32 newly project-authored records; '
        '31 reused and 8 new validation records. New source-based advice is paraphrased; source links remain per record. '
        'All numerical contexts are simulated. Previous candidates and the live model are preserved.\n', encoding='utf-8')
    validate_prepared_dataset(output)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extra-cases', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output, args.extra_cases)
    print(json.dumps({k: result[k] for k in ('counts', 'new_dialogue_counts', 'planned_optimizer_steps')}, ensure_ascii=False))
