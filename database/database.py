import os
import sys
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Add project root and backend to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from backend.config import Config
except ImportError:
    try:
        from config import Config
    except ImportError:
        Config = None

# Configure logger
logger = logging.getLogger("crm.database")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


SQLITE_DB_PATH = BASE_DIR / "uploads" / "crm_database.sqlite"


from datetime import datetime, date


def _parse_datetime(val_str):
    if not isinstance(val_str, str):
        return val_str
    val_clean = val_str.strip()
    if not (("-" in val_clean and ":" in val_clean) or (len(val_clean) == 10 and "-" in val_clean)):
        return val_str
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(val_clean, fmt)
            if fmt == "%Y-%m-%d":
                return dt.date()
            return dt
        except ValueError:
            pass
    return val_str


def _convert_row(row, dictionary=True):
    if row is None:
        return None
    if dictionary and isinstance(row, sqlite3.Row):
        row = dict(row)
    if isinstance(row, dict):
        res = {}
        for k, v in row.items():
            res[k] = _parse_datetime(v)
        return res
    return row



import re


def _translate_mysql_to_sqlite(query):
    translated = query.replace("%s", "?")
    translated = translated.replace("NOW()", "CURRENT_TIMESTAMP")
    if "ON DUPLICATE KEY UPDATE" in translated:
        translated = translated.split("ON DUPLICATE KEY UPDATE")[0].replace("INSERT INTO", "INSERT OR REPLACE INTO")

    translated = re.sub(r"DATE_SUB\s*\(\s*(?:NOW\(\)|CURRENT_TIMESTAMP)\s*,\s*INTERVAL\s+(\d+)\s+DAY\s*\)", r"datetime('now', '-\1 days')", translated, flags=re.IGNORECASE)
    translated = re.sub(r"DATE_SUB\s*\(\s*CURDATE\(\)\s*,\s*INTERVAL\s+(\d+)\s+DAY\s*\)", r"date('now', '-\1 days')", translated, flags=re.IGNORECASE)
    translated = re.sub(r"DATE_SUB\s*\(\s*CURDATE\(\)\s*,\s*INTERVAL\s+(\d+)\s+MONTH\s*\)", r"date('now', '-\1 months')", translated, flags=re.IGNORECASE)
    translated = re.sub(r"DATE_SUB\s*\(\s*(?:NOW\(\)|CURRENT_TIMESTAMP)\s*,\s*INTERVAL\s+(\d+)\s+MONTH\s*\)", r"datetime('now', '-\1 months')", translated, flags=re.IGNORECASE)
    translated = re.sub(r"DATE_SUB\s*\(\s*CURDATE\(\)\s*,\s*INTERVAL\s+WEEKDAY\s*\([^)]+\)\s+DAY\s*\)", r"date('now', '-7 days')", translated, flags=re.IGNORECASE)
    translated = re.sub(r"MAKEDATE\s*\([^)]+\)\s*\+\s*INTERVAL\s+[^)]+\s+MONTH", r"date('now', 'start of year')", translated, flags=re.IGNORECASE)

    return translated


class SQLiteCursorWrapper:
    def __init__(self, cursor, dictionary=True):
        self._cursor = cursor
        self.dictionary = dictionary

    def execute(self, query, params=None):
        translated = _translate_mysql_to_sqlite(query)
        if params is None:
            params = ()
        return self._cursor.execute(translated, params)


    def fetchone(self):
        row = self._cursor.fetchone()
        return _convert_row(row, dictionary=self.dictionary)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [_convert_row(r, dictionary=self.dictionary) for r in rows]


    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def close(self):
        self._cursor.close()


def _mysql_date_format(val, fmt):
    if not val:
        return ""
    dt = _parse_datetime(str(val))
    if isinstance(dt, (datetime, date)):
        fmt_py = fmt.replace("%Y", "%Y").replace("%m", "%m").replace("%d", "%d").replace("%H", "%H").replace("%i", "%M").replace("%s", "%S")
        return dt.strftime(fmt_py)
    return str(val)


