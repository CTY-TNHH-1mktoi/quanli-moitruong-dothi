from collections import Counter, defaultdict
import json
from pathlib import Path
import tempfile
import unittest

from evaluate_xanhnon import assess, evaluation_cases, load_comparison, ASSESSMENT_VERSION
from prepare_xanhnon_correction_data import correction_records, validate_records, ROOT
from review_xanhnon_after_training import review_cases


def extra_cases():
    result = []
    for name in ('eval_consultation.json', 'eval_balanced_extra.json', 'eval_correction_confirmation.json'):
        result.extend(json.loads((ROOT / 'data/xanhnon' / name).read_text(encoding='utf-8')))
    return result


class CorrectionTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = correction_records()

    def test_mix_and_all_contexts_retained(self):
        self.assertEqual(Counter(r['mixture_component'] for r in self.data['train']), {'expertise': 84, 'dialogue': 36})
        self.assertEqual(Counter(r['mixture_component'] for r in self.data['validation']), {'expertise': 14, 'dialogue': 6})
        for rows in self.data.values():
            for row in rows:
                self.assertTrue(row['supervise_last_assistant_only'])
                self.assertLessEqual(len(row['messages'][-1]['content'].split()), 85)

    def test_questions_and_history_pairs_do_not_leak_into_confirmation_or_validation(self):
        from evaluate_xanhnon import CASES
        validate_records(self.data, CASES + extra_cases())

    def test_paired_question_answers_change_with_supplied_values(self):
        for topic in ('history_weather', 'history_future_aqi', 'current_weather', 'current_over_history'):
            grouped = defaultdict(set)
            for row in self.data['train']:
                if row['topic'] == topic:
                    grouped[row['original_question']].add(row['messages'][-1]['content'])
            self.assertEqual(len(grouped), 3)
            self.assertTrue(all(len(answers) == 2 for answers in grouped.values()), topic)

    def test_missing_aqi_prompt_does_not_supply_a_valid_current_value(self):
        for rows in self.data.values():
            for row in rows:
                if row['topic'] == 'missing_aqi':
                    self.assertIsNone(row['snapshot']['DuLieu']['US_AQI'])
                    self.assertNotIn('Mức US AQI:', row['messages'][-2]['content'])

    def test_noise_targets_do_not_increase_duration_and_ozone_is_explained(self):
        for rows in self.data.values():
            for row in rows:
                answer = row['messages'][-1]['content']
                if row['topic'] == 'noise_duration':
                    result = assess({'id': 'check', 'question': row['original_question'], 'check_noise_duration': True}, {'reply': answer, 'truncated': False}, 0)
                    self.assertTrue(result['passed'], result['violations'])
                    self.assertIn('Giảm thời gian', answer)
                if row['topic'] == 'ozone':
                    self.assertIn('kích ứng phổi', answer)

    def test_correct_forecast_numbers_with_wrong_day_cannot_pass(self):
        cases = json.loads((ROOT / 'data/xanhnon/eval_balanced_extra.json').read_text(encoding='utf-8'))
        case = next(c for c in cases if c['id'] == 'balanced_weather_tomorrow_context')
        wrong = assess(case, {'reply': 'Hà Nội hôm nay 23.6 °C, độ ẩm 67%.', 'truncated': False}, 0)
        right = assess(case, {'reply': 'Theo dự báo minh họa, Hà Nội ngày mai 23.6 °C, độ ẩm 67%.', 'truncated': False}, 0)
        self.assertFalse(wrong['passed'])
        self.assertIn('wrong_time_scope_for_tomorrow', wrong['violations'])
        self.assertTrue(right['passed'], right['violations'])

    def test_prose_is_not_mistaken_for_mechanical_heading(self):
        for text, expected in [('Chưa thể kết luận về bụi chỉ từ một số đo.', True),
                               ('Kết luận: chưa đủ dữ liệu.', False)]:
            self.assertEqual(assess({'id': 'sensor', 'question': 'Cảm biến'}, {'reply': text, 'truncated': False}, 0)['passed'], expected)

    def test_reviewer_keeps_old_cases_and_adds_eight_confirmation_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'extra.json'
            path.write_text(json.dumps(extra_cases(), ensure_ascii=False), encoding='utf-8')
            cases, fingerprint, coverage = review_cases(path)
            self.assertEqual(len(cases), 36)
            self.assertEqual(coverage, {'development_regression_cases': 28, 'additional_confirmation_cases': 8})
            self.assertEqual(len(fingerprint), 64)
            _, _, reused_coverage = review_cases(path, all_development=True)
            self.assertEqual(reused_coverage, {'development_regression_cases': 36, 'additional_confirmation_cases': 0})
            path.write_text(json.dumps(extra_cases()[1:], ensure_ascii=False), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'previous 28'):
                review_cases(path)

    def test_old_scoring_or_changed_questions_cannot_reuse_a_baseline(self):
        cases, fingerprint = evaluation_cases()
        baseline = {'evaluation_scope': 'raw', 'cases': cases, 'cases_sha256': fingerprint,
                    'assessment_version': ASSESSMENT_VERSION}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'baseline.json'
            path.write_text(json.dumps(baseline), encoding='utf-8')
            load_comparison(path, 'raw', cases)
            changed = [dict(c) for c in cases]
            changed[0]['question'] = 'Changed question with identical ID'
            with self.assertRaisesRegex(ValueError, 'fresh baseline'):
                load_comparison(path, 'raw', changed)
            baseline['assessment_version'] -= 1
            path.write_text(json.dumps(baseline), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'fresh baseline'):
                load_comparison(path, 'raw', cases)


if __name__ == '__main__':
    unittest.main()
