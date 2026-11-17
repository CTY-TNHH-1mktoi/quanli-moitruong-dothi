import unittest

from review_xanhnon_4b_lora import checked_answer


class FourbReviewTests(unittest.TestCase):
    def review(self, reply, **options):
        return checked_answer({'id':'fourb_unit_new','question':'Phân biệt tên bụi và đơn vị.'},
                              {'reply':reply,'truncated':options.get('truncated',False)},0)

    def test_quantity_unit_confusion_is_rejected_even_when_old_rubric_passes(self):
        row=self.review('PM2.5 là đơn vị đo nồng độ bụi.')
        self.assertTrue(row['original_rubric_passed'])
        self.assertFalse(row['passed'])
        self.assertIn('PM25_incorrectly_called_a_unit',row['violations'])

    def test_correct_explanation_and_negated_incorrect_label_are_accepted(self):
        for reply in ['PM2.5 là nhóm hạt bụi; µg/m³ là đơn vị nồng độ.',
                      'Không nên gọi PM2.5 là đơn vị đo nồng độ.',
                      'Đừng coi PM2.5 là đơn vị đo.']:
            self.assertTrue(self.review(reply)['passed'],reply)

    def test_empty_or_incomplete_output_is_a_failed_case(self):
        self.assertIn('empty_generation',self.review('')['violations'])
        self.assertIn('truncated_generation',self.review('PM2.5 là bụi',truncated=True)['violations'])

    def test_internal_identifiers_and_wrong_speaker_are_rejected(self):
        self.assertIn('internal_source_or_task_identifier_leak',self.review('Theo nidcd_noise, giảm tiếp xúc tiếng ồn.')['violations'])
        self.assertIn('wrong_speaker_reference',self.review('Bạn đang ở đây, bạn ơi.')['violations'])


if __name__=='__main__':
    unittest.main()
