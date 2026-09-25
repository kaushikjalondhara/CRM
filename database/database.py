import os
import sys
import logging
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


def get_db_connection(include_database=True, autocommit=False):
    """
    Establish and return a MySQL database connection.
    Gracefully handles connection errors without crashing or leaking sensitive credentials.

    Args:
        include_database (bool): If True, connects to specified DB. If False, connects to MySQL server root.
        autocommit (bool): Connection autocommit setting.

    Returns:
        mysql.connector.connection.MySQLConnection or None
    """
    try:
        import mysql.connector
        from mysql.connector import Error as MySQLError
    except ImportError:
        logger.warning("mysql-connector-python is not installed. Database operations unavailable.")
        return None

    db_config = get_db_config(include_database=include_database)
    safe_summary = get_safe_config_summary(db_config)

    try:
        connection = mysql.connector.connect(autocommit=autocommit, **db_config)
        if connection.is_connected():
            return connection
    except MySQLError as err:
        # Sanitize error to avoid leaking credentials
        logger.warning(
            "MySQL connection failed: %s (Target: %s:%s, User: %s, DB: %s).",
            err.msg if hasattr(err, "msg") else str(err),
            safe_summary.get("host"),
            safe_summary.get("port"),
            safe_summary.get("user"),
            safe_summary.get("database", "[None]")
        )
        return None
    except Exception as ex:
        logger.warning("Unexpected error connecting to MySQL server: %s", str(ex))
        return None

    return None


@contextmanager
def get_db_cursor(commit=False, dictionary=True):
    """
    Context manager that yields a cursor and ensures connection & cursor are closed cleanly.

    Usage:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT * FROM users")
            results = cursor.fetchall()
    """
    conn = get_db_connection(include_database=True)
    if not conn:
        raise ConnectionError("Unable to establish MySQL database connection. Verify server is running and .env is configured.")

    cursor = None
    try:
        cursor = conn.cursor(dictionary=dictionary)
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        if conn and conn.is_connected():
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def execute_query(query, params=None, fetch_one=False, fetch_all=True, commit=False, dictionary=True):
    """
    Reusable helper to execute a query and return results safely with automatic resource cleanup.

    Returns:
        tuple: (data, error_message)
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
    Initialize the database using schema.sql.
    Creates crm_database if it does not exist, and executes all DDL and seed statements.

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        import mysql.connector
    except ImportError:
        return (False, "mysql-connector-python not installed")

    if schema_file is None:
        schema_file = BASE_DIR / "database" / "schema.sql"

    if not Path(schema_file).exists():
        return (False, f"Schema file not found at {schema_file}")

    with open(schema_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Step 1: Connect to server without database to ensure DB creation
    server_conn = get_db_connection(include_database=False, autocommit=True)
    if not server_conn:
        return (False, "Could not connect to MySQL server. Ensure MySQL is running.")

    try:
        cursor = server_conn.cursor()
        db_name = get_db_config().get("database", "crm_database")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.close()
    except Exception as e:
        return (False, f"Failed to create database: {str(e)}")
    finally:
        server_conn.close()

    # Step 2: Connect to target database and execute statements
    db_conn = get_db_connection(include_database=True, autocommit=True)
    if not db_conn:
        return (False, f"Could not connect to database `{db_name}`.")

    try:
        cursor = db_conn.cursor()
        # Parse and execute statements
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
        if db_conn.is_connected():
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
            connection.close()
            return {
                "status": "connected",
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
            "message": "Could not connect to MySQL server. Ensure MySQL is running and .env credentials are correct.",
            "config": safe_config
        }


if __name__ == "__main__":
    result = check_db_connection()
    print("Database Diagnostic Result:")
    print(result)
