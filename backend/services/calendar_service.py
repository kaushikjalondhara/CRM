"""
CRM Calendar Service
Aggregates scheduled Meetings, Calls, Tasks, and Custom Events from MySQL.
"""

from database.database import execute_query
from backend.services.activity_service import log_activity


def get_calendar_events(start_date: str | None = None, end_date: str | None = None,
                        event_type: str | None = None, current_user: dict | None = None) -> list:
    """
    Fetch and aggregate events across meetings, calls, tasks, and custom calendar events.
    """
    events = []

    # 1. Custom Calendar Events from `calendar_events` table
    ce_sql = """
        SELECT ce.id, ce.title, ce.description, ce.event_type, ce.start_time, ce.end_time, ce.status,
               c.first_name as c_fn, c.last_name as c_ln, c.company_name as c_company,
               l.first_name as l_fn, l.last_name as l_ln
        FROM calendar_events ce
        LEFT JOIN customers c ON ce.customer_id = c.id
        LEFT JOIN leads l ON ce.lead_id = l.id
        ORDER BY ce.start_time ASC
    """
    ce_rows, _ = execute_query(ce_sql, fetch_all=True)
    for r in (ce_rows or []):
        cust = f"{r['c_fn']} {r['c_ln']}".strip() if r.get("c_fn") else None
        lead = f"{r['l_fn']} {r['l_ln']}".strip() if r.get("l_fn") else None
        events.append({
            "id": f"event_{r['id']}",
            "raw_id": r["id"],
            "title": r["title"],
            "description": r.get("description") or "",
            "start": r["start_time"].isoformat() if r.get("start_time") else None,
            "end": r["end_time"].isoformat() if r.get("end_time") else None,
            "event_type": r.get("event_type") or "custom",
            "status": r.get("status") or "scheduled",
            "related_name": cust or lead or "",
            "color": "#7c3aed"
        })

    # 2. Meetings
    m_sql = """
        SELECT m.id, m.title, m.notes as description, m.meeting_date, m.start_time, m.status,
               c.first_name as c_fn, c.last_name as c_ln,
               l.first_name as l_fn, l.last_name as l_ln
        FROM meetings m
        LEFT JOIN customers c ON m.customer_id = c.id
        LEFT JOIN leads l ON m.lead_id = l.id
        ORDER BY m.meeting_date ASC, m.start_time ASC
    """
    m_rows, _ = execute_query(m_sql, fetch_all=True)
    for r in (m_rows or []):
        cust = f"{r['c_fn']} {r['c_ln']}".strip() if r.get("c_fn") else None
        lead = f"{r['l_fn']} {r['l_ln']}".strip() if r.get("l_fn") else None
        m_date = str(r["meeting_date"]) if r.get("meeting_date") else None
        s_time = str(r["start_time"]) if r.get("start_time") else None
        start_str = f"{m_date}T{s_time}" if (m_date and s_time) else m_date
        events.append({
            "id": f"meeting_{r['id']}",
            "raw_id": r["id"],
            "title": f"Meeting: {r['title']}",
            "description": r.get("description") or "",
            "start": start_str,
            "end": None,
            "event_type": "meeting",
            "status": r.get("status") or "scheduled",
            "related_name": cust or lead or "",
            "color": "#2563eb",
            "url": f"meetings.html?meeting_id={r['id']}"
        })

    # 3. Calls
    c_sql = """
        SELECT cl.id, cl.purpose as subject, cl.notes, cl.call_date, cl.call_time, cl.status,
               c.first_name as c_fn, c.last_name as c_ln,
               l.first_name as l_fn, l.last_name as l_ln
        FROM calls cl
        LEFT JOIN customers c ON cl.customer_id = c.id
        LEFT JOIN leads l ON cl.lead_id = l.id
        ORDER BY cl.call_date ASC, cl.call_time ASC
    """
    c_rows, _ = execute_query(c_sql, fetch_all=True)
    for r in (c_rows or []):
        cust = f"{r['c_fn']} {r['c_ln']}".strip() if r.get("c_fn") else None
        lead = f"{r['l_fn']} {r['l_ln']}".strip() if r.get("l_fn") else None
        c_date = str(r["call_date"]) if r.get("call_date") else None
        c_time = str(r["call_time"]) if r.get("call_time") else None
        start_str = f"{c_date}T{c_time}" if (c_date and c_time) else c_date
        events.append({
            "id": f"call_{r['id']}",
            "raw_id": r["id"],
            "title": f"Call: {r.get('subject') or 'Call'}",
            "description": r.get("notes") or "",
            "start": start_str,
            "end": None,
            "event_type": "call",
            "status": r.get("status") or "scheduled",
            "related_name": cust or lead or "",
            "color": "#059669",
            "url": f"calls.html?call_id={r['id']}"
        })

    # 4. Tasks (Due Dates)
    t_sql = """
        SELECT t.id, t.title, t.description, t.due_date, t.priority, t.status,
               c.first_name as c_fn, c.last_name as c_ln
        FROM tasks t
        LEFT JOIN customers c ON t.customer_id = c.id
        WHERE t.due_date IS NOT NULL
        ORDER BY t.due_date ASC
    """
    t_rows, _ = execute_query(t_sql, fetch_all=True)
    for r in (t_rows or []):
        cust = f"{r['c_fn']} {r['c_ln']}".strip() if r.get("c_fn") else None
        due = r["due_date"]
        events.append({
            "id": f"task_{r['id']}",
            "raw_id": r["id"],
            "title": f"Task: {r['title']}",
            "description": r.get("description") or "",
            "start": f"{due.strftime('%Y-%m-%d')}T09:00:00" if due else None,
            "end": None,
            "event_type": "task",
            "status": r.get("status") or "pending",
            "priority": r.get("priority") or "medium",
            "related_name": cust or "",
            "color": "#d97706",
            "url": f"tasks.html?task_id={r['id']}"
        })

    # Filter by event_type if specified
    if event_type:
        events = [e for e in events if e["event_type"] == event_type]

    return events


