import json
import unittest

from chat_knowledge import normalized
from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_context_data import context_records
from prepare_xanhnon_consultation_data import consultation_records
from prepare_xanhnon_runtime_data import SIMULATION_NOTICE, runtime_review_records
from sensor_training_data import ROOT


class ContextTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.knowledge = json.loads((ROOT / 'data/xanhnon/knowledge.json').read_text(encoding='utf-8'))
        cls.rows = context_records(cls.knowledge)

    def test_evaluation_questions_and_dialogue_pairs_stay_out_of_training(self):
        cases, _ = evaluation_cases(ROOT / 'data/xanhnon/eval_consultation.json')
        heldout = {normalized(case['question']) for case in cases}
        owners = {}
        for split, row in self.rows + consultation_records(self.knowledge) + runtime_review_records(self.knowledge):
            self.assertNotIn(normalized(row['original_question']), heldout)
            for index in range(1, len(row['messages']), 2):
                pair = json.dumps(row['messages'][index:index + 2], ensure_ascii=False, sort_keys=True)
                self.assertIn(owners.get(pair), (None, split), row['group_id'])
                owners[pair] = split

    def test_targets_are_source_traced_and_simulated_not_self_supervised_chat(self):
        for split, row in self.rows:
            self.assertTrue(row['supervise_last_assistant_only'])
            self.assertTrue(row['synthetic_context'])
            self.assertTrue(row['source_ids'])
            self.assertTrue(set(row['source_ids']) <= set(self.knowledge['sources']))
            self.assertIn(SIMULATION_NOTICE, row['messages'][-2]['content'])
            self.assertNotIn('model_reply', row)

    def test_next_day_uses_provided_forecast_or_acknowledges_its_absence(self):
        for split, row in self.rows:
            if row['topic'] not in ('weather_next_day', 'air_next_day', 'clarified_topic_keeps_day'):
                continue
            payload, answer = [turn['content'] for turn in row['messages'][-2:]]
            self.assertIn('mai', answer)
            if 'chưa cung cấp dự báo' in payload:
                self.assertIn('chưa có dự báo', answer)
                self.assertNotIn('hiện có US AQI', answer)
            else:
                self.assertIn('Theo dự báo được cung cấp', answer)
                self.assertIn('giả lập', payload)
                self.assertNotIn('chưa có', answer)

    def test_unknowns_ask_for_evidence_and_helpful_does_not_erase_context(self):
        for split, row in self.rows:
            answer = row['messages'][-1]['content']
            if row['topic'] in ('unfamiliar_measurement_asks_source', 'clarify_unclear_topic'):
                self.assertEqual(answer.count('?'), 1)
            if row['topic'] == 'context_after_helpful':
                self.assertIn('hữu ích', row['messages'][-4]['content'].lower())
                self.assertIn('khăn ẩm', answer)
                self.assertIn('không bảo đảm', answer)
            if row['topic'] == 'explicit_new_topic':
                self.assertNotIn('bụi', answer)
                self.assertNotIn('AQI', answer)
            if row['topic'] == 'natural_concept_question':
                self.assertNotIn('chưa có', answer)
                self.assertNotIn('không có dữ liệu', answer)


if __name__ == '__main__':
    unittest.main()
