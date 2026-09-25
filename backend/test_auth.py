"""
CRM Authentication and RBAC Automated Test Suite (Step 3)
Tests user login, password hashing, JWT life-cycle, role-based access control,
permission checks, and protected routes.
"""

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import jwt

# Add root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app import app
from backend.config import Config
from backend.services.auth_service import hash_password, verify_password, generate_token
from database.database import execute_query


def run_auth_test_suite():
    print("=" * 68)
    print("   CRM AUTHENTICATION & RBAC (STEP 3) — VERIFICATION SUITE")
    print("=" * 68)

    client = app.test_client()

    # -------------------------------------------------------------
    # PART 1: Password Hashing Utilities
    # -------------------------------------------------------------
    print("\n[TEST 1] Password Hashing & Verification...")
    raw_pass = "SecureCRM@2026!"
    hashed = hash_password(raw_pass)
    assert hashed != raw_pass, "Password was not hashed!"
    assert verify_password(raw_pass, hashed), "Password verification failed for valid password"
    assert not verify_password("WrongPass123", hashed), "Password verification succeeded for invalid password"
    print(" -> PASSED: Werkzeug password hashing functions validated.")

    # -------------------------------------------------------------
    # PART 2: Login API Validations
    # -------------------------------------------------------------
    print("\n[TEST 2] Login API Validation & Error Responses...")

    # 2.1 Empty fields
    res = client.post("/api/auth/login", json={})
    assert res.status_code == 400
    assert res.get_json()["success"] is False
    print("  - Empty payload returns 400 Bad Request: PASSED")

    res = client.post("/api/auth/login", json={"email": "admin@crm.local", "password": ""})
    assert res.status_code == 400
    print("  - Empty password returns 400 Bad Request: PASSED")

    res = client.post("/api/auth/login", json={"email": "", "password": "any"})
    assert res.status_code == 400
    print("  - Empty email returns 400 Bad Request: PASSED")

    # 2.2 Invalid email format
    res = client.post("/api/auth/login", json={"email": "not-an-email", "password": "Admin@123456"})
    assert res.status_code == 400
    assert "email format" in res.get_json()["message"].lower()
    print("  - Invalid email format returns 400 Bad Request: PASSED")

    # 2.3 Non-existent user
    res = client.post("/api/auth/login", json={"email": "nonexistent@crm.local", "password": "Admin@123456"})
    assert res.status_code == 401
    assert "invalid email or password" in res.get_json()["message"].lower()
    print("  - Non-existent user returns 401 (safe generic message): PASSED")

    # 2.4 Wrong password
    res = client.post("/api/auth/login", json={"email": "admin@crm.local", "password": "IncorrectPassword!"})
    assert res.status_code == 401
    assert "invalid email or password" in res.get_json()["message"].lower()
    print("  - Wrong password returns 401: PASSED")

    # 2.5 Inactive user
    res = client.post("/api/auth/login", json={"email": "inactive@crm.local", "password": "Inactive@123456"})
    assert res.status_code == 403
    assert "inactive" in res.get_json()["message"].lower()
    print("  - Inactive user returns 403 Forbidden with safe explanation: PASSED")

    # 2.6 Correct login (Admin)
    res = client.post("/api/auth/login", json={"email": "admin@crm.local", "password": "Admin@123456"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "token" in data
    assert "user" in data
    admin_token = data["token"]
    admin_user = data["user"]
    assert admin_user["email"] == "admin@crm.local"
    assert admin_user["role"] == "Admin"
    assert "password_hash" not in admin_user
    assert "password" not in admin_user
    print("  - Correct Admin login returns 200 with JWT and sanitized user: PASSED")

    # 2.7 Verify last_login updated in database
    db_user, _ = execute_query("SELECT last_login FROM users WHERE email = 'admin@crm.local'", fetch_one=True)
    assert db_user["last_login"] is not None
    print(f"  - users.last_login updated in database: {db_user['last_login']}: PASSED")

    # -------------------------------------------------------------
    # PART 3: Current User API (GET /api/auth/me)
    # -------------------------------------------------------------
    print("\n[TEST 3] Current User API (/api/auth/me)...")

    # 3.1 Missing token
    res = client.get("/api/auth/me")
    assert res.status_code == 401
    print("  - Missing token returns 401: PASSED")

    # 3.2 Invalid token format
    res = client.get("/api/auth/me", headers={"Authorization": "Basic 12345"})
    assert res.status_code == 401
    print("  - Invalid header format returns 401: PASSED")

    # 3.3 Tampered / Invalid token
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.valid.jwt.token"})
    assert res.status_code == 401
    print("  - Tampered token returns 401: PASSED")

    # 3.4 Valid Admin token
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    me_data = res.get_json()["user"]
    assert me_data["email"] == "admin@crm.local"
    assert me_data["role"] == "Admin"
    assert len(me_data["permissions"]) >= 37
    assert "customers.view" in me_data["permissions"]
    assert "password_hash" not in me_data
    print(f"  - Valid token returns profile with {len(me_data['permissions'])} permissions: PASSED")

    # -------------------------------------------------------------
    # PART 4: Token Expiration & Revocation
    # -------------------------------------------------------------
    print("\n[TEST 4] Token Expiration and Logout Revocation...")

    # 4.1 Expired token
    expired_payload = {
        "user_id": 1,
        "role_id": 1,
        "role": "Admin",
        "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
        "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
    }
    expired_token = jwt.encode(expired_payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "expired" in res.get_json()["message"].lower()
    print("  - Expired token returns 401: PASSED")

    # 4.2 Logout API & Revocation
    res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    print("  - POST /api/auth/logout returns 200: PASSED")

    # After logout, token must be revoked and rejected
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 401
    assert "revoked" in res.get_json()["message"].lower()
    print("  - Revoked token rejected with 401: PASSED")

    # -------------------------------------------------------------
    # PART 5: Role-Based Access Control & Permission Checks
    # -------------------------------------------------------------
    print("\n[TEST 5] Role-Based Access Control & Permissions across Roles...")

    # Login Manager
    res = client.post("/api/auth/login", json={"email": "manager@crm.local", "password": "Manager@123456"})
    assert res.status_code == 200
    mgr_token = res.get_json()["token"]

    # Login Sales Employee
    res = client.post("/api/auth/login", json={"email": "sales@crm.local", "password": "Sales@123456"})
    assert res.status_code == 200
    sales_token = res.get_json()["token"]

    # Login Staff
    res = client.post("/api/auth/login", json={"email": "staff@crm.local", "password": "Staff@123456"})
    assert res.status_code == 200
    staff_token = res.get_json()["token"]

    # Test Manager permissions
    # Manager has 'reports.view'
    res = client.get("/api/auth/test-permission/reports.view", headers={"Authorization": f"Bearer {mgr_token}"})
    assert res.status_code == 200
    print("  - Manager has 'reports.view': PASSED (200 Granted)")

    # Manager does NOT have 'users.delete'
    res = client.get("/api/auth/test-permission/users.delete", headers={"Authorization": f"Bearer {mgr_token}"})
    assert res.status_code == 403
    print("  - Manager lacks 'users.delete': PASSED (403 Forbidden)")

    # Test Sales Employee permissions
    # Sales has 'deals.create'
    res = client.get("/api/auth/test-permission/deals.create", headers={"Authorization": f"Bearer {sales_token}"})
    assert res.status_code == 200
    print("  - Sales Employee has 'deals.create': PASSED (200 Granted)")

    # Sales lacks 'reports.view'
    res = client.get("/api/auth/test-permission/reports.view", headers={"Authorization": f"Bearer {sales_token}"})
    assert res.status_code == 403
    print("  - Sales Employee lacks 'reports.view': PASSED (403 Forbidden)")

    # Test Staff permissions
    # Staff has 'tasks.view'
    res = client.get("/api/auth/test-permission/tasks.view", headers={"Authorization": f"Bearer {staff_token}"})
    assert res.status_code == 200
    print("  - Staff has 'tasks.view': PASSED (200 Granted)")

    # Staff lacks 'customers.delete'
    res = client.get("/api/auth/test-permission/customers.delete", headers={"Authorization": f"Bearer {staff_token}"})
    assert res.status_code == 403
    print("  - Staff lacks 'customers.delete': PASSED (403 Forbidden)")

    # Re-login Admin and test
    res = client.post("/api/auth/login", json={"email": "admin@crm.local", "password": "Admin@123456"})
    new_admin_token = res.get_json()["token"]
    res = client.get("/api/auth/test-permission/any.arbitrary.permission", headers={"Authorization": f"Bearer {new_admin_token}"})
    assert res.status_code == 200
    print("  - Admin bypasses specific checks with full authority: PASSED (200 Granted)")

    print("\n" + "=" * 68)
    print("   ALL 14 AUTHENTICATION & RBAC TESTS PASSED SUCCESSFULLY!")
    print("=" * 68)


if __name__ == "__main__":
    run_auth_test_suite()
