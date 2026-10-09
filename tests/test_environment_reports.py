from datetime import datetime
import json
import unittest
from unittest.mock import patch

from flask import Flask
import pyodbc

from environment_reports import build_report, create_report_blueprint


class ReportAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 7, 12)
        self.rows = [
            {"Manguon": 1, "TenNguon": "Open-Meteo Hà Nội", "ThoiGian": "2026-10-07T09:00:00",
             "PM25": 10, "PM10": 20, "NhietDo": 28, "DoAm": 60, "TiengOn": 80},
            {"Manguon": 2, "TenNguon": "Open-Meteo Hà Nội", "ThoiGian": "2026-10-07T11:00:00",
             "PM25": 50, "PM10": 120, "NhietDo": 36, "DoAm": 90, "TiengOn": 90},
        ]
        self.alerts = [
            {"Macanhbao": 1, "Manguon": 2, "LoaiCanhBao": "PM2.5", "MucDo": "Trung bình",
             "NoiDung": "Bụi cao", "ThoiGian": "2026-10-07T11:00:00"},
            {"Macanhbao": 2, "Manguon": 2, "LoaiCanhBao": "Tiếng ồn", "MucDo": "Cao",
             "NoiDung": "Tiếng ồn tổng hợp cao", "ThoiGian": "2026-10-07T11:00:00"},
        ]

    def test_statistics_and_alert_percentages_use_correct_denominators(self):
        report = build_report(self.rows, self.alerts, 1, self.now)
        pm = report["ChiSo"][0]
        self.assertEqual((pm["TrungBinh"], pm["ThapNhat"], pm["CaoNhat"], pm["ThayDoi"]), (30, 10, 50, 40))
        self.assertEqual(pm["TyLeNguongLuuY"], 50)
        self.assertEqual(report["TongQuan"]["SoCanhBao"], 2)
        self.assertEqual(report["TongQuan"]["SoCanhBaoCao"], 1)
        self.assertEqual(report["TongQuan"]["TyLeBanGhiCoCanhBao"], 50)
        self.assertEqual(len(report["XuHuong"]), 2)
        self.assertTrue(report["QuyHoach"] and report["XuLySuCo"])

    def test_missing_and_nonfinite_values_are_not_zero_or_json_nan(self):
        self.rows[0]["PM25"] = None
        self.rows[1]["PM25"] = float("nan")
        report = build_report(self.rows, [], 7, self.now)
        pm = report["ChiSo"][0]
        self.assertEqual(pm["SoBanGhi"], 0)
        self.assertIsNone(pm["TrungBinh"])
        self.assertIsNone(pm["TyLeNguongLuuY"])
        self.assertIsNone(pm["ThayDoi"])
        json.dumps(report, allow_nan=False)

    def test_noise_is_not_averaged_as_arithmetic_decibels(self):
        noise = build_report(self.rows, [], 7, self.now)["ChiSo"][-1]
        self.assertIsNone(noise["TrungBinh"])
        self.assertIsNone(noise["ThayDoi"])
        self.assertEqual(noise["GanNhat"], 90)
        self.assertEqual(noise["LoaiDuLieu"], "tong_hop_khu_vuc")

    def test_empty_period_is_not_reported_as_safe(self):
        report = build_report([], self.alerts, 30, self.now)
        self.assertEqual(report["TongQuan"]["MucUuTien"], "Chưa có dữ liệu")
        self.assertIsNone(report["TongQuan"]["TyLeBanGhiCoCanhBao"])
        self.assertEqual(report["CanhBao"], [])
        self.assertIn("Không có bản ghi", report["GhiChu"][0])

    def test_hourly_and_daily_buckets_preserve_missing_dates(self):
        report = build_report(self.rows, [], 7, self.now)
        self.assertEqual(len(report["XuHuong"]), 1)
        self.assertEqual(report["XuHuong"][0]["TrungBinhPM25"], 30)
        self.assertEqual(report["XuHuong"][0]["SoBanGhiPM25"], 2)


class ReportRouteTests(unittest.TestCase):
    def setUp(self):
        self.repository_patch = patch("environment_reports.ReportRepository")
        self.repository = self.repository_patch.start().return_value
        self.addCleanup(self.repository_patch.stop)
        application = Flask(__name__)
        application.register_blueprint(create_report_blueprint(lambda: None, lambda cursor: []))
        self.client = application.test_client()

    def test_invalid_periods_do_not_create_database_reports(self):
        for days in [None, True, "7", 0, 2, 31, []]:
            self.assertEqual(self.client.post("/api/baocao", json={"days": days}).status_code, 400)
        self.repository.create.assert_not_called()

    def test_save_and_reopen_use_the_stored_snapshot(self):
        saved = {"MaBaoCao": 17, "TongQuan": {"SoBanGhi": 42}, "SoNgay": 7}
        self.repository.create.return_value = saved
        self.repository.get.return_value = saved
        created = self.client.post("/api/baocao", json={"days": 7})
        reopened = self.client.get("/api/baocao/17")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.get_json(), reopened.get_json())
        self.repository.create.assert_called_once_with(7, "hanoi")
        self.repository.get.assert_called_once_with(17, "hanoi")

    def test_selected_place_is_sent_to_every_repository_operation(self):
        self.repository.create.return_value = {"MaBaoCao": 18}
        self.repository.list.return_value = []
        self.repository.get.return_value = None
        self.assertEqual(self.client.post("/api/baocao", json={"days": 7, "location": "tphcm"}).status_code, 201)
        self.assertEqual(self.client.get("/api/baocao?location=tphcm&offset=10").status_code, 200)
        self.assertEqual(self.client.get("/api/baocao/17?location=tphcm").status_code, 404)
        self.repository.create.assert_called_once_with(7, "tphcm")
        self.repository.list.assert_called_once_with(10, 10, "tphcm")
        self.repository.get.assert_called_once_with(17, "tphcm")

    def test_unknown_place_does_not_read_or_save_a_report(self):
        for path in ["/api/baocao?location=unknown", "/api/baocao/17?location=unknown"]:
            self.assertEqual(self.client.get(path).status_code, 400)
        self.assertEqual(self.client.post("/api/baocao", json={"days": 7, "location": "unknown"}).status_code, 400)
        self.repository.create.assert_not_called()
        self.repository.list.assert_not_called()
        self.repository.get.assert_not_called()

    def test_unknown_saved_report_returns_404(self):
        self.repository.get.return_value = None
        self.assertEqual(self.client.get("/api/baocao/9999").status_code, 404)

    def test_sql_failure_does_not_claim_a_report_was_saved(self):
        self.repository.create.side_effect = pyodbc.Error("private server details")
        with self.assertLogs(level="ERROR"):
            response = self.client.post("/api/baocao", json={"days": 7})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private", response.get_json()["loi"])


if __name__ == "__main__":
    unittest.main()
