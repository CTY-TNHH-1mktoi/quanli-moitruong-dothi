"""Prepare a bounded, source-traced batch for contextual Vietnamese conversation.

All readings and forecasts are explicit simulations. No production chat or model
answer is used as a factual target, and the fixed answer evaluation stays separate.
"""

import argparse
from collections import Counter
import json
from pathlib import Path

import chatbot
from prepare_xanhnon_consultation_data import consultation_records
from prepare_xanhnon_data import make_record
from prepare_xanhnon_review_data import prepare
from prepare_xanhnon_runtime_data import SIMULATION_NOTICE, runtime_review_records, snapshot_for
from sensor_training_data import ROOT, digest, save_json


SOURCE = 'environment_context_v7'


def context_records(knowledge):
    docs = {doc['id']: doc for doc in knowledge['documents']}
    followups = ['Mai ra sao bạn?', 'Còn sáng mai thì sao nhỉ?', 'Thế buổi mai thế nào?',
                 'Tư vấn tiếp cho ngày mai với.', 'Sang ngày mai thì có gì khác?',
                 'Ngày tiếp theo thì tình hình thế nào?', 'Mình hỏi tiếp ngày mai nhé.',
                 'Vậy còn điều kiện của ngày mai?']
    choices = ['Thời tiết thôi nhé.', 'Mình chọn nhiệt độ và độ ẩm.', 'Ý mình là thời tiết.',
               'Cái về thời tiết ấy.', 'Xem nhiệt độ với độ ẩm nhé.', 'Mình đang muốn xem thời tiết.',
               'Câu trước mình nói về thời tiết.', 'Cho mình phần nhiệt độ, độ ẩm thôi.']
    unclear = ['Xem giúp điều kiện buổi mai nhé.', 'Mình muốn biết mai có ổn không.',
               'Bạn xem mai có thay đổi gì không?', 'Mình cần hỏi tình hình sáng mai.',
               'Tư vấn cho ngày mai giúp với.', 'Còn tình hình ngày tới?',
               'Bạn kiểm tra điều kiện ngày mai nhé.', 'Mai thì bạn nghĩ sao?']
    no_filter = ['Vẫn chưa có máy lọc, mình nên bắt đầu bằng gì?',
                 'Nhưng phòng chưa có thiết bị lọc thì làm gì ngay?',
                 'Giờ mình chỉ lau dọn được thôi, nên làm sao?',
                 'Nếu chưa sắm được máy nào thì còn cách gì?',
                 'Mình muốn xử lý bụi trước khi có máy lọc, chỉ mình nhé.',
                 'Chưa có máy hút bụi hay máy lọc, làm thế nào trước?',
                 'Trong lúc chưa có máy thì tự dọn bụi bằng gì?',
                 'Chỉ có khăn lau, giảm bụi trước bằng cách nào?']
    switches = ['Chuyển sang độ ẩm hiện tại nhé, cho mình con số thôi.',
                'Giờ mình chỉ cần phần độ ẩm của nơi này.',
                'Bỏ chuyện bụi đi, độ ẩm bây giờ bao nhiêu?',
                'Cập nhật riêng độ ẩm hiện tại giúp mình.',
                'Mình đổi câu hỏi: ở đây độ ẩm đang là mấy phần trăm?',
                'Lúc này chỉ đọc độ ẩm, đừng đọc bụi nhé.',
                'Còn độ ẩm vừa được cập nhật thì bao nhiêu?',
                'Mình muốn chuyển qua số đo độ ẩm lúc này.']
    definitions = ['AQI là chữ gì mà mọi người nhắc nhiều vậy bạn?',
                   'Giải nghĩa AQI thật ngắn cho mình nha.',
                   'Giúp mình hiểu AQI theo kiểu dễ nhớ nhất.',
                   'Mình mới xem môi trường, AQI biểu thị điều gì?',
                   'Chỉ số chất lượng không khí nói lên chuyện gì vậy?',
                   'Gặp chữ AQI trên bảng, mình cần hiểu thế nào?',
                   'Bạn diễn đạt ý nghĩa của AQI bằng lời đơn giản nhé.',
                   'Nhắc lại mục đích của chỉ số AQI cho người mới với.']
    helpful = ['Rất hữu ích nhé.', 'Hữu ích quá bạn ơi.', 'Gợi ý này hữu ích, cảm ơn bạn.',
               'Câu trả lời vừa rồi hữu ích với mình.', 'Những cách giảm bụi này hữu ích đấy.',
               'Mình thấy hướng dẫn này hữu ích lắm.', 'Phần tư vấn cho phòng của mình khá hữu ích.',
               'Cảm ơn, thông tin giảm bụi thật hữu ích.']
    result = []

    def add(topic, index, question, answer, sources, history=(), fields=(), extra='', reference=''):
        snapshot = snapshot_for(index)
        payload = (SIMULATION_NOTICE + 'Dữ liệu bảng giám sát do ứng dụng cung cấp:\n'
                   + chatbot._dashboard_context(snapshot, fields) + '\n' + extra
                   + ('\nKiến thức tham chiếu đã kiểm tra: ' + reference if reference else '')
                   + '\nCâu hỏi của người dùng:\n' + question)
        record = make_record(list(history) + [{'role': 'user', 'content': payload},
                                              {'role': 'assistant', 'content': answer}],
                             SOURCE, f'context-v7:{topic}:{index}', topic=topic,
                             original_question=question, source_ids=sources,
                             synthetic_context=True, snapshot=snapshot,
                             supervise_last_assistant_only=True,
                             review='source_checked_facts_and_project_dialogue_policy')
        record['messages'][0]['content'] = chatbot._system_prompt(snapshot, False, fields)
        result.append(('train' if index < 6 else 'validation', record))

    for index in range(8):
        current = snapshot_for(index)['DuLieu']
        temp, humidity = round(20.4 + index * 0.8, 1), 61 + index * 3
        has_forecast = index % 2 == 0
        forecast = (f'Dự báo thời tiết giả lập cho Hà Nội, ngày mai, khung 06:00–09:00: '
                    f'nhiệt độ {temp:g} °C, độ ẩm {humidity}%.\n' if has_forecast
                    else 'Ứng dụng chưa cung cấp dự báo thời tiết cho ngày mai.\n')
        weather_history = [{'role': 'user', 'content': f'Nhiệt độ và độ ẩm Hà Nội hôm nay ra sao? Mình xem lượt {index + 1}.'},
                           {'role': 'assistant', 'content': f'Hà Nội hiện {current["NhietDo"]:g} °C, độ ẩm {current["DoAm"]}%.'}]
        answer = (f'Theo dự báo được cung cấp, sáng mai Hà Nội khoảng {temp:g} °C, độ ẩm {humidity}%.'
                  if has_forecast else 'Mình chưa có dự báo thời tiết cho ngày mai ở Hà Nội; số đo hiện tại chưa cho biết ngày mai sẽ thế nào.')
        add('weather_next_day', index, followups[index], answer, ['project'], weather_history,
            ('NhietDo', 'DoAm'), forecast)

        value = [73, 116, 159, 186, 43, 207, 131, 172][index]
        label, guidance = chatbot._aqi_guidance(value)
        air_forecast = (f'Dự báo giả lập US AQI Hà Nội ngày mai, 06:00–09:00: {value}, '
                        f'mức {label}. Hướng dẫn theo AirNow: {guidance}\n' if has_forecast
                        else 'Ứng dụng chưa cung cấp dự báo chất lượng không khí cho ngày mai.\n')
        air_history = [{'role': 'user', 'content': f'Đọc không khí Hà Nội hôm nay giúp mình nhé, lần hỏi {index + 1}.'},
                       {'role': 'assistant', 'content': f'Hiện tại Hà Nội có US AQI {current["US_AQI"]}.'}]
        answer = (f'Theo dự báo được cung cấp, sáng mai Hà Nội có US AQI {value}, mức {label}. {guidance}'
                  if has_forecast else 'Mình chưa có dự báo AQI ngày mai tại Hà Nội, nên chưa thể kết luận chất lượng không khí ngày mai từ số đo hiện tại.')
        add('air_next_day', index, followups[index], answer, ['project', 'airnow_aqi', 'airnow_particles'],
            air_history, ('US_AQI',), air_forecast)

        add('clarify_unclear_topic', index, unclear[index],
            'Bạn muốn xem thời tiết hay chất lượng không khí ngày mai?', ['project'])

        history = [{'role': 'user', 'content': unclear[index]},
                   {'role': 'assistant', 'content': 'Bạn muốn xem thời tiết hay chất lượng không khí ngày mai?'}]
        add('clarified_topic_keeps_day', index, choices[index],
            f'Theo dự báo được cung cấp, sáng mai Hà Nội khoảng {temp:g} °C, độ ẩm {humidity}%.',
            ['project'], history, (),
            f'Dự báo thời tiết giả lập Hà Nội ngày mai, 06:00–09:00: {temp:g} °C, độ ẩm {humidity}%.\n')

        history = [{'role': 'user', 'content': f'Mình cần giảm bụi trong phòng cạnh đường, đang xét phòng số {index + 1}.'},
                   {'role': 'assistant', 'content': docs['indoor_dust_actions']['answer']},
                   {'role': 'user', 'content': helpful[index]},
                   {'role': 'assistant', 'content': 'Cảm ơn bạn, mình đã ghi nhận!'}]
        add('context_after_helpful', index, no_filter[index], docs['indoor_dust_actions']['answer_without_filter'],
            docs['indoor_dust_actions']['source_ids'], history, reference=docs['indoor_dust_actions']['answer_without_filter'])

        code = f'ENV-X{71 + index}'
        question = f'Thiết bị theo dõi môi trường ghi chỉ số {code}, nó tính thế nào vậy?'
        add('unfamiliar_measurement_asks_source', index, question,
            f'Mình chưa có tài liệu xác nhận ý nghĩa và cách tính {code}. Bạn gửi tên thiết bị hoặc phần giải thích chỉ số trong hướng dẫn được không?',
            ['project'], extra=f'Tình huống giả lập: mã {code} chưa có trong tài liệu kiến thức của ứng dụng.\n')

        history = [{'role': 'user', 'content': f'Trước đó mình muốn giải thích bụi PM2.5 ở lượt {index + 1}.'},
                   {'role': 'assistant', 'content': docs['pm25_definition']['answer']}]
        add('explicit_new_topic', index, switches[index], f'Độ ẩm hiện tại tại Hà Nội là {current["DoAm"]}%.',
            ['project'], history, ('DoAm',))

        add('natural_concept_question', index, definitions[index], docs['aqi_definition']['answer'],
            docs['aqi_definition']['source_ids'], reference=docs['aqi_definition']['answer'])
    return result


