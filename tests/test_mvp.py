import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

from app import ROOT, make_server
from data_loader import Store, load_data


class MVPTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(ROOT/'data', Path(self.temp.name)/'progress.db')
        self.server = make_server(self.store, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.csrf = ''

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def call(self, path, body=None):
        request = urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}'+path,
                                         data=json.dumps(body).encode() if body is not None else None,
                                         headers={'Content-Type': 'application/json', 'X-CSRF-Token': self.csrf})
        try:
            with self.client.open(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code, json.load(exc)

    def login(self, user='E001', password='employee-demo'):
        self.assertEqual(self.call('/api/login', {'user': user, 'password': password})[0], 200)
        self.csrf = self.call('/api/me')[1]['csrf']

    def test_dataset_and_three_profiles(self):
        data = load_data(ROOT/'data')
        self.assertEqual([len(data[k]) for k in ('employees', 'events', 'skills')], [200, 40, 60])
        self.assertEqual(len({h['date'][:7] for h in data['history']}), 24)
        for employee_id in ('E001', 'E002', 'E003'):
            self.login(employee_id)
            code, p = self.call('/api/profile')
            self.assertEqual(code, 200)
            self.assertTrue(1 <= len(p['recommendations']) <= 3)
            for r in p['recommendations']:
                self.assertEqual(len(r['explanations']), 4)
                self.assertGreater(r['expected_gain'], 0)
                self.assertGreaterEqual(sum(v > 0 for v in r['components'].values()), 3)

    def test_progress_persistence_and_idempotency(self):
        self.login()
        before = self.call('/api/profile')[1]
        event = before['recommendations'][0]['event']['id']
        self.assertEqual(self.call('/api/complete', {'event_id': event}), (200, {'updated': True}))
        after = self.call('/api/profile')[1]
        self.assertGreater(after['assessment']['progress'], before['assessment']['progress'])
        self.assertEqual(len(after['history']), len(before['history'])+1)
        self.assertEqual(self.call('/api/complete', {'event_id': event}), (200, {'updated': False}))
        restored = Store(ROOT/'data', self.store.db_path).profile('E001')
        self.assertEqual(restored, after)
        self.assertNotIn(event, [r['event']['id'] for r in after['recommendations']])

    def test_access_and_input(self):
        self.assertEqual(self.call('/api/hr')[0], 401)
        self.assertEqual(self.call('/api/login', {'user': 'HR', 'password': 'bad'})[0], 401)
        self.login()
        self.assertEqual(self.call('/api/hr')[0], 403)
        self.assertEqual(self.call('/api/profile?employee_id=E002')[0], 403)
        self.assertEqual(self.call('/api/complete', {'event_id': 'EV999'})[0], 400)
        self.assertEqual(self.call('/api/complete', {'event_id': 'EV001', 'employee_id': 'E002'})[0], 400)
        self.csrf = 'bad'
        self.assertEqual(self.call('/api/complete', {'event_id': 'EV001'})[0], 403)
        self.login('HR', 'hr-demo')
        self.assertEqual(len(self.call('/api/hr')[1]['employees']), 200)
        self.assertEqual(self.call('/api/complete', {'event_id': 'EV001'})[0], 403)

    def test_empty_catalog_and_closed_gap(self):
        from recommendation_engine import recommend
        p = self.store.profile('E001')
        self.assertEqual(recommend(p['employee'], [], self.store.data['skills'], p['history']), [])
        p['employee']['skills'] = {s['id']: 5 for s in self.store.data['skills']}
        self.assertEqual(recommend(p['employee'], self.store.data['events'], self.store.data['skills'], []), [])


if __name__ == '__main__':
    unittest.main()
