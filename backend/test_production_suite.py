# ==============================================================================
# APEX CRM — FINAL PRODUCTION AUTOMATED VERIFICATION SUITE (STEP 6)
# Tests all 16 CRM modules, RBAC security, API error formats, and HTML assets
# ==============================================================================
import unittest
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app import create_app
from backend.config import Config
from database.database import get_db_connection

class TestApexCRMProductionSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        
        # Authenticate Admin
        login_res = cls.client.post('/api/auth/login', json={
            'email': 'admin@crm.local',
            'password': 'Admin@123456'
        })
        data = json.loads(login_res.data)
        assert login_res.status_code == 200, f'Admin login failed: {data}'
        cls.token = data['token']
        cls.auth_headers = {'Authorization': f'Bearer {cls.token}'}

    # 1. Health & Discovery
    def test_01_health_and_api_root(self):
        res = self.client.get('/api/health')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])

        res_root = self.client.get('/')
        self.assertEqual(res_root.status_code, 200)
        data_root = json.loads(res_root.data)
        self.assertEqual(data_root['status'], 'online')

    # 2. Standard Error Handlers (400, 401, 403, 404, 405)
    def test_02_error_handlers(self):
        # 404
        res404 = self.client.get('/api/non_existent_endpoint', headers=self.auth_headers)
        self.assertEqual(res404.status_code, 404)
        d404 = json.loads(res404.data)
        self.assertFalse(d404['success'])
        self.assertEqual(d404['error'], 'Endpoint not found')

        # 405
        res405 = self.client.post('/api/health')
        self.assertEqual(res405.status_code, 405)
        d405 = json.loads(res405.data)
        self.assertFalse(d405['success'])
        self.assertEqual(d405['error'], 'Method not allowed')

        # 401 without auth
        res401 = self.client.get('/api/customers')
        self.assertEqual(res401.status_code, 401)
        d401 = json.loads(res401.data)
        self.assertFalse(d401['success'])

    # 3. Security: Password Hashing in Database
    def test_03_password_hashing_security(self):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT email, password_hash FROM users WHERE status = "active" LIMIT 5')
        users = cursor.fetchall()
        cursor.close()
        conn.close()

        for u in users:
            # Passwords must be hashed using pbkdf2 or scrypt, NEVER plaintext
            self.assertTrue(u['password_hash'].startswith('scrypt:') or u['password_hash'].startswith('pbkdf2:'),
                            f'User {u["email"]} password is not securely hashed!')
            self.assertNotEqual(u['password_hash'], 'Admin@123456')

    # 4. Core CRM: Customers & 360 View
    def test_04_customers_and_notes(self):
        res = self.client.get('/api/customers?page=1&per_page=5', headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get('success', False))
        customers = data.get('customers') or data.get('data', {}).get('customers', [])
        self.assertGreater(len(customers), 0)

        # View customer 360
        cid = customers[0]['id']
        res_detail = self.client.get(f'/api/customers/{cid}', headers=self.auth_headers)
        self.assertEqual(res_detail.status_code, 200)
        detail = json.loads(res_detail.data)
        self.assertTrue('customer' in detail or ('data' in detail and 'customer' in detail['data']))

    # 5. Core CRM: Leads & Pipeline
    def test_05_leads_workflow(self):
        res = self.client.get('/api/leads?status=new', headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get('success', False))

    # 6. Core CRM: Deals Pipeline & Stages
    def test_06_deals_pipeline(self):
        res = self.client.get('/api/deals', headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get('success', False))

    # 7. Core CRM: Tasks, Calls & Meetings
    def test_07_tasks_calls_meetings(self):
        # Tasks
        res_t = self.client.get('/api/tasks', headers=self.auth_headers)
        self.assertEqual(res_t.status_code, 200)

        # Calls
        res_c = self.client.get('/api/calls', headers=self.auth_headers)
        self.assertEqual(res_c.status_code, 200)

        # Meetings
        res_m = self.client.get('/api/meetings', headers=self.auth_headers)
        self.assertEqual(res_m.status_code, 200)

    # 8. Business Modules: Products Catalog
    def test_08_products_module(self):
        res = self.client.get('/api/products', headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get('success', False))

    # 9. Business Modules: Invoices & Accurate Financials
    def test_09_invoices_and_financials(self):
        res = self.client.get('/api/invoices', headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get('success', False))
        invoices = data.get('invoices') or data.get('data', {}).get('invoices', [])
        self.assertGreater(len(invoices), 0)

        # Verify balance calculation
        inv = invoices[0]
        rem = float(inv.get('remaining_amount', 0.0))
        self.assertAlmostEqual(float(inv['total_amount']), float(inv['paid_amount']) + rem, places=2)

    # 10. Business Modules: Payments & Overpayment Protection
    def test_10_payment_overpayment_protection(self):
        res = self.client.get('/api/invoices?status=sent', headers=self.auth_headers)
        data = json.loads(res.data)
        invoices = data.get('invoices') or data.get('data', {}).get('invoices', [])
        if invoices:
            inv = invoices[0]
            excess_amount = float(inv.get('remaining_amount', inv.get('total_amount', 1000))) + 1000.0
            bad_pay = self.client.post('/api/payments', headers=self.auth_headers, json={
                'invoice_id': inv['id'],
                'amount': excess_amount,
                'payment_method': 'bank_transfer',
                'payment_date': '2026-09-22'
            })
            self.assertEqual(bad_pay.status_code, 400)
            pay_resp = json.loads(bad_pay.data)
            self.assertIn('exceeds', pay_resp.get('message', '').lower())

    # 11. Business Modules: Emails & Safe Draft Composition
    def test_11_emails_and_drafts(self):
        res = self.client.get('/api/emails', headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        res_tmpl = self.client.get('/api/emails/templates', headers=self.auth_headers)
        self.assertEqual(res_tmpl.status_code, 200)

    # 12. Notifications Center
    def test_12_notifications_center(self):
        res = self.client.get('/api/notifications', headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        res_count = self.client.get('/api/notifications/unread-count', headers=self.auth_headers)
        self.assertEqual(res_count.status_code, 200)
        data = json.loads(res_count.data)
        self.assertTrue('unread_count' in data or ('data' in data and 'unread_count' in data['data']))

    # 13. Reports Analytics
    def test_13_reports_analytics(self):
        res_summary = self.client.get('/api/dashboard/summary', headers=self.auth_headers)
        self.assertEqual(res_summary.status_code, 200)
        res_sales = self.client.get('/api/reports/sales', headers=self.auth_headers)
        self.assertEqual(res_sales.status_code, 200)
        res_rev = self.client.get('/api/reports/revenue', headers=self.auth_headers)
        self.assertEqual(res_rev.status_code, 200)
        res_leads = self.client.get('/api/reports/leads', headers=self.auth_headers)
        self.assertEqual(res_leads.status_code, 200)

    # 14. User Management & RBAC Permissions
    def test_14_users_and_roles(self):
        res_users = self.client.get('/api/users', headers=self.auth_headers)
        self.assertEqual(res_users.status_code, 200)
        data = json.loads(res_users.data)
        users = data.get('users') or data.get('data', {}).get('users', [])
        # Passwords must NOT be returned in user listings
        for u in users:
            self.assertNotIn('password', u)
            self.assertNotIn('password_hash', u)

        res_roles = self.client.get('/api/roles', headers=self.auth_headers)
        self.assertEqual(res_roles.status_code, 200)

    # 15. System Settings
    def test_15_system_settings(self):
        res_s = self.client.get('/api/settings', headers=self.auth_headers)
        self.assertEqual(res_s.status_code, 200)
        data = json.loads(res_s.data)
        settings = data.get('settings') or data.get('data', {}).get('settings', {})
        self.assertIn('company_name', settings)

    # 16. Frontend HTML Templates Integrity
    def test_16_frontend_html_templates_integrity(self):
        frontend_dir = BASE_DIR / 'frontend'
        templates = [
            'index.html', 'login.html', 'dashboard.html', 'customers.html',
            'customer-details.html', 'leads.html', 'lead-details.html',
            'deals.html', 'tasks.html', 'calls.html', 'meetings.html',
            'products.html', 'invoices.html', 'payments.html', 'emails.html',
            'notifications.html', 'reports.html', 'users.html', 'settings.html'
        ]
        for t in templates:
            file_path = frontend_dir / t
            self.assertTrue(file_path.exists(), f'Template {t} missing!')
            content = file_path.read_text(encoding='utf-8')
            self.assertIn('<meta name="viewport"', content, f'{t} is missing viewport meta tag!')
            self.assertIn('css/responsive.css', content, f'{t} is missing responsive.css!')
            
            # Verify no broken modal structures
            import re
            self.assertNotIn('modal-box', content, f'{t} contains unstyled modal-box class!')
            bad_backdrops = re.findall(r'<div\s+id=[\'"][^\'"]+[\'"]\s+class=[\'"]modal-backdrop[\'"]', content)
            self.assertEqual(len(bad_backdrops), 0, f'{t} has rogue outer modal-backdrop: {bad_backdrops}')

if __name__ == '__main__':
    unittest.main(verbosity=2)
