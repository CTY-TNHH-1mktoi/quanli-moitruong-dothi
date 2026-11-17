from collections import Counter
import json
import unittest

from chat_briefing import briefing, supplied_future, compact_messages, PROFILE
from evaluate_xanhnon import evaluation_cases, messages_for, assess
from prepare_xanhnon_correction_data import validate_records
from prepare_xanhnon_grounded_data import records, STORAGE
from prepare_xanhnon_runtime_data import snapshot_for


class BriefingTests(unittest.TestCase):
    def test_future_values_come_from_user_next_day_clause_only(self):
        turns = [{'role': 'user', 'content': 'Giả lập: hôm nay US AQI 38, ngày mai 207.'},
                 {'role': 'assistant', 'content': 'Ngày mai AQI 15.'}]
        self.assertEqual(supplied_future(turns, 'Còn mai?')['US_AQI'], 207)
        weather = [{'role': 'user', 'content': 'Hôm nay 31 °C, 88%; ngày mai 24.1 °C, độ ẩm 62%.'}]
        values = supplied_future(weather, 'Nhắc ngày mai nhé.')
        self.assertEqual(values, {'NhietDo': 24.1, 'DoAm': 62})
        self.assertFalse(supplied_future(turns[1:], 'Ngày mai sao?'))

    def test_current_data_replaces_old_hypothesis(self):
        turns = [{'role': 'user', 'content': 'Giả sử US AQI bằng 20.'}, {'role': 'assistant', 'content': 'AQI 20.'}]
        result = briefing('AQI Hà Nội hiện tại là bao nhiêu?', turns, snapshot_for(0))
        self.assertEqual(result['chung_cu']['US_AQI'], 164)
        self.assertEqual(result['chung_cu']['muc'], 'Xấu')

    def test_knowledge_does_not_include_unrequested_snapshot_numbers(self):
        result = briefing('Hạt PM2.5 có kích thước bao nhiêu và vào phổi được không?', (), snapshot_for(0))
        self.assertIn('2,5', result['chung_cu']['tai_lieu'])
        self.assertNotIn('µg/m³', json.dumps(result, ensure_ascii=False))
        self.assertNotIn('US_AQI', result['chung_cu'])

    def test_no_aqi_is_not_filled_from_low_pm25(self):
        snap = snapshot_for(0)
        snap['DuLieu'].update(US_AQI=None, PM25=2)
        result = briefing('Hôm nay không khí có ổn để đi bộ không?', (), snap)
        self.assertIsNone(result['chung_cu']['US_AQI'])
        self.assertNotIn('muc', result['chung_cu'])

    def test_forecast_is_not_fabricated_from_current_data(self):
        result = briefing('Thời tiết ngày mai thế nào?', (), snapshot_for(0))
        self.assertNotIn('NhietDo', result['chung_cu'])
        self.assertIn('chưa có dự báo', result['nhiem_vu'])

    def test_humidity_only_stays_focused_and_greeting_has_no_fake_residence(self):
        result = briefing('Mình chỉ hỏi độ ẩm hiện tại thôi.', (), snapshot_for(0))
        self.assertEqual(result['chung_cu']['DoAm'], 57)
        self.assertNotIn('NhietDo', result['chung_cu'])
        greeting = briefing('Chào Xanh Non, bạn có ở đây không?', (), snapshot_for(0))
        self.assertNotIn('dia_diem', greeting['chung_cu'])
        self.assertIn('giao tiếp', greeting['nhiem_vu'])

    def test_raw_generation_is_still_required_and_context_labels_cannot_leak(self):
        messages = compact_messages('AQI có nghĩa gì?', (), snapshot_for(0))
        self.assertEqual(messages[-1]['role'], 'user')
        self.assertFalse(any(m['role'] == 'assistant' for m in messages))
        result = assess({'id': 'label', 'question': 'AQI'}, {'reply': 'nhiem_vu: đọc chỉ số', 'truncated': False}, 0)
        self.assertIn('internal_context_label_leak', result['violations'])


class GroundedBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = records()

    def test_mixture_rehearsal_and_targets_are_preserved(self):
        self.assertEqual(Counter(r['mixture_component'] for r in self.data['train']), {'expertise': 112, 'dialogue': 48})
        self.assertEqual(len(self.data['validation']), 20)
        self.assertEqual(sum(r['novel_question_and_target'] for r in self.data['train']), 14)
        self.assertEqual(sum(r['source_passage_supplied'] for r in self.data['train']), 26)
        for rows in self.data.values():
            for row in rows:
                self.assertEqual(row['messages'][-1]['role'], 'assistant')
                self.assertTrue(row['supervise_last_assistant_only'])
                self.assertEqual(row['prompt_profile'], PROFILE)
                self.assertLessEqual(len(row['messages'][-1]['content'].split()), 85)

    def test_previous_generation_cases_and_history_pairs_stay_out(self):
        cases, _ = evaluation_cases(STORAGE / 'capacity-review-v11-answers-20261022/extra-cases.json')
        validate_records(self.data, cases)


if __name__ == '__main__':
    unittest.main()
