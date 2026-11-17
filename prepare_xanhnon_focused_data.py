"""Source-checked corrective dialogue after v12; no rejected answers are targets.

Keep all earlier topic families through 80 rehearsal rows, add 80 new authored
rows, and leave the 36 known development cases outside SFT. The compact input
profile and active-v2 initialization stay the same to isolate the data change.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import random
import shutil
from zoneinfo import ZoneInfo

from chat_briefing import PROFILE, briefing, compact_messages
from chatbot import _aqi_guidance
from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_correction_data import history, validate_records
from prepare_xanhnon_data import stable_id
from prepare_xanhnon_grounded_data import read_rows
from prepare_xanhnon_runtime_data import snapshot_for
from queue_sensor_training import validate_prepared_dataset
from sensor_training_data import ROOT, digest, save_json

STORAGE = Path('D:/XanhNon-auto-training')
SOURCE = 'environment_focused_v13'
QUESTIONS = {
    'pm_size': [
        'Đường kính PM2.5 có phải từ 2,5 micromet tới 10 micromet không?',
        'Mốc 2,5 trong PM2.5 là giới hạn trên hay giới hạn dưới của kích thước?',
        'Mình hiểu đường kính PM2.5 lớn hơn 2,5 micromet, hiểu vậy đúng chưa?',
        'Tóm tắt đường kính của bụi PM2.5 và khả năng vào phổi giúp mình.',
        'PM2.5 có bao gồm những hạt nhỏ hơn 2,5 micromet chứ?',
        'Có nên gọi hạt đường kính 2,5 đến 10 micromet là PM2.5 không?',
        'PM2.5 kích thước tối đa thường là mấy micromet nhỉ?',
        'Chỉ nói về kích thước PM2.5 thôi, hạt đó có xuống sâu trong phổi được không?',
        'Giới hạn đường kính của PM2.5 là 2,5 micromet hay 10 micromet vậy?',
    ],
    'lung_followup': [
        'Vậy nó có tới sâu trong phổi được thật không?',
        'Hạt nhỏ ấy có thể theo hơi thở vào sâu trong phổi chứ?',
        'Ý bạn là nó vào sâu trong phổi được à?',
        'Thế nó có thể đi sâu vào đường hô hấp và phổi không?',
        'Nó có chỉ mắc ở ngoài mũi và không vào phổi không?',
        'Vậy với hạt đó, phổi có thể bị tiếp xúc không?',
        'Cụ thể bụi ấy có lọt sâu vào phổi được không nhỉ?',
        'Bụi đó nhỏ thế thì có thể hít xuống phổi chứ?',
        'Vậy mình có thể hít những hạt đó vào tận phổi không?',
    ],
    'humidity_only': [
        'Mình cần riêng phần trăm độ ẩm bây giờ nhé.',
        'Không cần nhiệt độ, chỉ đọc độ ẩm mới nhất.',
        'Ý mình chỉ là độ ẩm đang cập nhật bằng bao nhiêu phần trăm?',
        'Cho mình con số độ ẩm hiện tại thôi nha.',
        'Bỏ qua nhiệt độ nhé, nói mỗi độ ẩm hiện giờ.',
        'Bạn đọc giúp độ ẩm trên bảng, chỉ số ấy thôi.',
        'Chỉ cho mình biết độ ẩm lúc này là mấy phần trăm.',
        'Mình hỏi lại: riêng độ ẩm Hà Nội hiện giờ bao nhiêu?',
        'Nói gọn số độ ẩm hiện tại ở địa điểm đang chọn giúp mình.',
    ],
    'forecast_weather': [
        'Mai phần thời tiết trong ví dụ của mình ra sao nhỉ?',
        'Đọc thời tiết ngày mai theo dữ liệu minh họa vừa nêu.',
        'Vậy nhiệt độ và độ ẩm hôm sau trong bản đó thế nào?',
        'Mình hỏi ngày mai, tóm tắt thời tiết từ ví dụ trên nhé.',
        'Lấy đúng hai số nhiệt độ và độ ẩm ngày mai giúp mình.',
        'Chuyển sang thời tiết hôm sau trong dự báo minh họa nha.',
        'Phần thời tiết ngày mai ấy, bạn nhắc lại ngắn gọn được chứ?',
        'Tóm tắt giúp thời tiết ngày mai mà mình vừa cung cấp.',
        'Nhắc số nhiệt độ và độ ẩm của ngày mai trong ví dụ nhé.',
    ],
    'forecast_air': [
        'Mai đi bộ thì nên điều chỉnh ra sao theo giả định vừa nêu?',
        'Theo ví dụ đó, không khí ngày mai thuộc mức gì?',
        'Dựa vào AQI hôm sau trong ví dụ, tư vấn hoạt động ngoài trời nhé.',
        'Mai mình ra công viên thì lưu ý gì theo giả định ấy?',
        'Bạn tư vấn buổi tập ngày mai theo con số giả lập ở trên.',
        'Ngày mai nếu không khí đúng như ví dụ, việc đi dạo nên thế nào?',
        'Vậy theo AQI ngày mai mình nêu, nên vận động thế nào?',
        'Chốt phần chất lượng không khí ngày mai theo giả định giúp mình.',
        'Theo US AQI giả lập hôm sau, hoạt động ngoài trời cần lưu ý gì?',
    ],
    'ask_time': [
        'Mình muốn bạn tư vấn kế hoạch đi dạo ngoài trời.',
        'Giúp mình chọn thời điểm phù hợp để chạy bộ nhé.',
        'Tư vấn một buổi vận động ngoài trời cho mình với.',
        'Mình dự định tập ở công viên, nên cân nhắc gì trước?',
        'Bạn giúp mình lên kế hoạch buổi đi bộ được chứ?',
        'Mình muốn ra ngoài tập thể dục, tư vấn giúp nha.',
        'Mình đang tính một buổi chạy bộ ngoài trời, nhờ bạn tư vấn.',
        'Cần tư vấn về điều kiện để đi dạo ngoài công viên.',
        'Giúp mình cân nhắc một buổi tập thể dục ngoài trời.',
    ],
    'ambiguous_time': [
        'Vậy mai sẽ như thế nào nhỉ?', 'Thế sang hôm sau có khác không?',
        'Còn ngày mai thì có ổn không bạn?', 'Bạn nói thêm ngày kế tiếp giúp mình.',
        'Mai vậy có nên lo gì không?', 'Nhìn sang ngày mai thì sao nhỉ?',
        'Còn phần ngày mai, nói rõ thêm được chứ?', 'Tư vấn tiếp cho ngày mai nha.',
        'Nếu chuyển qua hôm sau thì thế nào bạn nhỉ?',
    ],
    'greeting': [
        'Alo Xanh Non ơi, cho mình hỏi chút nha.',
        'Chào bạn, mình có thể hỏi một chuyện không?',
        'Hello Xanh Non, giúp mình một chút nhé!',
        'Chào trợ lý, bạn nghe mình hỏi được không?',
        'Hi bạn, mình nhờ tư vấn một chút được chứ?',
        'Xanh Non ơi, chào bạn nha!', 'Chào Xanh Non, mình hỏi nhờ tí nhé.',
        'A lô bạn ơi, mình có câu hỏi đây.', 'Chào bạn, mình muốn trao đổi một chút nha.',
    ],
    'missing_aqi': [
        'Hôm nay không khí như vậy có phù hợp để đi dạo chưa?',
        'Xem giúp mình không khí hiện tại có ổn để tập ở công viên không.',
        'Theo dữ liệu bây giờ, mình chạy bộ ngoài trời có được không?',
        'AQI hiện tại chưa có thì có thể kết luận không khí tốt không?',
        'Bảng đang thiếu AQI, hôm nay mình có nên tập ngoài trời?',
        'Nếu AQI bị trống, có lấy số PM2.5 để nói không khí tốt được không?',
        'Mình định đi bộ hôm nay, dữ liệu không khí hiện tại đủ để tư vấn chưa?',
        'Hôm nay có đủ thông tin không khí để khuyên mình đi tập không?',
        'Không thấy AQI hiện tại thì đánh giá hoạt động ngoài trời thế nào?',
    ],
    'ozone': [
        'Máy tạo ozone đang bật trong phòng có người, có nên tiếp tục không?',
        'Có người sinh hoạt trong phòng thì thiết bị phát O3 có phù hợp không?',
        'Dùng máy cố ý tạo ozone lúc cả nhà vẫn trong phòng có nên không?',
        'Để khử mùi phòng khi đang có người, bật máy tạo ozone được chứ?',
        'Khi mình vẫn ngồi trong phòng, có nên chạy thiết bị phát ozone?',
    ],
    'noise': [
        'Đứng gần loa rất to lâu hơn để tai quen tiếng ồn có nên không?',
        'Kéo dài thời gian nghe nhạc lớn có giúp bảo vệ tai không?',
        'Để quen tiếng ồn công trường, mình có nên ở đó lâu hơn không?',
        'Nếu đứng xa nguồn ồn rồi thì có nên tăng thời gian tiếp xúc không?',
        'Nghe âm thanh lớn lâu để luyện tai là tốt hay nên giảm thời gian?',
    ],
}


def authored_records():
    partitions = {'train': [], 'validation': []}
    for topic, questions in QUESTIONS.items():
        for index, question in enumerate(questions):
            turns, sources = [], ['project']
            snap = snapshot_for(index % 8)
            if topic in {'pm_size', 'lung_followup'}:
                sources = ['epa_pm']
                if topic == 'lung_followup':
                    turns = history('Giải thích giúp mình hạt bụi mang tên PM2.5 nhé.' if index < 8 else 'Bạn giải thích nhanh khái niệm bụi PM2.5 nhé.',
                                    'PM2.5 là bụi có đường kính thường không quá 2,5 micromet.')
                    answer = ('Không. ' if index == 4 else 'Có. ') + 'PM2.5 rất nhỏ nên có thể được hít vào sâu trong phổi.'
                else:
                    answer = 'PM2.5 có đường kính thường không quá 2,5 micromet và có thể được hít vào sâu trong phổi.'
            elif topic == 'humidity_only':
                value = 42 + index * 6
                snap['DuLieu']['DoAm'] = value
                turns = history('Mình đang xem các chỉ số thời tiết ở Hà Nội.' if index < 8 else 'Mình đang mở bảng theo dõi thời tiết của địa điểm đã chọn.',
                                'Bạn cần mình đọc cả nhiệt độ và độ ẩm chứ?')
                answer = f'Độ ẩm Hà Nội hiện là {value}%.'
            elif topic == 'forecast_weather':
                temperature, humidity = round(22.3 + index * .8, 1), 54 + index * 3
                turns = history(f'Ví dụ dự báo Hà Nội: hôm nay 31.1 °C, độ ẩm 88%; ngày mai {temperature} °C, độ ẩm {humidity}%.',
                                'Mình sẽ giữ riêng thông tin của từng ngày trong ví dụ.')
                answer = f'Theo dự báo minh họa bạn đưa, Hà Nội ngày mai {temperature} °C, độ ẩm {humidity}%.'
            elif topic == 'forecast_air':
                value = [46, 83, 128, 167, 209, 265, 316, 194, 144][index]
                level, advice = _aqi_guidance(value)
                sources += ['airnow_aqi', 'airnow_particles']
                turns = history(f'Tình huống giả lập ở Hà Nội: hôm nay US AQI 37, ngày mai US AQI {value}.',
                                'Mình hiểu đây là giả định, không phải dự báo đã được kiểm chứng.')
                answer = f'Theo giả định của bạn, ngày mai US AQI {value}, mức {level}. {advice}'
            elif topic == 'ask_time':
                answer = 'Bạn định đi vào ngày nào, khoảng mấy giờ?'
            elif topic == 'ambiguous_time':
                turns = history('Mình đang quan tâm đồng thời cả thời tiết lẫn AQI quanh khu vực.' if index < 8 else 'Mình đang xem đồng thời cả thời tiết và US AQI ở khu vực này.',
                                'Mình có thể hỗ trợ bạn đọc từng nhóm thông tin.')
                answer = 'Bạn muốn hỏi thời tiết hay chất lượng không khí ngày mai?'
            elif topic == 'greeting':
                answer = ['Chào bạn! Mình đây, bạn muốn hỏi điều gì?',
                          'Được chứ, mình là Xanh Non. Bạn cần mình hỗ trợ gì?',
                          'Chào bạn, mình sẵn sàng nghe bạn hỏi nhé!'][index % 3]
            elif topic == 'missing_aqi':
                snap['DuLieu'].update(US_AQI=None, PM25=2 + index)
                sources += ['airnow_aqi']
                answer = 'Mình chưa có US AQI hiện tại nên chưa đủ dữ liệu để đánh giá không khí cho buổi tập. Không lấy nguyên số PM2.5 thay cho AQI.'
            elif topic == 'ozone':
                sources = ['epa_air_cleaners']
                answer = 'Không nên dùng thiết bị cố ý tạo ozone khi có người trong phòng, vì ozone có thể kích ứng phổi.'
            elif topic == 'noise':
                sources = ['nidcd_noise']
                answer = 'Không. Hãy giảm thời gian tiếp xúc với tiếng ồn, đứng xa nguồn âm và dùng bảo vệ tai phù hợp khi cần; không nghe lâu hơn để quen tai.'
            else:
                raise ValueError(topic)
            group = f'{SOURCE}:{topic}:{index}'
            messages = compact_messages(question, turns, snap) + [{'role': 'assistant', 'content': answer}]
            row = {'id': stable_id(group + json.dumps(messages, ensure_ascii=False))[:20],
                   'source': SOURCE, 'group_id': group, 'topic': topic,
                   'original_question': question, 'messages': messages, 'snapshot': snap,
                   'source_ids': sources, 'synthetic_context': True,
                   'mixture_component': 'dialogue' if topic in {'ask_time', 'ambiguous_time', 'greeting', 'humidity_only'} else 'expertise',
                   'supervise_last_assistant_only': True, 'prompt_profile': PROFILE,
                   'novel_question_and_target': True,
                   'review': 'project_authored_paraphrases_of_primary_sources; not model-generated targets'}
            partitions['validation' if index == len(questions)-1 else 'train'].append(row)
    return partitions


def records(storage=STORAGE):
    parent = Path(storage) / 'grounded-v12-data-20261022-reviewed'
    previous = read_rows(parent / 'train.jsonl')
    grouped = defaultdict(list)
    rehearsal = []
    for row in previous:
        if row['topic'].startswith('knowledge_') or row.get('novel_question_and_target'):
            rehearsal.append(deepcopy(row))
        else:
            grouped[row['topic']].append(row)
    if len(rehearsal) != 40 or len(grouped) != 20:
        raise ValueError('Earlier reviewed batch layout changed')
    for topic in sorted(grouped):
        rehearsal.extend(deepcopy(sorted(grouped[topic], key=lambda r: r['id'])[:2]))
    result = authored_records()
    result['train'] = rehearsal + result['train']
    result['validation'] = read_rows(parent / 'validation.jsonl') + result['validation']
    if len(result['train']) != 160 or len(result['validation']) != 31:
        raise ValueError('Unexpected focused-batch size')
    if not {r['topic'] for r in previous} <= {r['topic'] for r in result['train']}:
        raise ValueError('An earlier topic family lost all rehearsal')
    return result


def prepare(output, extra_cases, storage=STORAGE):
    output, storage = Path(output), Path(storage)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new empty directory')
    recipe_hash, profile_hash = digest(Path(__file__)), digest(ROOT / 'chat_briefing.py')
    partitions = records(storage)
    cases, case_hash = evaluation_cases(extra_cases)
    deduplication = validate_records(partitions, cases)
    parent = storage / 'grounded-v12-data-20261022-reviewed'
    original = json.loads((parent / 'manifest.json').read_text(encoding='utf-8'))
    known_sources = {s['id'] for s in original['sources']}
    for rows in partitions.values():
        for row in rows:
            if not set(row['source_ids']) <= known_sources:
                raise ValueError('Unknown source attribution')
            if row['messages'][-1]['role'] != 'assistant':
                raise ValueError('Missing supervised answer')
            if len(row['messages'][-1]['content'].split()) > 85:
                raise ValueError('Training answer exceeds the answer-length budget')
            task = briefing(row['original_question'], row['messages'][1:-2], row['snapshot'])
            if row['source'] == SOURCE and task['nhiem_vu'] == 'hỏi rõ thông tin cần thiết':
                raise ValueError('New teacher answer conflicts with an unknown task: ' + row['original_question'])
    output.mkdir(parents=True, exist_ok=True)
    for split, rows in partitions.items():
        random.Random(43).shuffle(rows)
        (output / (split + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    if digest(Path(__file__)) != recipe_hash or digest(ROOT / 'chat_briefing.py') != profile_hash:
        raise RuntimeError('Recipe changed while preparing the batch')
    manifest = {'schema_version': 1, 'built_at': datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(),
        'require_complete_dialogues': True, 'seed': 43, 'prompt_profile': PROFILE,
        'counts': {s: dict(Counter(r['source'] for r in rows)) for s, rows in partitions.items()},
        'mixture_counts': {s: dict(Counter(r['mixture_component'] for r in rows)) for s, rows in partitions.items()},
        'new_dialogue_counts': {'train': 80, 'validation': 11},
        'reused_question_and_target_counts': {'train': 80, 'validation': 20},
        'required_train_sources': ['environment_grounded_v12', SOURCE],
        'required_train_topics': sorted({r['topic'] for r in partitions['train']}),
        'artifacts_sha256': {s + '.jsonl': digest(output / (s + '.jsonl')) for s in partitions},
        'sources': original['sources'], 'rehearsal_sources': [], 'skipped_sources': [],
        'deduplication': deduplication, 'training_configuration': original['training_configuration'],
        'input_sha256': {'recipe': recipe_hash, 'prompt_profile_recipe': profile_hash,
                        'previous_manifest': digest(parent / 'manifest.json'),
                        'previous_train': digest(parent / 'train.jsonl'),
                        'previous_validation': digest(parent / 'validation.jsonl')},
        'evaluation_cases_sha256': case_hash, 'model_activated': False,
        'experiment': {'name': 'focused-v13', 'starts_from_active_v2': True,
                       'continues_rejected_v12': False, 'same_prompt_profile_and_learning_rate_as_v12': True,
                       'all_previous_topic_families_rehearsed': True},
        'review': {'sources_rechecked_at': '2026-10-22', 'new_targets_project_authored': True,
                   'independent_expert_certification': False},
        'limitations': ['Small targeted correction experiment; not a newly downloaded public dataset.',
                       'All 36 known evaluation cases are development cases and informed the topic selection.',
                       'Source-checked targets do not guarantee factual generated answers.',
                       'Numeric scenarios and future forecasts are synthetic, not actual live predictions.',
                       'An experimental prompt profile needs application integration and manual answer review before release.']}
    save_json(output / 'manifest.json', manifest)
    shutil.copy2(parent / 'LICENSE-APACHE-2.0.txt', output / 'LICENSE-APACHE-2.0.txt')
    (output / 'NOTICE.md').write_text('# Focused v13\n\n80 reused training rows and 80 newly project-authored training rows; '
        '20 reused and 11 new validation rows. Primary-source attribution is retained per record. '
        'All numerical scenarios are simulated. No rejected model answer is used as a target.\n', encoding='utf-8')
    validate_prepared_dataset(output)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extra-cases', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output, args.extra_cases)
    print(json.dumps({k: result[k] for k in ('counts', 'new_dialogue_counts', 'mixture_counts')}, ensure_ascii=False))
