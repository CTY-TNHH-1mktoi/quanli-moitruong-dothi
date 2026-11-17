import json
from pathlib import Path
import unittest

from chat_answer_checks import semantic_violations
from chat_briefing_v15 import briefing, compact_messages, PROFILE
from evaluate_xanhnon import assess, evaluation_cases, messages_for
from prepare_xanhnon_correction_data import validate_records
from prepare_xanhnon_grounded_data import read_rows
from prepare_xanhnon_meaning_data import STORAGE, SOURCE, audit, records
from prepare_xanhnon_runtime_data import snapshot_for


class MeaningChecksTests(unittest.TestCase):
    def test_actual_v14_failures_are_rejected(self):
        fixtures = [
            ('Bạn cứ mở cửa phía đường khi ngoài trời nhiều bụi, lau bụi bằng khăn ẩm.', 'unsafe_open_windows_in_dusty_outdoor_air'),
            ('Khi ngoài trời bụi nhiều, bạn nên mở rộng cửa phòng.', 'unsafe_open_windows_in_dusty_outdoor_air'),
            ('PM2.5 là độ ẩm không khí, còn AQI là chỉ số quy đổi.', 'incorrect_PM25_identified_as_humidity'),
            ('Độ ẩm ngày mai Hà Nội 28,2 °C và độ ẩm 61%.', 'incorrect_temperature_unit_assigned_to_humidity'),
            ('Nhiệt độ hiện tại là 72%.', 'incorrect_humidity_unit_assigned_to_temperature'),
            ('Theo EPA (Trung tâm Sức khỏe và Môi trường Hoa Kỳ), PM2.5 có thể vào phổi.', 'invented_EPA_agency_name'),
        ]
        for reply, issue in fixtures:
            with self.subTest(reply=reply):
                self.assertIn(issue, semantic_violations(reply))
                self.assertIn(issue, assess({'id': 'generic', 'question': 'Tư vấn'}, {'reply': reply, 'truncated': False}, 0)['violations'])

    def test_negation_correct_units_and_correct_names_are_not_rejected(self):
        for reply in [
            'Hạn chế mở cửa phía đường khi ngoài trời nhiều bụi; lau bụi bằng khăn ẩm.',
            'Không nên mở cửa khi ngoài trời nhiều bụi.',
            'Khép cửa khi ngoài trời nhiều bụi. Chỉ mở cửa khi không khí ngoài trời sạch hơn.',
            'Chỉ mở cửa khi không khí ngoài trời sạch hơn, còn khi nhiều bụi thì khép lại.',
            'PM2.5 không phải độ ẩm; µg/m³ đo nồng độ bụi.',
            'Hà Nội ngày mai nhiệt độ 28.2 °C, độ ẩm 61%.',
            'Độ ẩm là 61%; nhiệt độ là 28,2 °C.',
            'EPA là Cơ quan Bảo vệ Môi trường Hoa Kỳ.',
        ]:
            self.assertEqual(semantic_violations(reply), [], reply)


class MeaningDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = records()

    def test_all_previous_targets_retained_and_context_rebuilt(self):
        parent = STORAGE / 'rehearsal-v14-data-20261022-reviewed'
        for split, count, new_count in [('train', 336, 64), ('validation', 55, 16)]:
            rows = self.data[split]
            self.assertEqual(len(rows), count)
            self.assertEqual(sum(r['novel_in_v15'] for r in rows), new_count)
            old = {r['id']: r for r in read_rows(parent / (split + '.jsonl'))}
            replay = {r['parent_record_id']: r for r in rows if not r['novel_in_v15']}
            self.assertEqual(set(old), set(replay))
            for key, row in replay.items():
                self.assertEqual(row['messages'][-1], old[key]['messages'][-1])
                self.assertEqual(row['messages'][1:-2], old[key]['messages'][1:-2])
                self.assertEqual(row['prompt_profile'], PROFILE)
            self.assertTrue(all(r['supervise_last_assistant_only'] for r in rows))

    def test_all_targets_pass_the_new_semantic_audit(self):
        audit(self.data)

    def test_exact_48_evaluation_questions_and_histories_stay_outside_sft(self):
        old = json.loads((STORAGE / 'rehearsal-review-v14-answers-20261022/extra-cases.json').read_text(encoding='utf-8'))
        fresh = json.loads((Path(__file__).resolve().parents[1] / 'data/xanhnon/eval_meaning_confirmation.json').read_text(encoding='utf-8'))
        from evaluate_xanhnon import CASES
        self.assertEqual(len(CASES + old + fresh), 48)
        validate_records(self.data, CASES + old + fresh)

    def test_profile_supplies_quantities_and_actions_but_no_final_assistant_reply(self):
        result = briefing('PM2.5, AQI và độ ẩm là cùng một đại lượng hay khác nhau?', (), snapshot_for(0))
        self.assertIn('bụi mịn', result['chung_cu']['phan_biet'])
        weather = briefing('Thời tiết hiện tại ở đây thế nào?', (), snapshot_for(0))
        self.assertEqual(weather['chung_cu']['ten_dai_luong'], {'NhietDo': 'nhiệt độ', 'DoAm': 'độ ẩm'})
        turns = [{'role': 'user', 'content': 'Mình cần giảm bụi phòng gần đường.'}, {'role': 'assistant', 'content': 'Mình sẽ giúp bạn.'}]
        dust = briefing('Chưa có máy lọc thì giảm bụi bằng cách nào?', turns, snapshot_for(0))
        self.assertIn('Khép cửa', dust['chung_cu']['tai_lieu'])
        messages = compact_messages('Nhiệt độ hiện tại là bao nhiêu?', (), snapshot_for(0))
        self.assertEqual(messages[-1]['role'], 'user')
        self.assertFalse(any(m['role'] == 'assistant' for m in messages))

    def test_new_profile_is_available_to_real_generation_evaluation(self):
        case = {'question': 'Thời tiết hiện tại ở đây thế nào?'}
        self.assertEqual(messages_for(case, PROFILE), compact_messages(case['question'], (),
            {'DiaDiem': snapshot_for(0)['DiaDiem'], 'ThoiGian': '2026-10-19T09:00:00',
             'DuLieu': {'US_AQI':175,'PM25':45.4,'PM10':60,'NhietDo':24.8,'DoAm':95,'TiengOn':74.99}}))


if __name__ == '__main__':
    unittest.main()
