from collections import Counter
import json
import unittest

from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_consultation_data import consultation_records
from prepare_xanhnon_data import normalize
from prepare_xanhnon_runtime_data import runtime_review_records, SIMULATION_NOTICE
from sensor_training_data import ROOT


class ConsultationTrainingTests(unittest.TestCase):
    def test_history_pairs_do_not_leak_between_training_and_validation(self):
        knowledge = json.loads((ROOT / 'data/xanhnon/knowledge.json').read_text(encoding='utf-8'))
        owners = {}
        for split, row in runtime_review_records(knowledge) + consultation_records(knowledge):
            for offset in range(1, len(row['messages']), 2):
                pair = normalize(json.dumps(row['messages'][offset:offset + 2], ensure_ascii=False, sort_keys=True))
                self.assertIn(owners.get(pair), (None, split), row['group_id'])
                owners[pair] = split

    def test_new_records_are_source_traced_final_turn_targets_without_evaluation_questions(self):
        knowledge = json.loads((ROOT / 'data/xanhnon/knowledge.json').read_text(encoding='utf-8'))
        rows = consultation_records(knowledge)
        cases, _ = evaluation_cases(ROOT / 'data/xanhnon/eval_consultation.json')
        held_out = {case['question'] for case in cases}
        old_questions = {row['original_question'] for _, row in runtime_review_records(knowledge)}
        self.assertEqual(Counter(split for split, _ in rows), {'train': 60, 'validation': 20})
        for split, row in rows:
            self.assertNotIn(row['original_question'], held_out | old_questions)
            self.assertTrue(row['supervise_last_assistant_only'])
            self.assertTrue(row['synthetic_context'])
            self.assertTrue(set(row['source_ids']) <= set(knowledge['sources']))
            self.assertIn(SIMULATION_NOTICE, row['messages'][-2]['content'])
            answer = row['messages'][-1]['content']
            if row['topic'] == 'concept_aqi':
                self.assertIn('AQI là chỉ số', answer)
                self.assertNotIn('chưa có', answer)
            if row['topic'] == 'no_filter_followup':
                self.assertIn('khăn ẩm', answer)
                self.assertNotIn('máy hút bụi', answer)
            if row['topic'] in ('clarify_activity_time', 'clarify_why'):
                self.assertEqual(answer.count('?'), 1)
            if row['topic'] == 'current_replaces_assumption':
                self.assertIn(row['snapshot']['DiaDiem']['Ten'], answer)
                self.assertIn('AQI ' + str(row['snapshot']['DuLieu']['US_AQI']), answer)
            if row['topic'] == 'pm_units_not_index':
                self.assertIn('nồng độ PM2.5', answer)
                self.assertIn('không lấy', answer)
        for split in ('train', 'validation'):
            self.assertEqual(len({row['topic'] for part, row in rows if part == split}), 10)


if __name__ == '__main__':
    unittest.main()
