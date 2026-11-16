import os
import sys
import unittest
import json
import io

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.database import get_db_connection, init_db
from app.spark_engine import SparkWarehouseEngine
from app.seed_data import seed_database

class TestWarehouseSparkSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initializes application and database with test data."""
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        seed_database(reset=True)

    def login_admin(self):
        """Helper to log in as administrator."""
        return self.client.post('/login/admin', data={
            'username': 'admin@warehouse.io',
            'password': 'admin123'
        }, follow_redirects=True)

    def login_user(self):
        """Helper to access standard warehouse staff / user portal without credentials."""
        return self.client.get('/enter/user', follow_redirects=True)

    def logout(self):
        """Helper to clear session."""
        return self.client.get('/logout', follow_redirects=True)

    def test_01_landing_and_portal_selection(self):
        """Tests that landing page displays distinct USER and ADMIN portals with frictionless user access."""
        self.logout()
        res = self.client.get('/landing')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'USER DASHBOARD', res.data)
        self.assertIn(b'ADMIN LOGIN', res.data)
        self.assertIn(b'No Login Credentials Required', res.data)
        self.assertIn(b'/enter/user', res.data)
        self.assertIn(b'/login/admin', res.data)

    def test_02_direct_user_access_and_admin_authentication(self):
        """Tests direct frictionless User access and secure Admin credential authentication."""
        self.logout()

        # 1. Clicking User card or opening /enter/user opens User Dashboard directly without asking for any username, ID or password
        user_res = self.client.get('/enter/user', follow_redirects=True)
        self.assertEqual(user_res.status_code, 200)
        self.assertIn(b'Warehouse Operations Dashboard', user_res.data)
        self.assertIn(b'Staff Operations Portal', user_res.data)
        self.assertIn(b'READ-ONLY ACCESS', user_res.data)

        # 2. Legacy /login/user redirect should route directly into User Dashboard without login prompt
        self.logout()
        legacy_res = self.client.get('/login/user', follow_redirects=True)
        self.assertEqual(legacy_res.status_code, 200)
        self.assertIn(b'Warehouse Operations Dashboard', legacy_res.data)

        # 3. Direct access to /user/dashboard without prior session also opens directly
        self.logout()
        direct_res = self.client.get('/user/dashboard', follow_redirects=True)
        self.assertEqual(direct_res.status_code, 200)
        self.assertIn(b'Warehouse Operations Dashboard', direct_res.data)

        # 4. Admin portal requires valid Admin credentials
        self.logout()
        # Invalid password rejected
        bad_admin = self.client.post('/login/admin', data={
            'username': 'admin@warehouse.io',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        self.assertIn(b'Invalid administrator username/email or password', bad_admin.data)

        # Non-admin rejected from Admin Portal
        user_on_admin = self.client.post('/login/admin', data={
            'username': 'user@warehouse.io',
            'password': 'user123'
        }, follow_redirects=True)
        self.assertIn(b'Access Denied', user_on_admin.data)

        # Valid admin credentials accepted
        admin_res = self.login_admin()
        self.assertEqual(admin_res.status_code, 200)
        self.assertIn(b'Executive Warehouse Dashboard', admin_res.data)
        self.assertIn(b'Chief Warehouse Controller', admin_res.data)

    def test_03_role_based_access_control(self):
        """Verifies that Users cannot access Admin Dashboard or Admin settings by changing URL."""
        self.logout()
        self.login_user()

        # User attempting to access Admin Dashboard via direct URL
        res_admin_dash = self.client.get('/dashboard', follow_redirects=True)
        self.assertIn(b'Access denied', res_admin_dash.data)
        self.assertIn(b'Warehouse Operations Dashboard', res_admin_dash.data)

        # User attempting to access Data Management (CSV Bulk Uploads)
        res_data_mgmt = self.client.get('/data-management', follow_redirects=True)
        self.assertIn(b'Access denied', res_data_mgmt.data)

        # User attempting to access Admin Profile & Cluster Diagnostics
        res_profile = self.client.get('/profile', follow_redirects=True)
        self.assertIn(b'Access denied', res_profile.data)

        # User CAN access their own dashboard and operational modules
        res_user_dash = self.client.get('/user/dashboard')
        self.assertEqual(res_user_dash.status_code, 200)

        res_inv = self.client.get('/inventory')
        self.assertEqual(res_inv.status_code, 200)

        res_risk = self.client.get('/risk-analysis')
        self.assertEqual(res_risk.status_code, 200)

        res_perf = self.client.get('/performance')
        self.assertEqual(res_perf.status_code, 200)

        res_alerts = self.client.get('/alerts')
        self.assertEqual(res_alerts.status_code, 200)

        res_reports = self.client.get('/reports')
        self.assertEqual(res_reports.status_code, 200)

    def test_04_api_role_security_enforcement(self):
        """Verifies backend RBAC: User cannot execute mutations via direct API requests (403 Forbidden)."""
        self.logout()
        self.login_user()

        # 1. User cannot ADD products via API (403)
        res_add = self.client.post('/api/products', json={
            "product_id": "HACK-001",
            "product_name": "Unauthorized Item",
            "category": "Electronics",
            "quantity": 10,
            "unit_price": 50.0,
            "supplier": "Hacker",
            "warehouse_location": "Nowhere",
            "reorder_threshold": 5
        })
        self.assertEqual(res_add.status_code, 403)
        self.assertFalse(json.loads(res_add.data)["success"])

        # 2. User cannot UPDATE products via API (403)
        res_upd = self.client.put('/api/products/PRD-1001', json={"quantity": 9999})
        self.assertEqual(res_upd.status_code, 403)

        # 3. User cannot DELETE products via API (403)
        res_del = self.client.delete('/api/products/PRD-1001')
        self.assertEqual(res_del.status_code, 403)

        # 4. User cannot RECORD stock movements via API (403)
        res_move = self.client.post('/api/transactions', json={
            "product_id": "PRD-1001",
            "transaction_type": "INCOMING",
            "quantity": 100
        })
        self.assertEqual(res_move.status_code, 403)

        # 5. User cannot RESOLVE alerts via API (403)
        res_alert = self.client.post('/api/alerts/1/resolve')
        self.assertEqual(res_alert.status_code, 403)

        # 6. User cannot UPLOAD CSV datasets via API (403)
        res_csv = self.client.post('/api/upload/products', data={})
        self.assertEqual(res_csv.status_code, 403)

        # 7. User CAN READ all analytics & catalog data (200 OK)
        res_dash = self.client.get('/api/analytics/dashboard')
        self.assertEqual(res_dash.status_code, 200)

        res_risk = self.client.get('/api/analytics/risk')
        self.assertEqual(res_risk.status_code, 200)

        res_prods = self.client.get('/api/products')
        self.assertEqual(res_prods.status_code, 200)

        res_txs = self.client.get('/api/transactions')
        self.assertEqual(res_txs.status_code, 200)

        res_alerts = self.client.get('/api/alerts')
        self.assertEqual(res_alerts.status_code, 200)

    def test_05_admin_product_crud(self):
        """Tests admin product creation, retrieval, update, and deletion."""
        self.logout()
        self.login_admin()

        # 1. Create Product
        new_prod = {
            "product_id": "TEST-SKU-999",
            "product_name": "Precision Laser Rangefinder",
            "category": "Electronics",
            "quantity": 40,
            "unit_price": 85.50,
            "supplier": "Leica Geosystems",
            "warehouse_location": "Zone A - Aisle 05 - Bin 110",
            "reorder_threshold": 12
        }
        res_add = self.client.post('/api/products', json=new_prod)
        self.assertEqual(res_add.status_code, 200)
        data_add = json.loads(res_add.data)
        self.assertTrue(data_add["success"])

        # 2. Get Product Detail
        res_get = self.client.get('/api/products/TEST-SKU-999')
        self.assertEqual(res_get.status_code, 200)
        data_get = json.loads(res_get.data)
        self.assertEqual(data_get["product"]["product_name"], "Precision Laser Rangefinder")
        self.assertEqual(data_get["product"]["quantity"], 40)

        # 3. Update Product
        update_data = {
            "product_name": "Precision Laser Rangefinder Pro",
            "quantity": 45,
            "unit_price": 89.99
        }
        res_upd = self.client.put('/api/products/TEST-SKU-999', json=update_data)
        self.assertEqual(res_upd.status_code, 200)
        data_upd = json.loads(res_upd.data)
        self.assertTrue(data_upd["success"])

        # 4. Delete Product
        res_del = self.client.delete('/api/products/TEST-SKU-999')
        self.assertEqual(res_del.status_code, 200)
        data_del = json.loads(res_del.data)
        self.assertTrue(data_del["success"])

    def test_06_stock_transaction_and_inventory_adjustment(self):
        """Tests stock transaction processing and real-time quantity adjustments."""
        self.logout()
        self.login_admin()

        # Check existing product PRD-1001
        res_init = self.client.get('/api/products/PRD-1001')
        initial_qty = json.loads(res_init.data)["product"]["quantity"]

        # Record INCOMING shipment of 20 units
        inbound_tx = {
            "product_id": "PRD-1001",
            "transaction_type": "INCOMING",
            "quantity": 20,
            "reference_no": "TEST-PO-101",
            "notes": "Test Inbound Shipment"
        }
        res_in = self.client.post('/api/transactions', json=inbound_tx)
        self.assertEqual(res_in.status_code, 200)
        new_qty_after_in = json.loads(res_in.data)["new_quantity"]
        self.assertEqual(new_qty_after_in, initial_qty + 20)

        # Record OUTGOING dispatch of 5 units
        outbound_tx = {
            "product_id": "PRD-1001",
            "transaction_type": "OUTGOING",
            "quantity": 5,
            "reference_no": "TEST-SO-202",
            "notes": "Test Outbound Order"
        }
        res_out = self.client.post('/api/transactions', json=outbound_tx)
        self.assertEqual(res_out.status_code, 200)
        new_qty_after_out = json.loads(res_out.data)["new_quantity"]
        self.assertEqual(new_qty_after_out, initial_qty + 20 - 5)

    def test_07_spark_analytics_engine(self):
        """Tests actual Apache Spark processing on warehouse inventory."""
        self.logout()
        self.login_admin()

        res_dash = self.client.get('/api/analytics/dashboard')
        self.assertEqual(res_dash.status_code, 200)
        data_dash = json.loads(res_dash.data)
        self.assertTrue(data_dash["success"])

        summary = data_dash["data"]["summary"]
        self.assertGreater(summary["total_products"], 0)
        self.assertGreater(summary["total_stock_units"], 0)
        self.assertGreater(summary["total_inventory_value"], 0.0)

        # Verify Spark Diagnostics
        spark_info = data_dash["spark"]
        self.assertTrue(spark_info["spark_active"])
        self.assertIn("local", spark_info["master"])

    def test_08_smart_stock_risk_analysis(self):
        """Tests PySpark Smart Stock Risk Analysis computation and risk classification."""
        self.logout()
        self.login_user()

        res = self.client.get('/api/analytics/risk')
        self.assertEqual(res.status_code, 200)
        result = json.loads(res.data)
        self.assertTrue(result["success"])

        data = result["data"]
        self.assertIn("Critical", data["counts"])
        self.assertIn("High", data["counts"])
        self.assertIn("Moderate", data["counts"])
        self.assertIn("Healthy", data["counts"])
        self.assertGreater(data["total_evaluated"], 0)

    def test_09_alerts_management(self):
        """Tests alerts querying and resolution for admin."""
        self.logout()
        self.login_admin()

        res = self.client.get('/api/alerts?status=ACTIVE')
        self.assertEqual(res.status_code, 200)
        result = json.loads(res.data)
        self.assertTrue(result["success"])
        alerts = result["alerts"]
        self.assertGreater(len(alerts), 0)

        first_id = alerts[0]["id"]
        res_resolve = self.client.post(f'/api/alerts/{first_id}/resolve')
        self.assertEqual(res_resolve.status_code, 200)
        self.assertTrue(json.loads(res_resolve.data)["success"])

    def test_10_csv_report_exports(self):
        """Tests downloading CSV reports."""
        self.logout()
        self.login_user()  # Users are allowed to download reports

        reports = ['inventory', 'risk', 'transactions', 'categories']
        for r in reports:
            res = self.client.get(f'/api/export/{r}')
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get('Content-Type'), 'text/csv; charset=utf-8')
            self.assertGreater(len(res.data), 50)

if __name__ == '__main__':
    unittest.main()
