"""
CRM Meeting Service
Handles meeting calendar scheduling, location/participant tracking,
and start/end time validation.
"""

from datetime import datetime
from database.database import execute_query
from backend.services.activity_service import log_activity

VALID_MEETING_STATUSES = ("scheduled", "completed", "cancelled")


def validate_meeting_times(meeting_date: str, start_time: str, end_time: str | None):
    """Validate that meeting end time is after start time."""
    if not end_time:
        return True, None

    try:
        s_clean = str(start_time).replace("T", " ").split(" ")[-1]
        e_clean = str(end_time).replace("T", " ").split(" ")[-1]

        fmt = "%H:%M" if len(s_clean.split(":")) == 2 else "%H:%M:%S"
        fmt_end = "%H:%M" if len(e_clean.split(":")) == 2 else "%H:%M:%S"

        t_start = datetime.strptime(s_clean, fmt).time()
        t_end = datetime.strptime(e_clean, fmt_end).time()

        if t_end <= t_start:
            return False, "Meeting end time must be after start time."
        return True, None
    except Exception as e:
        return False, f"Invalid time format: {str(e)}"


def list_meetings(search=None, status=None, assigned_to=None, date_from=None, date_to=None,
                  customer_id=None, lead_id=None, page=1, per_page=15):
    """List meetings with filtering and pagination."""
    conditions = []
    params = []

    if search:
        search_term = f"%{search.strip()}%"
        conditions.append("(m.title LIKE %s OR m.location LIKE %s OR m.notes LIKE %s)")
        params.extend([search_term, search_term, search_term])

    if status and status != "all":
        conditions.append("m.status = %s")
        params.append(status)

    if assigned_to:
        conditions.append("m.assigned_to = %s")
        params.append(assigned_to)

    if date_from:
        conditions.append("m.meeting_date >= %s")
        params.append(date_from)

    if date_to:
        conditions.append("m.meeting_date <= %s")
        params.append(date_to)

    if customer_id:
        conditions.append("m.customer_id = %s")
        params.append(customer_id)

    if lead_id:
        conditions.append("m.lead_id = %s")
        params.append(lead_id)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_sql = f"SELECT COUNT(*) as total FROM meetings m {where_sql}"
    count_res, _ = execute_query(count_sql, tuple(params), fetch_one=True)
    total_count = count_res["total"] if count_res else 0

    offset = (page - 1) * per_page

    query_sql = f"""
        SELECT m.*,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name,
               cust.first_name as cust_first_name, cust.last_name as cust_last_name, cust.company_name as cust_company,
               l.first_name as lead_first_name, l.last_name as lead_last_name
        FROM meetings m
        LEFT JOIN users u ON m.assigned_to = u.id
        LEFT JOIN customers cust ON m.customer_id = cust.id
        LEFT JOIN leads l ON m.lead_id = l.id
        {where_sql}
        ORDER BY m.meeting_date DESC, m.start_time DESC
        LIMIT %s OFFSET %s
    """
    query_params = list(params) + [per_page, offset]
    rows, err = execute_query(query_sql, tuple(query_params), fetch_all=True)

    meetings = []
    for r in (rows or []):
        assigned_name = f"{r['assigned_first_name']} {r['assigned_last_name']}".strip() if r.get("assigned_first_name") else "Unassigned"
        contact_name = ""
        if r.get("customer_id"):
            contact_name = f"{r['cust_first_name']} {r['cust_last_name']}"
            if r.get("cust_company"):
                contact_name += f" ({r['cust_company']})"
        elif r.get("lead_id"):
            contact_name = f"Lead: {r['lead_first_name']} {r['lead_last_name']}"

        meetings.append({
            "id": r["id"],
            "title": r["title"],
            "meeting_date": r["meeting_date"].isoformat() if r.get("meeting_date") else None,
            "start_time": f"{r['meeting_date']} {r['start_time']}" if r.get("meeting_date") and r.get("start_time") else str(r.get("start_time") or ""),
            "end_time": f"{r['meeting_date']} {r['end_time']}" if r.get("meeting_date") and r.get("end_time") else str(r.get("end_time") or ""),
            "location": r.get("location") or "",
            "meeting_type": r.get("meeting_type") or "In-Person",
            "participants": r.get("participants") or "",
            "status": r["status"],
            "notes": r.get("notes") or "",
            "customer_id": r.get("customer_id"),
            "lead_id": r.get("lead_id"),
            "contact_type": "customer" if r.get("customer_id") else ("lead" if r.get("lead_id") else None),
            "contact_id": r.get("customer_id") or r.get("lead_id"),
            "contact_name": contact_name,
            "assigned_to": r.get("assigned_to"),
            "assigned_to_name": assigned_name,
            "user_first_name": r.get("assigned_first_name") or "",
            "user_last_name": r.get("assigned_last_name") or "",
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None
        })

    return {
        "success": True,
        "meetings": meetings,
        "pagination": {
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page if per_page else 1
        }
    }