def prepare_context_data(destination, sensor_dir, continue_candidate=False):
    knowledge = json.loads((ROOT / 'data/xanhnon/knowledge.json').read_text(encoding='utf-8'))
    additions = context_records(knowledge)
    rehearsal = [(split, row) for split, row in consultation_records(knowledge)
                 if (split == 'train' and int(row['group_id'].rsplit(':', 1)[-1]) in (0, 2, 3, 5))
                 or (split == 'validation' and int(row['group_id'].rsplit(':', 1)[-1]) == 7)]
    noise = [(split, row) for split, row in runtime_review_records(knowledge)
             if row['topic'] == 'noise_duration' and ((split == 'train' and int(row['group_id'].rsplit(':', 1)[-1]) in (1, 2, 4, 5))
                                                     or int(row['group_id'].rsplit(':', 1)[-1]) == 7)]
    manifest = prepare(destination, sensor_dir, generated=additions + rehearsal + noise,
        training_configuration={'max_length': 1024, 'epochs': 1, 'learning_rate': 0.00003,
                                'start_from_active_release': not continue_candidate},
        rehearsal_limits={'style_train': 16, 'advice_train': 8, 'sensor_train': 4,
                          'base_validation': 2, 'sensor_validation': 2})
    manifest.update(new_dialogue_counts=dict(Counter(split for split, row in additions)),
                    consultation_rehearsal_counts=dict(Counter(split for split, row in rehearsal)),
                    noise_correction_counts=dict(Counter(split for split, row in noise)),
                    review_rationale=['Retain the previous subject across short temporal follow-ups.',
                                      'Ask one clarification when the subject is genuinely ambiguous.',
                                      'Read supplied simulated forecasts; never treat current readings as forecasts.',
                                      'Continue consultation after a helpful message and respect a new explicit topic.',
                                      'Ask for the definition/source of an unfamiliar measurement instead of inventing it.',
                                      'Rehearse reviewed AQI, PM10 and noise facts after v6 regressed on answer evaluation.'],
                    training_input={'synthetic_snapshots_and_forecasts_explicit': True,
                                    'new_records_supervision': 'final_assistant_turn_only',
                                    'knowledge_sha256': digest(ROOT / 'data/xanhnon/knowledge.json'),
                                    'generator_sha256': digest(Path(__file__))})
    save_json(Path(destination) / 'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sensor-data', type=Path, default=Path('D:/XanhNon-auto-training/sensor-dataset'))
    parser.add_argument('--continue-reviewed-candidate', action='store_true')
    args = parser.parse_args()
    manifest = prepare_context_data(args.output, args.sensor_data, args.continue_reviewed_candidate)
    print(json.dumps({key: manifest[key] for key in ('counts', 'new_dialogue_counts', 'consultation_rehearsal_counts',
                                                   'training_configuration')}, ensure_ascii=False))
