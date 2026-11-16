from collections import Counter
import json
import unittest

from evaluate_xanhnon import evaluation_cases, assess
from prepare_xanhnon_balanced_data import balanced_records, ROOT
from prepare_xanhnon_data import normalize, stable_id
from prepare_xanhnon_runtime_data import SIMULATION_NOTICE


class BalancedTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.knowledge = json.loads((ROOT / 'data/xanhnon/knowledge.json').read_text(encoding='utf-8'))
        cls.supplement = json.loads((ROOT / 'data/xanhnon/specialist_supplement.json').read_text(encoding='utf-8'))
        cls.data = balanced_records(cls.knowledge, cls.supplement)

    def test_requested_mix_and_reviewed_subset(self):
        self.assertEqual(Counter(r['mixture_component'] for r in self.data['train']),
                         {'expertise': 70, 'dialogue': 30})
        self.assertEqual(len(self.data['validation']), 20)
        adapted = [r for r in self.data['train'] if r.get('original_pool_record_id')]
        self.assertEqual(len(adapted), 6)
        self.assertTrue(all(r['reviewed_for_pilot'] for rows in self.data.values() for r in rows))
        self.assertTrue(all(r['review'] != 'automatic_rules_only' for rows in self.data.values() for r in rows))

    def test_source_groups_and_dialogue_pairs_do_not_cross_splits(self):
        pair_owners, group_owners = {}, {}
        for split, rows in self.data.items():
            for row in rows:
                self.assertEqual(group_owners.get(row['group_id'], split), split)
                group_owners[row['group_id']] = split
                for offset in range(1, len(row['messages']), 2):
                    key = stable_id(normalize(json.dumps(row['messages'][offset:offset + 2], ensure_ascii=False, sort_keys=True)))
                    self.assertEqual(pair_owners.get(key, split), split, row['id'])
                    pair_owners[key] = split

    def test_fixed_generation_questions_and_their_histories_stay_out(self):
        cases, _ = evaluation_cases(ROOT / 'data/xanhnon/eval_consultation.json')
        forbidden = {normalize(case['question']) for case in cases}
        forbidden.update(normalize(t['content']) for c in cases for t in c.get('history', []) if t['role'] == 'user')
        for rows in self.data.values():
            for row in rows:
                self.assertNotIn(normalize(row.get('original_question', '')), forbidden)
                for turn in row['messages']:
                    if turn['role'] == 'user':
                        self.assertNotIn(normalize(turn['content']), forbidden)

    def test_new_examples_have_explicit_simulation_and_mask_history_answers(self):
        for rows in self.data.values():
            for row in rows:
                if not row['novel_for_pilot']:
                    continue
                self.assertTrue(row['supervise_last_assistant_only'])
                self.assertIn(SIMULATION_NOTICE, row['messages'][-2]['content'])
                self.assertLessEqual(len(row['messages'][-1]['content'].split()), 85)

    def test_tomorrow_values_are_supplied_and_not_replaced_by_current_values(self):
        for row in self.data['train']:
            if not row.get('simulated_forecast'):
                continue
            self.assertIn(row['simulated_forecast'], row['messages'][-2]['content'])
            answer = row['messages'][-1]['content']
            self.assertIn('Dự báo', answer)
            if 'US AQI' in row['simulated_forecast']:
                self.assertIn('132', answer)
                self.assertIn('Kém', answer)
                self.assertNotIn(str(row['snapshot']['DuLieu']['US_AQI']), answer)
            else:
                self.assertIn('26 °C', answer)
                self.assertIn('72%', answer)

    def test_all_source_ids_are_accounted_for(self):
        allowed = set(self.knowledge['sources']) | set(self.supplement['sources'])
        allowed |= {'iscape_development', 'iscape_outdoor', 'iscape_workshops', 'beijing_air'}
        for rows in self.data.values():
            for row in rows:
                self.assertTrue(row['source_ids'])
                self.assertLessEqual(set(row['source_ids']), allowed)

    def test_additional_context_cases_stay_out_of_the_training_batch(self):
        extra = json.loads((ROOT / 'data/xanhnon/eval_balanced_extra.json').read_text(encoding='utf-8'))
        self.assertEqual(len(extra), 8)
        forbidden = {normalize(case['question']) for case in extra}
        forbidden.update(normalize(t['content']) for c in extra for t in c.get('history', []) if t['role'] == 'user')
        for rows in self.data.values():
            for row in rows:
                self.assertNotIn(normalize(row.get('original_question', '')), forbidden)
                for turn in row['messages']:
                    if turn['role'] == 'user':
                        self.assertNotIn(normalize(turn['content']), forbidden)

    def test_forecast_evaluation_rejects_today_values(self):
        extra = json.loads((ROOT / 'data/xanhnon/eval_balanced_extra.json').read_text(encoding='utf-8'))
        case = next(c for c in extra if c['id'] == 'balanced_weather_tomorrow_context')
        wrong = assess(case, {'reply': 'Hà Nội hiện 24.8 °C, độ ẩm 95%.', 'truncated': False}, 0)
        right = assess(case, {'reply': 'Theo dự báo minh họa ngày mai: 23.6 °C, độ ẩm 67%.', 'truncated': False}, 0)
        self.assertFalse(wrong['passed'])
        self.assertTrue(right['passed'], right['violations'])


if __name__ == '__main__':
    unittest.main()
