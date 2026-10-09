from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import math
import time
import unittest
from unittest.mock import patch
from unittest.mock import Mock

import app as backend
import chatbot
from environment_reports import build_report
from location_catalog import get_location
from noise_data import aggregate_noise


class LocationIsolationTests(unittest.TestCase):
    def setUp(self):
        self.client = backend.app.test_client()
        self.schema = patch.object(backend.location_store, "ensure_schema")
        self.schema.start()
        self.addCleanup(self.schema.stop)

    def test_history_alerts_and_analysis_filter_the_selected_place(self):
        with patch.object(backend, "query", return_value=[]) as query:
            for path in ["/api/dulieu/moinhat", "/api/dulieu/lichsu", "/api/canhbao", "/api/phantich"]:
                response = self.client.get(path + "?location=tphcm")
                self.assertEqual(response.status_code, 200)
                sql, params = query.call_args.args
                self.assertIn("MaDiaDiem", sql)
                self.assertEqual(params[-1], "tphcm")

    def test_unknown_place_never_falls_back_to_hanoi(self):
        with patch.object(backend, "query") as query, patch.object(backend, "generate_reply") as generate:
            self.assertEqual(self.client.get("/api/capnhat?location=unknown").status_code, 400)
            self.assertEqual(self.client.post("/api/chat", json={"message": "Chào", "location": "unknown"}).status_code, 400)
            query.assert_not_called()
            generate.assert_not_called()

    def test_switching_places_uses_separate_caches(self):
        cache = {identifier: {"time": time.time(), "result": {"DiaDiem": get_location(identifier), "Manguon": value}}
                 for identifier, value in [("hanoi", 1), ("tphcm", 2)]}
        with patch.object(backend, "environment_cache", cache), patch.object(backend, "query") as query:
            self.assertEqual(self.client.get("/api/capnhat?location=tphcm").get_json()["Manguon"], 2)
            self.assertEqual(self.client.get("/api/capnhat").get_json()["Manguon"], 1)
            query.assert_not_called()

    def test_simultaneous_refreshes_save_one_snapshot_per_place(self):
        cache = {}

        def update(location):
            time.sleep(.05)
            result = {"Manguon": 3, "DiaDiem": location}
            cache[location["MaDiaDiem"]] = {"time": time.time(), "result": result}
            return backend.jsonify(result)

        def fetch(_):
            with backend.app.test_client() as client:
                return client.get("/api/capnhat?location=tphcm").get_json()

        with patch.object(backend, "environment_cache", cache), patch.object(backend, "environment_locks", {}), \
                patch.object(backend, "query", return_value=[]), patch.object(backend, "update_environment", side_effect=update) as save:
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(fetch, range(4)))
            save.assert_called_once()
            self.assertTrue(all(result["Manguon"] == 3 for result in results))

    def test_chat_does_not_use_hanoi_readings_for_an_unloaded_city(self):
        hanoi = {"DiaDiem": get_location(), "DuLieu": {"PM25": 999}}
        with patch.object(backend, "environment_cache", {}), patch.object(backend, "last_result", hanoi), \
                patch.object(backend, "generate_reply", return_value={"reply": "Chào"}) as generate:
            self.assertEqual(self.client.post("/api/chat", json={"message": "Chào", "location": "tphcm"}).status_code, 200)
        snapshot = generate.call_args.args[2]
        self.assertEqual(snapshot["DuLieu"], {})
        prompt = chatbot._system_prompt(snapshot)
        self.assertIn("Hồ Chí Minh", prompt)
        self.assertNotIn("999", prompt)
        self.assertNotIn("Cầu Giấy", prompt)

    def test_report_noise_advice_names_the_selected_city(self):
        report = build_report([{"Manguon": 1, "TenNguon": "Open-Meteo TP.HCM",
                                "ThoiGian": "2026-10-07T09:00:00", "TiengOn": 90}],
                              [], 7, datetime(2026, 10, 7, 12), get_location("tphcm"))
        self.assertEqual(report["DiaDiem"]["MaDiaDiem"], "tphcm")
        noise_advice = next(item["NoiDung"] for item in report["QuyHoach"] if "tiếng ồn" in item["TieuDe"])
        self.assertIn("Hồ Chí Minh", noise_advice)
        self.assertNotIn("Cầu Giấy", noise_advice)

    def test_latest_question_includes_selected_readings_and_explicit_missing_noise(self):
        runtime = chatbot.NativeChatbot.__new__(chatbot.NativeChatbot)
        runtime.generate = Mock(return_value={"reply": "Thành phố Hồ Chí Minh", "truncated": False})
        snapshot = {"DiaDiem": get_location("tphcm"), "DuLieu": {"PM25": 45.4, "TiengOn": None}}
        history = [{"role": "user", "content": "Chào"}, {"role": "assistant", "content": "Xin chào"}]
        with patch.object(chatbot, "_load_runtime", return_value=runtime):
            chatbot._generate("Địa điểm đang chọn là gì?", history, snapshot)
        messages = runtime.generate.call_args.args[0]
        self.assertEqual(messages[1:3], history)
        self.assertIn("Hồ Chí Minh", messages[-1]["content"])
        self.assertIn("PM2.5: 45.4", messages[-1]["content"])
        self.assertIn("Tiếng ồn: chưa có dữ liệu", messages[-1]["content"])
        self.assertNotIn("Cầu Giấy", messages[-1]["content"])
        self.assertTrue(messages[-1]["content"].endswith("Địa điểm đang chọn là gì?"))


class NoiseLocationTests(unittest.TestCase):
    def setUp(self):
        self.location = {"ViDo": 21, "KinhDo": 105, "TenKhuVucTiengOn": "Khu thử", "TepTiengOn": "a.areas.geojson"}
        self.cells = [
            {"lat": 21, "lon": 105, "value": value, "weight": weight, "file": filename,
             "first": "2023-01-01T00:00:00Z", "last": "2023-01-02T00:00:00Z"}
            for value, weight, filename in [(60, 1, "a.areas.geojson"), (80, 3, "a.areas.geojson"), (100, 100, "b.areas.geojson")]
        ]

    def test_energy_average_excludes_nearby_cells_from_other_regions(self):
        noise = aggregate_noise(self.cells, self.location, 2)
        expected = round(10 * math.log10((10 ** 6 + 3 * 10 ** 8) / 4), 2)
        self.assertEqual(noise["TiengOn"], expected)
        self.assertEqual((noise["SoO"], noise["SoLanDo"]), (2, 4))
        self.assertEqual(noise["DoGanNhat"], "2023-01-02T00:00:00Z")

    def test_missing_region_is_not_filled_from_another_place(self):
        self.location["TepTiengOn"] = "missing.areas.geojson"
        self.assertIsNone(aggregate_noise(self.cells, self.location, 2))
        self.location.pop("TepTiengOn")
        self.location["ViDo"] = 10
        self.assertIsNone(aggregate_noise(self.cells, self.location, 2))


if __name__ == "__main__":
    unittest.main()
