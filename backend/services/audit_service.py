"""
CRM Audit Log Service
Tracks immutable operational changes, logins, updates, and deletes across CRM entities.
"""

import json
from flask import request
from database.database import execute_query


def log_audit(user_id: int | None, action: str, entity: str, entity_id: int | None = None,
              old_val: dict | str | None = None, new_val: dict | str | None = None,
              ip_address: str | None = None, user_agent: str | None = None):
    """
    Log an immutable audit entry to MySQL `audit_logs` table.
    """
    try:
        # Extract IP and User Agent from Flask context if available and not passed
        if not ip_address:
            try:
                ip_address = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1")
            except Exception:
                ip_address = "127.0.0.1"

        if not user_agent:
            try:
                user_agent = request.headers.get("User-Agent", "")[:255]
            except Exception:
                user_agent = "System"

        old_str = json.dumps(old_val) if isinstance(old_val, (dict, list)) else (str(old_val) if old_val is not None else None)
        new_str = json.dumps(new_val) if isinstance(new_val, (dict, list)) else (str(new_val) if new_val is not None else None)

        sql = """
            INSERT INTO audit_logs (user_id, action, entity, entity_id, old_value, new_value, ip_address, user_agent, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        execute_query(sql, (user_id, action, entity, entity_id, old_str, new_str, ip_address, user_agent), commit=True)
    except Exception as ex:
        # Logging audit failure shouldn't crash the primary business transaction
        pass


def _format_dt(val, fmt="%Y-%m-%d %H:%M:%S"):
    if not val:
        return None
    if hasattr(val, "strftime"):
        return val.strftime(fmt)
    return str(val)


def list_audit_logs(search: str | None = None, entity: str | None = None, action: str | None = None,
                    user_id: int | None = None, start_date: str | None = None,
                    end_date: str | None = None, page: int = 1, per_page: int = 25) -> tuple[dict | None, str | None]:
    """
    Fetch paginated audit log entries with filters.
    """
    try:
        page = max(1, page or 1)
        per_page = max(1, per_page or 25)

        where = []
        params = []

        if search and str(search).strip():
            where.append("(a.action LIKE %s OR a.entity LIKE %s OR u.first_name LIKE %s OR u.last_name LIKE %s OR a.ip_address LIKE %s)")
            t = f"%{str(search).strip()}%"
            params.extend([t, t, t, t, t])

        if entity and str(entity).strip():
            where.append("a.entity = %s")
            params.append(str(entity).strip())

        if action and str(action).strip():
            where.append("a.action = %s")
            params.append(str(action).strip())

        if user_id:
            try:
                where.append("a.user_id = %s")
                params.append(int(user_id))
            except (ValueError, TypeError):
                pass

        if start_date and str(start_date).strip():
            s_date = str(start_date).strip()
            where.append("a.created_at >= %s")
            params.append(s_date if " " in s_date else f"{s_date} 00:00:00")

        if end_date and str(end_date).strip():
            e_date = str(end_date).strip()
            where.append("a.created_at <= %s")
            params.append(e_date if " " in e_date else f"{e_date} 23:59:59")

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        count_sql = f"""
            SELECT COUNT(*) as total
            FROM audit_logs a
            LEFT JOIN users u ON a.user_id = u.id
            {where_sql}
        """
        count_res, err = execute_query(count_sql, tuple(params), fetch_one=True)
        if err:
            return None, err

        total = count_res["total"] if count_res and "total" in count_res else 0
        offset = max(0, (page - 1) * per_page)

        sql = f"""
            SELECT a.id, a.user_id, a.action, a.entity, a.entity_id,
                   a.old_value, a.new_value, a.ip_address, a.user_agent, a.created_at,
                   u.first_name, u.last_name, u.email, r.name as role_name
            FROM audit_logs a
            LEFT JOIN users u ON a.user_id = u.id
            LEFT JOIN roles r ON u.role_id = r.id
            {where_sql}
            ORDER BY a.id DESC
            LIMIT %s OFFSET %s
        """
        fetch_params = list(params) + [per_page, offset]
        rows, err = execute_query(sql, tuple(fetch_params), fetch_all=True)
        if err:
            return None, err

        logs = []
        for r in (rows or []):
            fn = r.get("first_name") or ""
            ln = r.get("last_name") or ""
            uname = f"{fn} {ln}".strip() or "System"
            entity_val = r.get("entity") or "system"

            logs.append({
                "id": r.get("id"),
                "user_id": r.get("user_id"),
                "user_name": uname,
                "actor_name": uname,
                "user_email": r.get("email"),
                "actor_email": r.get("email"),
                "role": r.get("role_name") or "System",
                "action": r.get("action") or "",
                "entity": entity_val,
                "entity_type": entity_val,
                "entity_id": r.get("entity_id"),
                "old_value": r.get("old_value"),
                "new_value": r.get("new_value"),
                "ip_address": r.get("ip_address") or "N/A",
                "user_agent": r.get("user_agent") or "N/A",
                "created_at": _format_dt(r.get("created_at"))
            })

        return {
            "logs": logs,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 1
        }, None
    except Exception as ex:
        return None, str(ex)
