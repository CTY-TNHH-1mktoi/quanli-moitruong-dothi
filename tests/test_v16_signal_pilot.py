import json
from pathlib import Path
import unittest

from chat_briefing_v16 import briefing
from prepare_xanhnon_v16_pilot import EXPECTED, confirmation_cases
from prepare_xanhnon_correction_data import validate_records


DATA = Path('D:/XanhNon-auto-training/qwen3-4b-v16-signal-data-20261024')


class SignalPilotTests(unittest.TestCase):
    def rows(self):
        return {s:[json.loads(line) for line in (DATA/(s+'.jsonl')).read_text(encoding='utf-8').splitlines()]
                for s in ('train','validation')}

    def test_no_target_teaches_guessing_after_missing_evidence(self):
        for rows in self.rows().values():
            for row in rows:
                evidence = briefing(row['original_question'],row['messages'][1:-2],row['snapshot'])
                self.assertNotEqual(evidence['nhiem_vu'],'hỏi rõ thông tin cần thiết')
                if row['topic'] in EXPECTED:
                    self.assertIn(evidence['nhiem_vu'],EXPECTED[row['topic']])
                if row['topic'] == 'selected_location':
                    values = row['snapshot']['DuLieu']
                    self.assertEqual(evidence['chung_cu']['NhietDo'],values['NhietDo'])
                    self.assertEqual(evidence['chung_cu']['DoAm'],values['DoAm'])
                if row['topic'] == 'missing_aqi':
                    self.assertIsNone(row['snapshot']['DuLieu']['US_AQI'])

    def test_confirmation_questions_and_histories_are_excluded_from_sft(self):
        cases = json.loads((DATA/'cases.json').read_text(encoding='utf-8'))
        validate_records(self.rows(),cases)
        self.assertEqual(len(self.rows()['train']),16)
        self.assertEqual(len({r['topic'] for r in self.rows()['train']}),16)
        self.assertEqual(len(cases),24)

    def test_manifest_protects_generation_prompts_too(self):
        from sensor_training_data import digest
        manifest=json.loads((DATA/'manifest.json').read_text(encoding='utf-8'))
        for name,expected in manifest['artifacts_sha256'].items():
            self.assertEqual(digest(DATA/name),expected)

    def test_rubric_catches_cjk_and_unqualified_hypothetical_measurements(self):
        from review_xanhnon_v16_signal import check
        cases={c['id']:c for c in confirmation_cases()}
        row=check(cases['signal_hypothesis'],{'reply':'Ngày mai AQI 186, mức Xấu, nên giảm vận động.','truncated':False},1)
        self.assertIn('hypothesis_not_qualified',row['violations'])
        row=check(cases['signal_presence'],{'reply':'Mình ở đây, 气象.','truncated':False},1)
        self.assertIn('unexpected_CJK_in_Vietnamese_reply',row['violations'])

    def test_rubric_catches_observed_dialogue_regressions(self):
        from review_xanhnon_v16_signal import check
        cases={c['id']:c for c in confirmation_cases()}
        row=check(cases['signal_presence'],{'reply':cases['signal_presence']['question']+' 🌿','truncated':False},1)
        self.assertIn('question_echo_instead_of_direct_answer',row['violations'])
        row=check(cases['signal_missing'],{'reply':'Bạn đang ở Hà Nội. Hãy thử lại sau vài giờ.','truncated':False},1)
        self.assertIn('selected_location_assumed_to_be_user_location',row['violations'])
        self.assertIn('unsupported_retry_interval',row['violations'])
        row=check(cases['signal_why'],{'reply':'Mình cần xem ánh sáng để tư vấn.','truncated':False},1)
        self.assertIn('light_not_present_in_supplied_time_explanation',row['violations'])


if __name__ == '__main__':
    unittest.main()
