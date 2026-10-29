"""Security regressions: run against original snapshot to demonstrate failures."""
import json
import time
from test_service import ShopTest
from test_http import HttpTest


class SecurityTest(ShopTest):
    def test_anonymous_sensitive_routes(self):
        for path in ('/profile?id=1', '/search', '/orders', '/files', '/debug/logs', '/assistant/context', '/admin/export'):
            with self.subTest(path=path):
                self.assertEqual(self.request('GET', path)[0], 401)

    def test_foreign_access(self):
        auth = self.login()
        for path in ('/profile?id=2', '/assistant/context?order_id=2', '/files?user=bob', '/files?path=../../private/operator-note.txt'):
            with self.subTest(path=path):
                self.assertEqual(self.request('GET', path, headers=auth)[0], 403)
        self.assertTrue(all(row['owner'] == 1 for row in self.request('GET', '/orders', headers=auth)[1]))

    def test_sql_injection(self):
        auth = self.login()
        for path in ('/profile?id=1%20OR%201=1', '/assistant/context?order_id=1%20OR%201=1'):
            self.assertEqual(self.request('GET', path, headers=auth)[0], 400)
        self.assertEqual(self.request('GET', "/search?q=%27%20OR%201=1%20--", headers=auth), (200, []))
        self.assertEqual(len(self.request('GET', '/search', headers=auth)[1]), 1)

    def test_forged_role(self):
        self.assertEqual(self.request('GET', '/admin/export', headers={**self.login(), 'X-Role': 'staff'})[0], 403)
        self.assertEqual(self.request('GET', '/admin/export', headers=self.login('staff', 'learn-staff'))[0], 200)

    def test_price_is_catalog(self):
        for price in (-1, 0, 'free', None):
            self.assertEqual(self.request('POST', '/orders', {'product': 'chair', 'price': price}, self.login())[1]['price'], 5000)

    def test_xss_escaped(self):
        self.request('POST', '/reviews', {'product': 'chair', 'text': '<script>alert(1)</script>'}, self.login())
        result = self.request('GET', '/reviews/view')[1]
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;script&gt;', result)

    def test_log_redaction_and_bounds(self):
        auth = self.login()
        self.assertEqual(self.request('GET', '/debug/logs', headers=auth)[0], 403)
        staff = self.login('staff', 'learn-staff')
        for _ in range(210):
            self.request('GET', '/health?secret=TEST_SECRET')
        raw = json.dumps(self.request('GET', '/debug/logs', headers=staff)[1])
        for secret in ('learn-alice', auth['X-Token'], 'TEST_SECRET'):
            self.assertNotIn(secret, raw)
        self.assertLessEqual(len(self.shop.logs), 200)

    def test_tools_enforce_access(self):
        auth = self.login()
        for tool, args in [('delete_tree', {'path': '.'}), ('export_profiles', {}), ('read_file', {'path': 'private/operator-note.txt'}), ('read_file', {'path': 'files/bob/receipt.txt'}), ('read_file', {'path': 'files/alice/../../private/operator-note.txt'})]:
            self.assertEqual(self.request('POST', '/assistant/execute', {'decision': {'tool': tool, 'arguments': args}}, auth)[0], 403)
        self.assertTrue(self.shop.sandbox.root.exists())
        self.assertEqual(self.request('POST', '/assistant/execute', {'decision': {'tool': 'refuse', 'arguments': {'reason': 'unsafe'}}}, auth)[0], 200)

    def test_malformed_and_expired(self):
        auth = self.login()
        for decision in (None, [], {}, {'tool': [], 'arguments': {}}, {'tool': 'read_file', 'arguments': []}):
            self.assertEqual(self.request('POST', '/assistant/execute', {'decision': decision}, auth)[0], 400)
        self.assertEqual(self.request('POST', '/orders', {'product': []}, auth)[0], 400)
        self.shop.sessions[auth['X-Token']]['expires'] = time.monotonic() - 1
        self.assertEqual(self.request('GET', '/profile', headers=auth)[0], 401)

    def test_review_size_and_login_limit(self):
        auth = self.login()
        self.assertEqual(self.request('POST', '/reviews', {'product': 'chair', 'text': 'x' * 2001}, auth)[0], 400)
        for _ in range(30):
            self.request('POST', '/login', {'username': 'alice', 'password': 'wrong'})
        self.assertEqual(self.request('POST', '/login', {'username': 'alice', 'password': 'wrong'})[0], 429)


class SecurityHttpTest(HttpTest):
    def test_bad_json_shapes_and_headers(self):
        for body in ([], 'bad', 1, None):
            if body is not None:
                self.assertEqual(self.call('POST', '/login', body)[0], 400)
        status, headers, body = self.call('GET', '/health')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertNotIn('type', json.loads(self.call('GET', '/profile?id=bad')[2]))

    def test_raw_http_validation(self):
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        cases = [(b'{', {'Content-Type': 'application/json'}, 400),
                 (b'{}', {'Content-Type': 'text/plain'}, 415),
                 (b'x' * 65537, {'Content-Type': 'application/json'}, 413)]
        for data, headers, expected in cases:
            request = Request(self.base + '/login', data=data, headers=headers, method='POST')
            try:
                response = urlopen(request, timeout=5)
            except HTTPError as exc:
                response = exc
            with response:
                self.assertEqual(response.status, expected)
