"""
CRM Global Activity Logging Service
Logs actions across Customers, Leads, Deals, Tasks, Calls, and Meetings to the `activities` table.
"""

import logging
from database.database import execute_query

logger = logging.getLogger("crm.activity_service")


def log_activity(user_id: int | None, entity_type: str, entity_id: int, activity_type: str, description: str):
    """
    Log an event to the global activities table.
    """
    try:
        safe_entity_id = entity_id if entity_id is not None else 0
        sql = """
            INSERT INTO activities (user_id, entity_type, entity_id, activity_type, description, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """
        execute_query(sql, (user_id, entity_type, safe_entity_id, activity_type, description), commit=True)
    except Exception as e:
        logger.error("Failed to log activity: %s", str(e))


def get_recent_activities(limit: int = 10, entity_type: str | None = None, entity_id: int | None = None):
    """
    Fetch recent activities with user name for dashboard or entity detail views.
    """
    params = []
    where_clauses = []

    if entity_type:
        where_clauses.append("a.entity_type = %s")
        params.append(entity_type)
    if entity_id is not None:
        where_clauses.append("a.entity_id = %s")
        params.append(entity_id)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    sql = f"""
        SELECT a.id, a.user_id, a.entity_type, a.entity_id, a.activity_type,
               a.description, a.created_at,
               u.first_name, u.last_name, u.email, r.name as role_name
        FROM activities a
        LEFT JOIN users u ON a.user_id = u.id
        LEFT JOIN roles r ON u.role_id = r.id
        {where_sql}
        ORDER BY a.created_at DESC
        LIMIT %s
    """
    params.append(limit)

    rows, err = execute_query(sql, tuple(params), fetch_all=True)
    if err:
        logger.error("Error fetching activities: %s", err)
        return []

    # Format output
    result = []
    for r in rows or []:
        user_display = f"{r['first_name']} {r['last_name']}" if r.get("first_name") else "System"
        result.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "user_name": user_display,
            "entity_type": r["entity_type"],
            "entity_id": r["entity_id"],
            "activity_type": r["activity_type"],
            "description": r["description"],
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None
        })
    return result
