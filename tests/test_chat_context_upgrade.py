"""Exercise real dialogue failures through JSON/SSE and the forecast readers."""
from datetime import datetime,timedelta
import json
import unittest
from unittest.mock import patch

import app as backend
import chatbot
import chat_air_data as air
from chat_scope import OUT_OF_SCOPE_REPLY
from chat_time_context import explicit_clock
from location_catalog import get_location,named_location


class ContextUpgradeTests(unittest.TestCase):
    now=datetime(2026,10,24,12,30,tzinfo=air.VN_TIME)
    snapshot={'DiaDiem':get_location('hanoi'),'DuLieu':{'US_AQI':12,'NhietDo':99,'DoAm':98}}

    @staticmethod
    def history(question,answer):
        return [{'role':'user','content':question},{'role':'assistant','content':answer}]

    def readings(self):
        start=self.now.replace(hour=0,minute=0)
        return {'LayLuc':self.now.isoformat(),'current':{'us_aqi':77},'hourly':{
            'time':[(start+timedelta(hours=i)).isoformat() for i in range(96)],
            'temperature_2m':[22]*96,'relative_humidity_2m':[63]*96,
            'us_aqi':[40 if i%24!=18 else 173 for i in range(96)]}}

    def test_why_variants_do_not_turn_into_an_aqi_reading(self):
        for prompt in ('Bạn dự định đi ngày nào, khoảng mấy giờ?',
                       'Bạn muốn tập ngày nào và lúc mấy giờ?',
                       'Bạn định đi vào ngày nào, khoảng mấy giờ?'):
            turns=self.history('Mình muốn đi bộ.',prompt)
            with patch.object(chatbot,'_load_runtime',side_effect=AssertionError('No model')):
                reply=chatbot.generate_reply('Bạn hỏi giờ mình đi để làm gì nhỉ?',turns,self.snapshot)['reply']
            self.assertIn('số đo hoặc dự báo',reply)
            self.assertNotIn('AQI',reply)
            self.assertFalse(chatbot.needs_environment_data('Bạn hỏi giờ mình đi để làm gì nhỉ?',turns))

    def test_clock_slot_is_retained_when_the_user_answers_the_day(self):
        initial='Mình muốn chạy bộ lúc 18h30, tư vấn giúp.'
        prompt=chatbot.generate_reply(initial,[],self.snapshot)['reply']
        self.assertIn('18:30',prompt)
        turns=self.history(initial,prompt)
        with patch.object(air,'local_now',return_value=self.now),patch.object(chatbot,'get_air_data',return_value=self.readings()),patch.object(chatbot,'_load_runtime',side_effect=AssertionError('No model')):
            reply=chatbot.generate_reply('Ngày mai',turns,self.snapshot)['reply']
        self.assertIn('25/10',reply)
        self.assertIn('18:00–19:00',reply)
        self.assertIn('173',reply)
        self.assertNotIn('40–173',reply)

    def test_hour_reply_keeps_the_day_and_now_clears_the_old_clock(self):
        turns=self.history('Mình muốn đi bộ ngày mai.','Bạn muốn đi lúc mấy giờ?')
        resolved=chatbot._dialogue_question('18:30 nhé',turns)
        self.assertEqual(explicit_clock(resolved),(18,30))
        self.assertIn('ngày mai',chatbot.future_period(resolved))
        turns+=self.history('18:30 nhé','Mình đã xem dự báo theo giờ.')
        current=chatbot._dialogue_question('Còn bây giờ?',turns)
        self.assertIsNone(explicit_clock(current))
        self.assertIsNone(chatbot.future_period(current))

    def test_hourly_windows_do_not_treat_measurements_or_relative_hours_as_clock_times(self):
        self.assertIsNone(explicit_clock('US AQI 180, độ ẩm 63%'))
        self.assertIsNone(explicit_clock('2 giờ nữa'))
        start,end=air.forecast_window('Ngày mai lúc 18h30',self.now)
        self.assertEqual((start.day,start.hour,end.hour),(25,18,19))
        self.assertIsNone(air.forecast_window('Ngày mai lúc 25h',self.now))
        self.assertIsNone(air.forecast_window('Hôm nay lúc 8h',self.now))

    def test_place_change_keeps_forecast_day_across_a_social_turn(self):
        turns=self.history('Thời tiết Hà Nội ngày mai thế nào?','Dự báo Hà Nội ngày mai.')
        turns+=self.history('Cảm ơn nhé','Không có gì nhé!')
        with patch.object(air,'local_now',return_value=self.now),patch.object(chatbot,'get_weather_data',return_value=self.readings()) as fetch,patch.object(chatbot,'_load_runtime',side_effect=AssertionError('No model')):
            first=chatbot.generate_reply('còn Đà Nẵng thì sao?',turns,self.snapshot)['reply']
            turns+=self.history('còn Đà Nẵng thì sao?',first)
            second=chatbot.generate_reply('Còn ngày kia?',turns,self.snapshot)['reply']
        self.assertIn('Đà Nẵng',first)
        self.assertIn('25/10',first)
        self.assertIn('Đà Nẵng',second)
        self.assertIn('26/10',second)
        self.assertEqual(fetch.call_args.args[0]['MaDiaDiem'],'danang')

    def test_current_place_change_reads_the_new_place_and_never_old_numbers(self):
        turns=self.history('Thời tiết Hà Nội hiện tại thế nào?','Số cũ 999.')
        with patch.object(chatbot,'local_now',return_value=self.now),patch.object(chatbot,'get_weather_data',return_value=self.readings()) as fetch,patch.object(chatbot,'_load_runtime',side_effect=AssertionError('No model')):
            reply=chatbot.generate_reply('còn Đà Nẵng thì sao?',turns,self.snapshot)['reply']
        self.assertIn('Đà Nẵng',reply)
        self.assertIn('22 °C',reply)
        self.assertIn('63%',reply)
        self.assertNotIn('99',reply)
        self.assertEqual(fetch.call_args.args[0]['MaDiaDiem'],'danang')
        self.assertEqual(self.snapshot['DiaDiem']['MaDiaDiem'],'hanoi')

    def test_air_place_change_uses_new_current_aqi(self):
        turns=self.history('Không khí Hà Nội hiện tại thế nào?','US AQI 12.')
        with patch.object(chatbot,'get_air_data',return_value=self.readings()) as fetch,patch.object(chatbot,'_load_runtime',side_effect=AssertionError('No model')):
            reply=chatbot.generate_reply('Còn Đà Nẵng?',turns,self.snapshot)['reply']
        self.assertIn('77',reply)
        self.assertIn('Đà Nẵng',reply)
        self.assertEqual(fetch.call_args.args[0]['MaDiaDiem'],'danang')

    def test_city_followup_does_not_resume_after_an_unrelated_request(self):
        turns=self.history('Thời tiết Hà Nội ngày mai?','Đã xem dự báo.')
        turns+=self.history('Viết code Python',OUT_OF_SCOPE_REPLY)
        with patch.object(chatbot,'_load_runtime',side_effect=AssertionError('No environmental inference')),patch.object(chatbot,'get_weather_data',side_effect=AssertionError('No weather request')),patch.object(chatbot,'_conversation_reply',return_value={'reply':'Trả lời theo chủ đề mới.','truncated':False}):
            self.assertEqual(chatbot.generate_reply('Còn Đà Nẵng?',turns,self.snapshot)['reply'],'Trả lời theo chủ đề mới.')
        self.assertEqual(named_location('Hải Châu, Đà Nẵng')['Ten'],'Hải Châu, Đà Nẵng')

    def test_json_and_stream_share_context_resolution(self):
        body={'message':'Còn Đà Nẵng?','location':'hanoi','learn_from_chat':False,
              'history':self.history('Thời tiết Hà Nội ngày mai?','Đã xem dự báo.')}
        with patch.object(air,'local_now',return_value=self.now),patch.object(chatbot,'get_weather_data',return_value=self.readings()),patch.object(backend,'chat_snapshot',return_value=self.snapshot),patch.object(chatbot,'_load_runtime',side_effect=AssertionError('No model')):
            client=backend.app.test_client()
            complete=client.post('/api/chat',json=body)
            stream=client.post('/api/chat',json={**body,'stream':True},buffered=True)
        self.assertEqual(complete.status_code,200)
        events=[json.loads(line[6:]) for line in stream.get_data(as_text=True).splitlines() if line.startswith('data: ')]
        self.assertEqual(events[-1],{'type':'done',**complete.get_json()})
        self.assertIn('Đà Nẵng',complete.get_json()['reply'])


if __name__=='__main__':unittest.main()
