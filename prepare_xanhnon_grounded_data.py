"""Train short evidence-grounded replies and rehearse the broader knowledge set.

Prior checked rows are reused transparently; a new input format is not claimed
to be a newly collected public dataset. Old batches and the live app are intact.
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

from chat_briefing import PROFILE, compact_messages, catalog
from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_correction_data import validate_records, history
from prepare_xanhnon_data import stable_id
from prepare_xanhnon_runtime_data import snapshot_for
from queue_sensor_training import validate_prepared_dataset
from sensor_training_data import ROOT, digest, save_json

SOURCE = 'environment_grounded_v12'
STORAGE = Path('D:/XanhNon-auto-training')


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def convert(row, *, novel=False):
    result = deepcopy(row)
    question = row['original_question']
    turns = row['messages'][1:-2]
    evidence = None
    if row['topic'].startswith('knowledge_'):
        # Standard RAG rehearsal: a checked source passage accompanies the task.
        # This passage comes from the document, never from an unchecked model.
        doc = catalog()[0][row['topic'].removeprefix('knowledge_')]
        evidence = {'nhiem_vu': 'giải thích theo tài liệu được cung cấp',
                    'chung_cu': {'tai_lieu': doc['answer']}, 'source_ids': doc['source_ids']}
        if doc['id'] == 'pm25_definition':
            evidence['chung_cu']['tai_lieu'] = 'PM2.5 thường không quá 2,5 micromet; có thể được hít vào sâu trong phổi.'
    result['messages'] = compact_messages(question, turns, row['snapshot'], supplied_evidence=evidence) + [
        {'role': 'assistant', 'content': row['messages'][-1]['content']}]
    result.update(source=SOURCE, group_id=SOURCE + ':' + row['group_id'],
                  prompt_profile=PROFILE, supervise_last_assistant_only=True,
                  original_record_id=row['id'], original_source=row['source'],
                  novel_question_and_target=novel, new_input_format=True,
                  source_passage_supplied=evidence is not None)
    result['id'] = stable_id(result['group_id'] + json.dumps(result['messages'], ensure_ascii=False))[:20]
    return result


def authored():
    # New project-written dialogues; numerical values are explicitly simulated.
    entries = [
        ('greeting', 'Chào Xanh Non, giúp mình một chút nha.', 'Chào bạn! Bạn cần mình hỗ trợ điều gì về môi trường?', [], ['project']),
        ('thanks', 'Mình hiểu rồi, cảm ơn bạn nhiều.', 'Không có gì nhé! Bạn cứ hỏi thêm khi cần.', [], ['project']),
        ('goodbye', 'Mình chào bạn, hẹn lần sau nhé.', 'Hẹn gặp lại bạn nhé!', [], ['project']),
        ('help', 'Bạn hỗ trợ mình những vấn đề môi trường nào?', 'Mình giúp bạn hiểu chỉ số môi trường, đọc dữ liệu được cung cấp và cân nhắc cách giảm tiếp xúc hoặc hoạt động phù hợp.', [], ['project']),
        ('ambiguous', 'Mai ổn hơn không nhỉ?', 'Bạn muốn hỏi thời tiết hay chất lượng không khí ngày mai?',
         history('Mình đang cân nhắc cả khí tượng lẫn mức ô nhiễm không khí.', 'Bạn có thể hỏi riêng từng phần.'), ['project']),
        ('future_weather', 'Nhắc lại riêng phần thời tiết ngày mai nhé.', 'Theo dự báo minh họa bạn đưa, Hà Nội ngày mai 27.4 °C, độ ẩm 66%.',
         history('Ví dụ của mình: dự báo Hà Nội ngày mai 27.4 °C, độ ẩm 66%.', 'Mình sẽ dùng đúng thông tin của ngày mai trong ví dụ.'), ['project']),
        ('future_air', 'Vậy mai không khí sao?', 'Theo giả định ngày mai US AQI 147, mức Kém. Nhóm nhạy cảm nên giảm thời gian và cường độ hoạt động ngoài trời.',
         history('Giả lập ở Hà Nội: US AQI hôm nay 39, ngày mai 147.', 'Mình sẽ giữ riêng hai thời điểm.'), ['project', 'airnow_aqi', 'airnow_particles']),
        ('current_correction', 'Ý mình là xem AQI ở thời điểm hiện tại.', 'Hà Nội hiện có US AQI 47, mức Tốt.',
         history('Mình vừa nêu một dự báo giả định cho ngày mai.', 'Khi bạn hỏi hiện tại, mình cần dùng dữ liệu trên bảng mới.'), ['project', 'airnow_aqi']),
        ('humidity_correction', 'Chỉ đọc số độ ẩm mới giúp mình.', 'Độ ẩm ở Hà Nội hiện là 73%.',
         history('Mình đang xem thời tiết ở địa điểm đã chọn.', 'Bạn cần cả nhiệt độ và độ ẩm không?'), ['project']),
        ('shorten', 'Rút gọn phần PM2.5 vừa nói nhé.', 'PM2.5 là bụi có đường kính thường không quá 2,5 micromet, có thể được hít vào sâu trong phổi.',
         history('Tên PM2.5 chỉ những hạt như thế nào?', 'PM2.5 gồm các hạt bụi có đường kính thường không quá 2,5 micromet và có thể đi sâu vào phổi.'), ['epa_pm']),
        ('why_time', 'Sao bạn cần biết ngày mình định đi?', 'Mình cần chọn số đo hoặc dự báo đúng thời điểm bạn định đi. Bạn dự định đi lúc nào?',
         history('Mình muốn lên kế hoạch đi dạo ngoài trời.', 'Bạn định đi vào ngày nào, khoảng mấy giờ?'), ['project']),
        ('ask_help', 'Mình nên nói rõ những thông tin nào để bạn tư vấn hoạt động?', 'Bạn cho mình biết địa điểm, thời điểm và hoạt động dự định nhé.', [], ['project']),
        ('pm25_precision', 'Hạt PM2.5 có đường kính thường tới mốc nào, không cần đọc nồng độ nhé.', 'PM2.5 thường có đường kính không quá 2,5 micromet và có thể được hít vào sâu trong phổi.', [], ['epa_pm']),
        ('noise_precision', 'Khoảng cách với nguồn âm lớn và thời gian ở đó nên điều chỉnh ra sao?', 'Đứng xa nguồn ồn hơn và giảm thời gian tiếp xúc. Nếu phải ở nơi rất ồn, dùng bảo vệ tai phù hợp.', [], ['nidcd_noise']),
    ]
    for index, (topic, question, answer, turns, sources) in enumerate(entries):
        # The two focused numeric corrections deliberately use known snapshots.
        snap_index = 5 if topic == 'current_correction' else 4 if topic == 'humidity_correction' else index % 8
        row = {'id': f'authored-v12-{topic}', 'source': SOURCE, 'group_id': f'authored-v12:{topic}',
               'topic': topic, 'original_question': question, 'source_ids': sources,
               'snapshot': snapshot_for(snap_index), 'synthetic_context': True,
               'mixture_component': 'expertise' if index >= 12 else 'dialogue',
               'messages': [{'role': 'system', 'content': ''}] + turns + [
                   {'role': 'user', 'content': question}, {'role': 'assistant', 'content': answer}],
               'review': 'project_authored_using_checked_source_facts_and_dialogue_policy'}
        yield row


def records(storage=STORAGE):
    old = storage / 'correction-v10-data-20261021-reviewed'
    partitions = {s: [convert(row) for row in read_rows(old / (s + '.jsonl'))] for s in ('train', 'validation')}
    rehearsal = [row for row in read_rows(storage / 'balanced-v9-data-20261021-reviewed/train.jsonl')
                 if row.get('topic', '').startswith('knowledge_')]
    if len(rehearsal) != 26:
        raise ValueError('Expected all 26 reviewed knowledge rehearsal rows')
    partitions['train'] += [convert(row) for row in rehearsal]
    partitions['train'] += [convert(row, novel=True) for row in authored()]
    return partitions


def prepare(output, extra_cases, storage=STORAGE):
    output, storage = Path(output), Path(storage)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new empty output directory')
    profile_hash, recipe_hash = digest(ROOT / 'chat_briefing.py'), digest(Path(__file__))
    partitions = records(storage)
    cases, case_hash = evaluation_cases(extra_cases)
    deduplication = validate_records(partitions, cases)
    expected = {'expertise': 112, 'dialogue': 48}
    if Counter(r['mixture_component'] for r in partitions['train']) != expected:
        raise ValueError('Unexpected 70/30 training mixture')
    old = json.loads((storage / 'correction-v10-data-20261021-reviewed/manifest.json').read_text(encoding='utf-8'))
    initial = storage / 'capacity-v11-initial-adapter-20261022'
    output.mkdir(parents=True, exist_ok=True)
    for split, rows in partitions.items():
        random.Random(42).shuffle(rows)
        (output / (split + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    manifest = {'schema_version': 1, 'built_at': datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(),
        'require_complete_dialogues': True, 'seed': 42, 'prompt_profile': PROFILE,
        'counts': {s: dict(Counter(r['source'] for r in rows)) for s, rows in partitions.items()},
        'mixture_counts': {s: dict(Counter(r['mixture_component'] for r in rows)) for s, rows in partitions.items()},
        'new_dialogue_counts': {'train': 14, 'validation': 0},
        'reused_question_and_target_counts': {'train': 146, 'validation': 20},
        'required_train_sources': [SOURCE], 'required_train_topics': sorted({r['topic'] for r in partitions['train']}),
        'artifacts_sha256': {s + '.jsonl': digest(output / (s + '.jsonl')) for s in partitions},
        'sources': old['sources'], 'rehearsal_sources': [], 'skipped_sources': [], 'deduplication': deduplication,
        'training_configuration': {'max_length': 768, 'epochs': 1, 'learning_rate': .00003,
            'start_from_active_release': True, 'capacity_adapter': str(initial),
            'capacity_adapter_manifest_sha256': digest(initial / 'expansion-manifest.json')},
        'input_sha256': {'recipe': recipe_hash, 'prompt_profile_recipe': profile_hash,
            'knowledge': digest(ROOT / 'data/xanhnon/knowledge.json'),
            'specialist_cases': digest(ROOT / 'data/xanhnon/specialist_supplement.json'),
            'v10_train': digest(storage / 'correction-v10-data-20261021-reviewed/train.jsonl'),
            'v10_validation': digest(storage / 'correction-v10-data-20261021-reviewed/validation.jsonl'),
            'v9_rehearsal_train': digest(storage / 'balanced-v9-data-20261021-reviewed/train.jsonl')},
        'evaluation_cases_sha256': case_hash, 'model_activated': False,
        'experiment': {'start_from_rejected_v11': False, 'new_input_profile': True,
            'old_knowledge_rehearsal': 26, 'prompt_profile_installed_in_live_app': False,
            'comparison': 'Fresh v2 and candidate evaluations use the same compact evidence profile.'},
        'limitations': ['All 36 existing cases are development regression cases, not unseen confirmation.',
            '14 newly authored records; other questions/targets are transparently reused.',
            'This evaluates source-grounded generation, not unsupported intrinsic model knowledge.',
            'Synthetic and user-supplied examples are not API-verified real forecasts.',
            'Prompt/format, mixture and learning-rate changes form one engineering experiment.',
            'Prototype prompt profile needs runtime integration and answer review before any release.']}
    if profile_hash != digest(ROOT / 'chat_briefing.py') or recipe_hash != digest(Path(__file__)):
        raise RuntimeError('Preparation recipe changed while running')
    save_json(output / 'manifest.json', manifest)
    shutil.copy2(storage / 'correction-v10-data-20261021-reviewed/LICENSE-APACHE-2.0.txt', output / 'LICENSE-APACHE-2.0.txt')
    (output / 'NOTICE.md').write_text('# Grounded v12 pilot\n\nProject-written and previously source-checked examples, plus 14 new project-authored records. '
        'Per-record attribution and original record IDs are retained. All numerical scenarios are synthetic. '
        'The new context format is not a newly collected public dataset. No unreviewed generated answer is used as a target.\n', encoding='utf-8')
    validate_prepared_dataset(output)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extra-cases', type=Path, required=True)
    args = parser.parse_args()
    m = prepare(args.output, args.extra_cases)
    print(json.dumps({k: m[k] for k in ('counts', 'mixture_counts', 'new_dialogue_counts', 'training_configuration')}, ensure_ascii=False))