def _mysql_curdate():
    return date.today().strftime("%Y-%m-%d")


def _mysql_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _mysql_ifnull(a, b):
    return b if a is None else a


class SQLiteConnectionWrapper:
    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.create_function("DATE_FORMAT", 2, _mysql_date_format)
        self._conn.create_function("CURDATE", 0, _mysql_curdate)
        self._conn.create_function("NOW", 0, _mysql_now)
        self._conn.create_function("IFNULL", 2, _mysql_ifnull)

    def cursor(self, dictionary=True):
        return SQLiteCursorWrapper(self._conn.cursor(), dictionary=dictionary)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


    def close(self):
        self._conn.close()

    def is_connected(self):
        return True


def init_sqlite_db(db_path=SQLITE_DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    schema_statements = [
        """CREATE TABLE IF NOT EXISTS roles (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          description TEXT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS permissions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          description TEXT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS role_permissions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          role_id INTEGER NOT NULL,
          permission_id INTEGER NOT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          UNIQUE (role_id, permission_id)
        );""",
        """CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          role_id INTEGER NOT NULL,
          first_name TEXT NOT NULL,
          last_name TEXT NOT NULL,
          email TEXT NOT NULL UNIQUE,
          phone TEXT NULL,
          password_hash TEXT NOT NULL,
          profile_image TEXT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          last_login DATETIME NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS customers (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          customer_code TEXT NOT NULL UNIQUE,
          first_name TEXT NOT NULL,
          last_name TEXT NOT NULL,
          company_name TEXT NULL,
          email TEXT NULL,
          phone TEXT NULL,
          alternate_phone TEXT NULL,
          address TEXT NULL,
          city TEXT NULL,
          state TEXT NULL,
          country TEXT NULL,
          pincode TEXT NULL,
          industry TEXT NULL,
          customer_type TEXT NULL,
          status TEXT NOT NULL DEFAULT 'prospect',
          assigned_to INTEGER NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS customer_documents (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          customer_id INTEGER NOT NULL,
          file_name TEXT NOT NULL,
          file_path TEXT NOT NULL,
          file_type TEXT NULL,
          file_size INTEGER NULL,
          uploaded_by INTEGER NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS customer_notes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          customer_id INTEGER NOT NULL,
          user_id INTEGER NULL,
          note TEXT NOT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS leads (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          lead_code TEXT NOT NULL UNIQUE,
          first_name TEXT NOT NULL,
          last_name TEXT NOT NULL,
          company_name TEXT NULL,
          email TEXT NULL,
          phone TEXT NULL,
          source TEXT NULL,
          industry TEXT NULL,
          status TEXT NOT NULL DEFAULT 'new',
          priority TEXT NOT NULL DEFAULT 'medium',
          expected_value REAL NOT NULL DEFAULT 0.00,
          assigned_to INTEGER NULL,
          follow_up_date DATE NULL,
          notes TEXT NULL,
          converted_customer_id INTEGER NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS lead_activities (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          lead_id INTEGER NOT NULL,
          user_id INTEGER NULL,
          activity_type TEXT NOT NULL,
          description TEXT NOT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS deals (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          deal_code TEXT NOT NULL UNIQUE,
          lead_id INTEGER NULL,
          customer_id INTEGER NOT NULL,
          title TEXT NOT NULL,
          description TEXT NULL,
          value REAL NOT NULL DEFAULT 0.00,
          stage TEXT NOT NULL DEFAULT 'new',
          probability INTEGER NOT NULL DEFAULT 0,
          expected_close_date DATE NULL,
          assigned_to INTEGER NULL,
          status TEXT NOT NULL DEFAULT 'open',
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS deal_activities (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          deal_id INTEGER NOT NULL,
          user_id INTEGER NULL,
          activity_type TEXT NOT NULL,
          description TEXT NOT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS tasks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          description TEXT NULL,
          customer_id INTEGER NULL,
          lead_id INTEGER NULL,
          deal_id INTEGER NULL,
          assigned_to INTEGER NULL,
          priority TEXT NOT NULL DEFAULT 'medium',
          status TEXT NOT NULL DEFAULT 'pending',
          due_date DATETIME NULL,
          completed_at DATETIME NULL,
          created_by INTEGER NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS calls (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          customer_id INTEGER NULL,
          lead_id INTEGER NULL,
          deal_id INTEGER NULL,
          assigned_to INTEGER NULL,
          call_date DATE NOT NULL,
          call_time TIME NULL,
          purpose TEXT NULL,
          status TEXT NOT NULL DEFAULT 'scheduled',
          notes TEXT NULL,
          created_by INTEGER NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS meetings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          customer_id INTEGER NULL,
          lead_id INTEGER NULL,
          deal_id INTEGER NULL,
          assigned_to INTEGER NULL,
          meeting_date DATE NOT NULL,
          start_time TIME NOT NULL,
          end_time TIME NULL,
          location TEXT NULL,
          meeting_type TEXT NULL,
          participants TEXT NULL,
          status TEXT NOT NULL DEFAULT 'scheduled',
          notes TEXT NULL,
          created_by INTEGER NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS products (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          product_code TEXT NOT NULL UNIQUE,
          name TEXT NOT NULL,
          category TEXT NULL,
          description TEXT NULL,
          price REAL NOT NULL DEFAULT 0.00,
          tax_percentage REAL NOT NULL DEFAULT 0.00,
          discount_percentage REAL NOT NULL DEFAULT 0.00,
          stock INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'active',
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS invoices (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          invoice_number TEXT NOT NULL UNIQUE,
          customer_id INTEGER NOT NULL,
          deal_id INTEGER NULL,
          invoice_date DATE NOT NULL,
          due_date DATE NOT NULL,
          subtotal REAL NOT NULL DEFAULT 0.00,
          tax_amount REAL NOT NULL DEFAULT 0.00,
          discount_amount REAL NOT NULL DEFAULT 0.00,
          total_amount REAL NOT NULL DEFAULT 0.00,
          paid_amount REAL NOT NULL DEFAULT 0.00,
          remaining_amount REAL NOT NULL DEFAULT 0.00,
          status TEXT NOT NULL DEFAULT 'draft',
          notes TEXT NULL,
          created_by INTEGER NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS invoice_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          invoice_id INTEGER NOT NULL,
          product_id INTEGER NULL,
          description TEXT NULL,
          quantity INTEGER NOT NULL DEFAULT 1,
          unit_price REAL NOT NULL DEFAULT 0.00,
          tax_percentage REAL NOT NULL DEFAULT 0.00,
          discount_percentage REAL NOT NULL DEFAULT 0.00,
          total REAL NOT NULL DEFAULT 0.00,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS payments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          invoice_id INTEGER NOT NULL,
          customer_id INTEGER NOT NULL,
          amount REAL NOT NULL,
          payment_method TEXT NOT NULL,
          transaction_reference TEXT NULL,
          payment_date DATE NOT NULL,
          notes TEXT NULL,
          created_by INTEGER NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS emails (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          customer_id INTEGER NULL,
          lead_id INTEGER NULL,
          deal_id INTEGER NULL,
          sender_id INTEGER NULL,
          recipient_email TEXT NOT NULL,
          subject TEXT NOT NULL,
          message TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'draft',
          sent_at DATETIME NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS email_templates (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          subject TEXT NOT NULL,
          body TEXT NOT NULL,
          created_by INTEGER NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS notifications (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          title TEXT NOT NULL,
          message TEXT NOT NULL,
          type TEXT NOT NULL,
          related_type TEXT NULL,
          related_id INTEGER NULL,
          is_read INTEGER NOT NULL DEFAULT 0,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS activities (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NULL,
          entity_type TEXT NOT NULL,
          entity_id INTEGER NOT NULL,
          activity_type TEXT NOT NULL,
          description TEXT NOT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS settings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          setting_key TEXT NOT NULL UNIQUE,
          setting_value TEXT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS calendar_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          description TEXT NULL,
          event_date DATE NOT NULL,
          start_time TIME NULL,
          end_time TIME NULL,
          event_type TEXT NOT NULL DEFAULT 'event',
          assigned_to INTEGER NULL,
          created_by INTEGER NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS audit_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NULL,
          action TEXT NOT NULL,
          module TEXT NOT NULL,
          ip_address TEXT NULL,
          details TEXT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS documents (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          file_name TEXT NOT NULL,
          file_path TEXT NOT NULL,
          file_size INTEGER NULL,
          category TEXT NULL,
          uploaded_by INTEGER NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS reminders (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          reminder_date DATETIME NOT NULL,
          assigned_to INTEGER NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS login_history (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          ip_address TEXT NULL,
          user_agent TEXT NULL,
          status TEXT NOT NULL DEFAULT 'success',
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS audit_trail (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NULL,
          action TEXT NOT NULL,
          target TEXT NULL,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );"""
    ]


    for stmt in schema_statements:
        cursor.execute(stmt)

    roles = [
        ('Admin', 'System administrator with full system and security access'),
        ('Manager', 'Sales and operations manager with team management and reporting access'),
        ('Sales Employee', 'Sales representative handling leads, customers, deals, and tasks'),
        ('Staff', 'Operational staff member with standard task and record viewing access')
    ]
    for r_name, r_desc in roles:
        cursor.execute("INSERT OR IGNORE INTO roles (name, description) VALUES (?, ?)", (r_name, r_desc))

    permissions = [
        ('dashboard.view', 'View executive analytics dashboard'),
        ('customers.view', 'View customer records and documents'),
        ('customers.create', 'Create new customer records'),
        ('customers.update', 'Update customer records'),
        ('customers.delete', 'Delete customer records'),
        ('leads.view', 'View leads and lead activities'),
        ('leads.create', 'Create new leads'),
        ('leads.update', 'Update lead records'),
        ('leads.delete', 'Delete leads'),
        ('leads.convert', 'Convert lead to customer'),
        ('deals.view', 'View deals and pipelines'),
        ('deals.create', 'Create new deal opportunities'),
        ('deals.update', 'Update deal stages and values'),
        ('deals.delete', 'Delete deals'),
        ('tasks.view', 'View task lists and calendars'),
        ('tasks.create', 'Create new tasks'),
        ('tasks.update', 'Update task progress and status'),
        ('tasks.delete', 'Delete tasks'),
        ('calls.view', 'View call logs'),
        ('calls.create', 'Schedule and record calls'),
        ('calls.update', 'Update call logs'),
        ('calls.delete', 'Delete call logs'),
        ('meetings.view', 'View meetings schedule'),
        ('meetings.create', 'Schedule new meetings'),
        ('meetings.update', 'Update meeting details'),
        ('meetings.delete', 'Cancel or delete meetings'),
        ('products.view', 'View product catalog and pricing'),
        ('products.create', 'Create products in catalog'),
        ('products.update', 'Update product information and stock'),
        ('products.delete', 'Delete products from catalog'),
        ('invoices.view', 'View invoices and billing'),
        ('invoices.create', 'Generate invoices'),
        ('invoices.update', 'Update invoice details'),
        ('invoices.delete', 'Delete or void invoices'),
        ('payments.view', 'View payment transaction history'),
        ('payments.create', 'Record new customer payments'),
        ('payments.update', 'Update payment records'),
        ('payments.delete', 'Delete payment records'),
        ('reports.view', 'Generate and view CRM analytics reports'),
        ('users.view', 'View user profiles'),
        ('users.create', 'Create user accounts'),
        ('users.update', 'Update user profiles and statuses'),
        ('users.delete', 'Deactivate or delete user accounts'),
        ('settings.view', 'View system settings'),
        ('settings.update', 'Modify system settings')
    ]
    for p_name, p_desc in permissions:
        cursor.execute("INSERT OR IGNORE INTO permissions (name, description) VALUES (?, ?)", (p_name, p_desc))

    # 1. Admin (role_id=1): All permissions
    cursor.execute("SELECT id FROM permissions")
    for p_row in cursor.fetchall():
        p_id = p_row[0]
        cursor.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (1, ?)", (p_id,))

    # 2. Manager (role_id=2): Executive & Team Management Permissions
    manager_perms = [
        'dashboard.view', 'customers.view', 'customers.create', 'customers.update', 'customers.delete',
        'leads.view', 'leads.create', 'leads.update', 'leads.delete', 'leads.convert',
        'deals.view', 'deals.create', 'deals.update', 'deals.delete',
        'tasks.view', 'tasks.create', 'tasks.update', 'tasks.delete',
        'calls.view', 'calls.create', 'calls.update', 'calls.delete',
        'meetings.view', 'meetings.create', 'meetings.update', 'meetings.delete',
        'products.view', 'invoices.view', 'payments.view', 'reports.view', 'users.view', 'settings.view'
    ]
    for name in manager_perms:
        cursor.execute("SELECT id FROM permissions WHERE name = ?", (name,))
        r = cursor.fetchone()
        if r:
            cursor.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (2, ?)", (r[0],))

    # 3. Sales Employee (role_id=3): Field Sales & Prospecting Permissions
    sales_perms = [
        'dashboard.view', 'customers.view', 'customers.create', 'customers.update',
        'leads.view', 'leads.create', 'leads.update', 'leads.convert',
        'deals.view', 'deals.create', 'deals.update',
        'tasks.view', 'tasks.create', 'tasks.update',
        'calls.view', 'calls.create', 'calls.update',
        'meetings.view', 'meetings.create', 'meetings.update',
        'products.view', 'invoices.view'
    ]
    for name in sales_perms:
        cursor.execute("SELECT id FROM permissions WHERE name = ?", (name,))
        r = cursor.fetchone()
        if r:
            cursor.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (3, ?)", (r[0],))

    # 4. Staff (role_id=4): Operational Viewing & Progress Update Permissions
    staff_perms = [
        'dashboard.view', 'customers.view',
        'tasks.view', 'tasks.update',
        'calls.view',
        'meetings.view',
        'products.view'
    ]
    for name in staff_perms:
        cursor.execute("SELECT id FROM permissions WHERE name = ?", (name,))
        r = cursor.fetchone()
        if r:
            cursor.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (4, ?)", (r[0],))



    users = [
        (1, 'Super', 'Admin', 'admin@crm.local', '+1-555-0100', 'scrypt:32768:8:1$VZM2MFSG2uskfIj1$0cc66b74a71d7115a88b773b5ee0b3758b62ffe60528e3b14b3d75e2e859429aecbb6e901a59ac73000f6272fbd2c8b93a78a9686c06fbd10feaeb506b61e745', 'active'),
        (2, 'Morgan', 'Manager', 'manager@crm.local', '+1-555-0101', 'scrypt:32768:8:1$9Lgz4WXIwcQa237s$7dcdd649b636bd3c6da151bcb12e2302cc31d5b62e73a78875874f720e0130d3a74f15cf7e7c2357d05439ad1767bbedceddc901b7842401fa94c06346af7b5b', 'active'),
        (3, 'Sarah', 'Sales', 'sales@crm.local', '+1-555-0102', 'scrypt:32768:8:1$z0YMyL53aXDrpsgX$4cff470149fff1c06fdcbeef582a94d15d0df0fa6ed9dc6ffc9ec143032970276c4d563f7d17ca84141116db9762ab54d174da476fa56899865bde2f819afe10', 'active'),
        (4, 'Steve', 'Staff', 'staff@crm.local', '+1-555-0103', 'scrypt:32768:8:1$LttrBHLXnQjMf9ME$e82bc44299ea637147a2da2c8786b680817482cb84f0db559e876cab637e2b153a4e0fe9764b720727e5e92c2f9c447ad73c99ec53473bd66c1a7b74545c13ab', 'active')
    ]
    for r_id, fn, ln, email, phone, pw, st in users:
        cursor.execute("INSERT OR IGNORE INTO users (role_id, first_name, last_name, email, phone, password_hash, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (r_id, fn, ln, email, phone, pw, st))

    settings = [
        ('system_name', 'Apex Enterprise CRM'),
        ('company_name', 'Apex Dynamics Inc.'),
        ('default_currency', 'USD'),
        ('default_timezone', 'UTC'),
        ('lead_auto_assignment', 'true'),
        ('invoice_due_days', '30')
    ]
    for k, v in settings:
        cursor.execute("INSERT OR IGNORE INTO settings (setting_key, setting_value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()


def get_db_config(include_database=True):
    """
    Extract database connection parameters from Config or fallback environment defaults.
    Never exposes passwords in return string representation.
    """
    if Config:
        host = Config.DB_HOST
        port = Config.DB_PORT
        user = Config.DB_USER
        password = Config.DB_PASSWORD
        database = Config.DB_NAME
    else:
        host = os.getenv("DB_HOST", "localhost")
        port = int(os.getenv("DB_PORT", 3306))
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "")
        database = os.getenv("DB_NAME", "crm_database")

    config = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "connect_timeout": 5,
        "charset": "utf8mb4"
    }

    if include_database:
        config["database"] = database

    return config


def get_safe_config_summary(config=None):
    """
    Returns a copy of the database configuration safe for logging (passwords masked).
    """
    if config is None:
        config = get_db_config()
    safe = dict(config)
    if "password" in safe:
        safe["password"] = "******" if safe["password"] else "[EMPTY]"
    return safe


_MYSQL_UNAVAILABLE = False


def get_db_connection(include_database=True, autocommit=False):
    """
    Establish and return a database connection.
    Tries MySQL connection first. If MySQL is unreachable (e.g. cloud deployment without MySQL daemon),
    automatically falls back to SQLite database for seamless operation.
    """
    global _MYSQL_UNAVAILABLE

    db_type = os.getenv("DB_TYPE", "").lower()
    is_cloud = bool(os.getenv("RENDER") or os.getenv("IS_CLOUD"))
    db_host = os.getenv("DB_HOST", "localhost")

    if db_type == "sqlite" or _MYSQL_UNAVAILABLE or (is_cloud and db_host in ("localhost", "127.0.0.1")):
        init_sqlite_db()
        return SQLiteConnectionWrapper(SQLITE_DB_PATH)

    db_config = get_db_config(include_database=include_database)
    safe_summary = get_safe_config_summary(db_config)

    try:
        import mysql.connector
        connection = mysql.connector.connect(autocommit=autocommit, **db_config)
        if connection.is_connected():
            return connection
    except Exception as err:
        _MYSQL_UNAVAILABLE = True
        logger.info(
            "MySQL connection unavailable (%s: Target %s:%s). Active mode set to SQLite.",
            str(err),
            safe_summary.get("host"),
            safe_summary.get("port")
        )

    # Automatic Fallback to SQLite when MySQL is not available
    try:
        init_sqlite_db()
        return SQLiteConnectionWrapper(SQLITE_DB_PATH)
    except Exception as sqlite_err:
        logger.error("SQLite fallback failed: %s", str(sqlite_err))
        return None



@contextmanager
def get_db_cursor(commit=False, dictionary=True):
    """
    Context manager that yields a cursor and ensures connection & cursor are closed cleanly.
    """
    conn = get_db_connection(include_database=True)
    if not conn:
        raise ConnectionError("Unable to establish database connection (MySQL and SQLite fallback failed).")

    cursor = None
    try:
        cursor = conn.cursor(dictionary=dictionary)
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        if conn and hasattr(conn, "rollback") and conn.is_connected():
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and hasattr(conn, "close") and conn.is_connected():
            conn.close()


def execute_query(query, params=None, fetch_one=False, fetch_all=True, commit=False, dictionary=True):
    """
    Reusable helper to execute a query and return results safely with automatic resource cleanup.
    """
    try:
        with get_db_cursor(commit=commit, dictionary=dictionary) as cursor:
            cursor.execute(query, params or ())
            if commit:
                return ({"affected_rows": cursor.rowcount, "last_id": cursor.lastrowid}, None)
            if fetch_one:
                return (cursor.fetchone(), None)
            if fetch_all:
                return (cursor.fetchall(), None)
            return (None, None)
    except Exception as e:
        logger.error("Query execution error: %s", str(e))
        return (None, str(e))


def init_db(schema_file=None):
    """
    Initialize database. Uses MySQL schema if MySQL server available, else initializes SQLite.
    """
    conn = get_db_connection(include_database=False)
    if isinstance(conn, SQLiteConnectionWrapper):
        init_sqlite_db()
        return (True, "SQLite database initialized successfully.")

    if schema_file is None:
        schema_file = BASE_DIR / "database" / "schema.sql"

    if not Path(schema_file).exists():
        return (False, f"Schema file not found at {schema_file}")

    with open(schema_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    server_conn = get_db_connection(include_database=False, autocommit=True)
    if not server_conn or isinstance(server_conn, SQLiteConnectionWrapper):
        init_sqlite_db()
        return (True, "SQLite database fallback initialized successfully.")

    try:
        cursor = server_conn.cursor()
        db_name = get_db_config().get("database", "crm_database")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.close()
    except Exception as e:
        return (False, f"Failed to create database: {str(e)}")
    finally:
        server_conn.close()

    db_conn = get_db_connection(include_database=True, autocommit=True)
    if not db_conn:
        return (False, f"Could not connect to database `{db_name}`.")

    try:
        cursor = db_conn.cursor()
        statements = []
        current_stmt = []
        for line in sql_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--") or stripped.startswith("/*"):
                continue
            current_stmt.append(line)
            if stripped.endswith(";"):
                stmt = "\n".join(current_stmt).strip()
                if stmt:
                    statements.append(stmt)
                current_stmt = []

        executed_count = 0
        for stmt in statements:
            try:
                cursor.execute(stmt)
                executed_count += 1
            except Exception as stmt_err:
                logger.error("Error executing statement:\n%s\nError: %s", stmt[:100], str(stmt_err))
                cursor.close()
                db_conn.close()
                return (False, f"SQL Execution error in statement: {stmt_err}")

        cursor.close()
        db_conn.close()
        return (True, f"Database `{db_name}` initialized successfully with {executed_count} statements executed.")

    except Exception as e:
        if hasattr(db_conn, "is_connected") and db_conn.is_connected():
            db_conn.close()
        return (False, f"Database initialization failed: {str(e)}")


def check_db_connection():
    """
    Diagnostic helper to test database connectivity status without exposing credentials.
    """
    safe_config = get_safe_config_summary()
    connection = get_db_connection(include_database=True)

    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            is_sqlite = isinstance(connection, SQLiteConnectionWrapper)
            connection.close()
            return {
                "status": "connected",
                "engine": "SQLite (Cloud Fallback)" if is_sqlite else "MySQL",
                "message": "Database connection verified successfully",
                "config": safe_config
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Query execution failed: {str(e)}",
                "config": safe_config
            }
    else:
        return {
            "status": "disconnected",
            "message": "Could not connect to database server.",
            "config": safe_config
        }


if __name__ == "__main__":
    result = check_db_connection()
    print("Database Diagnostic Result:")
    print(result)
