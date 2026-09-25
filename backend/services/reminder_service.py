"""
CRM Automatic Reminder Service
Scans MySQL records for upcoming meetings, due tasks, overdue invoices, and lead follow-ups.
Deduplicates reminders and dispatches notifications.
"""

import datetime
from database.database import execute_query
from backend.services.notification_service import create_notification


def check_and_generate_reminders() -> dict:
    """
    Scans database and automatically creates reminders & notifications.
    Deduplicated per entity per day to prevent spam.
    """
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow = now + datetime.timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%d %H:%M:%S")

    created_count = 0

    # 1. Upcoming Meetings (within next 24 hours)
    m_sql = """
        SELECT m.id, m.title, m.meeting_date, m.start_time, m.created_by,
               c.first_name, c.last_name
        FROM meetings m
        LEFT JOIN customers c ON m.customer_id = c.id
        WHERE m.meeting_date >= CURDATE() AND m.status = 'scheduled'
    """
    meetings, _ = execute_query(m_sql, fetch_all=True)

    for m in (meetings or []):
        uid = m.get("created_by") or 1
        m_id = m["id"]
        m_time = f"{m.get('meeting_date')} {m.get('start_time')}"
        # Check deduplication
        dup, _ = execute_query(
            "SELECT id FROM reminders WHERE related_type = 'meeting' AND related_id = %s AND DATE(created_at) = CURDATE()",
            (m_id,), fetch_one=True
        )
        if not dup:
            cname = f" with {m['first_name']} {m['last_name']}" if m.get("first_name") else ""
            title = f"Upcoming Meeting: {m['title']}"
            msg = f"Scheduled meeting{cname} at {m_time}."

            execute_query(
                "INSERT INTO reminders (user_id, title, message, reminder_type, related_type, related_id, remind_at, is_sent, sent_at, created_at) VALUES (%s, %s, %s, 'meeting', 'meeting', %s, NOW(), 1, NOW(), NOW())",
                (uid, title, msg, m_id),
                commit=True
            )
            create_notification(
                user_id=uid,
                title=title,
                message=msg,
                notif_type="meeting",
                related_type="meeting",
                related_id=m_id
            )
            created_count += 1

    # 2. Tasks Due Today or Overdue
    t_sql = """
        SELECT t.id, t.title, t.due_date, t.assigned_to, t.priority
        FROM tasks t
        WHERE t.due_date <= %s AND t.status != 'completed'
    """
    tasks, _ = execute_query(t_sql, (today_str,), fetch_all=True)

    for t in (tasks or []):
        uid = t["assigned_to"] or 1
        t_id = t["id"]
        dup, _ = execute_query(
            "SELECT id FROM reminders WHERE related_type = 'task' AND related_id = %s AND DATE(created_at) = CURDATE()",
            (t_id,), fetch_one=True
        )
        if not dup:
            is_overdue = t["due_date"].strftime("%Y-%m-%d") < today_str if t.get("due_date") else False
            prefix = "Overdue Task Alert" if is_overdue else "Task Due Today"
            title = f"{prefix}: {t['title']}"
            msg = f"Priority: {t.get('priority', 'medium').capitalize()}. Due: {t['due_date']}."

            execute_query(
                "INSERT INTO reminders (user_id, title, message, reminder_type, related_type, related_id, remind_at, is_sent, sent_at, created_at) VALUES (%s, %s, %s, 'task', 'task', %s, NOW(), 1, NOW(), NOW())",
                (uid, title, msg, t_id),
                commit=True
            )
            create_notification(
                user_id=uid,
                title=title,
                message=msg,
                notif_type="task",
                related_type="task",
                related_id=t_id
            )
            created_count += 1

    # 3. Overdue Invoices
    i_sql = """
        SELECT i.id, i.invoice_number, i.remaining_amount, i.due_date, i.created_by,
               c.first_name, c.last_name
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        WHERE i.due_date < %s AND i.status IN ('sent', 'partially_paid', 'overdue')
    """
    invoices, _ = execute_query(i_sql, (today_str,), fetch_all=True)

    for inv in (invoices or []):
        uid = inv["created_by"] or 1
        inv_id = inv["id"]
        dup, _ = execute_query(
            "SELECT id FROM reminders WHERE related_type = 'invoice' AND related_id = %s AND DATE(created_at) = CURDATE()",
            (inv_id,), fetch_one=True
        )
        if not dup:
            title = f"Overdue Invoice Alert: {inv['invoice_number']}"
            msg = f"Client: {inv['first_name']} {inv['last_name']}. Outstanding: ₹{float(inv['remaining_amount']):,.2f}. Due date was {inv['due_date']}."

            execute_query(
                "INSERT INTO reminders (user_id, title, message, reminder_type, related_type, related_id, remind_at, is_sent, sent_at, created_at) VALUES (%s, %s, %s, 'invoice', 'invoice', %s, NOW(), 1, NOW(), NOW())",
                (uid, title, msg, inv_id),
                commit=True
            )
            create_notification(
                user_id=uid,
                title=title,
                message=msg,
                notif_type="invoice",
                related_type="invoice",
                related_id=inv_id
            )
            created_count += 1

    return {
        "status": "success",
        "reminders_created": created_count,
        "checked_at": now.strftime("%Y-%m-%d %H:%M:%S")
    }


def list_reminders(user_id: int, limit: int = 20) -> list:
    """Retrieve active reminders for a user."""
    sql = """
        SELECT id, title, message, reminder_type, related_type, related_id, remind_at, created_at
        FROM reminders
        WHERE user_id = %s OR user_id IS NULL
        ORDER BY created_at DESC
        LIMIT %s
    """
    rows, _ = execute_query(sql, (user_id, limit), fetch_all=True)
    reminders = []
    for r in (rows or []):
        reminders.append({
            "id": r["id"],
            "title": r["title"],
            "message": r["message"],
            "reminder_type": r["reminder_type"],
            "related_type": r["related_type"],
            "related_id": r["related_id"],
            "remind_at": r["remind_at"].strftime("%Y-%m-%d %H:%M:%S") if r.get("remind_at") else None,
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r.get("created_at") else None
        })
    return reminders


_scheduler_running = False

def start_reminder_scheduler(interval_seconds: int = 300):
    """Start non-blocking daemon thread to periodically check for overdue tasks, meetings, invoices."""
    global _scheduler_running
    if _scheduler_running:
        return
    _scheduler_running = True

    import threading
    import time

    def _loop():
        time.sleep(10)
        while _scheduler_running:
            try:
                check_and_generate_reminders()
            except Exception:
                pass
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_loop, daemon=True, name="CRM-ReminderScheduler")
    thread.start()

