"""
Automated Verification Suite for Step 5: Business Modules
Tests Products, Invoices, Payments, Emails, Notifications, Reports, Users, Roles, Settings, and Dashboard.
"""

import os
import sys
import unittest
import json
from pathlib import Path

# Add project root and backend to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "backend"))

from backend.app import create_app
from database.database import execute_query


class TestStep5CRM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

        # Login as admin to get bearer token
        login_res = cls.client.post("/api/auth/login", json={
            "email": "admin@crm.local",
            "password": "Admin@123456"
        })
        data = json.loads(login_res.data)
        assert data.get("success"), f"Admin login failed: {data}"
        cls.token = data["token"]
        cls.headers = {
            "Authorization": f"Bearer {cls.token}",
            "Content-Type": "application/json"
        }

        # Ensure we have at least one customer for testing invoices
        cust_row, _ = execute_query("SELECT id FROM customers LIMIT 1", fetch_one=True)
        if not cust_row:
            c_res = cls.client.post("/api/customers", headers=cls.headers, json={
                "first_name": "Test",
                "last_name": "Client",
                "email": "testclient@step5.local",
                "phone": "9998887776",
                "company_name": "Step5 Corp"
            })
            c_data = json.loads(c_res.data)
            cls.customer_id = c_data["customer"]["id"]
        else:
            cls.customer_id = cust_row["id"]

    # ---------------------------------------------------------
    # 1. PRODUCTS
    # ---------------------------------------------------------
    def test_01_product_lifecycle_and_validations(self):
        # 1a. Validation tests
        res = self.client.post("/api/products", headers=self.headers, json={
            "name": "Invalid Price Prod",
            "price": -50.0
        })
        self.assertEqual(res.status_code, 400)

        res = self.client.post("/api/products", headers=self.headers, json={
            "name": "Invalid Tax Prod",
            "price": 100.0,
            "tax_percentage": 150.0
        })
        self.assertEqual(res.status_code, 400)

        # 1b. Create valid product
        res = self.client.post("/api/products", headers=self.headers, json={
            "name": "CRM Enterprise License",
            "category": "Software",
            "description": "Annual enterprise license",
            "price": 1000.0,
            "tax_percentage": 18.0,
            "discount_percentage": 10.0,
            "stock": 50,
            "status": "active"
        })
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        prod = data["product"]
        self.assertEqual(prod["name"], "CRM Enterprise License")
        self.assertEqual(prod["price"], 1000.0)
        prod_id = prod["id"]

        # 1c. Get single product
        get_res = self.client.get(f"/api/products/{prod_id}", headers=self.headers)
        self.assertEqual(get_res.status_code, 200)
        get_data = json.loads(get_res.data)
        self.assertEqual(get_data["product"]["id"], prod_id)

        # 1d. List and filter products
        list_res = self.client.get("/api/products?category=Software", headers=self.headers)
        self.assertEqual(list_res.status_code, 200)
        list_data = json.loads(list_res.data)
        self.assertGreaterEqual(list_data["data"]["total"], 1)

        # 1e. Update product
        upd_res = self.client.put(f"/api/products/{prod_id}", headers=self.headers, json={
            "name": "CRM Enterprise License v2",
            "price": 1200.0
        })
        self.assertEqual(upd_res.status_code, 200)
        upd_data = json.loads(upd_res.data)
        self.assertEqual(upd_data["product"]["name"], "CRM Enterprise License v2")

        # Keep prod_id for invoice test
        TestStep5CRM.product_id = prod_id

    # ---------------------------------------------------------
    # 2. INVOICES & MULTI-ITEM CALCULATIONS
    # ---------------------------------------------------------
    def test_02_invoice_multi_item_and_calculations(self):
        # Create invoice with 2 items:
        # Item 1: Qty 2, Unit Price 1000, Tax 18%, Disc 10%
        #   base = 2000, tax = 360, disc = 200, total = 2160
        # Item 2: Qty 1, Unit Price 500, Tax 5%, Disc 0%
        #   base = 500, tax = 25, disc = 0, total = 525
        # Expected Invoice:
        #   Subtotal = 2500.00
        #   Tax = 385.00
        #   Discount = 200.00
        #   Total = 2685.00
        #   Remaining = 2685.00
        res = self.client.post("/api/invoices", headers=self.headers, json={
            "customer_id": self.customer_id,
            "invoice_date": "2026-09-22",
            "due_date": "2026-10-07",
            "status": "sent",
            "items": [
                {
                    "product_id": getattr(self, "product_id", None),
                    "description": "Item 1 Description",
                    "quantity": 2,
                    "unit_price": 1000.0,
                    "tax_percentage": 18.0,
                    "discount_percentage": 10.0
                },
                {
                    "description": "Custom Service",
                    "quantity": 1,
                    "unit_price": 500.0,
                    "tax_percentage": 5.0,
                    "discount_percentage": 0.0
                }
            ]
        })
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        inv = data["invoice"]

        self.assertAlmostEqual(inv["subtotal"], 2500.0, places=2)
        self.assertAlmostEqual(inv["tax_amount"], 385.0, places=2)
        self.assertAlmostEqual(inv["discount_amount"], 200.0, places=2)
        self.assertAlmostEqual(inv["total_amount"], 2685.0, places=2)
        self.assertAlmostEqual(inv["remaining_amount"], 2685.0, places=2)
        self.assertEqual(inv["paid_amount"], 0.0)
        self.assertEqual(inv["status"], "sent")
        self.assertEqual(len(inv["items"]), 2)

        TestStep5CRM.invoice_id = inv["id"]

    # ---------------------------------------------------------
    # 3. PAYMENTS & OVERPAYMENT VALIDATION
    # ---------------------------------------------------------
    def test_03_payment_recording_and_overpayment_protection(self):
        inv_id = TestStep5CRM.invoice_id

        # 3a. Test overpayment rejection: total is 2685, attempting 3000
        bad_pay = self.client.post("/api/payments", headers=self.headers, json={
            "invoice_id": inv_id,
            "amount": 3000.0,
            "payment_method": "bank_transfer"
        })
        self.assertEqual(bad_pay.status_code, 400)
        bad_data = json.loads(bad_pay.data)
        self.assertIn("exceeds", bad_data["message"].lower())

        # 3b. Record partial payment of 1000.00
        pay1 = self.client.post("/api/payments", headers=self.headers, json={
            "invoice_id": inv_id,
            "amount": 1000.0,
            "payment_method": "bank_transfer",
            "transaction_reference": "TXN-1001",
            "notes": "First partial payment"
        })
        self.assertEqual(pay1.status_code, 201)

        # Verify invoice is now partially_paid
        inv_res = self.client.get(f"/api/invoices/{inv_id}", headers=self.headers)
        inv = json.loads(inv_res.data)["invoice"]
        self.assertAlmostEqual(inv["paid_amount"], 1000.0, places=2)
        self.assertAlmostEqual(inv["remaining_amount"], 1685.0, places=2)
        self.assertEqual(inv["status"], "partially_paid")

        # 3c. Pay remaining balance of 1685.00
        pay2 = self.client.post("/api/payments", headers=self.headers, json={
            "invoice_id": inv_id,
            "amount": 1685.0,
            "payment_method": "upi",
            "transaction_reference": "UPI-9988"
        })
        self.assertEqual(pay2.status_code, 201)

        # Verify invoice is now paid
        inv_res2 = self.client.get(f"/api/invoices/{inv_id}", headers=self.headers)
        inv2 = json.loads(inv_res2.data)["invoice"]
        self.assertAlmostEqual(inv2["paid_amount"], 2685.0, places=2)
        self.assertAlmostEqual(inv2["remaining_amount"], 0.0, places=2)
        self.assertEqual(inv2["status"], "paid")
        self.assertEqual(len(inv2["payments"]), 2)

    # ---------------------------------------------------------
    # 4. EMAILS & TEMPLATES
    # ---------------------------------------------------------
    def test_04_email_templates_and_dev_mode_composition(self):
        # 4a. Create template
        tmpl_name = f"Invoice Reminder {os.urandom(3).hex()}"
        tmpl_res = self.client.post("/api/emails/templates", headers=self.headers, json={
            "name": tmpl_name,
            "subject": "Notice: Invoice Due",
            "body": "Dear Customer, please be reminded that your invoice is ready."
        })
        self.assertEqual(tmpl_res.status_code, 201)
        tmpl_data = json.loads(tmpl_res.data)
        tmpl_id = tmpl_data["template"]["id"]

        # 4b. List templates
        list_tmpl = self.client.get("/api/emails/templates", headers=self.headers)
        self.assertEqual(list_tmpl.status_code, 200)

        # 4c. Compose email in dev mode (without configured SMTP)
        comp_res = self.client.post("/api/emails", headers=self.headers, json={
            "recipient_email": "customer@business.com",
            "subject": "Invoice Followup",
            "message": "<p>Thank you for your business!</p>",
            "customer_id": self.customer_id
        })
        self.assertEqual(comp_res.status_code, 201)
        comp_data = json.loads(comp_res.data)
        self.assertTrue(comp_data["success"])
        # In dev mode, must clearly indicate SMTP is unconfigured and draft is saved
        self.assertIn("not configured", comp_data["message"].lower())
        self.assertEqual(comp_data["email"]["status"], "draft")

    # ---------------------------------------------------------
    # 5. NOTIFICATIONS
    # ---------------------------------------------------------
    def test_05_notifications_center(self):
        # 5a. Unread count
        cnt_res = self.client.get("/api/notifications/unread-count", headers=self.headers)
        self.assertEqual(cnt_res.status_code, 200)
        cnt_data = json.loads(cnt_res.data)
        self.assertIn("unread_count", cnt_data)

        # 5b. List notifications
        list_res = self.client.get("/api/notifications", headers=self.headers)
        self.assertEqual(list_res.status_code, 200)
        list_data = json.loads(list_res.data)
        self.assertTrue(list_data["success"])

        # 5c. Mark all as read
        read_all = self.client.put("/api/notifications/read-all", headers=self.headers)
        self.assertEqual(read_all.status_code, 200)

        # 5d. Verify count is now 0
        cnt_res2 = self.client.get("/api/notifications/unread-count", headers=self.headers)
        cnt_data2 = json.loads(cnt_res2.data)
        self.assertEqual(cnt_data2["unread_count"], 0)

    # ---------------------------------------------------------
    # 6. REPORTS & ANALYTICS
    # ---------------------------------------------------------
    def test_06_reports_endpoints(self):
        for rep in ["sales", "revenue", "customers", "leads", "tasks", "invoices"]:
            res = self.client.get(f"/api/reports/{rep}?date_filter=all", headers=self.headers)
            self.assertEqual(res.status_code, 200, f"Report {rep} failed")
            data = json.loads(res.data)
            self.assertTrue(data["success"])
            self.assertIn("report", data)
            self.assertIn("summary", data["report"])

    # ---------------------------------------------------------
    # 7. USERS & ROLES
    # ---------------------------------------------------------
    def test_07_users_and_role_permissions(self):
        # 7a. Get roles & permissions
        r_res = self.client.get("/api/roles", headers=self.headers)
        self.assertEqual(r_res.status_code, 200)

        p_res = self.client.get("/api/permissions", headers=self.headers)
        self.assertEqual(p_res.status_code, 200)

        # 7b. Create new user
        test_email = f"emp_{os.urandom(3).hex()}@crm.local"
        u_res = self.client.post("/api/users", headers=self.headers, json={
            "first_name": "Alexander",
            "last_name": "Wright",
            "email": test_email,
            "phone": "9876543210",
            "role_id": 3, # Sales Employee
            "password": "Password@123",
            "status": "active"
        })
        self.assertEqual(u_res.status_code, 201)
        u_data = json.loads(u_res.data)
        new_uid = u_data["user"]["id"]
        # Never leak password
        self.assertNotIn("password_hash", u_data["user"])

        # 7c. Toggle status
        s_res = self.client.put(f"/api/users/{new_uid}/status", headers=self.headers, json={"status": "inactive"})
        self.assertEqual(s_res.status_code, 200)
        self.assertEqual(json.loads(s_res.data)["user"]["status"], "inactive")

        # 7d. Prevent self-deactivation (Admin user id = 1)
        admin_self = self.client.put("/api/users/1/status", headers=self.headers, json={"status": "inactive"})
        self.assertEqual(admin_self.status_code, 400)

    # ---------------------------------------------------------
    # 8. SETTINGS
    # ---------------------------------------------------------
    def test_08_settings_configuration(self):
        # 8a. Get settings
        get_res = self.client.get("/api/settings", headers=self.headers)
        self.assertEqual(get_res.status_code, 200)
        data = json.loads(get_res.data)
        self.assertTrue(data["success"])
        self.assertIn("company_name", data["settings"])

        # 8b. Update settings
        upd_res = self.client.put("/api/settings", headers=self.headers, json={
            "company_name": "APEX CRM Enterprise Edition",
            "invoice_prefix": "APX-INV"
        })
        self.assertEqual(upd_res.status_code, 200)
        upd_data = json.loads(upd_res.data)
        self.assertEqual(upd_data["settings"]["company_name"], "APEX CRM Enterprise Edition")
        self.assertEqual(upd_data["settings"]["invoice_prefix"], "APX-INV")

    # ---------------------------------------------------------
    # 9. DASHBOARD METRICS INTEGRATION
    # ---------------------------------------------------------
    def test_09_dashboard_summary_includes_business_metrics(self):
        res = self.client.get("/api/dashboard/summary", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data["success"])
        cards = data.get("cards", {})

        # Verify revenue, invoices, and products are present
        self.assertIn("total_revenue", cards)
        self.assertIn("total_invoices", cards)
        self.assertIn("total_products", cards)
        self.assertGreaterEqual(cards["total_invoices"], 1)
        self.assertGreaterEqual(cards["total_products"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
