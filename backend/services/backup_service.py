"""
CRM Database Backup & Restore Service
Generates portable SQL database dumps and handles protected administrative restores.
"""

import os
import datetime
from pathlib import Path
from database.database import execute_query, get_db_cursor
from backend.services.audit_service import log_audit

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKUPS_FOLDER = BASE_DIR / "uploads" / "backups"


def _ensure_backups_dir():
    os.makedirs(BACKUPS_FOLDER, exist_ok=True)


def create_database_backup(user_id: int | None = None, backup_type: str = "full") -> tuple[dict | None, str | None]:
    """
    Export all MySQL database tables and records to a standalone SQL file.
    Logs result in `backup_logs` table.
    """
    _ensure_backups_dir()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"crm_backup_{timestamp}.sql"
    file_path = BACKUPS_FOLDER / filename

    try:
        tables_res, err = execute_query("SHOW TABLES;", fetch_all=True)
        if err or not tables_res:
            return None, err or "No database tables found"

        table_names = [list(r.values())[0] for r in tables_res]

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"-- ==========================================================\n")
            f.write(f"-- Apex CRM Automated Database Backup\n")
            f.write(f"-- Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Database: crm_database\n")
            f.write(f"-- ==========================================================\n\n")
            f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

            for tbl in table_names:
                # Get CREATE TABLE statement
                create_res, _ = execute_query(f"SHOW CREATE TABLE `{tbl}`;", fetch_one=True)
                if create_res and "Create Table" in create_res:
                    f.write(f"-- Table structure for `{tbl}`\n")
                    f.write(f"DROP TABLE IF EXISTS `{tbl}`;\n")
                    f.write(f"{create_res['Create Table']};\n\n")

                # Get rows
                rows, _ = execute_query(f"SELECT * FROM `{tbl}`;", fetch_all=True)
                if rows:
                    f.write(f"-- Dumping data for `{tbl}` ({len(rows)} records)\n")
                    cols = list(rows[0].keys())
                    cols_str = ", ".join([f"`{c}`" for c in cols])

                    for r in rows:
                        val_parts = []
                        for c in cols:
                            val = r[c]
                            if val is None:
                                val_parts.append("NULL")
                            elif isinstance(val, (int, float)):
                                val_parts.append(str(val))
                            elif isinstance(val, (datetime.date, datetime.datetime)):
                                val_parts.append(f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'")
                            else:
                                escaped = str(val).replace("\\", "\\\\").replace("'", "''").replace("\n", "\\n").replace("\r", "\\r")
                                val_parts.append(f"'{escaped}'")

                        f.write(f"INSERT INTO `{tbl}` ({cols_str}) VALUES ({', '.join(val_parts)});\n")
                    f.write("\n")

            f.write("SET FOREIGN_KEY_CHECKS = 1;\n")
            f.write("-- Backup successfully completed.\n")

        file_size = os.path.getsize(file_path)

        # Log into backup_logs
        sql = """
            INSERT INTO backup_logs (user_id, file_name, file_size, backup_type, status, notes, created_at)
            VALUES (%s, %s, %s, %s, 'success', %s, NOW())
        """
        res, err = execute_query(sql, (
            user_id, filename, file_size, backup_type, f"Automated export of {len(table_names)} tables"
        ), commit=True)

        backup_id = res.get("last_id") if isinstance(res, dict) else res
        log_audit(user_id, "backup_created", "backup", backup_id, None, {"filename": filename, "size": file_size})

        return {
            "id": backup_id,
            "file_name": filename,
            "filename": filename,
            "file_size": file_size,
            "file_size_formatted": f"{round(file_size / 1024, 1)} KB",
            "tables_count": len(table_names),
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, None

    except Exception as ex:
        if file_path.exists():
            try:
                os.remove(file_path)
            except Exception:
                pass
        return None, f"Backup creation error: {str(ex)}"


def list_backups() -> list:
    """Retrieve history of database backups."""
    sql = """
        SELECT b.id, b.user_id, b.file_name, b.file_size, b.backup_type, b.status, b.notes, b.created_at,
               u.first_name, u.last_name
        FROM backup_logs b
        LEFT JOIN users u ON b.user_id = u.id
        ORDER BY b.id DESC
    """
    rows, _ = execute_query(sql, fetch_all=True)
    backups = []
    for r in (rows or []):
        uname = f"{r['first_name']} {r['last_name']}".strip() if r.get("first_name") else "Admin"
        backups.append({
            "id": r["id"],
            "file_name": r["file_name"],
            "filename": r["file_name"],
            "file_size": r["file_size"],
            "file_size_formatted": f"{round((r['file_size'] or 0) / 1024, 1)} KB",
            "backup_type": r["backup_type"],
            "status": r["status"],
            "created_by": uname,
            "notes": r.get("notes") or "",
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r.get("created_at") else None
        })
    return backups


def get_backup(identifier: int | str) -> tuple[dict | None, str | None]:
    """Get metadata for a single backup by ID or file_name."""
    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
        sql = "SELECT id, file_name, file_size FROM backup_logs WHERE id = %s"
        r, err = execute_query(sql, (int(identifier),), fetch_one=True)
    else:
        sql = "SELECT id, file_name, file_size FROM backup_logs WHERE file_name = %s"
        r, err = execute_query(sql, (str(identifier),), fetch_one=True)

    if err or not r:
        return None, err or "Backup record not found"
    return r, None


def restore_database_backup(backup_id: int, user_id: int | None = None, confirmation_code: str = "") -> tuple[bool, str | None]:
    """
    Protected database restore. Requires exact confirmation code 'CONFIRM_RESTORE'.
    """
    if confirmation_code != "CONFIRM_RESTORE":
        return False, "Security verification failed. Confirmation code 'CONFIRM_RESTORE' required."

    rec, err = get_backup(backup_id)
    if err or not rec:
        return False, err or "Backup file not found"

    file_path = BACKUPS_FOLDER / rec["file_name"]
    if not file_path.exists():
        return False, f"Backup file '{rec['file_name']}' is missing from disk storage"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            sql_content = f.read()

        statements = [stmt.strip() for stmt in sql_content.split(";\n") if stmt.strip()]

        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            for stmt in statements:
                if stmt.startswith("--") or not stmt:
                    continue
                cursor.execute(stmt)
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        log_audit(user_id, "backup_restored", "backup", backup_id, None, {"filename": rec["file_name"]})
        return True, None

    except Exception as ex:
        return False, f"Database restore failed: {str(ex)}"