def get_meeting_by_id(meeting_id: int):
    """Fetch meeting by ID."""
    sql = """
        SELECT m.*,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name
        FROM meetings m
        LEFT JOIN users u ON m.assigned_to = u.id
        WHERE m.id = %s
    """
    meeting, err = execute_query(sql, (meeting_id,), fetch_one=True)
    if err or not meeting:
        return None

    assigned_name = f"{meeting['assigned_first_name']} {meeting['assigned_last_name']}".strip() if meeting.get("assigned_first_name") else "Unassigned"
    return {
        "id": meeting["id"],
        "title": meeting["title"],
        "meeting_date": meeting["meeting_date"].isoformat() if meeting.get("meeting_date") else None,
        "start_time": f"{meeting['meeting_date']} {meeting['start_time']}" if meeting.get("meeting_date") and meeting.get("start_time") else str(meeting.get("start_time") or ""),
        "end_time": f"{meeting['meeting_date']} {meeting['end_time']}" if meeting.get("meeting_date") and meeting.get("end_time") else str(meeting.get("end_time") or ""),
        "location": meeting.get("location") or "",
        "meeting_type": meeting.get("meeting_type") or "In-Person",
        "participants": meeting.get("participants") or "",
        "status": meeting["status"],
        "notes": meeting.get("notes") or "",
        "customer_id": meeting.get("customer_id"),
        "lead_id": meeting.get("lead_id"),
        "deal_id": meeting.get("deal_id"),
        "contact_type": "customer" if meeting.get("customer_id") else ("lead" if meeting.get("lead_id") else None),
        "contact_id": meeting.get("customer_id") or meeting.get("lead_id"),
        "assigned_to": meeting.get("assigned_to"),
        "assigned_to_name": assigned_name,
        "user_first_name": meeting.get("assigned_first_name") or "",
        "user_last_name": meeting.get("assigned_last_name") or "",
        "created_at": meeting["created_at"].isoformat() if meeting.get("created_at") else None
    }


