from collections import defaultdict
import json
import unittest

from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_correction_data import validate_records
from prepare_xanhnon_grounded_data import read_rows
from prepare_xanhnon_rehearsal_data import STORAGE, SOURCE, audit, new_records, records


class RehearsalTrainingTests(unittest.TestCase):
    def test_every_prior_record_is_retained_once(self):
        data = records()
        for split, count in [('train', 272), ('validation', 39)]:
            self.assertEqual(len(data[split]), count)
            ids = {r['id'] for r in data[split]}
            self.assertEqual(len(ids), count)
            for folder in ('grounded-v12-data-20261022-reviewed', 'focused-v13-data-20261022-reviewed'):
                self.assertLessEqual({r['id'] for r in read_rows(STORAGE / folder / (split + '.jsonl'))}, ids)
        self.assertEqual(sum(r['source'] == SOURCE for r in data['train']), 32)

    def test_identical_weather_question_follows_changed_supplied_numbers(self):
        questions = defaultdict(list)
        for row in new_records()['train']:
            if row['topic'] == 'current_weather_reading':
                questions[row['original_question']].append(row)
        self.assertEqual(len(questions), 4)
        for pair in questions.values():
            self.assertEqual(len(pair), 2)
            self.assertNotEqual(pair[0]['messages'][-1], pair[1]['messages'][-1])
            for row in pair:
                answer = row['messages'][-1]['content']
                self.assertIn(str(row['snapshot']['DuLieu']['NhietDo']), answer)
                self.assertIn(str(row['snapshot']['DuLieu']['DoAm']) + '%', answer)
                self.assertNotIn('AQI', answer)

    def test_missing_current_aqi_does_not_reuse_an_old_valid_aqi(self):
        data = new_records()
        audit(data)
        for rows in data.values():
            for row in rows:
                if row['topic'] == 'missing_current_aqi':
                    self.assertIsNone(row['snapshot']['DuLieu']['US_AQI'])
                    self.assertIn('thời điểm cũ', row['messages'][2]['content'])
                    self.assertIn('chưa có US AQI hiện tại', row['messages'][-1]['content'])

    def test_no_exact_evaluation_question_history_or_pair_leak(self):
        cases, _ = evaluation_cases(STORAGE / 'focused-review-v13-answers-20261022/extra-cases.json')
        validate_records(records(), cases)
        for split, rows in new_records().items():
            pairs = [json.dumps(r['messages'], ensure_ascii=False, sort_keys=True) for r in rows]
            self.assertEqual(len(pairs), len(set(pairs)), split)


if __name__ == '__main__':
    unittest.main()
