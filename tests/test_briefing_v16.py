import json
import unittest

from chat_briefing_v15 import briefing as old_briefing
from chat_briefing_v16 import briefing, compact_messages, has_activity_time


class BriefingV16Tests(unittest.TestCase):
    snapshot={'DiaDiem':{'MaDiaDiem':'hanoi','Ten':'Hà Nội'},'DuLieu':{'NhietDo':17.3,'DoAm':63}}

    def test_first_person_is_not_a_nighttime_reference(self):
        for question in ['Tôi muốn chạy bộ ngoài trời, bạn tư vấn giúp.',
                         'Tôi định đi dạo ở công viên.', 'toi muon chay bo ngoai troi',
                         'Tư vấn chạy bộ cho tôi', 'Tu van di bo giup toi']:
            self.assertFalse(has_activity_time(question),question)
            self.assertEqual(briefing(question,snapshot=self.snapshot)['nhiem_vu'],
                             'hỏi thời điểm định hoạt động',question)

    def test_real_time_references_are_preserved(self):
        for question in ['Tôi muốn chạy bộ tối.', 'toi chay bo buoi toi', 'Mình chạy bộ lúc 7 giờ',
                         'Tối nay chạy bộ được không?', 'Mình đi bộ ngày mai',
                         'Tôi chạy bộ 7h30', 'Tôi đi bộ 07:30 ngày 25/10']:
            self.assertTrue(has_activity_time(question),question)

    def test_explicit_aqi_hypotheses_keep_their_evidence_instead_of_asking_for_time(self):
        for value in [75,175,225]:
            question=f'Giả sử US AQI lên {value} thì nên điều chỉnh việc tập ngoài trời ra sao?'
            self.assertEqual(briefing(question,snapshot=self.snapshot),old_briefing(question,snapshot=self.snapshot))
            self.assertEqual(briefing(question,snapshot=self.snapshot)['chung_cu']['US_AQI'],value)

    def test_presence_does_not_replace_an_environmental_question(self):
        self.assertEqual(briefing('Xanh Non ơi, bạn nghe thấy mình chứ?')['nhiem_vu'], 'đáp lại lời gọi trợ lý')
        question='Bạn nghe tiếng ồn lớn lâu có ảnh hưởng không?'
        self.assertNotEqual(briefing(question)['nhiem_vu'],'đáp lại lời gọi trợ lý')

    def test_clarification_keeps_the_assistant_as_the_speaker_who_asked(self):
        turns=[{'role':'user','content':'Mình đang lên kế hoạch đi bộ ở khuôn viên gần nhà.'},
               {'role':'assistant','content':'Bạn định đi vào ngày nào, khoảng mấy giờ?'}]
        result=briefing('Bạn hỏi giờ mình đi để làm gì nhỉ?',turns)
        self.assertEqual(result['chung_cu']['nguoi_da_hoi'],'mình (trợ lý)')
        result=briefing('Bạn hỏi mốc giờ hoạt động để phục vụ việc gì?',turns)
        self.assertEqual(result['chung_cu']['nguoi_da_hoi'],'mình (trợ lý)')

    def test_selected_location_and_readings_are_already_available(self):
        result=briefing('Đọc giúp mình nhiệt độ và độ ẩm của điểm đang được chọn nhé.',snapshot=self.snapshot)
        self.assertEqual(result['chung_cu']['dia_diem'],'Hà Nội')
        self.assertEqual(result['chung_cu']['NhietDo'],17.3)
        self.assertEqual(result['chung_cu']['DoAm'],63)

    def test_casual_future_turn_clarifies_topic_or_keeps_the_previous_one(self):
        question='Bạn cho mình biết hôm tới ra sao với.'
        self.assertEqual(briefing(question)['nhiem_vu'],'hỏi rõ chủ đề')
        turns=[{'role':'user','content':'Tình huống minh họa: ngày mai Hà Nội 21 °C, độ ẩm 61%.'},
               {'role':'assistant','content':'Mình hiểu đây là số liệu minh họa.'}]
        result=briefing(question,turns,self.snapshot)
        self.assertEqual(result['chung_cu']['NhietDo'],21)
        self.assertEqual(result['chung_cu']['DoAm'],61)
        self.assertIn('minh họa',result['chung_cu']['loai_nguon'])

    def test_unit_evidence_and_current_values_stay_distinct(self):
        result=briefing('PM2.5 là đơn vị hay tên loại hạt?',snapshot=self.snapshot)
        self.assertEqual(result['chung_cu']['PM2.5']['loai'],'nhóm hạt bụi mịn')
        self.assertIn('đơn vị nồng độ',result['chung_cu']['µg/m³'])
        result=briefing('PM2.5, AQI và độ ẩm là cùng một đại lượng hay khác nhau?')
        self.assertIn('%',result['chung_cu']['do_am'])
        question='Nồng độ PM2.5 hiện tại bao nhiêu?'
        self.assertEqual(briefing(question,snapshot=self.snapshot),old_briefing(question,snapshot=self.snapshot))
        question='Cho mình xem nhanh thời tiết Hà Nội đang thế nào nhé.'
        self.assertEqual(briefing(question,snapshot=self.snapshot)['chung_cu'],
                         old_briefing(question,snapshot=self.snapshot)['chung_cu'])

    def test_internal_ids_are_not_model_text_but_sources_can_be_requested(self):
        question='Mình nên nghe nhạc lớn lâu hơn để quen tai không?'
        text=json.dumps(compact_messages(question),ensure_ascii=False)
        self.assertNotIn('nidcd_noise',text)
        self.assertNotIn('source_ids',text)
        messages=compact_messages('Cho mình nguồn kiến thức PM2.5 là gì?')
        self.assertIn('https://',messages[-1]['content'])


if __name__=='__main__':
    unittest.main()
