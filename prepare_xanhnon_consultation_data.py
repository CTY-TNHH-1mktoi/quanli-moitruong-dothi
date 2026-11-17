"""Prepare a bounded follow-up batch from reviewed v5 consultation failures.

The previous datasets remain immutable. New questions are distinct from the
fixed generation suite; all numeric snapshots are explicitly simulated.
"""

import argparse
from collections import Counter
import json
from pathlib import Path

import chatbot
from location_catalog import get_location
from prepare_xanhnon_data import make_record
from prepare_xanhnon_review_data import prepare
from prepare_xanhnon_runtime_data import runtime_record, runtime_review_records, snapshot_for
from sensor_training_data import ROOT, digest, save_json


def consultation_records(knowledge):
    docs = {item['id']: item for item in knowledge['documents']}
    questions = {
        'concept_aqi': [
            'Mình mới dùng ứng dụng, chữ AQI nói lên điều gì vậy?',
            'Giải nghĩa AQI giúp mình, chưa cần đọc số hiện tại nhé.',
            'AQI cao lên có nghĩa chất lượng không khí tốt lên hay xấu đi?',
            'Nếu chỉ giải thích khái niệm AQI thì có cần số đo hôm nay không?',
            'Mình chưa hiểu chỉ số chất lượng không khí dùng để nói điều gì.',
            'AQI để biết không khí sạch hay bẩn hả bạn?',
            'Nói gọn giúp người mới: chỉ số chất lượng không khí có ý nghĩa gì?',
            'Đọc AQI thì mình hiểu được điều gì về ô nhiễm?'],
        'pm_comparison_safe': [
            'So hai tên PM10 và PM2.5: mốc đường kính là bao nhiêu, có hít vào được không?',
            'PM10 to hơn nên không phải lo gì cho sức khỏe đúng chứ?',
            'Mình cần nhớ giới hạn kích thước của hai loại PM và có thể hít chúng không.',
            'PM2.5 nhỏ hơn, vậy PM10 có phải bụi vô hại không?',
            'Phân biệt đường kính của hai nhóm bụi PM10, PM2.5 và khả năng hít vào.',
            'Nói gọn hai mốc đường kính của bụi PM, đừng coi PM10 là không đáng lo nhé.',
            'PM10 có vào đường hô hấp không, còn PM2.5 nhỏ cỡ nào?',
            'Bạn nhắc lại hai mốc kích thước bụi PM và chuyện hít phải giúp mình.'],
        'aqi_boundary': [
            'Trong ví dụ US AQI {value}, hãy cho mình đúng mức, màu và cách điều chỉnh vận động.',
            'Giả định chỉ số US AQI là {value}, màu cảnh báo và mức tương ứng là gì?',
            'Lấy ví dụ AQI của Mỹ {value}: mình cần biết mức nào và nên tập ngoài trời ra sao.',
            'Nếu số US AQI trong tình huống bằng {value}, bạn đọc giúp mức và màu chuẩn.',
            'Một tình huống giả lập có US AQI {value}. Diễn giải mức và việc vận động ngắn gọn nhé.',
            'Giả sử bảng báo US AQI {value}, mức cảnh báo là gì và cần điều chỉnh hoạt động thế nào?',
            'Với ví dụ US AQI {value}, mức chất lượng không khí được gọi thế nào?',
            'Chỉ xét giả định US AQI {value}: màu, tên mức và điều chỉnh hoạt động là gì?'],
        'concept_followup': [
            'Nhỏ vậy thì có hít sâu xuống phổi được k?',
            'Thế loại hạt ấy có lọt vào sâu trong phổi chứ?',
            'Còn chúng vào phổi khi thở thì sao nhỉ?',
            'Vậy cái bụi vừa nhắc có xuống phổi khi hít thở không?',
            'Hạt đó đi sâu vào phổi được à bạn?',
            'Mình hỏi tiếp loại bụi ấy có hít xuống phổi được không nhé.',
            'Vừa nói loại nhỏ ấy, nó có thể tới sâu trong phổi chứ?',
            'Thế bụi vừa giải thích có thể được hít sâu vào phổi à?'],
        'no_filter_followup': [
            'Nhưng mình k có cả máy lọc lẫn máy hút bụi, làm gì trước đây?',
            'Nhà chưa sắm thiết bị nào cả, giờ có việc gì tự làm được k?',
            'Mình không dùng thiết bị lọc được, cho mình việc làm ngay đi.',
            'Vậy nếu chỉ có khăn và đồ lau dọn, mình làm gì cho bớt bụi?',
            'Ừ nhưng hiện không có máy lọc hay máy hút bụi đâu, còn cách nào?',
            'Cảm ơn, mà mình chưa sắm được máy gì, giờ tự giảm bụi bằng cách nào?',
            'Thế không có thiết bị lọc nào trong nhà thì tự làm được gì?',
            'Đang chưa mua thêm máy được, chỉ mình việc lau dọn và hạn chế bụi trước nhé.'],
        'clarify_activity_time': [
            'Mình đang tính chạy mấy vòng công viên, tư vấn với bạn ơi.',
            'Tư vấn cho mình buổi vận động ở ngoài trời nhé bạn.',
            'Định ra công viên đi bộ, bạn giúp mình cân nhắc môi trường với.',
            'Bạn giúp mình sắp xếp một buổi đạp xe ngoài trời được k?',
            'Mình muốn lên lịch đi dạo, bạn tư vấn môi trường trước nhé.',
            'Mình tính tập ở sân ngoài trời, bạn cần biết gì để tư vấn?',
            'Đang lên kế hoạch đi bộ công viên, nhờ bạn tư vấn với.',
            'Giúp mình cân nhắc một buổi chạy ở bên ngoài nhé.'],
        'clarify_why': [
            'Ủa hỏi vậy để làm gì nhỉ?',
            'Mình chưa hiểu câu vừa hỏi lắm.',
            'Sao lại cần hỏi lúc nào?',
            'Bạn giải thích thêm ý đó đi.',
            'Ý bạn về giờ đi là thế nào?',
            'Hỏi giờ đi thì liên quan gì đến không khí vậy?',
            'Nói rõ hơn câu hỏi vừa rồi giúp mình.',
            'Chỗ bạn hỏi thời gian mình chưa hiểu, giải thích ngắn nhé.'],
        'source_uncertainty': [
            'Chỉ nhìn số PM2.5 trong bảng có biết chắc bụi do xe trước nhà mình gây ra không?',
            'AQI đang cao thì kết luận ngay nhà máy bên cạnh gây ô nhiễm được chứ?',
            'Chỉ có nồng độ bụi thì mình chỉ đích danh nguồn gây ra được k?',
            'Số đo bụi trên ứng dụng có chứng minh xe cộ là nguồn duy nhất không?',
            'Từ một giá trị PM10, bạn xác định chắc công trường gần nhà là thủ phạm được không?',
            'Bảng đang có bụi cao, có đủ cơ sở quy hết cho đường xe chạy không?',
            'Có thể dùng một số AQI để khẳng định nguồn thải cụ thể không bạn?',
            'Mỗi nồng độ PM2.5 thôi thì có biết chính xác bụi từ cơ sở nào không?'],
        'current_replaces_assumption': [
            'Quay về địa điểm đang chọn: US AQI hiện giờ là mấy và thuộc mức nào?',
            'Mình bỏ giả sử lúc nãy nhé, AQI mới trong bảng bây giờ ra sao?',
            'Còn US AQI hiện tại của nơi đang giám sát thì thế nào?',
            'Giờ đọc số AQI vừa cập nhật cho mình, không dùng ví dụ cũ nhé.',
            'Trở lại số đo AQI hiện tại ở địa điểm đã chọn, bạn đọc giúp nhé.',
            'Mình hỏi dữ liệu AQI mới chứ không hỏi chỗ giả định trước đó nhé.',
            'Còn AQI lúc này ở nơi ứng dụng đang chọn, mức hiện tại là gì?',
            'Bỏ ví dụ cũ, mình muốn số US AQI bây giờ theo bảng giám sát.'],
        'pm_units_not_index': [
            'Giả sử PM2.5 đo được {value} µg/m³, ghi AQI bằng nguyên số đó đúng k?',
            'Giả định nồng độ PM2.5 {value} µg/m³, đây là nồng độ hay chỉ số AQI?',
            'Nếu PM2.5 bằng {value} µg/m³, mình dùng số {value} đó làm US AQI được chứ?',
            'Giả sử máy báo PM2.5 {value} µg/m³. Có phải đó cũng là số AQI luôn không?',
            'Giả định PM2.5 {value} µg/m³, hai cách ghi nồng độ và AQI có thể thay nhau không?',
            'Nếu đọc {value} µg/m³ cho PM2.5 thì có cần phân biệt nồng độ với AQI không?',
            'Giả sử PM2.5 là {value} µg/m³, lấy luôn số ấy làm AQI có nhầm không bạn?',
            'Giả định nồng độ bụi mịn {value} µg/m³, bạn phân biệt nó với US AQI ngắn gọn nhé.'],
    }
    values = [159, 197, 200, 202, 46, 303, 148, 286]
    particle_history = [
        'Mình muốn hiểu ký hiệu PM2.5 trong bảng.',
        'Chữ PM2.5 trong mục bụi chỉ kích thước gì?',
        'Giải thích tên bụi PM2.5 cho người mới giúp mình.',
        'Bạn nói rõ giới hạn kích thước của PM2.5 trước nhé.',
        'Mình cần biết PM2.5 là tên của nhóm bụi nào.',
        'Bụi ghi PM2.5 có giới hạn đường kính ra sao?',
        'Đọc giúp mình ý nghĩa tên gọi nhóm bụi PM2.5.',
        'Số 2.5 trong tên nhóm bụi có ý nghĩa gì thế?']
    particle_thanks = [
        'À, mình hiểu mốc kích thước của bụi trong bảng rồi.',
        'Cảm ơn, giải thích về ký hiệu khá dễ hiểu.',
        'Mình nắm được tên nhóm bụi rồi, cảm ơn bạn.',
        'Hiểu rồi nhé, cảm ơn đã nói rõ giới hạn đường kính.',
        'Cảm ơn, mình đã hiểu nhóm bụi nhỏ đó.',
        'Giờ mình rõ hơn về số chỉ kích thước rồi nhé.',
        'Cảm ơn đã giải nghĩa ký hiệu của bụi mịn.',
        'À, ra là số đó nói về kích thước, cảm ơn nhé.']
    rooms = ['phòng ngủ cạnh đường', 'phòng làm việc', 'phòng khách tầng một', 'căn hộ của mình',
             'phòng học', 'phòng đọc sách', 'nhà trọ', 'phòng sinh hoạt']
    thanks = ['Cảm ơn, mình hiểu cách giảm bụi cho phòng ngủ rồi.',
              'Mình nắm ý cho phòng làm việc rồi, cảm ơn nhé.',
              'Cảm ơn bạn đã gợi ý cho phòng khách.',
              'Mình hiểu hướng xử lý căn hộ rồi nhé.',
              'Cảm ơn đã chỉ cách giảm bụi phòng học.',
              'Mình đã hiểu gợi ý cho phòng đọc, cảm ơn bạn.',
              'Cảm ơn đã hướng dẫn cách xử lý bụi nhà trọ.',
              'Mình nắm được cách giảm bụi phòng sinh hoạt rồi, cảm ơn nhé.']
    records = []
    for topic, variants in questions.items():
        for index, question in enumerate(variants):
            snapshot = snapshot_for(index)
            # Several cities prevent the assistant from treating every example as Hanoi.
            place = get_location(['hanoi', 'danang', 'tphcm', 'hue'][index % 4])
            snapshot = {**snapshot, 'DiaDiem': place}
            history = []
            if topic == 'concept_aqi':
                answer = docs['aqi_definition']['answer']
                sources = docs['aqi_definition']['source_ids']
            elif topic == 'pm_comparison_safe':
                answer = ('PM2.5 gồm hạt có đường kính thường không quá 2,5 µm; PM10 thường không quá 10 µm. '
                          'Cả hai đều có thể được hít vào đường hô hấp; không nên coi PM10 là vô hại.')
                sources = ['epa_pm']
            elif topic == 'aqi_boundary':
                value = values[index]
                question = question.format(value=value)
                level, advice = chatbot._aqi_guidance(value)
                color = next(color for maximum, color in [(50, 'xanh lá'), (100, 'vàng'), (150, 'cam'),
                                                           (200, 'đỏ'), (300, 'tím'), (500, 'nâu đỏ')] if value <= maximum)
                answer = f'Theo giả định US AQI {value}, mức này là {level} ({color}). {advice}'
                sources = ['airnow_aqi', 'airnow_particles', 'project']
            elif topic == 'concept_followup':
                history = [{'role': 'user', 'content': particle_history[index]},
                           {'role': 'assistant', 'content': 'Tên PM2.5 chỉ các hạt bụi có đường kính thường không quá 2,5 micromet.'}]
                if index % 2:
                    history += [{'role': 'user', 'content': particle_thanks[index]},
                                {'role': 'assistant', 'content': 'Không có gì nhé!'}]
                answer = 'Có thể bạn nhé. Hạt PM2.5 rất nhỏ nên có thể được hít vào sâu trong phổi.'
                sources = ['epa_pm']
            elif topic == 'no_filter_followup':
                history = [{'role': 'user', 'content': f'Bụi ngoài đường bay vào {rooms[index]}, nhờ bạn gợi ý cách giảm.'},
                           {'role': 'assistant', 'content': 'Bạn có thể giảm nguồn bụi trong nhà và dùng máy lọc phù hợp nếu có.'}]
                if index % 2:
                    history += [{'role': 'user', 'content': thanks[index]},
                                {'role': 'assistant', 'content': 'Không có gì, bạn nhé.'}]
                answer = ('Bạn có thể lau bụi bằng khăn ẩm, hạn chế mở cửa phía đường khi ngoài trời nhiều bụi '
                          'và tránh khói thuốc, đốt nến trong nhà. Các cách này giúp giảm nguồn bụi nhưng không loại hết bụi mịn.')
                sources = docs['indoor_dust_actions']['source_ids']
            elif topic == 'clarify_activity_time':
                answer = 'Bạn định đi hôm nay hay vào thời điểm nào khác?'
                sources = ['project']
            elif topic == 'clarify_why':
                history = [{'role': 'user', 'content': questions['clarify_activity_time'][index]},
                           {'role': 'assistant', 'content': 'Bạn định vận động hôm nay hay vào thời điểm nào khác?'}]
                answer = 'Mình hỏi để xem dữ liệu môi trường có phù hợp lúc bạn định tập không. Bạn dự định đi lúc nào?'
                sources = ['project']
            elif topic == 'current_replaces_assumption':
                old = 11 + index * 9
                level, _ = chatbot._aqi_guidance(old)
                history = [{'role': 'user', 'content': f'Giả sử một nơi khác báo US AQI {old} thì ở mức gì?'},
                           {'role': 'assistant', 'content': f'Trong giả định đó, US AQI {old} thuộc mức {level}.'}]
                value = snapshot['DuLieu']['US_AQI']
                level, _ = chatbot._aqi_guidance(value)
                answer = f'Theo dữ liệu mới được cung cấp, {place["Ten"]} hiện có US AQI {value}, thuộc mức {level}.'
                sources = ['airnow_aqi', 'project']
            elif topic == 'pm_units_not_index':
                value = [14, 29, 58, 77, 93, 116, 33, 68][index]
                question = question.format(value=value)
                answer = (f'Không bạn nhé. {value} µg/m³ là nồng độ PM2.5, còn AQI là chỉ số quy đổi theo quy tắc '
                          'và khoảng thời gian phù hợp; không lấy trực tiếp số nồng độ làm AQI.')
                sources = ['epa_pm', 'airnow_aqi', 'project']
            else:
                answer = ('Chưa đủ cơ sở bạn nhé. Một giá trị bụi hoặc AQI không xác định được nguồn gây ô nhiễm cụ thể; '
                          'cần thêm thông tin về nguồn thải và điều kiện tại khu vực.')
                sources = ['epa_pm', 'project']
            split, row = runtime_record(topic, index, question, answer, sources, snapshot, history)
            metadata = {key: value for key, value in row.items() if key not in ('id', 'source', 'group_id', 'messages')}
            record = make_record(row['messages'][1:], 'environment_consultation_v6',
                                 f'consultation-v6:{topic}:{index}', **metadata)
            record['messages'][0]['content'] = row['messages'][0]['content']
            records.append((split, record))
    return records


