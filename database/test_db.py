"""
CRM Database Automated Verification Test Suite (Step 2)
Tests schema integrity, table creation, relationships, indexes, and seed data.
"""

import sys
from pathlib import Path
from werkzeug.security import check_password_hash

# Ensure root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from database.database import (
        get_db_connection,
        get_db_cursor,
        execute_query,
        init_db,
        check_db_connection
    )
except ImportError:
    from database import (
        get_db_connection,
        get_db_cursor,
        execute_query,
        init_db,
        check_db_connection
    )

EXPECTED_TABLES = [
    "roles",
    "permissions",
    "role_permissions",
    "users",
    "customers",
    "customer_documents",
    "customer_notes",
    "leads",
    "lead_activities",
    "deals",
    "deal_activities",
    "tasks",
    "calls",
    "meetings",
    "products",
    "invoices",
    "invoice_items",
    "payments",
    "emails",
    "email_templates",
    "notifications",
    "activities",
    "settings"
]

EXPECTED_PERMISSIONS_COUNT = 37
EXPECTED_ROLES = ["Admin", "Manager", "Sales Employee", "Staff"]


def test_database_suite():
    print("=" * 65)
    print("   CRM DATABASE STEP 2 — VERIFICATION TEST SUITE")
    print("=" * 65)

    # 1. Initialize schema
    print("\n[TEST 1] Initializing schema and applying database/schema.sql...")
    success, msg = init_db()
    print(f"Result: {msg}")
    assert success, f"Failed to initialize schema: {msg}"
    print(" -> PASSED: Database schema initialized successfully.")

    # 2. Check connection health
    print("\n[TEST 2] Checking connection health via check_db_connection()...")
    health = check_db_connection()
    print(f"Status: {health.get('status')}")
    assert health.get("status") == "connected", f"Database health check failed: {health}"
    print(" -> PASSED: Connection verified.")

    # 3. Verify all 23 tables exist
    print("\n[TEST 3] Verifying all 23 tables exist in crm_database...")
    with get_db_cursor(dictionary=False) as cursor:
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]

    print(f"Found {len(tables)} tables in database:")
    for t in tables:
        print(f"  - {t}")

    missing_tables = [t for t in EXPECTED_TABLES if t not in tables]
    assert not missing_tables, f"Missing required tables: {missing_tables}"
    assert len(tables) >= 23, f"Expected 23 tables, found {len(tables)}"
    print(f" -> PASSED: All {len(EXPECTED_TABLES)} required tables exist!")

    # 4. Verify seed roles
    print("\n[TEST 4] Verifying default roles seed data...")
    roles_data, err = execute_query("SELECT id, name FROM roles ORDER BY id")
    assert err is None, f"Query error: {err}"
    role_names = [r["name"] for r in roles_data]
    print(f"Roles found: {role_names}")
    for exp_role in EXPECTED_ROLES:
        assert exp_role in role_names, f"Missing role: {exp_role}"
    print(" -> PASSED: All 4 default roles verified.")

    # 5. Verify permissions
    print("\n[TEST 5] Verifying permissions seed data...")
    perms_data, err = execute_query("SELECT COUNT(*) AS total FROM permissions", fetch_one=True)
    assert err is None, f"Query error: {err}"
    total_perms = perms_data["total"]
    print(f"Total permissions: {total_perms} (Expected: {EXPECTED_PERMISSIONS_COUNT})")
    assert total_perms >= EXPECTED_PERMISSIONS_COUNT, f"Expected at least {EXPECTED_PERMISSIONS_COUNT} permissions, got {total_perms}"
    print(" -> PASSED: All permissions verified.")

    # 6. Verify role permissions assignments
    print("\n[TEST 6] Verifying role-permissions matrix...")
    rp_counts, err = execute_query("""
        SELECT r.name, COUNT(rp.permission_id) as perm_count
        FROM roles r
        LEFT JOIN role_permissions rp ON r.id = rp.role_id
        GROUP BY r.id, r.name
    """)
    assert err is None, f"Query error: {err}"
    for r in rp_counts:
        print(f"  Role '{r['name']}': {r['perm_count']} permissions assigned")
        assert r["perm_count"] > 0, f"Role {r['name']} has zero permissions assigned"
    print(" -> PASSED: Role-permission assignments verified.")

    # 7. Verify demo admin user
    print("\n[TEST 7] Verifying demo Admin user and password hash...")
    admin_user, err = execute_query(
        "SELECT u.id, u.email, u.status, u.password_hash, r.name as role_name "
        "FROM users u JOIN roles r ON u.role_id = r.id "
        "WHERE u.email = 'admin@crm.local'",
        fetch_one=True
    )
    assert err is None, f"Query error: {err}"
    assert admin_user is not None, "Demo admin user 'admin@crm.local' was not found in users table!"
    print(f"Admin User found: id={admin_user['id']}, email={admin_user['email']}, role={admin_user['role_name']}")
    assert admin_user["role_name"] == "Admin"
    assert admin_user["status"] == "active"

    # Verify password hash works with documented dev password
    dev_password = "Admin@123456"
    valid_hash = check_password_hash(admin_user["password_hash"], dev_password)
    assert valid_hash, "Admin user password hash does NOT match development password 'Admin@123456'!"
    print(" -> PASSED: Demo admin user exists and password hash verified.")

    # 8. Verify Foreign Key relationships
    print("\n[TEST 8] Verifying foreign keys on critical tables...")
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = 'crm_database' AND REFERENCED_TABLE_NAME IS NOT NULL
        """)
        fks = cursor.fetchall()

    print(f"Total Foreign Keys identified in crm_database: {len(fks)}")
    assert len(fks) >= 20, f"Expected at least 20 foreign key constraints, found {len(fks)}"
    print(" -> PASSED: Foreign key constraints verified.")

    # 9. Verify Indexes
    print("\n[TEST 9] Verifying indexes on required tables...")
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = 'crm_database'
        """)
        indexes = cursor.fetchall()

    index_keys = {(idx["TABLE_NAME"], idx["COLUMN_NAME"]) for idx in indexes}
    required_index_pairs = [
        ("users", "email"),
        ("customers", "email"),
        ("customers", "phone"),
        ("customers", "company_name"),
        ("customers", "status"),
        ("customers", "assigned_to"),
        ("leads", "email"),
        ("leads", "phone"),
        ("leads", "status"),
        ("leads", "assigned_to"),
        ("deals", "stage"),
        ("deals", "status"),
        ("deals", "assigned_to"),
        ("tasks", "status"),
        ("tasks", "due_date"),
        ("invoices", "invoice_number"),
        ("invoices", "status"),
        ("payments", "payment_date"),
        ("notifications", "user_id"),
        ("notifications", "is_read"),
        ("activities", "entity_type"),
        ("activities", "entity_id"),
    ]

    for tbl, col in required_index_pairs:
        assert (tbl, col) in index_keys, f"Missing expected index on {tbl}.{col}"
    print(f" -> PASSED: All {len(required_index_pairs)} required index fields verified.")

    # 10. Verify Settings Seed Data
    print("\n[TEST 10] Verifying settings seed records...")
    settings_data, err = execute_query("SELECT setting_key, setting_value FROM settings")
    assert err is None, f"Query error: {err}"
    settings_dict = {s["setting_key"]: s["setting_value"] for s in settings_data}
    assert "system_name" in settings_dict
    assert "company_name" in settings_dict
    print(f"Settings verified: {settings_dict}")
    print(" -> PASSED: Settings verified.")

    print("\n" + "=" * 65)
    print("   ALL 10 DATABASE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    test_database_suite()