def schedule_meeting(data: dict, user_id: int):
    """Schedule a new meeting with time validations."""
    title = data.get("title", "").strip()
    meeting_date = data.get("meeting_date")
    start_time_raw = data.get("start_time")
    end_time_raw = data.get("end_time")

    if not title:
        return {"success": False, "message": "Meeting title is required"}, 400
    if not start_time_raw:
        return {"success": False, "message": "Start time is required"}, 400

    clean_start = str(start_time_raw).replace("T", " ")
    parts_start = clean_start.split(" ")
    if not meeting_date and len(parts_start) > 1:
        meeting_date = parts_start[0]
        start_time = parts_start[1]
    elif len(parts_start) > 1:
        start_time = parts_start[1]
    else:
        start_time = parts_start[0]

    if not meeting_date:
        return {"success": False, "message": "Meeting date is required"}, 400

    end_time = None
    if end_time_raw:
        clean_end = str(end_time_raw).replace("T", " ")
        parts_end = clean_end.split(" ")
        end_time = parts_end[1] if len(parts_end) > 1 else parts_end[0]

    is_valid, time_err = validate_meeting_times(meeting_date, start_time, end_time)
    if not is_valid:
        return {"success": False, "message": time_err}, 400

    status = data.get("status", "scheduled")
    if status not in VALID_MEETING_STATUSES:
        status = "scheduled"

    customer_id = data.get("customer_id") or None
    lead_id = data.get("lead_id") or None
    deal_id = data.get("deal_id") or None

    contact_type = data.get("contact_type")
    contact_id = data.get("contact_id")
    if contact_type == "customer" and contact_id:
        customer_id = contact_id
    elif contact_type == "lead" and contact_id:
        lead_id = contact_id
    elif contact_type == "deal" and contact_id:
        deal_id = contact_id

    assigned_to = data.get("assigned_to") or data.get("user_id") or None

    sql = """
        INSERT INTO meetings (
            title, customer_id, lead_id, deal_id, assigned_to,
            meeting_date, start_time, end_time, location, meeting_type,
            participants, status, notes, created_by, created_at
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, NOW()
        )
    """
    params = (
        title, customer_id, lead_id, deal_id, assigned_to,
        meeting_date, start_time, end_time, data.get("location", ""),
        data.get("meeting_type", "In-Person"), data.get("participants", ""),
        status, data.get("notes", ""), user_id
    )
    res, err = execute_query(sql, params, commit=True)
    if err:
        return {"success": False, "message": f"Database error: {err}"}, 500

    new_id = res.get("last_id")
    log_activity(user_id, "meeting", new_id, "create", f"Scheduled meeting '{title}' on {meeting_date} at {start_time}")

    created = get_meeting_by_id(new_id)
    return {"success": True, "message": "Meeting scheduled successfully", "meeting": created, "meeting_id": new_id}, 201


def update_meeting(meeting_id: int, data: dict, user_id: int):
    """Update meeting details."""
    existing = get_meeting_by_id(meeting_id)
    if not existing:
        return {"success": False, "message": "Meeting not found"}, 404

    title = data.get("title", existing["title"]).strip()
    meeting_date = data.get("meeting_date", existing["meeting_date"])
    start_time = data.get("start_time", existing["start_time"])
    end_time = data.get("end_time", existing["end_time"]) or None

    is_valid, time_err = validate_meeting_times(meeting_date, start_time, end_time)
    if not is_valid:
        return {"success": False, "message": time_err}, 400

    status = data.get("status", existing["status"])
    if status not in VALID_MEETING_STATUSES:
        status = existing["status"]

    assigned_to = data.get("assigned_to") if "assigned_to" in data else existing["assigned_to"]
    assigned_to = assigned_to or None
    customer_id = data.get("customer_id", existing["customer_id"]) or None
    lead_id = data.get("lead_id", existing["lead_id"]) or None
    deal_id = data.get("deal_id", existing["deal_id"]) or None

    sql = """
        UPDATE meetings SET
            title = %s, customer_id = %s, lead_id = %s, deal_id = %s,
            assigned_to = %s, meeting_date = %s, start_time = %s, end_time = %s,
            location = %s, meeting_type = %s, participants = %s, status = %s,
            notes = %s, updated_at = NOW()
        WHERE id = %s
    """
    params = (
        title, customer_id, lead_id, deal_id, assigned_to,
        meeting_date, start_time, end_time, data.get("location", existing["location"]),
        data.get("meeting_type", existing["meeting_type"]), data.get("participants", existing["participants"]),
        status, data.get("notes", existing["notes"]), meeting_id
    )
    _, err = execute_query(sql, params, commit=True)
    if err:
        return {"success": False, "message": err}, 500

    log_activity(user_id, "meeting", meeting_id, "update", f"Updated meeting '{title}' [{status}]")
    updated = get_meeting_by_id(meeting_id)
    return {"success": True, "message": "Meeting updated successfully", "meeting": updated}, 200


def delete_meeting(meeting_id: int, user_id: int):
    """Delete a meeting."""
    existing = get_meeting_by_id(meeting_id)
    if not existing:
        return {"success": False, "message": "Meeting not found"}, 404

    _, err = execute_query("DELETE FROM meetings WHERE id = %s", (meeting_id,), commit=True)
    if err:
        return {"success": False, "message": err}, 500

    log_activity(user_id, "meeting", meeting_id, "delete", f"Cancelled/Deleted meeting '{existing['title']}'")
    return {"success": True, "message": "Meeting deleted successfully"}, 200
