from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
import requests

from air_quality_map import (AirMapRepository, AirMapUnavailable, MAX_POINTS, VN_TIME,
                             create_air_map_blueprint, make_grid, normalize_samples)


class AirGridTests(unittest.TestCase):
    def test_grid_covers_viewport_with_bounded_work(self):
        for bounds in [(20, 103, 22, 109), (6, 99, 26, 115), (21.01, 105.01, 21.02, 105.02)]:
            lats, lons, step = make_grid(bounds)
            self.assertLessEqual(len(lats) * len(lons), MAX_POINTS)
            self.assertGreaterEqual(len(lats), 2)
            self.assertGreaterEqual(len(lons), 2)
            self.assertGreaterEqual(step, .4)
        lats, lons, _ = make_grid((20, 103, 22, 109))
        self.assertLessEqual(lats[0], 20)
        self.assertGreaterEqual(lats[-1], 22)
        self.assertLessEqual(lons[0], 103)
        self.assertGreaterEqual(lons[-1], 109)

    def test_invalid_and_outside_bounds_do_not_trigger_country_wide_sampling(self):
        for bounds in [(True, 100, 22, 108), (float('nan'), 100, 22, 108), (24, 100, 20, 108), (20, 100, 91, 108)]:
            with self.assertRaises(ValueError):
                make_grid(bounds)
        self.assertEqual(make_grid((40, -80, 45, -70))[:2], ([], []))

    def test_samples_preserve_requested_coordinates_source_time_and_missing_values(self):
        samples = normalize_samples([(21, 105), (22, 106)], [
            {'current': {'time': '2026-10-07T22:00', 'us_aqi': 0, 'pm2_5': 3}},
            {'location_id': 1, 'current': {'time': '2026-10-07T22:00', 'us_aqi': None, 'pm2_5': float('nan')}},
        ], datetime(2026, 10, 7, 22))
        self.assertEqual(samples[0]['US_AQI'], 0)
        self.assertEqual(samples[1]['ViDo'], 22)
        self.assertIsNone(samples[1]['US_AQI'])
        self.assertIsNone(samples[1]['PM25'])
        self.assertEqual(samples[0]['ThoiGianNguon'], '2026-10-07T22:00:00')

    def test_partial_or_misordered_source_responses_are_not_assigned_to_wrong_places(self):
        for payload in [[], [{'location_id': 9}], [{'current': 'bad'}]]:
            with self.assertRaises(AirMapUnavailable):
                normalize_samples([(21, 105)], payload, datetime(2026, 10, 7))


class AirRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()
        self.conn.__enter__.return_value = self.conn
        self.cur = self.conn.cursor.return_value
        self.cur.fetchall.return_value = []
        self.repo = AirMapRepository(lambda: self.conn)

    def test_parallel_same_points_fetch_and_save_once(self):
        response = MagicMock()
        response.json.return_value = {'current': {'time': datetime.now(VN_TIME).replace(tzinfo=None).isoformat(), 'us_aqi': 75, 'pm2_5': 20}}
        with patch('air_quality_map.requests.get', return_value=response) as get:
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: self.repo.get_samples([(21, 105)]), range(4)))
        get.assert_called_once()
        inserts = [call for call in self.cur.execute.call_args_list if 'INSERT INTO' in call.args[0]]
        self.assertEqual(len(inserts), 1)
        self.assertTrue(all(next(iter(result[0].values()))['US_AQI'] == 75 for result in results))

    def test_source_failure_does_not_invent_values_or_write_samples(self):
        with patch('air_quality_map.requests.get', side_effect=requests.ConnectionError('test')):
            with self.assertLogs('air_quality_map', level='ERROR'), self.assertRaises(AirMapUnavailable):
                self.repo.get_samples([(21, 105)])
        self.assertFalse(any('INSERT INTO' in call.args[0] for call in self.cur.execute.call_args_list))


class AirRouteTests(unittest.TestCase):
    def test_invalid_bounds_and_unknown_location_return_400_without_fetching(self):
        app = Flask(__name__)
        app.register_blueprint(create_air_map_blueprint(lambda: None))
        with patch('air_quality_map.requests.get') as get:
            for query in ['location=unknown', 'south=nan&west=100&north=23&east=108', 'south=20', 'south=23&west=100&north=20&east=108']:
                self.assertEqual(app.test_client().get('/api/bando/khongkhi?' + query).status_code, 400)
        get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
