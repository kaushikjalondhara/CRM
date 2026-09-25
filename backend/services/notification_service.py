"""
CRM Notification Service
Handles creating, querying, marking, and deleting user notifications.
"""

import logging
from database.database import execute_query

logger = logging.getLogger("crm.notification_service")

VALID_NOTIFICATION_TYPES = {
    "task", "meeting", "call", "payment", "invoice", "lead", "deal", "system"
}


def create_notification(user_id: int, title: str, message: str,
                        notif_type: str = "system",
                        related_type: str | None = None,
                        related_id: int | None = None) -> tuple[int | None, str | None]:
    """
    Create a notification record for a specific user.
    """
    if not user_id:
        return None, "user_id is required"
    if not title or not title.strip():
        return None, "Notification title is required"
    if not message or not message.strip():
        return None, "Notification message is required"

    if notif_type not in VALID_NOTIFICATION_TYPES:
        notif_type = "system"

    sql = """
        INSERT INTO notifications (user_id, title, message, type, related_type, related_id, is_read, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, 0, NOW())
    """
    params = (user_id, title.strip(), message.strip(), notif_type, related_type, related_id)
    res, err = execute_query(sql, params, commit=True)
    if err:
        logger.error("Failed to create notification for user %s: %s", user_id, err)
        return None, err

    notif_id = res.get("last_id") if isinstance(res, dict) else res
    return notif_id, None


def list_notifications(user_id: int, is_read: int | None = None, notif_type: str | None = None,
                       page: int = 1, per_page: int = 20) -> tuple[dict | None, str | None]:
    """
    List notifications for a user with optional filter by read status and type.
    """
    where_clauses = ["user_id = %s"]
    params: list = [user_id]

    if is_read is not None:
        where_clauses.append("is_read = %s")
        params.append(1 if is_read else 0)

    if notif_type and notif_type in VALID_NOTIFICATION_TYPES:
        where_clauses.append("type = %s")
        params.append(notif_type)

    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    # Count total
    count_sql = f"SELECT COUNT(*) as total FROM notifications {where_sql}"
    count_res, err = execute_query(count_sql, tuple(params), fetch_one=True)
    if err:
        return None, err
    total = count_res["total"] if count_res else 0

    # Unread total for user
    unread_res, _ = execute_query("SELECT COUNT(*) as unread FROM notifications WHERE user_id = %s AND is_read = 0", (user_id,), fetch_one=True)
    unread_count = unread_res["unread"] if unread_res else 0

    offset = max(0, (page - 1) * per_page)
    fetch_sql = f"""
        SELECT id, user_id, title, message, type, related_type, related_id, is_read, created_at
        FROM notifications
        {where_sql}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    fetch_params = list(params) + [per_page, offset]
    rows, err = execute_query(fetch_sql, tuple(fetch_params), fetch_all=True)
    if err:
        return None, err

    notifications = []
    for r in (rows or []):
        notifications.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "title": r["title"],
            "message": r["message"],
            "type": r["type"],
            "related_type": r["related_type"],
            "related_id": r["related_id"],
            "is_read": bool(r["is_read"]),
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None
        })

    return {
        "notifications": notifications,
        "unread_count": unread_count,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 1
    }, None


def get_unread_count(user_id: int) -> int:
    """
    Return unread notification count for a user.
    """
    res, err = execute_query(
        "SELECT COUNT(*) as unread FROM notifications WHERE user_id = %s AND is_read = 0",
        (user_id,),
        fetch_one=True
    )
    if err or not res:
        return 0
    return int(res["unread"])


def mark_as_read(notification_id: int, user_id: int) -> tuple[bool, str | None]:
    """
    Mark a single notification as read for the user.
    """
    sql = "UPDATE notifications SET is_read = 1 WHERE id = %s AND user_id = %s"
    _, err = execute_query(sql, (notification_id, user_id), commit=True)
    if err:
        return False, err
    return True, None


def mark_all_as_read(user_id: int) -> tuple[int, str | None]:
    """
    Mark all notifications as read for a user.
    """
    sql = "UPDATE notifications SET is_read = 1 WHERE user_id = %s AND is_read = 0"
    _, err = execute_query(sql, (user_id,), commit=True)
    if err:
        return 0, err
    return 1, None


def delete_notification(notification_id: int, user_id: int) -> tuple[bool, str | None]:
    """
    Delete a notification.
    """
    sql = "DELETE FROM notifications WHERE id = %s AND user_id = %s"
    _, err = execute_query(sql, (notification_id, user_id), commit=True)
    if err:
        return False, err
    return True, None
