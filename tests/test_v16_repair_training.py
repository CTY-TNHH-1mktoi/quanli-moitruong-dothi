import json
from pathlib import Path
import tempfile
import unittest

from prepare_xanhnon_correction_data import validate_records
from prepare_xanhnon_v16_repair import new_rows,LOCATIONS
from train_xanhnon import adapter_metadata


DATA=Path('D:/XanhNon-auto-training/qwen3-4b-v16-repair-data-20261024-reviewed')


class RepairTrainingTests(unittest.TestCase):
    def test_corrections_keep_roles_numbers_and_evidence_consistent(self):
        rows,audit=new_rows()
        self.assertEqual({s:len(v) for s,v in rows.items()},{'train':24,'validation':8})
        for row in audit:
            answer=row['target'];evidence=row['evidence']
            self.assertNotIn('ánh sáng',answer)
            self.assertNotIn('sau vài giờ',answer)
            self.assertNotIn('Bạn đang ở',answer)
            if row['topic']=='selected_location':
                self.assertIn(f"{evidence['chung_cu']['NhietDo']:g}",answer)
                self.assertIn(str(evidence['chung_cu']['DoAm'])+'%',answer)
            if row['topic']=='explain_own_question':
                self.assertIn('mình',answer.casefold())
                self.assertTrue(any(w in answer for w in ('dữ liệu','dự báo','số đo')))
            if row['topic']=='missing_aqi' and 'dia_diem' not in evidence['chung_cu']:
                self.assertFalse(any(name in answer for _,name in LOCATIONS))

    @unittest.skipUnless(DATA.exists(),'Local repair batch not prepared')
    def test_all_rehearsal_and_new_cases_are_kept_outside_sft(self):
        rows={s:[json.loads(line) for line in (DATA/(s+'.jsonl')).read_text(encoding='utf-8').splitlines()]
              for s in ('train','validation')}
        cases=json.loads((DATA/'cases.json').read_text(encoding='utf-8'))
        validate_records(rows,cases)
        self.assertEqual(len(rows['train']),48)
        self.assertEqual(len({r['topic'] for r in rows['train']}),16)
        self.assertEqual(len(cases),80)

    def test_broader_modules_cannot_be_silently_applied_to_an_old_adapter(self):
        self.assertEqual(adapter_metadata(None)['target_modules'],['q_proj','v_proj'])
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)
            (path/'adapter_config.json').write_text(json.dumps({'r':8,'lora_alpha':16,
                'target_modules':['q_proj','v_proj'],'layers_to_transform':[32,33,34,35]}),encoding='utf-8')
            with self.assertRaises(ValueError):
                adapter_metadata(path,['q_proj','v_proj','o_proj'])

    def test_fresh_case_flags_use_the_same_grounding_guards(self):
        from review_xanhnon_v16_signal import check
        case={'id':'a_new_missing_case','question':'Dữ liệu US AQI bị thiếu thì sao?',
              'selected_location_only':True,'no_retry_interval':True}
        row=check(case,{'reply':'Bạn đang ở Hà Nội. Thử lại sau vài giờ.','truncated':False},1)
        self.assertIn('selected_location_assumed_to_be_user_location',row['violations'])
        self.assertIn('unsupported_retry_interval',row['violations'])


if __name__=='__main__':
    unittest.main()
