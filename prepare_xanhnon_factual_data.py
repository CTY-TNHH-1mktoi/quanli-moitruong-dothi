"""Prepare a stronger bounded corrective experiment after v7 answer regression.

The rejected adapter is not continued. Targets come from the project's reviewed
sources; historical sensor rows are rehearsed without downloading duplicates.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import chatbot
from prepare_xanhnon_consultation_data import consultation_records
from prepare_xanhnon_data import make_record
from prepare_xanhnon_review_data import prepare
from prepare_xanhnon_runtime_data import runtime_record, runtime_review_records, snapshot_for
from sensor_training_data import ROOT, digest, save_json


SOURCE = 'environment_factual_v8'


def factual_records(knowledge):
    docs = {doc['id']:doc for doc in knowledge['documents']}
    questions = {
        'noise_correction':[
            'Ở cạnh loa lớn lâu để quen tai là cách bảo vệ tai đúng không?',
            'Muốn bớt ảnh hưởng của nơi ồn thì nên nghe ngắn lại hay tập nghe lâu hơn?',
            'Mình nghe tiếng máy lớn mỗi ngày, nghỉ ở nơi yên có ích hay nên ở lại cho quen?',
            'Để tai quen tiếng lớn, cứ kéo dài thời gian đứng gần nguồn ồn có ổn chứ?'],
        'pm10_correction':[
            'Nhóm hạt PM10 lớn hơn nhóm PM2.5, vậy có thể coi là vô hại hoàn toàn chứ?',
            'Giúp mình sửa quan niệm bụi PM10 không ảnh hưởng sức khỏe vì kích thước lớn.',
            'Giải thích hai giới hạn kích thước của bụi PM và vì sao PM10 vẫn cần chú ý.',
            'Nếu nhớ PM10 có giới hạn đường kính 10 µm thì có được bỏ qua tác động khi hít phải không?'],
        'aqi_correction':[
            'Giả lập US AQI {value}: đọc tên mức và màu, rồi gợi ý điều chỉnh việc vận động.',
            'Với giả định US AQI {value}, mình đang ở mức cảnh báo và màu nào?',
            'Trong ví dụ có US AQI {value}, mình cần hiểu tên mức cùng hoạt động ngoài trời ra sao?',
            'Giả sử chỉ số của Mỹ là US AQI {value}. Mức nào, màu nào và cần điều chỉnh vận động thế nào?'],
        'concentration_correction':[
            'Cảm biến báo PM2.5 {value} µg/m³; có được ghi luôn AQI là {value} trên báo cáo không?',
            'Mình đang nhầm nồng độ PM2.5 {value} µg/m³ với chỉ số AQI {value}, sửa giúp nhé.',
            'Ví dụ máy báo PM2.5 {value} µg/m³, dùng số {value} làm US AQI có chính xác không?',
            'Nếu đọc PM2.5 {value} µg/m³, con số đó có phải chỉ số AQI cùng giá trị không?']}
    result=[]
    for topic, variants in questions.items():
        for index, question in enumerate(variants):
            sources=[]
            if topic == 'noise_correction':
                answer=docs['noise_actions']['answer']
                sources=docs['noise_actions']['source_ids']
            elif topic == 'pm10_correction':
                answer=('PM2.5 gồm hạt có đường kính thường không quá 2,5 µm; PM10 thường không quá 10 µm. '
                        'Cả hai đều có thể được hít vào đường hô hấp, nên không nên coi PM10 là vô hại.')
                sources=['epa_pm']
            elif topic == 'aqi_correction':
                value=[162,193,158,187][index]
                question=question.format(value=value)
                label, advice=chatbot._aqi_guidance(value)
                answer=f'Theo giả định US AQI {value}, mức này là {label} (đỏ). {advice}'
                sources=['airnow_aqi','airnow_particles','project']
            else:
                value=[26,74,97,122][index]
                question=question.format(value=value)
                answer=(f'Không. {value} µg/m³ là nồng độ PM2.5; AQI là chỉ số quy đổi theo quy tắc '
                        'và thời gian lấy trung bình phù hợp. Không lấy nguyên con số nồng độ làm AQI.')
                sources=['epa_pm','airnow_aqi','project']
            _, original=runtime_record(topic,index,question,answer,sources,snapshot_for(index))
            metadata={key:value for key,value in original.items() if key not in ('id','source','group_id','messages')}
            row=make_record(original['messages'][1:],SOURCE,f'factual-v8:{topic}:{index}',**metadata)
            row['messages'][0]['content']=original['messages'][0]['content']
            result.append(('train' if index < 3 else 'validation',row))
    return result


def corrective_batch(knowledge):
    concepts={'concept_aqi','pm_comparison_safe','aqi_boundary','concept_followup','no_filter_followup',
              'clarify_activity_time','clarify_why','current_replaces_assumption','pm_units_not_index'}
    practical={'noise_duration','pm_size','lung_direct'}
    return (factual_records(knowledge)
            + [(split,row) for split,row in consultation_records(knowledge) if row['topic'] in concepts]
            + [(split,row) for split,row in runtime_review_records(knowledge) if row['topic'] in practical])


def prepare_factual_data(destination,sensor_dir):
    knowledge=json.loads((ROOT/'data/xanhnon/knowledge.json').read_text(encoding='utf-8'))
    rows=corrective_batch(knowledge)
    manifest=prepare(destination,sensor_dir,generated=rows,
        training_configuration={'max_length':1024,'epochs':2,'learning_rate':0.00015,
                                'start_from_active_release':True},
        rehearsal_limits={'style_train':16,'advice_train':8,'sensor_train':2,
                          'base_validation':1,'sensor_validation':1})
    manifest.update(new_dialogue_counts=dict(Counter(split for split,row in rows if row['source']==SOURCE)),
                    correction_and_rehearsal_counts=dict(Counter(split for split,row in rows)),
                    review_rationale=['v7 had no net answer gain and regressed on noise exposure duration.',
                                      'Start from the active v2 adapter; do not continue the rejected v7 adapter.',
                                      'Use two epochs and a higher learning rate as an isolated corrective experiment.',
                                      'Retain source-backed facts, multi-turn context, Vietnamese style and four sensor sources.',
                                      'Validation loss alone cannot qualify this candidate for activation.'],
                    training_input={'synthetic_snapshots_explicit':True,'supervision':'final_assistant_turn_only',
                                    'knowledge_sha256':digest(ROOT/'data/xanhnon/knowledge.json'),
                                    'generator_sha256':digest(Path(__file__))})
    save_json(Path(destination)/'manifest.json',manifest)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--sensor-data',type=Path,default=Path('D:/XanhNon-auto-training/sensor-dataset'))
    args=parser.parse_args()
    result=prepare_factual_data(args.output,args.sensor_data)
    print(json.dumps({key:result[key] for key in ['counts','new_dialogue_counts','correction_and_rehearsal_counts','training_configuration']},ensure_ascii=False))
