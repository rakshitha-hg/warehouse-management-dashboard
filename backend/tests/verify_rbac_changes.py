import os
import sys
import unittest
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.seed_data import seed_database

class TestRBACSpecifics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        seed_database(reset=False)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_user_login_page_is_completely_removed(self):
        """Confirms template is deleted and GET /login/user redirects to /enter/user."""
        template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'templates', 'login_user.html')
        self.assertFalse(os.path.exists(template_path), "login_user.html should be removed!")

        self.logout()
        res = self.client.get('/login/user', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/enter/user', res.headers.get('Location'))

    def test_one_click_user_card_opens_dashboard_without_credentials(self):
        """Confirms clicking the User card directly accesses the User dashboard without prompts."""
        self.logout()
        # Direct call to /enter/user
        res = self.client.get('/enter/user', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Warehouse Operations Dashboard', res.data)
        self.assertIn(b'Staff Operations Portal', res.data)
        self.assertIn(b'READ-ONLY ACCESS', res.data)

        # Confirm session is established as User
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('role'), 'User')

    def test_unauthenticated_direct_access_to_user_dashboard(self):
        """Direct access to /user/dashboard without prior session also opens directly without prompting for password."""
        self.logout()
        res = self.client.get('/user/dashboard', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Warehouse Operations Dashboard', res.data)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('role'), 'User')

    def test_admin_requires_credentials(self):
        """Admin dashboard cannot be accessed without entering admin credentials."""
        self.logout()
        # Direct URL access to /dashboard without login redirects to /login/admin
        res = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login/admin', res.headers.get('Location'))

        # Login page is rendered
        res_page = self.client.get('/login/admin')
        self.assertEqual(res_page.status_code, 200)
        self.assertIn(b'Administrator Portal', res_page.data)
        self.assertIn(b'Warehouse Controller Sign In', res_page.data)

        # Submitting correct credentials grants access
        res_post = self.client.post('/login/admin', data={
            'username': 'admin@warehouse.io',
            'password': 'admin123'
        }, follow_redirects=True)
        self.assertEqual(res_post.status_code, 200)
        self.assertIn(b'Executive Warehouse Dashboard', res_post.data)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('role'), 'Administrator')

    def test_user_cannot_access_admin_urls(self):
        """Users are blocked from accessing admin URLs and redirected with access denied."""
        self.logout()
        self.client.get('/enter/user', follow_redirects=True)

        admin_routes = ['/dashboard', '/data-management', '/profile']
        for route in admin_routes:
            res = self.client.get(route, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b'Access denied', res.data)
            self.assertIn(b'Warehouse Operations Dashboard', res.data)

    def test_user_cannot_call_mutating_apis(self):
        """Users are blocked with 403 Forbidden on all mutating backend APIs."""
        self.logout()
        self.client.get('/enter/user', follow_redirects=True)

        mutations = [
            ('POST', '/api/products', {"product_id": "X"}),
            ('PUT', '/api/products/PRD-1001', {"quantity": 10}),
            ('DELETE', '/api/products/PRD-1001', None),
            ('POST', '/api/transactions', {"product_id": "PRD-1001"}),
            ('POST', '/api/alerts/1/resolve', None),
            ('POST', '/api/alerts/resolve-all', None),
            ('POST', '/api/upload/products', {}),
            ('POST', '/api/upload/transactions', {}),
            ('POST', '/api/demo/reset', {})
        ]

        for method, endpoint, payload in mutations:
            if method == 'POST':
                res = self.client.post(endpoint, json=payload if payload is not None else {})
            elif method == 'PUT':
                res = self.client.put(endpoint, json=payload)
            elif method == 'DELETE':
                res = self.client.delete(endpoint)
            self.assertEqual(res.status_code, 403, f"{method} {endpoint} should return 403 Forbidden for User")
            data = json.loads(res.data)
            self.assertFalse(data['success'])
            self.assertIn('Administrator privileges required', data['error'])

    def test_user_can_access_all_read_only_modules(self):
        """Users can access all operational dashboards, catalog, risk, movement, performance, alerts, and reports."""
        self.logout()
        self.client.get('/enter/user', follow_redirects=True)

        read_routes = ['/inventory', '/risk-analysis', '/movement-intelligence', '/performance', '/alerts', '/reports']
        for route in read_routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"User should be able to access {route}")

if __name__ == '__main__':
    unittest.main()