def prepare_consultation_data(destination, sensor_dir, continue_candidate=False):
    knowledge = json.loads((ROOT / 'data/xanhnon/knowledge.json').read_text(encoding='utf-8'))
    additions = consultation_records(knowledge)
    previous = [(split, row) for split, row in runtime_review_records(knowledge)
                if split == 'validation' or int(row['group_id'].rsplit(':', 1)[-1]) in (0, 3)]
    settings = {'max_length': 1024, 'epochs': 1, 'learning_rate': 0.00005,
                'start_from_active_release': not continue_candidate}
    manifest = prepare(destination, sensor_dir, generated=previous + additions, training_configuration=settings,
                       rehearsal_limits={'style_train': 24, 'advice_train': 8, 'sensor_train': 4,
                                         'base_validation': 2, 'sensor_validation': 2})
    manifest['new_dialogue_counts'] = dict(Counter(split for split, _ in additions))
    manifest['runtime_rehearsal_counts'] = dict(Counter(split for split, _ in previous))
    manifest['review_rationale'] = ['Answer conceptual questions without claiming current data is required.',
        'Correct PM size, PM10 risk and AQI category misconceptions.',
        'Answer follow-ups after a social turn; honor the absence of filtering devices.',
        'Ask one relevant question when the activity time changes the advice.']
    manifest['source_verification'] = {'checked_on': '2026-10-19', 'ids': ['epa_pm', 'airnow_aqi', 'nidcd_noise'],
                                      'method': 'Read official pages; advice uses the reviewed project knowledge base.'}
    manifest['training_input'] = {'synthetic_snapshots_explicit': True, 'new_records_supervision': 'final_assistant_turn_only',
        'source_sha256': {name: digest(ROOT / name) for name in ('prepare_xanhnon_consultation_data.py',
            'prepare_xanhnon_runtime_data.py', 'chatbot.py', 'chat_knowledge.py', 'chat_scope.py')}}
    save_json(Path(destination) / 'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sensor-data', type=Path, default=Path('D:/XanhNon-auto-training/sensor-dataset'))
    parser.add_argument('--continue-reviewed-candidate', action='store_true')
    args = parser.parse_args()
    result = prepare_consultation_data(args.output, args.sensor_data, args.continue_reviewed_candidate)
    print(json.dumps({key: result[key] for key in ('counts', 'new_dialogue_counts', 'runtime_rehearsal_counts',
                                                 'deduplication', 'training_configuration')}, ensure_ascii=False))
