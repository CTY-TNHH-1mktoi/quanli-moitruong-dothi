"""A reviewed 70/30 pilot; no unreviewed pool is copied wholesale or activated."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import shutil

import chatbot
from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_consultation_data import consultation_records
from prepare_xanhnon_data import normalize, stable_id
from prepare_xanhnon_runtime_data import runtime_record, runtime_review_records, snapshot_for
from sensor_training_data import ROOT, digest, save_json

SOURCE = 'environment_balanced_v9'
POOL = Path('D:/XanhNon-auto-training/dialogue-pool-20261021-v2')
SENSORS = Path('D:/XanhNon-auto-training/sensor-dataset')


def reviewed_record(key, topic, question, answer, source_ids, *, component='expertise', history=(),
                    forecast=None, index=0, **metadata):
    _, row = runtime_record(topic, index % 8, question, answer, source_ids, snapshot_for(index % 8), history)
    row.update(source=SOURCE, group_id=f'{SOURCE}:{key}', mixture_component=component,
               reviewed_for_pilot=True, novel_for_pilot=True, **metadata)
    if forecast:
        marker = 'Câu hỏi của người dùng:\n'
        row['messages'][-2]['content'] = row['messages'][-2]['content'].replace(
            marker, 'Dự báo giả lập được cung cấp cho ngày mai, đúng địa điểm đang chọn:\n' + forecast + '\n\n' + marker)
        row['simulated_forecast'] = forecast
    row['id'] = stable_id(row['group_id'] + json.dumps(row['messages'], ensure_ascii=False))[:20]
    return row


def dialogue(question, answer, *history):
    return question, answer, [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': text}
                              for i, text in enumerate(history)]


def authored_dialogues():
    # Each item was read as a complete interaction, including the final target.
    train = [
        dialogue('Chào bạn Xanh Non nhé!', 'Chào bạn! Bạn muốn xem chỉ số môi trường hay cần mình tư vấn điều gì?'),
        dialogue('Alo, có nghe mình không?', 'Mình đây, bạn cứ hỏi nhé.'),
        dialogue('Mình thấy phần vừa giải thích hữu ích đó.', 'Cảm ơn bạn nhé! Còn chỗ nào muốn hỏi thêm, bạn cứ nhắn mình.',
                 'Mình muốn hiểu ý nghĩa của chỉ số chất lượng không khí.', 'AQI giúp diễn đạt mức ô nhiễm và mức lo ngại đối với sức khỏe.'),
        dialogue('Mình cần bạn tư vấn chút được không?', 'Được chứ. Bạn đang quan tâm không khí, hoạt động ngoài trời hay tiếng ồn?'),
        dialogue('Mai thì sao nhỉ?', 'Dự báo ngày mai tại Hà Nội: US AQI 132, mức Kém. Nhóm nhạy cảm nên giảm thời gian và cường độ vận động ngoài trời.',
                 'Hỏi về chất lượng không khí ở nơi đang chọn nhé.', 'Bạn đang xem chất lượng không khí ở Hà Nội.'),
        dialogue('Còn ngày mai thế nào bạn?', 'Dự báo ngày mai ở Hà Nội: nhiệt độ 26 °C, độ ẩm 72%.',
                 'Mình muốn xem nhiệt độ và độ ẩm ở Hà Nội.', 'Mình sẽ đọc nhiệt độ và độ ẩm theo dữ liệu được cung cấp.'),
        dialogue('Thế mai ra sao?', 'Bạn muốn hỏi thời tiết hay chất lượng không khí ngày mai?',
                 'Hôm nay mình đang xem cả thời tiết lẫn không khí.', 'Hai phần này có các chỉ số khác nhau, bạn có thể hỏi riêng từng phần.'),
        dialogue('Ý mình là không khí ấy.', 'Dự báo không khí ngày mai tại Hà Nội có US AQI 132, thuộc mức Kém.',
                 'Ngày mai tình hình thế nào?', 'Bạn muốn hỏi thời tiết hay chất lượng không khí ngày mai?'),
        dialogue('Chỉ nhắc độ ẩm thôi nha.', 'Độ ẩm ở Hà Nội hiện là 73%.',
                 'Mình đang xem hai số nhiệt độ và độ ẩm của Hà Nội.', 'Bạn muốn mình đọc riêng chỉ số nào?'),
        dialogue('Nó đi vào phổi như thế nào?', 'Hạt PM2.5 rất nhỏ nên có thể được hít vào sâu trong phổi.',
                 'Tên PM2.5 dùng để nói về nhóm bụi nào vậy?', 'Đó là nhóm hạt bụi có đường kính thường không quá 2,5 micromet.',
                 'Mình hiểu hơn rồi, cảm ơn nha.', 'Không có gì nhé!'),
        dialogue('Sao bạn cần biết giờ đi của mình?', 'Mình hỏi để dùng số đo hoặc dự báo đúng lúc bạn định đi. Bạn dự định đi lúc nào?',
                 'Mình muốn đi dạo ở công viên.', 'Bạn định đi lúc nào?'),
        dialogue('Nói đơn giản hơn giúp mình.', 'AQI giống một thang báo mức ô nhiễm: số càng cao thì không khí càng đáng lo.',
                 'Giải nghĩa chữ AQI cho người mới nhé.', 'AQI là chỉ số chất lượng không khí và mức lo ngại đối với sức khỏe.'),
        dialogue('Đừng liệt kê số đo, mình chỉ hỏi ý nghĩa ký hiệu đó.', 'PM2.5 chỉ nhóm hạt bụi có đường kính thường không quá 2,5 micromet.',
                 'Mình đang tìm hiểu tên PM2.5.', 'Bạn muốn hiểu ký hiệu hay xem nồng độ hiện tại?'),
        dialogue('Ko có máy nào hết thì làm sao?', 'Bạn có thể lau bụi bằng khăn ẩm, hạn chế mở cửa phía đường lúc nhiều bụi và giảm nguồn khói trong nhà.',
                 'Mình muốn giảm bụi trong phòng trọ gần đường.', 'Có thể giảm nguồn bụi và dùng thiết bị lọc nếu có.'),
        dialogue('Đổi qua tiếng ồn nhé, mình nên làm gì?', 'Bạn nên giảm thời gian tiếp xúc và đứng xa nguồn ồn. Nếu phải ở nơi rất ồn, dùng bảo vệ tai phù hợp.',
                 'Mình vừa hỏi về bụi ngoài đường.', 'Bạn có thể hỏi tiếp hoặc chuyển sang một chỉ số môi trường khác.'),
        dialogue('Bạn trả lời nhầm sang bụi rồi, mình hỏi độ ẩm.', 'Bạn nói đúng, mình sẽ tập trung vào độ ẩm. Bạn muốn xem số hiện tại hay hỏi cách xử lý ẩm trong phòng?',
                 'Mình đang tìm hiểu độ ẩm.', 'Bụi có thể từ ngoài trời lọt vào nhà.'),
        dialogue('Bạn có thể hướng dẫn những việc nào trong ứng dụng?', 'Mình giúp bạn hiểu các chỉ số môi trường, đọc số liệu được cung cấp và cân nhắc hoạt động phù hợp với điều kiện môi trường.'),
        dialogue('Ừ, vậy nói gọn lại đi.', 'Nồng độ bụi và AQI là hai đại lượng khác nhau; không lấy nguyên số nồng độ làm AQI.',
                 'Mình đang nhầm nồng độ bụi với chỉ số quy đổi.', 'Nồng độ cho biết lượng bụi trong không khí, còn AQI được quy đổi theo một thang chỉ số.'),
        dialogue('Vậy cái nào có trước, thời tiết hay số AQI?', 'Bạn đang hỏi cách ứng dụng lấy dữ liệu hay quan hệ giữa thời tiết và ô nhiễm?'),
        dialogue('Mình nói thiếu ý: đang hỏi ngày mai, không phải hôm nay.', 'Vậy mình sẽ xét dự báo ngày mai. Bạn muốn xem thời tiết hay chất lượng không khí?',
                 'Tình hình chỗ mình thế nào?', 'Bạn muốn hỏi về thời điểm nào?'),
        dialogue('Chắc chắn hạt đó vô hại chứ?', 'Không nên coi PM10 là vô hại; loại bụi này vẫn có thể được hít vào đường hô hấp.',
                 'Mình đang nói tới nhóm bụi PM10.', 'Tên PM10 nói tới giới hạn đường kính thường không quá 10 micromet.'),
        dialogue('Thế mình bắt đầu hỏi thế nào cho bạn dễ hiểu?', 'Bạn có thể nói địa điểm, thời điểm và điều muốn biết, chẳng hạn: “Không khí Hà Nội sáng mai thế nào?”.'),
        dialogue('Cho mình hỏi chuyện vừa nói ấy được không?', 'Được nhé. Bạn muốn hỏi tiếp phần chỉ số, tác động hay cách giảm tiếp xúc?',
                 'Mình đang xem thông tin bụi mịn trong ứng dụng.', 'Bạn có thể hỏi về ý nghĩa chỉ số và cách hạn chế tiếp xúc.'),
        dialogue('Cảm ơn nha, chào bạn.', 'Không có gì nhé, hẹn gặp lại bạn!'),
    ]
    validation = [
        dialogue('Chào Xanh Non, hỗ trợ mình với nha.', 'Chào bạn! Bạn đang cần xem chỉ số môi trường hay tư vấn điều gì?'),
        dialogue('Hỏi tiếp hôm sau thì sao?', 'Bạn muốn hỏi thời tiết hay chất lượng không khí cho hôm sau?',
                 'Mình đang đọc cả thời tiết và AQI tại địa điểm đã chọn.', 'Bạn có thể xem từng phần để tránh nhầm các chỉ số.'),
        dialogue('Nói lại bằng lời dễ hiểu giúp mình được chứ?', 'AQI là thang báo mức ô nhiễm; số cao hơn nghĩa là mức lo ngại lớn hơn.',
                 'Mình chưa rõ chữ AQI được dùng để diễn đạt gì.', 'Nó diễn đạt chất lượng không khí và mức lo ngại đối với sức khỏe.'),
        dialogue('Chỗ giờ đi liên quan thế nào vậy bạn?', 'Thời điểm giúp chọn đúng số đo hoặc dự báo cho lúc bạn định đi. Bạn dự định đi khi nào?',
                 'Mình định ra ngoài vận động nhẹ.', 'Bạn dự định đi vào lúc nào?'),
        dialogue('Mình chỉ muốn biết mỗi độ ẩm mới thôi.', 'Độ ẩm ở Hà Nội hiện là 85%.',
                 'Mình xem phần thời tiết ở địa điểm đang chọn.', 'Bạn muốn xem nhiệt độ, độ ẩm hay cả hai?'),
        dialogue('Cảm ơn, phần ấy giúp mình hiểu hơn.', 'Không có gì nhé! Bạn cứ hỏi thêm khi cần.',
                 'Mình đã phân biệt được chỉ số với nồng độ bụi.', 'Đúng rồi, nên đọc đúng đại lượng và đơn vị.'),
    ]
    return train, validation


def core_questions():
    return {
        'indoor_dust_actions': 'Phòng ở sát đường xe chạy, mình muốn tự hạn chế bụi lọt vào, nên bắt đầu từ đâu?',
        'humidity_actions': 'Tường phòng thường ẩm, mình cần kiểm tra việc gì trước khi chỉ nghĩ tới mua máy?',
        'noise_actions': 'Muốn bớt tác động của âm thanh lớn, mình nên điều chỉnh thời gian và khoảng cách thế nào?',
        'waste_actions': 'Muốn giảm lượng đồ dùng một lần và rác trong nhà, bạn gợi ý vài việc dễ bắt đầu nhé.',
        'filter_actions': 'Chọn và dùng thiết bị lọc bụi cho phòng thì cần để ý điều gì thay vì chỉ nhìn quảng cáo?',
        'heat_actions': 'Nếu cần vận động khi ngoài trời nóng, mình điều chỉnh thời điểm và cường độ ra sao?',
        'aqi_definition': 'Ý nghĩa chính của chữ AQI trên giao diện là gì, trả lời gọn nhé.',
        'aqi_categories': 'Bạn nhắc giúp sáu khoảng chỉ số US AQI cùng màu và cách gọi trong ứng dụng.',
        'pm25_definition': 'Giới hạn đường kính của hạt PM2.5 là bao nhiêu và có thể hít sâu xuống phổi không?',
        'pm10_definition': 'Cách hiểu đúng tên PM10 là nhóm bụi có đường kính được giới hạn ra sao?',
        'pm_comparison': 'So hai mốc đường kính của PM2.5 và PM10 giúp mình, đồng thời đừng coi PM10 là vô hại nhé.',
        'pm_units': 'Đơn vị microgam trên mét khối trong số đo bụi thể hiện điều gì?',
        'pm_aqi_difference': 'Vì sao không được thay chỉ số AQI bằng nguyên số nồng độ bụi trên bảng?',
        'pm_sources': 'Những hoạt động đô thị nào có thể tạo bụi trực tiếp hoặc gián tiếp?',
        'pm_health': 'Tác động chung của hạt bụi hít phải và giới hạn khi suy từ chỉ số sang bệnh là gì?',
        'sensitive_groups': 'Khi theo dõi ô nhiễm bụi, những nhóm người nào thường cần chú ý hơn?',
        'outdoor_principles': 'Theo AQI tăng lên, có những cách nào điều chỉnh một buổi vận động ngoài trời?',
        'indoor_particles': 'Nguồn hạt bụi trong căn phòng có thể từ ngoài vào hay chỉ phát sinh bên trong?',
        'air_filters': 'Lọc hạt tốt có bảo đảm mọi loại chất ô nhiễm trong căn phòng đều biến mất không?',
        'missing_aqi': 'Giá trị chỉ số AQI không hiển thị thì được hiểu là số không hay chưa đủ dữ liệu?',
        'missing_pm': 'Ô PM2.5 trên bảng bị trống, mình nên hiểu thế nào trước khi nhận xét không khí?',
        'location_time': 'Khi nhận xét số đo trên bản đồ, vì sao cần xem cả vị trí lẫn lúc cập nhật?',
        'data_source': 'Trong dự án, thông tin thời tiết, không khí và tiếng ồn lấy từ những loại nguồn nào?',
        'forecast_missing': 'Có mỗi số đo của lúc này thì có đủ để khẳng định chất lượng không khí hôm sau không?',
        'weather_air_difference': 'Trời dễ chịu và ít nóng có đủ căn cứ để gọi chất lượng không khí là tốt chưa?',
        'medical_limit': 'Từ AQI và số đo bụi, mình được nhận xét ô nhiễm hay có thể tự kết luận bệnh và thuốc?',
    }


def reviewed_external(pool):
    raw = {r['id']: r for r in [json.loads(line) for line in (pool / 'train.jsonl').read_text(encoding='utf-8').splitlines()]}
    adaptations = [
        ('f33437ec313877b8d3f4', 'Với mô tả “AQI là chỉ số chất lượng không khí”, đặt một câu hỏi tương ứng giúp mình.',
         'AQI được dùng để diễn đạt điều gì về không khí?', ()),
        ('cb6fa1011939fcb3f158', 'Ví dụ minh họa có ba giá trị nồng độ là 12, 18 và 24 µg/m³. Trung bình số học là bao nhiêu?',
         'Trung bình số học là 18 µg/m³: (12 + 18 + 24) / 3. Đây chỉ là phép tính trên ba giá trị ví dụ.', ()),
        ('a02d7a5b776bd56a0529', 'Số nhiệt độ giả lập âm bốn phẩy hai độ C viết có dấu thế nào?',
         'Viết là −4,2 °C; dấu trừ cho biết nhiệt độ dưới 0 °C.', ()),
        ('ec8dfeb330441fd2be0a', 'Chỉ muốn xem độ ẩm: mình chọn mục AQI, nhiệt độ hay độ ẩm?',
         'Bạn chọn mục độ ẩm, thường hiển thị bằng phần trăm (%).', ()),
        ('b7b244ca3bde4346cf89', 'Bạn lấy một ví dụ để mình phân biệt được không?',
         '“Hạn chế nguồn bụi, ví dụ khói thuốc” là nêu một trường hợp. “Hạn chế nguồn bụi, nghĩa là giảm nơi phát sinh bụi” là giải thích lại ý đó.',
         ('Mình đang phân biệt cách nói “ví dụ” và “nghĩa là” trong lời tư vấn giảm bụi.', '“Ví dụ” nêu một trường hợp, còn “nghĩa là” diễn giải lại ý vừa nói.')),
        ('971cfdf17adfa0777926', 'Nếu dự báo ghi 12 PM thì đó là trưa hay đêm?',
         '12 PM là 12 giờ trưa; 12 AM là 0 giờ, tức nửa đêm.',
         ('Mình đang đọc nhãn giờ AM và PM trong một bảng dự báo minh họa.', 'AM dùng cho buổi trước trưa, PM dùng cho buổi sau trưa theo quy ước giờ 12 tiếng.')),
    ]
    result = []
    for index, (original_id, question, answer, history_text) in enumerate(adaptations):
        original = raw[original_id]
        history = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': text} for i, text in enumerate(history_text)]
        result.append(reviewed_record('adapted:' + original_id, 'reviewed_language_adaptation', question, answer,
            ['project'], component='dialogue', history=history, index=index,
            upstream_repo=original['upstream_repo'], upstream_revision=original['upstream_revision'],
            upstream_id=original['upstream_id'], license=original['license'],
            original_pool_record_id=original_id,
            original_pool_record_sha256=stable_id(json.dumps(original, ensure_ascii=False, sort_keys=True)),
            review='manually_read_source_and_rewritten_project_scenario',
            adaptation='Rewrote topic/numbers/replies for the environment app; source text is not treated as environmental authority.'))
    return result


def balanced_records(knowledge, supplement, pool=POOL, sensors=SENSORS):
    partitions = {'train': [], 'validation': []}
    for index, case in enumerate(supplement['cases']):
        partitions['train'].append(reviewed_record('specialist:' + case['id'], case['topic'],
            case['messages'][-2]['content'], case['messages'][-1]['content'], case['source_ids'],
            history=case['messages'][:-2], index=index, source_case_id=case['id']))
    questions = core_questions()
    assert set(questions) == {doc['id'] for doc in knowledge['documents']}
    for index, doc in enumerate(knowledge['documents']):
        answer = doc['answer']
        if doc['id'] == 'pm25_definition':
            answer = 'PM2.5 gồm hạt có đường kính thường không quá 2,5 micromet; chúng có thể được hít vào sâu trong phổi.'
        elif doc['id'] == 'pm_comparison':
            answer = 'PM2.5 thường không quá 2,5 µm; PM10 thường không quá 10 µm. Cả hai đều có thể được hít vào đường hô hấp; PM10 không phải bụi vô hại.'
        elif doc['id'] == 'pm_aqi_difference':
            answer = doc['answer'].split(' Khi thiếu')[0]
        elif doc['id'] == 'noise_actions':
            answer = 'Giảm thời gian tiếp xúc với tiếng ồn và đứng xa nguồn ồn. Nếu phải ở nơi rất ồn, dùng nút tai hoặc chụp tai phù hợp; không nghe lâu hơn để quen tai.'
        partitions['train'].append(reviewed_record('knowledge:' + doc['id'], 'knowledge_' + doc['id'],
            questions[doc['id']], answer, doc['source_ids'], index=index))
    limits = {'concept_aqi': 2, 'pm_comparison_safe': 2, 'aqi_boundary': 2,
              'current_replaces_assumption': 2, 'pm_units_not_index': 2, 'concept_followup': 4,
              'no_filter_followup': 4, 'clarify_activity_time': 2, 'clarify_why': 2, 'source_uncertainty': 2}
    validation_topics = {'concept_aqi', 'pm_comparison_safe', 'aqi_boundary',
                         'current_replaces_assumption', 'pm_units_not_index', 'no_filter_followup', 'source_uncertainty'}
    counts = Counter()
    for split, original in consultation_records(knowledge):
        if split == 'train' and counts[original['topic']] < limits.get(original['topic'], 0):
            row = deepcopy(original)
            row.update(mixture_component='expertise', reviewed_for_pilot=True, novel_for_pilot=False)
            partitions[split].append(row)
            counts[original['topic']] += 1
        elif split == 'validation' and original['topic'] in validation_topics:
            row = deepcopy(original)
            row.update(mixture_component='expertise', reviewed_for_pilot=True, novel_for_pilot=False)
            partitions[split].append(row)
    counts = Counter()
    for split, original in runtime_review_records(knowledge):
        if split == 'train' and original['topic'] in ('noise_duration', 'lung_direct') and counts[original['topic']] < 2:
            row = deepcopy(original)
            row.update(mixture_component='expertise', reviewed_for_pilot=True, novel_for_pilot=False)
            partitions['train'].append(row)
            counts[original['topic']] += 1
    sensor_rows = [json.loads(line) for line in (sensors / 'train.jsonl').read_text(encoding='utf-8').splitlines()]
    for source in sorted({r['source'] for r in sensor_rows if r['source'].startswith('sensor_')}):
        for original in sorted((r for r in sensor_rows if r['source'] == source), key=lambda r: r['id'])[:2]:
            row = deepcopy(original)
            row.update(mixture_component='expertise', reviewed_for_pilot=True, novel_for_pilot=False)
            partitions['train'].append(row)
    for split, items in zip(('train', 'validation'), authored_dialogues()):
        for index, (question, answer, history) in enumerate(items):
            forecast = ('US AQI: 132.' if split == 'train' and index in (4, 7) else
                        'Nhiệt độ: 26 °C; độ ẩm: 72%.' if split == 'train' and index == 5 else None)
            # The two focused-humidity targets correspond to snapshot indices 4 and 7.
            snapshot_index = 4 if split == 'train' and index == 8 else 7 if split == 'validation' and index == 4 else index
            partitions[split].append(reviewed_record(f'dialogue:{split}:{index}', 'natural_context',
                question, answer, ['project', 'epa_pm', 'epa_indoor_pm', 'nidcd_noise', 'airnow_aqi', 'airnow_particles'],
                component='dialogue', history=history, forecast=forecast, index=snapshot_index))
    partitions['train'].extend(reviewed_external(pool))
    return partitions


def prepare(output, pool=POOL, sensors=SENSORS):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use an empty output directory; previous batches remain immutable')
    recipe_hash = digest(Path(__file__))
    knowledge_path = ROOT / 'data/xanhnon/knowledge.json'
    supplement_path = ROOT / 'data/xanhnon/specialist_supplement.json'
    knowledge = json.loads(knowledge_path.read_text(encoding='utf-8'))
    supplement = json.loads(supplement_path.read_text(encoding='utf-8'))
    partitions = balanced_records(knowledge, supplement, pool, sensors)
    train_mix = Counter(r['mixture_component'] for r in partitions['train'])
    assert train_mix == {'expertise': 70, 'dialogue': 30}, train_mix
    assert len(partitions['validation']) == 20
    cases, case_hash = evaluation_cases(ROOT / 'data/xanhnon/eval_consultation.json')
    forbidden = {normalize(c['question']) for c in cases}
    forbidden.update(normalize(t['content']) for c in cases for t in c.get('history', []) if t['role'] == 'user')
    owners, groups, ids = {}, {}, set()
    for split, rows in partitions.items():
        for row in rows:
            assert row['id'] not in ids, 'Duplicate record'
            ids.add(row['id'])
            assert groups.get(row['group_id'], split) == split, 'Cross-split source group'
            groups[row['group_id']] = split
            assert normalize(row.get('original_question', '')) not in forbidden, row['id']
            for i in range(1, len(row['messages']), 2):
                q, a = row['messages'][i:i+2]
                assert normalize(q['content']) not in forbidden, row['id']
                key = stable_id(normalize(json.dumps([q, a], ensure_ascii=False, sort_keys=True)))
                assert owners.get(key, split) == split, 'Cross-split dialogue pair'
                owners[key] = split
    assert digest(Path(__file__)) == recipe_hash, 'Recipe changed during preparation'
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for split, rows in partitions.items():
        random.Random(42).shuffle(rows)
        path = output / (split + '.jsonl')
        path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        artifacts[path.name] = digest(path)
    sources = {**knowledge['sources'], **supplement['sources']}
    sensor_manifest = json.loads((sensors / 'manifest.json').read_text(encoding='utf-8'))
    manifest = {'schema_version': 1, 'built_at': datetime.now(timezone.utc).isoformat(),
        'require_complete_dialogues': True, 'seed': 42, 'counts': {s: dict(Counter(r['source'] for r in rows)) for s, rows in partitions.items()},
        'mixture_counts': {s: dict(Counter(r['mixture_component'] for r in rows)) for s, rows in partitions.items()},
        'new_dialogue_counts': {s: sum(r['novel_for_pilot'] for r in rows) for s, rows in partitions.items()},
        'required_train_sources': sorted({r['source'] for r in partitions['train']}),
        'required_train_topics': sorted({r.get('topic') for r in partitions['train'] if r.get('topic')}),
        'artifacts_sha256': artifacts, 'environment_sources': sources,
        'sources': [{'id': key, **value} for key, value in sources.items()],
        'rehearsal_sources': sensor_manifest.get('sources', []), 'skipped_sources': [],
        'deduplication': {'duplicate_record_ids_removed': 0, 'cross_split_pairs': 0},
        'training_configuration': {'max_length': 1024, 'epochs': 1, 'learning_rate': .00003, 'start_from_active_release': True},
        'review': {'all_selected_examples_read': True, 'external_examples_rewritten': 6,
                   'unreviewed_pool_copied': False, 'independent_expert_certification': False},
        'input_sha256': {'recipe': recipe_hash, 'knowledge': digest(knowledge_path),
                         'specialist_cases': digest(supplement_path), 'pool_manifest': digest(pool / 'manifest.json'),
                         'sensor_manifest': digest(sensors / 'manifest.json')},
        'evaluation_cases_sha256': case_hash, 'model_activated': False,
        'limitations': ['70/30 is a pilot allocation by record count, not a proven optimal ratio.',
                        'Only six read-and-rewritten language examples are used from the new pool.',
                        'Source-checked project examples are not independent expert certification.',
                        'Synthetic and historical readings are not live measurements.',
                        'Question phrasings share concepts with internal validation; keep the fixed generation suite separate.',
                        'Loss improvement alone cannot qualify the candidate for activation.']}
    save_json(output / 'manifest.json', manifest)
    shutil.copy2(ROOT / 'data/xanhnon/LICENSE-APACHE-2.0.txt', output / 'LICENSE-APACHE-2.0.txt')
    notice = (sensors / 'NOTICE.md').read_text(encoding='utf-8')
    notice += '\n\n# Reviewed 70/30 pilot\n\nProject-authored/source-checked environmental and dialogue examples, plus six explicitly rewritten examples whose source attribution is retained per record. The unreviewed 607-row pool is not copied wholesale.\n'
    for repo, revision in sorted({(r['upstream_repo'], r['upstream_revision']) for r in partitions['train'] if 'upstream_repo' in r}):
        notice += f'\n- https://huggingface.co/datasets/{repo} — revision {revision}; Apache-2.0; questions/replies adapted to the environment application.\n'
    notice += '\nSpecialist source links and project review limitations are recorded in manifest.json.\n'
    (output / 'NOTICE.md').write_text(notice, encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output)
    print(json.dumps({k: result[k] for k in ['counts', 'mixture_counts', 'new_dialogue_counts', 'training_configuration']}, ensure_ascii=False))