def create_calendar_event(data: dict, user_id: int | None = None) -> tuple[int | None, str | None]:
    """Create a new custom calendar event."""
    title = (data.get("title") or "").strip()
    if not title:
        return None, "Title is required"

    start_time = data.get("start_time")
    if not start_time:
        return None, "Start time is required"

    end_time = data.get("end_time") or None
    raw_event_type = data.get("event_type") or "meeting"
    valid_types = ("meeting", "call", "task", "follow_up", "custom")
    event_type = raw_event_type if raw_event_type in valid_types else "custom"

    description = (data.get("description") or "").strip() or None
    customer_id = data.get("customer_id")
    lead_id = data.get("lead_id")
    status = data.get("status") or "scheduled"

    sql = """
        INSERT INTO calendar_events (user_id, title, description, event_type, start_time, end_time, customer_id, lead_id, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """
    res, err = execute_query(sql, (user_id, title, description, event_type, start_time, end_time, customer_id, lead_id, status), commit=True)
    if err:
        return None, err

    event_id = res.get("last_id") if isinstance(res, dict) else res
    log_activity(user_id, "calendar_event", event_id, "created", f"Created calendar event '{title}'")
    return event_id, None


def update_calendar_event(event_id: int, data: dict, user_id: int | None = None) -> tuple[bool, str | None]:
    """Update a custom calendar event."""
    title = (data.get("title") or "").strip()
    if not title:
        return False, "Title is required"

    start_time = data.get("start_time")
    if not start_time:
        return False, "Start time is required"

    raw_event_type = data.get("event_type") or "meeting"
    valid_types = ("meeting", "call", "task", "follow_up", "custom")
    event_type = raw_event_type if raw_event_type in valid_types else "custom"

    sql = """
        UPDATE calendar_events
        SET title = %s, description = %s, event_type = %s, start_time = %s, end_time = %s,
            customer_id = %s, lead_id = %s, status = %s, updated_at = NOW()
        WHERE id = %s
    """
    _, err = execute_query(sql, (
        title, data.get("description"), event_type,
        start_time, data.get("end_time"), data.get("customer_id"),
        data.get("lead_id"), data.get("status", "scheduled"), event_id
    ), commit=True)

    if err:
        return False, err

    log_activity(user_id, "calendar_event", event_id, "updated", f"Updated calendar event '{title}'")
    return True, None


def delete_calendar_event(event_id: int, user_id: int | None = None) -> tuple[bool, str | None]:
    """Delete a custom calendar event."""
    sql = "DELETE FROM calendar_events WHERE id = %s"
    _, err = execute_query(sql, (event_id,), commit=True)
    if err:
        return False, err

    log_activity(user_id, "calendar_event", event_id, "deleted", f"Deleted calendar event #{event_id}")
    return True, None
