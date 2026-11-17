from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import Mock, patch

import app as backend
import chat_air_data as air
import chatbot
from location_catalog import get_location


class AirDataTests(unittest.TestCase):
    now = datetime(2026, 10, 19, 10, 30, tzinfo=air.VN_TIME)

    @staticmethod
    def data():
        start = datetime(2026, 10, 19)
        return {"utc_offset_seconds": 25200, "current": {"time": "2026-10-19T10:00", "us_aqi": 42},
                "hourly": {"time": [(start + timedelta(hours=i)).isoformat() for i in range(72)],
                           "us_aqi": [42]*24 + [120]*12 + [175]*12 + [50]*24}}

    def test_forecast_is_for_local_tomorrow_not_current_aqi_and_not_rain(self):
        with patch.object(air, "local_now", return_value=self.now), \
                patch.object(chatbot, "get_air_data", return_value=self.data()), \
                patch.object(chatbot, "_load_runtime", side_effect=AssertionError("Use actual forecast")):
            for question in ["mai không khí thế nào", "AQI mai bao nhiêu?", "Sáng mai không khí ra sao?"]:
                reply = chatbot.generate_reply(question, [], {"DiaDiem": get_location("hanoi"), "DuLieu": {"US_AQI": 42}})["reply"]
                self.assertIn("20/10", reply)
                self.assertIn("120", reply)
                self.assertNotIn("42", reply)
                self.assertNotIn("mưa", reply)
                self.assertNotIn("không có dữ liệu", reply)
                self.assertIsNone(chatbot._grounded_reply(question, [], {}))
                self.assertEqual(chatbot._requested_fields(question), ())
            reply = chatbot.generate_reply("Mai có nên đi dạo không?", [], {"DiaDiem": get_location("hanoi")})["reply"]
            self.assertIn("giảm", reply)
            self.assertIn("175", reply)

    def test_time_windows_follow_vietnam_midnight_and_requested_period(self):
        midnight = self.now.replace(hour=0, minute=5)
        start, end = air.forecast_window("Sáng mai không khí thế nào?", midnight)
        self.assertEqual((start.day, start.hour, end.hour), (20, 5, 12))
        self.assertEqual(air.forecast_window("Ngày kia AQI?", midnight)[0].day, 21)
        self.assertEqual(air.forecast_window("Hai giờ nữa AQI?", midnight)[0].hour, 2)
        self.assertIsNone(air.forecast_window("Tuần tới AQI?", midnight))

    def test_forecast_rejects_partial_missing_invalid_or_past_data(self):
        with patch.object(air, "local_now", return_value=self.now):
            window = air.forecast_window("Mai AQI?")
        data = self.data()
        self.assertEqual(len(air.forecast_aqi(data, window)), 24)
        for invalid in [None, True, -1, float("nan"), "120"]:
            data = self.data()
            data["hourly"]["us_aqi"][24] = invalid
            self.assertEqual(air.forecast_aqi(data, window), [])
        data = self.data()
        data["hourly"]["us_aqi"][24:48] = [0]*24
        self.assertEqual([v for _, v in air.forecast_aqi(data, window)], [0]*24)

    def test_cache_is_location_scoped_and_rolls_over_at_midnight(self):
        response = Mock()
        response.json.return_value = self.data()
        with patch.object(air, "_cache", {}), patch.object(air, "local_now", return_value=self.now) as now, \
                patch.object(air.requests, "get", return_value=response) as fetch:
            air.get_air_data(get_location("hanoi"))
            air.get_air_data(get_location("hanoi"))
            self.assertEqual(fetch.call_count, 1)
            air.get_air_data(get_location("tphcm"))
            self.assertEqual(fetch.call_count, 2)
            now.return_value = self.now + timedelta(days=1)
            air.get_air_data(get_location("hanoi"))
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(fetch.call_args.kwargs["params"]["timezone"], "Asia/Ho_Chi_Minh")

    def test_api_failure_does_not_deny_access_to_existing_current_air(self):
        with patch.object(chatbot, "get_air_data", side_effect=air.AirDataUnavailable()), \
                patch.object(air, "local_now", return_value=self.now):
            reply = chatbot.generate_reply("Mai không khí thế nào?", [], {"DuLieu": {"US_AQI": 42}})["reply"]
        self.assertIn("chưa lấy được dự báo", reply)
        self.assertNotIn("không có khả năng", reply)
        self.assertNotIn("42", reply)

    def test_followup_keeps_air_topic_and_forecast_place(self):
        history = [{"role": "user", "content": "AQI Đà Nẵng hiện tại?"},
                   {"role": "assistant", "content": "Chưa rõ."}]
        with patch.object(chatbot, "get_air_data", return_value=self.data()) as fetch, \
                patch.object(air, "local_now", return_value=self.now):
            reply = chatbot.generate_reply("Còn mai?", history, {"DiaDiem": get_location("hanoi")})["reply"]
        self.assertIn("Đà Nẵng", reply)
        self.assertEqual(fetch.call_args.args[0]["MaDiaDiem"], "danang")

    def test_saved_snapshot_restores_air_after_server_restart_without_refresh(self):
        snapshot = {"DiaDiem": get_location("hanoi"), "DuLieu": {"US_AQI": 95}}
        rows = [{"ThoiGian": datetime.now().isoformat(), "ChiTiet": json.dumps(snapshot)}]
        with patch.object(backend, "environment_cache", {}), patch.object(backend, "last_result", None), \
                patch.object(backend.location_store, "ensure_schema"), patch.object(backend, "query", return_value=rows) as query, \
                patch.object(backend, "get_air_data", side_effect=AssertionError("Saved data is fresh")):
            reply = backend.app.test_client().post("/api/chat", json={"message": "Bạn có dữ liệu không khí không?"})
        self.assertEqual(reply.status_code, 200)
        self.assertIn("95 (Trung bình)", reply.get_json()["reply"])
        self.assertEqual(query.call_args.args[1], ("hanoi",))

    def test_saved_other_city_cannot_leak_its_aqi_into_selected_city(self):
        wrong = {"DiaDiem": get_location("tphcm"), "DuLieu": {"US_AQI": 999}}
        rows = [{"ThoiGian": datetime.now().isoformat(), "ChiTiet": json.dumps(wrong)}]
        data = {"LayLuc": self.now.isoformat(), "current": {"us_aqi": 42}}
        with patch.object(backend, "environment_cache", {}), patch.object(backend, "last_result", None), \
                patch.object(backend.location_store, "ensure_schema"), patch.object(backend, "query", return_value=rows), \
                patch.object(backend, "get_air_data", return_value=data):
            snapshot = backend.chat_snapshot(get_location("hanoi"), "AQI hiện tại?", [])
        self.assertEqual(snapshot["DuLieu"]["US_AQI"], 42)
        self.assertNotIn("999", json.dumps(snapshot))

    def test_air_refresh_does_not_relabel_old_weather_as_current(self):
        old = {"DiaDiem": get_location("hanoi"), "ThoiGian": "2026-01-01T00:00:00",
               "DuLieu": {"US_AQI": 175, "NhietDo": 24.8}}
        data = {"LayLuc": self.now.isoformat(), "current": {"us_aqi": 42}}
        with patch.object(backend, "environment_cache", {"hanoi": {"result": old}}), \
                patch.object(backend, "get_air_data", return_value=data):
            snapshot = backend.chat_snapshot(get_location("hanoi"), "AQI hiện tại?", [])
        self.assertEqual(snapshot["DuLieu"]["US_AQI"], 42)
        reply = chatbot.generate_reply("Nhiệt độ hiện tại bao nhiêu?", [], snapshot)["reply"]
        self.assertIn("đã cũ", reply)
        self.assertNotIn("hiện là 24.8", reply)

    def test_screenshot_json_and_stream_match_with_real_forecast_shape(self):
        body = {"message": "mai không khí thế nào", "location": "hanoi"}
        snapshot = {"DiaDiem": get_location("hanoi"), "DuLieu": {"US_AQI": 42}}
        with patch.object(backend, "chat_snapshot", return_value=snapshot), \
                patch.object(chatbot, "get_air_data", return_value=self.data()), \
                patch.object(air, "local_now", return_value=self.now):
            client = backend.app.test_client()
            complete = client.post("/api/chat", json=body)
            streamed = client.post("/api/chat", json={**body, "stream": True}, buffered=True)
        events = [json.loads(line[6:]) for line in streamed.get_data(as_text=True).splitlines() if line.startswith("data: ")]
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(events[-1], {"type": "done", **complete.get_json()})
        self.assertEqual("".join(e["text"] for e in events if e["type"] == "delta"), complete.get_json()["reply"])
