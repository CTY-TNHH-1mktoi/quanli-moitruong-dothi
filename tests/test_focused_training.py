from collections import Counter
import json
import unittest

from chat_briefing import briefing
from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_correction_data import validate_records
from prepare_xanhnon_focused_data import authored_records, records, STORAGE


class FocusedTrainingTests(unittest.TestCase):
    def test_rehearsal_keeps_all_previous_topics_and_frozen_validation(self):
        from prepare_xanhnon_grounded_data import read_rows
        original = STORAGE / 'grounded-v12-data-20261022-reviewed'
        data = records()
        self.assertEqual(len(data['train']), 160)
        self.assertEqual(len(data['validation']), 31)
        self.assertEqual(Counter(r['source'] for r in data['train']),
                         {'environment_grounded_v12': 80, 'environment_focused_v13': 80})
        old = read_rows(original / 'train.jsonl')
        self.assertLessEqual({r['topic'] for r in old}, {r['topic'] for r in data['train']})
        self.assertEqual({r['id'] for r in read_rows(original / 'validation.jsonl')},
                         {r['id'] for r in data['validation'] if r['source'] == 'environment_grounded_v12'})

    def test_new_targets_follow_supplied_numbers_and_time(self):
        for split, rows in authored_records().items():
            for row in rows:
                result = briefing(row['original_question'], row['messages'][1:-2], row['snapshot'])
                answer = row['messages'][-1]['content']
                self.assertEqual(row['messages'][-1]['role'], 'assistant')
                self.assertNotEqual(result['nhiem_vu'], 'hỏi rõ thông tin cần thiết', (split, row['original_question']))
                if row['topic'] == 'humidity_only':
                    self.assertIn(str(result['chung_cu']['DoAm']) + '%', answer)
                    self.assertNotIn('NhietDo', result['chung_cu'])
                elif row['topic'] == 'forecast_air':
                    self.assertIn(str(int(result['chung_cu']['US_AQI'])), answer)
                    self.assertIn('ngày mai', answer)
                elif row['topic'] == 'forecast_weather':
                    self.assertIn(str(result['chung_cu']['NhietDo']), answer)
                    self.assertIn(str(int(result['chung_cu']['DoAm'])) + '%', answer)
                elif row['topic'] == 'missing_aqi':
                    self.assertIsNone(row['snapshot']['DuLieu']['US_AQI'])
                self.assertLessEqual(len(answer.split()), 85)

    def test_known_evaluation_questions_and_histories_stay_outside_training(self):
        cases, _ = evaluation_cases(STORAGE / 'grounded-review-v12-answers-20261022/extra-cases.json')
        validate_records(records(), cases)

    def test_pm25_targets_do_not_rehearse_the_incorrect_size_range(self):
        for rows in authored_records().values():
            for row in rows:
                if row['topic'] in {'pm_size', 'lung_followup'}:
                    answer = row['messages'][-1]['content']
                    self.assertNotIn('10', answer)
                    self.assertIn('phổi', answer)
                    if row['topic'] == 'pm_size':
                        self.assertIn('không quá 2,5', answer)


if __name__ == '__main__':
    unittest.main()
