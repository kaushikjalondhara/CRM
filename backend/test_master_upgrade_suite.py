"""
Apex CRM - Master Upgrade 20 Advanced Features Automated Test Suite
Verifies all 20 advanced enterprise features end-to-end against the database.
"""

import os
import sys
import io
import json
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import create_app
from database.database import execute_query, check_db_connection


class MasterUpgrade20FeaturesTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        # Check DB
        db_stat = check_db_connection()
        if db_stat.get("status") != "connected":
            raise RuntimeError(f"Database connection required for Master Upgrade test suite: {db_stat.get('message')}")

        # Authenticate Admin
        login_res = cls.client.post("/api/auth/login", json={
            "email": "admin@crm.local",
            "password": "Admin@123456"
        })
        login_data = json.loads(login_res.data)
        if login_res.status_code != 200 or not login_data.get("token"):
            raise RuntimeError(f"Admin authentication failed: {login_data}")

        cls.token = login_data["token"]
        cls.headers = {
            "Authorization": f"Bearer {cls.token}",
            "Content-Type": "application/json"
        }

    # -------------------------------------------------------------------------
    # Feature 1: Global Search
    # -------------------------------------------------------------------------
    def test_01_global_search(self):
        res = self.client.get("/api/search?q=admin", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("results", data["data"])
        self.assertIn("total_results", data["data"])

    # -------------------------------------------------------------------------
    # Feature 2: Advanced Multi-Filters & Parametric Query Filters
    # -------------------------------------------------------------------------
    def test_02_advanced_filters(self):
        # Query customers with status + search filter
        cust_res = self.client.get("/api/customers?status=active&search=Kaushik", headers=self.headers)
        self.assertEqual(cust_res.status_code, 200)
        self.assertTrue(cust_res.get_json()["success"])

        # Query invoices with status + date range filter
        inv_res = self.client.get("/api/invoices?status=sent&start_date=2026-01-01", headers=self.headers)
        self.assertEqual(inv_res.status_code, 200)
        self.assertTrue(inv_res.get_json()["success"])

    # -------------------------------------------------------------------------
    # Feature 3: Export Engine (CSV, Excel .xlsx, PDF)
    # -------------------------------------------------------------------------
    def test_03_export_engine(self):
        # Test CSV export
        csv_res = self.client.get("/api/export/customers?format=csv", headers=self.headers)
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn("text/csv", csv_res.content_type)
        self.assertIn("Customer Code", csv_res.data.decode("utf-8-sig", errors="replace"))

        # Test Excel .xlsx export
        xlsx_res = self.client.get("/api/export/customers?format=xlsx", headers=self.headers)
        self.assertEqual(xlsx_res.status_code, 200)
        self.assertIn("openxmlformats", xlsx_res.content_type)
        self.assertTrue(len(xlsx_res.data) > 100)

        # Test PDF export
        pdf_res = self.client.get("/api/export/customers?format=pdf", headers=self.headers)
        self.assertEqual(pdf_res.status_code, 200)
        self.assertIn("application/pdf", pdf_res.content_type)
        self.assertTrue(pdf_res.data.startswith(b"%PDF"))

    # -------------------------------------------------------------------------
    # Feature 4: Print Stylesheet Integration
    # -------------------------------------------------------------------------
    def test_04_print_styling(self):
        css_path = os.path.join(self.app.root_path, "..", "frontend", "css", "style.css")
        with open(css_path, "r", encoding="utf-8") as fp:
            css_content = fp.read()
        self.assertIn("@media print", css_content)
        self.assertIn(".no-print", css_content)

    # -------------------------------------------------------------------------
    # Feature 5: ReportLab Pixel-Perfect Invoice Generator
    # -------------------------------------------------------------------------
    def test_05_reportlab_invoice_pdf(self):
        inv, _ = execute_query("SELECT id FROM invoices ORDER BY id ASC LIMIT 1", fetch_one=True)
        if not inv:
            c_res = self.client.post("/api/customers", json={"first_name": "PDF", "last_name": "Tester", "email": "pdf@test.com"}, headers=self.headers)
            cj = c_res.get_json() or {}
            cid = cj.get("id") or (cj.get("customer", {}) if isinstance(cj.get("customer"), dict) else {}).get("id") or 1
            i_res = self.client.post("/api/invoices", json={"customer_id": cid, "due_date": "2026-12-31", "items": [{"description": "PDF Test Item", "quantity": 1, "unit_price": 500}]}, headers=self.headers)
            ij = i_res.get_json() or {}
            inv_id = ij.get("id") or (ij.get("invoice", {}) if isinstance(ij.get("invoice"), dict) else {}).get("id") or 1
        else:
            inv_id = inv["id"]

        res = self.client.get(f"/api/export/invoices/{inv_id}/pdf", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("application/pdf", res.content_type)
        self.assertTrue(res.data.startswith(b"%PDF"))

    # -------------------------------------------------------------------------
    # Feature 6: Email Templates & SMTP Architecture
    # -------------------------------------------------------------------------
    def test_06_email_templates(self):
        res = self.client.get("/api/emails/templates", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        templates = data.get("templates", [])
        self.assertTrue(len(templates) >= 6)

    # -------------------------------------------------------------------------
    # Feature 7: Real-time Notification Center
    # -------------------------------------------------------------------------
    def test_07_notification_center(self):
        res = self.client.get("/api/notifications", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Mark all read
        read_all_res = self.client.put("/api/notifications/read-all", headers=self.headers)
        self.assertEqual(read_all_res.status_code, 200)

    # -------------------------------------------------------------------------
    # Feature 8: CRM Calendar (Meetings, Calls, Tasks, Events)
    # -------------------------------------------------------------------------
    def test_08_crm_calendar(self):
        # Fetch consolidated events
        res = self.client.get("/api/calendar/events", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("events", data)

        # Create custom calendar event
        event_payload = {
            "title": "Quarterly Sales All-Hands",
            "start_time": "2026-10-15T10:00:00",
            "end_time": "2026-10-15T11:30:00",
            "event_type": "event",
            "description": "Executive review of Q4 targets"
        }
        create_res = self.client.post("/api/calendar/events", headers=self.headers, json=event_payload)
        self.assertIn(create_res.status_code, (200, 201))
        event_id = create_res.get_json()["data"]["id"]

        # Delete custom calendar event
        del_res = self.client.delete(f"/api/calendar/events/{event_id}", headers=self.headers)
        self.assertEqual(del_res.status_code, 200)

    # -------------------------------------------------------------------------
    # Feature 9: Drag & Drop Deal Pipeline (HTML5 Kanban)
    # -------------------------------------------------------------------------
    def test_09_deal_pipeline_stages(self):
        res = self.client.get("/api/deals/pipeline", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("kanban", data)
        self.assertIn("stages", data)

    # -------------------------------------------------------------------------
    # Feature 10: Customer 360° Profile
    # -------------------------------------------------------------------------
    def test_10_customer_360_profile(self):
        res = self.client.get("/api/customers/1/360", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        c360 = data["data"]
        self.assertIn("customer", c360)
        self.assertIn("summary", c360)
        self.assertIn("invoices", c360)
        self.assertIn("timeline", c360)

    # -------------------------------------------------------------------------
    # Feature 11: Real Security Audit Log Explorer
    # -------------------------------------------------------------------------
    def test_11_audit_logs(self):
        res = self.client.get("/api/audit-logs", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("logs", data["data"])
        self.assertIsInstance(data["data"]["logs"], list)

    # -------------------------------------------------------------------------
    # Feature 12: File & Document Management
    # -------------------------------------------------------------------------
    def test_12_document_management(self):
        res = self.client.get("/api/documents", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("documents", data)

    # -------------------------------------------------------------------------
    # Feature 13: Database Backup & Protected Restore
    # -------------------------------------------------------------------------
    def test_13_database_backup(self):
        # 1. Create Backup
        create_res = self.client.post("/api/backup/create", headers=self.headers)
        self.assertIn(create_res.status_code, (200, 201))
        data = create_res.get_json()
        self.assertTrue(data["success"])
        filename = data["backup"]["filename"]
        self.assertTrue(filename.endswith(".sql"))

        # 2. List Backups
        list_res = self.client.get("/api/backup/list", headers=self.headers)
        self.assertEqual(list_res.status_code, 200)
        self.assertTrue(any(b["filename"] == filename for b in list_res.get_json()["backups"]))

        # 3. Download Backup
        dl_res = self.client.get(f"/api/backup/{filename}/download", headers=self.headers)
        self.assertEqual(dl_res.status_code, 200)
        self.assertIn("text/plain", dl_res.content_type)
        self.assertIn("Apex CRM Automated Database Backup", dl_res.data.decode("utf-8", errors="replace"))

    # -------------------------------------------------------------------------
    # Feature 14: Bulk Import System
    # -------------------------------------------------------------------------
    def test_14_bulk_import_system(self):
        # 1. Download template
        tpl_res = self.client.get("/api/import/template/customers?format=csv", headers=self.headers)
        self.assertEqual(tpl_res.status_code, 200)
        self.assertIn("first_name", tpl_res.data.decode("utf-8-sig"))

        # 2. Preview upload
        csv_data = "first_name,last_name,email,company_name,status\nTestFirst,TestLast,testimport@example.com,TestCo,prospect\n"
        data = {
            "module": "customers",
            "file": (io.BytesIO(csv_data.encode("utf-8")), "customers_import.csv")
        }
        prev_res = self.client.post("/api/import/preview", headers={"Authorization": f"Bearer {self.token}"}, data=data)
        self.assertEqual(prev_res.status_code, 200)
        p_data = prev_res.get_json()
        self.assertTrue(p_data["success"])
        self.assertEqual(p_data["data"]["valid_rows_count"], 1)

    # -------------------------------------------------------------------------
    # Feature 15: Bulk Actions (Customers, Leads, Tasks)
    # -------------------------------------------------------------------------
    def test_15_bulk_actions(self):
        # Fetch customers to run bulk status update
        cust_res = self.client.get("/api/customers", headers=self.headers)
        self.assertEqual(cust_res.status_code, 200)
        cust_data = cust_res.get_json()
        custs = cust_data.get("customers") or cust_data.get("data", {}).get("customers", [])
        if custs:
            cust_ids = [c["id"] for c in custs[:2]]
            bulk_status_res = self.client.post("/api/customers/bulk-action", headers=self.headers, json={
                "action": "status",
                "ids": cust_ids,
                "value": "active"
            })
            self.assertEqual(bulk_status_res.status_code, 200)
            self.assertTrue(bulk_status_res.get_json()["success"])

    # -------------------------------------------------------------------------
    # Feature 16: Advanced Executive Analytics Dashboard
    # -------------------------------------------------------------------------
    def test_16_executive_dashboard(self):
        res = self.client.get("/api/dashboard/summary?period=all", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("conversion_funnel", data)
        self.assertIn("revenue_trend", data)
        self.assertIn("top_sales_reps", data)
        self.assertIn("payment_status_breakdown", data)

    # -------------------------------------------------------------------------
    # Feature 17: Employee Performance Analytics
    # -------------------------------------------------------------------------
    def test_17_employee_performance(self):
        res = self.client.get("/api/reports/employee-performance", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("performance", data)
        self.assertIn("count", data)

    # -------------------------------------------------------------------------
    # Feature 18: Automatic Reminders Engine
    # -------------------------------------------------------------------------
    def test_18_reminders_daemon(self):
        res = self.client.get("/api/reminders", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Trigger manual check check-cycle
        check_res = self.client.post("/api/reminders/check", headers=self.headers)
        self.assertEqual(check_res.status_code, 200)
        self.assertTrue(check_res.get_json()["success"])

    # -------------------------------------------------------------------------
    # Feature 19: Profile & Account Management
    # -------------------------------------------------------------------------
    def test_19_profile_management(self):
        # 1. Fetch Profile
        res = self.client.get("/api/users/profile", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        p = data["profile"]
        self.assertIn("login_history", p)
        self.assertEqual(p["email"], "admin@crm.local")

        # 2. Update Profile Information
        up_res = self.client.put("/api/users/profile", headers=self.headers, json={
            "first_name": "Super",
            "last_name": "Admin",
            "email": "admin@crm.local",
            "phone": "+1 555-0100"
        })
        self.assertEqual(up_res.status_code, 200)
        self.assertTrue(up_res.get_json()["success"])

    # -------------------------------------------------------------------------
    # Feature 20: Production Deployment Ready
    # -------------------------------------------------------------------------
    def test_20_production_readiness(self):
        # 1. Verify Gunicorn config exists and compiles
        gunicorn_path = os.path.join(self.app.root_path, "gunicorn_conf.py")
        self.assertTrue(os.path.exists(gunicorn_path), "backend/gunicorn_conf.py missing")
        with open(gunicorn_path, "r", encoding="utf-8") as fp:
            compile(fp.read(), "gunicorn_conf.py", "exec")

        # 2. Verify .env.example
        env_ex_path = os.path.join(self.app.root_path, "..", ".env.example")
        self.assertTrue(os.path.exists(env_ex_path), ".env.example missing")

        # 3. Verify .gitignore protects credentials and backups
        gitignore_path = os.path.join(self.app.root_path, "..", ".gitignore")
        self.assertTrue(os.path.exists(gitignore_path), ".gitignore missing")
        with open(gitignore_path, "r", encoding="utf-8") as fp:
            gi_content = fp.read()
        self.assertIn(".env", gi_content)
        self.assertIn("uploads/backups", gi_content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
