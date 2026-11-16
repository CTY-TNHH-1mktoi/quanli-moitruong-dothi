"""v15: source-checked meaning corrections with an explicit evidence profile.

Rebuild all v14 records from their original question/history/snapshot, retain
their checked targets, then add 64 authored training and 16 validation records.
New confirmation scenarios stay outside SFT and are authored before training.
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

from chat_answer_checks import semantic_violations
from chat_briefing import catalog
from chat_briefing_v15 import PROFILE, briefing, compact_messages
from chatbot import _aqi_guidance
from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_correction_data import history, validate_records
from prepare_xanhnon_data import stable_id
from prepare_xanhnon_grounded_data import read_rows
from prepare_xanhnon_runtime_data import snapshot_for
from queue_sensor_training import validate_prepared_dataset
from sensor_training_data import ROOT, digest, save_json

STORAGE = Path('D:/XanhNon-auto-training')
SOURCE = 'environment_meaning_v15'
QUESTIONS = {
 'window_polarity': [
  'Bụi đường còn nhiều, chưa có máy lọc thì nên làm gì với cửa phòng?',
  'Nhà cạnh đường bụi, lúc chưa mua máy lọc nên khép hay mở cửa phía đường?',
  'Nếu chưa có máy lọc, mình hạn chế bụi từ đường vào phòng bằng cách nào?',
  'Phòng sát đường bụi, chưa có thiết bị lọc thì cửa nên xử lý ra sao?',
  'Bụi ngoài đường nhiều, còn cách giảm bụi nào khi chưa trang bị máy lọc?',
  'Mình chưa sắm máy lọc, bụi ngoài đường nhiều thì nên làm gì ngay?',
  'Chưa có máy lọc, cửa phòng sát đường bụi nên đóng bớt hay mở rộng?',
  'Không có máy lọc, mình làm thế nào để bớt bụi đường lọt vào phòng?',
  'Lúc đường nhiều bụi mà chưa có thiết bị lọc, mình nên xử lý cửa thế nào?',
  'Bụi từ đường vào phòng, chưa có máy lọc thì bắt đầu giảm bụi từ đâu?',
 ],
 'pm_humidity': [
  'Nồng độ PM2.5 và AQI có phải là số đo độ ẩm không?',
  'PM2.5 ghi µg/m³, AQI và độ ẩm % khác nhau ở đâu?',
  'Mình nhầm nồng độ PM2.5, AQI với độ ẩm, bạn phân biệt giúp.',
  'Có lấy nồng độ PM2.5 hoặc độ ẩm làm nguyên số AQI được không?',
  'AQI có đồng nghĩa nồng độ PM2.5 và độ ẩm không bạn?',
  'Giải thích riêng nồng độ bụi PM2.5, AQI và độ ẩm, nói gọn nhé.',
  'Nồng độ PM2.5, chỉ số AQI và độ ẩm có dùng chung đơn vị không?',
  'Bụi PM2.5 ghi nồng độ, còn AQI và độ ẩm thì hiểu sao?',
  'PM2.5, độ ẩm và AQI có phải ba cách ghi cùng nồng độ không?',
  'Phân biệt số nồng độ PM2.5 với AQI và phần trăm độ ẩm giúp mình.',
 ],
 'quantity_labels': [
  'Nói rõ nhiệt độ và độ ẩm hiện tại kèm đúng đơn vị nhé.',
  'Nhắc nhiệt độ và độ ẩm ngày mai trong dữ liệu minh họa mình đưa.',
  'Hiện giờ nhiệt độ là bao nhiêu độ C và độ ẩm mấy phần trăm?',
  'Đọc hai đại lượng thời tiết ngày mai đúng tên và đơn vị giúp mình.',
  'Cho mình nhiệt độ và độ ẩm mới nhất, nói rõ mỗi số là gì.',
  'Mai nhiệt độ bao nhiêu và độ ẩm bao nhiêu theo ví dụ đã nêu?',
  'Đọc số nhiệt độ và độ ẩm bây giờ, phân biệt hai đại lượng nha.',
  'Theo minh họa, ngày mai nhiệt độ và độ ẩm lần lượt thế nào?',
  'Nhắc nhiệt độ và độ ẩm hiện tại với đúng tên đại lượng giúp mình.',
  'Đọc lại thời tiết ngày mai trong ví dụ, ghi đúng nhiệt độ và độ ẩm.',
 ],
 'aqi_current_label': [
  'Quay về US AQI Hà Nội hiện tại, con số và mức là gì?',
  'Bỏ số AQI cũ, đọc US AQI Hà Nội lúc này và phân mức giúp mình.',
  'Hà Nội hiện giờ US AQI bao nhiêu, thuộc mức nào?',
  'Nhắc đúng US AQI mới nhất của Hà Nội và tên mức nhé.',
  'Mình muốn số US AQI Hà Nội hiện tại kèm tên mức không khí.',
  'Theo bảng mới, Hà Nội bây giờ US AQI và mức tương ứng là gì?',
  'Dùng US AQI hiện tại của Hà Nội để gọi đúng mức giúp mình.',
  'Đọc US AQI Hà Nội đang cập nhật, kèm phân loại chất lượng.',
  'Hà Nội hiện tại có US AQI và tên mức tương ứng thế nào?',
  'Bỏ ví dụ trước, dùng đúng US AQI Hà Nội hiện giờ để phân mức.',
 ],
 'source_fidelity': [
  'EPA là viết tắt tên tổ chức nào vậy?',
  'Vậy PM2.5 có thể xuống sâu trong phổi được chứ?',
  'Tên đầy đủ của EPA là gì?',
  'Bụi ấy có thể theo hơi hít vào sâu trong phổi chứ?',
  'EPA là cơ quan nào, cho mình tên chính xác nhé.',
  'Thế PM2.5 có thể đi sâu trong phổi không bạn?',
  'Tên tổ chức EPA viết đầy đủ như thế nào nhỉ?',
  'Vậy hạt bụi đó có tới sâu trong phổi khi hít vào không?',
  'EPA là tên viết tắt của cơ quan nào?',
  'Vậy bụi PM2.5 có thể được hít vào sâu trong phổi phải không?',
 ],
 'direct_time_question': [
  'Bạn tư vấn giúp mình lên kế hoạch tập thể dục ngoài trời nhé.',
  'Mình muốn đi dạo ngoài công viên, bạn tư vấn cho mình với.',
  'Nhờ bạn tư vấn điều kiện để chạy bộ ngoài trời.',
  'Mình định đi bộ ngoài trời, bạn giúp cân nhắc điều kiện nhé.',
  'Mình cần lời tư vấn trước một buổi chạy bộ ngoài công viên.',
  'Bạn giúp mình chuẩn bị kế hoạch vận động ngoài trời nha.',
  'Tư vấn giúp một buổi đi dạo ngoài trời cho mình.',
  'Cần bạn tư vấn kế hoạch tập thể dục tại công viên.',
  'Mình định lên kế hoạch chạy bộ ngoài trời, bạn tư vấn được chứ?',
  'Bạn giúp mình cân nhắc điều kiện cho buổi đi bộ ngoài trời nha.',
 ],
 'explain_time_question': [
  'Vì sao bạn hỏi ngày mình đi vậy?', 'Bạn hỏi giờ đi để làm gì thế?',
  'Ý là sao, tại sao cần biết ngày giờ mình tập?', 'Hỏi thời điểm như vậy để làm gì nhỉ?',
  'Vì sao việc tư vấn cần biết lúc mình ra ngoài?', 'Bạn hỏi ngày đi có liên quan gì vậy?',
  'Tại sao phải hỏi thời gian mình dự định tập?', 'Ý là sao, hỏi giờ mình đi để làm gì?',
  'Vì sao bạn cần mình nói rõ thời điểm sẽ đi?', 'Bạn hỏi ngày giờ để làm gì vậy bạn?',
 ],
 'future_air_consultation': [
  'Theo giả định ở trên, mai đi dạo nên điều chỉnh hoạt động thế nào?',
  'Mai tập ngoài trời thì lưu ý gì theo US AQI giả lập đó?',
  'Tư vấn buổi đi bộ ngày mai theo ví dụ chất lượng không khí vừa đưa.',
  'Với AQI giả định ấy, mai hoạt động ngoài trời nên thay đổi gì?',
  'Mình chạy bộ ngày mai, tư vấn theo số giả lập trên giúp nhé.',
  'Ngày mai nếu AQI đúng như ví dụ, buổi tập nên điều chỉnh ra sao?',
  'Dựa vào mức AQI giả định hôm sau, nên đi dạo ngoài trời thế nào?',
  'Nhắc US AQI và tư vấn vận động ngày mai theo giả định vừa nêu.',
  'Theo giá trị US AQI giả định ngày mai, buổi đi dạo nên điều chỉnh gì?',
  'Vậy mai tập thể dục ngoài trời thế nào theo giả lập không khí của mình?',
 ],
}


def new_records():
    result = {'train': [], 'validation': []}
    for topic, questions in QUESTIONS.items():
        for index, question in enumerate(questions):
            snap, turns, sources = snapshot_for(index % 8), [], ['project']
            if topic == 'window_polarity':
                room = ['Phòng trọ mình ở cạnh đường lớn nên hay có bụi vào.',
                        'Nhà mình gần con đường xe tải thường xuyên chạy qua.',
                        'Căn phòng của mình sát mặt đường khá nhiều bụi.',
                        'Mình ở phòng tầng thấp cạnh một tuyến đường nhiều xe.',
                        'Nhà bên đường nên mình muốn bớt bụi vào phòng.',
                        'Mình đang tìm cách giảm bụi đường trong phòng ở.',
                        'Phòng mình nhìn ra đường đông xe và hay có bụi.',
                        'Mình ở gần đường xe chạy và thường thấy bụi trong nhà.',
                        'Căn phòng của mình cạnh đoạn đường có nhiều xe qua lại.',
                        'Nhà mình ở sát đường nên thường có bụi lọt vào.'][index]
                thanks = ['Cảm ơn phần đầu nha.', 'Mình đã hiểu, lời tư vấn hữu ích.',
                          'Mình hiểu rồi, cảm ơn bạn nha.', 'Cảm ơn, mình đã rõ cách bắt đầu.',
                          'Ừ được, mình nắm được rồi.', 'Thông tin vừa rồi hữu ích, cảm ơn.',
                          'Cảm ơn, bạn nói vậy mình hiểu rồi.', 'Ừm, mình đã rõ phần đầu rồi.',
                          'Cảm ơn, bạn đã giải thích rõ bước đầu.', 'Mình nắm được các việc ban đầu rồi, cảm ơn.'][index]
                turns = history(room,
                                'Có thể giảm nguồn bụi và dùng thiết bị lọc nếu có.',
                                thanks, 'Bạn cứ hỏi tiếp nhé.')
                answer = 'Khép cửa phía đường khi ngoài trời nhiều bụi, lau bụi bằng khăn ẩm và tránh khói thuốc trong nhà. Chọn lúc không khí ngoài trời sạch hơn để thông gió.'
                sources = ['epa_indoor_pm', 'epa_air_cleaners']
            elif topic == 'pm_humidity':
                answer = 'PM2.5 là bụi mịn; µg/m³ đo nồng độ bụi. AQI là chỉ số quy đổi; độ ẩm dùng %, là đại lượng khác. Không lấy nguyên số nồng độ PM2.5 làm AQI.'
                sources = ['epa_pm', 'airnow_aqi', 'project']
            elif topic == 'quantity_labels':
                temperature, humidity = round(13.8 + index * 1.3, 1), 45 + index * 4
                if index % 2:
                    turns = history(f'Ví dụ thời tiết Hà Nội: hôm nay 34.8 °C, độ ẩm 91%; ngày mai {temperature} °C, độ ẩm {humidity}%.',
                                    'Đây là ví dụ số liệu bạn cung cấp, chưa xác minh bên ngoài.')
                    answer = f'Theo minh họa bạn đưa, ngày mai nhiệt độ {temperature} °C, độ ẩm {humidity}%.'
                else:
                    snap['DuLieu'].update(NhietDo=temperature, DoAm=humidity)
                    answer = f'Hà Nội hiện có nhiệt độ {temperature} °C, độ ẩm {humidity}%.'
            elif topic == 'aqi_current_label':
                value = [55, 104, 169, 224, 323, 42, 184, 139, 197, 77][index]
                snap['DuLieu']['US_AQI'] = value
                turns = history(f'Ở tình huống trước mình dùng số US AQI cũ là {7+index*10}.', 'Đó là số cũ, cần đọc dữ liệu hiện tại khi bạn hỏi lại.')
                level, _ = _aqi_guidance(value)
                answer = f'Hà Nội hiện có US AQI {value}, mức {level}.'
                sources += ['airnow_aqi']
            elif topic == 'source_fidelity':
                if index % 2 == 0:
                    answer = 'EPA là US Environmental Protection Agency, tức Cơ quan Bảo vệ Môi trường Hoa Kỳ.'
                    sources = ['epa_about']
                else:
                    prior = ['Giải thích một chút về đường kính PM2.5 nhé.',
                             'Mình muốn hiểu nhóm hạt bụi PM2.5 nhỏ như thế nào.',
                             'Bạn nói ngắn về kích thước của bụi PM2.5 nhé.',
                             'Nhắc khái niệm hạt bụi PM2.5 giúp mình với.',
                             'Cho mình hiểu rõ thế nào là hạt PM2.5 nhé.'][index // 2]
                    turns = history(prior, 'PM2.5 là bụi có đường kính thường không quá 2,5 micromet.')
                    answer = 'Có. PM2.5 rất nhỏ nên có thể được hít vào sâu trong phổi.'
                    sources = ['epa_pm']
            elif topic == 'direct_time_question':
                answer = 'Bạn định đi vào ngày nào, khoảng mấy giờ?'
            elif topic == 'explain_time_question':
                turns = history(QUESTIONS['direct_time_question'][index], 'Bạn định đi vào ngày nào, khoảng mấy giờ?')
                answer = 'Mình hỏi để dùng số đo hoặc dự báo đúng thời điểm bạn định đi. Bạn dự định đi vào lúc nào?'
            elif topic == 'future_air_consultation':
                value = [56, 116, 176, 218, 264, 307, 142, 199, 229, 164][index]
                turns = history(f'Giả định Hà Nội: hôm nay US AQI 33, ngày mai US AQI {value}.', 'Mình hiểu đây là giả định của bạn, không phải dự báo xác minh.')
                level, advice = _aqi_guidance(value)
                answer = f'Theo giả định của bạn, ngày mai US AQI {value}, mức {level}. {advice}'
                sources += ['airnow_aqi', 'airnow_particles']
            else:
                raise ValueError(topic)
            group = f'{SOURCE}:new:{topic}:{index}'
            messages = compact_messages(question, turns, snap) + [{'role': 'assistant', 'content': answer}]
            row = {'id': stable_id(group + json.dumps(messages, ensure_ascii=False))[:20],
                   'source': SOURCE, 'group_id': group, 'topic': topic,
                   'original_question': question, 'messages': messages, 'snapshot': snap,
                   'source_ids': sources, 'synthetic_context': True,
                   'supervise_last_assistant_only': True, 'prompt_profile': PROFILE,
                   'mixture_component': 'dialogue' if topic in {'direct_time_question', 'explain_time_question'} else 'expertise',
                   'novel_in_v15': True, 'review': 'project_authored_primary_source_paraphrases_and_project_dialogue_policy'}
            result['validation' if index >= 8 else 'train'].append(row)
    return result


def convert(row):
    result = deepcopy(row)
    turns, supplied = row['messages'][1:-2], None
    if row['topic'].startswith('knowledge_'):
        doc = catalog()[0][row['topic'].removeprefix('knowledge_')]
        passage = doc['answer']
        if doc['id'] == 'pm25_definition':
            passage = 'PM2.5 thường không quá 2,5 micromet; có thể được hít vào sâu trong phổi.'
        supplied = {'nhiem_vu': 'giải thích theo tài liệu được cung cấp', 'chung_cu': {'tai_lieu': passage}, 'source_ids': doc['source_ids']}
    messages = compact_messages(row['original_question'], turns, row['snapshot'], supplied_evidence=supplied) + [row['messages'][-1]]
    result.update(messages=messages, source=SOURCE, original_source=row['source'],
                  parent_record_id=row['id'], group_id=SOURCE + ':replay:' + row['group_id'],
                  prompt_profile=PROFILE, novel_in_v15=False)
    result['id'] = stable_id(result['group_id'] + json.dumps(messages, ensure_ascii=False))[:20]
    return result


def records(storage=STORAGE):
    parent = Path(storage) / 'rehearsal-v14-data-20261022-reviewed'
    result = new_records()
    for split in result:
        result[split] = [convert(r) for r in read_rows(parent / (split + '.jsonl'))] + result[split]
    if len(result['train']) != 336 or len(result['validation']) != 55:
        raise ValueError('Unexpected batch size')
    return result


def audit(partitions):
    for rows in partitions.values():
        for row in rows:
            target = row['messages'][-1]['content']
            if semantic_violations(target):
                raise ValueError('Target contradicts factual checks: ' + row['id'] + str(semantic_violations(target)))
            if len(target.split()) > 85:
                raise ValueError('Overlong target')
            if row.get('novel_in_v15'):
                evidence = briefing(row['original_question'], row['messages'][1:-2], row['snapshot'])
                if evidence['nhiem_vu'] == 'hỏi rõ thông tin cần thiết':
                    raise ValueError('Unrecognized teacher task: ' + row['original_question'])
                if row['topic'] in {'aqi_current_label', 'future_air_consultation'}:
                    if str(int(evidence['chung_cu']['US_AQI'])) not in target or evidence['chung_cu']['muc'] not in target:
                        raise ValueError('AQI target disagrees with evidence')
                if row['topic'] == 'quantity_labels':
                    for key in ('NhietDo', 'DoAm'):
                        value = evidence['chung_cu'][key]
                        if str(value) not in target and str(int(value)) not in target:
                            raise ValueError('Weather target disagrees with evidence')


def prepare(output, extra_cases, storage=STORAGE):
    output, storage = Path(output), Path(storage)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new empty output directory')
    recipe = digest(Path(__file__))
    partitions = records(storage)
    audit(partitions)
    cases, case_hash = evaluation_cases(extra_cases)
    deduplication = validate_records(partitions, cases)
    parent = storage / 'rehearsal-v14-data-20261022-reviewed'
    previous = json.loads((parent / 'manifest.json').read_text(encoding='utf-8'))
    sources = deepcopy(previous['sources']) + [{'id': 'epa_about', 'title': 'US EPA — About EPA', 'url': 'https://www.epa.gov/aboutepa', 'type': 'official'}]
    known = {s['id'] for s in sources}
    if any(not set(r['source_ids']) <= known for rows in partitions.values() for r in rows):
        raise ValueError('Unknown source attribution')
    output.mkdir(parents=True, exist_ok=True)
    for split, rows in partitions.items():
        random.Random(45).shuffle(rows)
        (output / (split + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    manifest = {'schema_version': 1, 'built_at': datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(),
        'require_complete_dialogues': True, 'seed': 45, 'prompt_profile': PROFILE,
        'counts': {s: dict(Counter(r['source'] for r in rows)) for s, rows in partitions.items()},
        'mixture_counts': {s: dict(Counter(r['mixture_component'] for r in rows)) for s, rows in partitions.items()},
        'new_dialogue_counts': {'train': 64, 'validation': 16},
        'reused_question_and_target_counts': {'train': 272, 'validation': 39},
        'required_train_sources': [SOURCE], 'required_train_topics': sorted({r['topic'] for r in partitions['train']}),
        'artifacts_sha256': {s + '.jsonl': digest(output / (s + '.jsonl')) for s in partitions},
        'sources': sources, 'rehearsal_sources': [], 'skipped_sources': [], 'deduplication': deduplication,
        'training_configuration': previous['training_configuration'],
        'input_sha256': {'recipe': recipe, 'prompt_profile_recipe': digest(ROOT / 'chat_briefing_v15.py'),
                         'base_prompt_profile_recipe': digest(ROOT / 'chat_briefing.py'),
                         'semantic_checks': digest(ROOT / 'chat_answer_checks.py'),
                         'knowledge': digest(ROOT / 'data/xanhnon/knowledge.json'),
                         'specialist_cases': digest(ROOT / 'data/xanhnon/specialist_supplement.json'),
                         'previous_manifest': digest(parent / 'manifest.json'),
                         'previous_train': digest(parent / 'train.jsonl'), 'previous_validation': digest(parent / 'validation.jsonl')},
        'evaluation_cases_sha256': case_hash, 'model_activated': False, 'planned_optimizer_steps': 168,
        'experiment': {'name': 'meaning-v15', 'starts_from_active_v2': True, 'continues_rejected_v14': False,
                       'unique_training_rows': 336, 'training_presentations': 672,
                       'prompt_profile_installed_in_live_app': False},
        'review': {'primary_sources_rechecked_at': '2026-10-22', 'project_authored_targets': True, 'independent_expert_certification': False},
        'limitations': ['272 earlier targets reused with a new evidence profile, plus 64 new authored training targets.',
                       'Two epochs repeat records, not 672 unique samples.',
                       'Known 36 generation cases informed corrections. Twelve new scenarios are outside SFT but are not an independent external benchmark.',
                       'All numeric readings and user-provided forecasts are synthetic.',
                       'Data and evidence-profile changes form one engineering experiment; no single-cause claim.',
                       'Automatic checks cannot replace manual factual and naturalness review before release.']}
    if recipe != digest(Path(__file__)):
        raise RuntimeError('Recipe changed while preparing data')
    save_json(output / 'manifest.json', manifest)
    shutil.copy2(parent / 'LICENSE-APACHE-2.0.txt', output / 'LICENSE-APACHE-2.0.txt')
    (output / 'NOTICE.md').write_text('# Meaning v15\n\n272 earlier training targets plus 64 new project-authored targets. '
        '39 earlier and 16 new validation targets. Evidence is source-checked and paraphrased; attribution is retained per record. '
        'All readings and forecast examples are simulated. No rejected answer is used as a target.\n', encoding='utf-8')
    validate_prepared_dataset(output)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extra-cases', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output, args.extra_cases)
    print(json.dumps({k: result[k] for k in ('counts', 'new_dialogue_counts', 'planned_optimizer_steps')}, ensure_ascii=False))
