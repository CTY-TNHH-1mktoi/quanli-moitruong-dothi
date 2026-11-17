import json
import unittest

from chat_knowledge import normalized
from evaluate_xanhnon import evaluation_cases
from prepare_xanhnon_factual_data import corrective_batch,SOURCE
from prepare_xanhnon_runtime_data import SIMULATION_NOTICE
from sensor_training_data import ROOT


class FactualTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.knowledge=json.loads((ROOT/'data/xanhnon/knowledge.json').read_text(encoding='utf-8'))
        cls.rows=corrective_batch(cls.knowledge)

    def test_fixed_evaluation_and_dialogue_pairs_remain_separate(self):
        cases,_=evaluation_cases(ROOT/'data/xanhnon/eval_consultation.json')
        heldout={normalized(case['question']) for case in cases}
        owners={}
        for split,row in self.rows:
            self.assertNotIn(normalized(row['original_question']),heldout)
            for offset in range(1,len(row['messages']),2):
                key=normalized(json.dumps(row['messages'][offset:offset+2],ensure_ascii=False,sort_keys=True))
                self.assertIn(owners.get(key),(None,split),row['group_id'])
                owners[key]=split

    def test_only_source_checked_last_answers_are_supervised(self):
        for split,row in self.rows:
            self.assertTrue(row['supervise_last_assistant_only'])
            self.assertTrue(row['synthetic_context'])
            self.assertTrue(set(row['source_ids'])<=set(self.knowledge['sources']))
            self.assertIn(SIMULATION_NOTICE,row['messages'][-2]['content'])

    def test_factual_targets_do_not_repeat_the_reviewed_unsafe_claims(self):
        for split,row in self.rows:
            if row['source']!=SOURCE:continue
            answer=row['messages'][-1]['content']
            if row['topic']=='noise_correction':
                self.assertIn('giảm thời gian',answer)
                self.assertNotIn('tăng thời gian',answer)
            elif row['topic']=='pm10_correction':
                self.assertIn('không quá 10',answer)
                self.assertIn('không nên coi PM10 là vô hại',answer)
            elif row['topic']=='aqi_correction':
                self.assertIn('Xấu (đỏ)',answer)
                self.assertNotIn('tím',answer)
            elif row['topic']=='concentration_correction':
                self.assertIn('nồng độ PM2.5',answer)
                self.assertIn('Không lấy nguyên',answer)


if __name__=='__main__':
    unittest.main()
