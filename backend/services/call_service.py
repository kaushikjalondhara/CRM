"""
CRM Call Service
Handles call logging, scheduling, follow-ups, and outcome status recording.
"""

from database.database import execute_query
from backend.services.activity_service import log_activity

VALID_CALL_STATUSES = ("scheduled", "completed", "missed", "cancelled")


def list_calls(search=None, status=None, assigned_to=None, date_from=None, date_to=None,
               customer_id=None, lead_id=None, page=1, per_page=15):
    """List calls with filtering and pagination."""
    conditions = []
    params = []

    if search:
        search_term = f"%{search.strip()}%"
        conditions.append("(c.purpose LIKE %s OR c.notes LIKE %s)")
        params.extend([search_term, search_term])

    if status and status != "all":
        conditions.append("c.status = %s")
        params.append(status)

    if assigned_to:
        conditions.append("c.assigned_to = %s")
        params.append(assigned_to)

    if date_from:
        conditions.append("c.call_date >= %s")
        params.append(date_from)

    if date_to:
        conditions.append("c.call_date <= %s")
        params.append(date_to)

    if customer_id:
        conditions.append("c.customer_id = %s")
        params.append(customer_id)

    if lead_id:
        conditions.append("c.lead_id = %s")
        params.append(lead_id)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_sql = f"SELECT COUNT(*) as total FROM calls c {where_sql}"
    count_res, _ = execute_query(count_sql, tuple(params), fetch_one=True)
    total_count = count_res["total"] if count_res else 0

    offset = (page - 1) * per_page

    query_sql = f"""
        SELECT c.*,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name,
               cust.first_name as cust_first_name, cust.last_name as cust_last_name, cust.company_name as cust_company,
               l.first_name as lead_first_name, l.last_name as lead_last_name, l.lead_code
        FROM calls c
        LEFT JOIN users u ON c.assigned_to = u.id
        LEFT JOIN customers cust ON c.customer_id = cust.id
        LEFT JOIN leads l ON c.lead_id = l.id
        {where_sql}
        ORDER BY c.call_date DESC, c.call_time DESC
        LIMIT %s OFFSET %s
    """
    query_params = list(params) + [per_page, offset]
    rows, err = execute_query(query_sql, tuple(query_params), fetch_all=True)

    calls = []
    for r in (rows or []):
        assigned_name = f"{r['assigned_first_name']} {r['assigned_last_name']}".strip() if r.get("assigned_first_name") else "Unassigned"
        contact_name = ""
        if r.get("customer_id"):
            contact_name = f"{r['cust_first_name']} {r['cust_last_name']}"
            if r.get("cust_company"):
                contact_name += f" ({r['cust_company']})"
        elif r.get("lead_id"):
            contact_name = f"Lead: {r['lead_first_name']} {r['lead_last_name']}"

        calls.append({
            "id": r["id"],
            "subject": r.get("purpose") or "",
            "purpose": r.get("purpose") or "",
            "call_date": r["call_date"].isoformat() if r.get("call_date") else None,
            "call_time": f"{r['call_date']} {r['call_time']}" if r.get("call_date") and r.get("call_time") else str(r.get("call_time") or ""),
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
        "calls": calls,
        "pagination": {
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page if per_page else 1
        }
    }


def get_call_by_id(call_id: int):
    """Fetch call details."""
    sql = """
        SELECT c.*,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name
        FROM calls c
        LEFT JOIN users u ON c.assigned_to = u.id
        WHERE c.id = %s
    """
    call, err = execute_query(sql, (call_id,), fetch_one=True)
    if err or not call:
        return None

    assigned_name = f"{call['assigned_first_name']} {call['assigned_last_name']}".strip() if call.get("assigned_first_name") else "Unassigned"
    return {
        "id": call["id"],
        "subject": call.get("purpose") or "",
        "purpose": call.get("purpose") or "",
        "call_date": call["call_date"].isoformat() if call.get("call_date") else None,
        "call_time": f"{call['call_date']} {call['call_time']}" if call.get("call_date") and call.get("call_time") else str(call.get("call_time") or ""),
        "status": call["status"],
        "notes": call.get("notes") or "",
        "customer_id": call.get("customer_id"),
        "lead_id": call.get("lead_id"),
        "deal_id": call.get("deal_id"),
        "contact_type": "customer" if call.get("customer_id") else ("lead" if call.get("lead_id") else None),
        "contact_id": call.get("customer_id") or call.get("lead_id"),
        "assigned_to": call.get("assigned_to"),
        "assigned_to_name": assigned_name,
        "user_first_name": call.get("assigned_first_name") or "",
        "user_last_name": call.get("assigned_last_name") or "",
        "created_at": call["created_at"].isoformat() if call.get("created_at") else None
    }


def schedule_call(data: dict, user_id: int):
    """Schedule / record a new call."""
    purpose = (data.get("purpose") or data.get("subject") or "").strip() or "General Discussion"

    call_time_val = data.get("call_time")
    call_date = data.get("call_date")

    if not call_date and call_time_val:
        clean_time = str(call_time_val).replace("T", " ")
        call_date = clean_time.split(" ")[0]
        if len(clean_time.split(" ")) > 1:
            call_time_val = clean_time.split(" ")[1]

    if not call_date:
        return {"success": False, "message": "Call date is required"}, 400

    status = data.get("status", "scheduled")
    if status not in VALID_CALL_STATUSES:
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
        INSERT INTO calls (
            customer_id, lead_id, deal_id, assigned_to, call_date, call_time,
            purpose, status, notes, created_by, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, NOW()
        )
    """
    params = (
        customer_id, lead_id, deal_id, assigned_to, call_date, call_time_val,
        purpose, status, data.get("notes", ""), user_id
    )
    res, err = execute_query(sql, params, commit=True)
    if err:
        return {"success": False, "message": f"Database error: {err}"}, 500

    new_id = res.get("last_id")
    log_activity(user_id, "call", new_id, "create", f"Scheduled call: '{purpose}' on {call_date}")

    created = get_call_by_id(new_id)
    return {"success": True, "message": "Call scheduled successfully", "call": created, "call_id": new_id}, 201


def update_call(call_id: int, data: dict, user_id: int):
    """Update call record."""
    existing = get_call_by_id(call_id)
    if not existing:
        return {"success": False, "message": "Call record not found"}, 404

    call_date = data.get("call_date", existing["call_date"])
    call_time = data.get("call_time", existing["call_time"]) or None
    purpose = data.get("purpose", existing["purpose"])
    status = data.get("status", existing["status"])
    if status not in VALID_CALL_STATUSES:
        status = existing["status"]

    notes = data.get("notes", existing["notes"])
    assigned_to = data.get("assigned_to") if "assigned_to" in data else existing["assigned_to"]
    assigned_to = assigned_to or None
    customer_id = data.get("customer_id", existing["customer_id"]) or None
    lead_id = data.get("lead_id", existing["lead_id"]) or None
    deal_id = data.get("deal_id", existing["deal_id"]) or None

    sql = """
        UPDATE calls SET
            customer_id = %s, lead_id = %s, deal_id = %s, assigned_to = %s,
            call_date = %s, call_time = %s, purpose = %s, status = %s,
            notes = %s, updated_at = NOW()
        WHERE id = %s
    """
    params = (
        customer_id, lead_id, deal_id, assigned_to, call_date, call_time,
        purpose, status, notes, call_id
    )
    _, err = execute_query(sql, params, commit=True)
    if err:
        return {"success": False, "message": err}, 500

    log_activity(user_id, "call", call_id, "update", f"Updated call: '{purpose}' [{status}]")
    updated = get_call_by_id(call_id)
    return {"success": True, "message": "Call updated successfully", "call": updated}, 200


def delete_call(call_id: int, user_id: int):
    """Delete a call record."""
    existing = get_call_by_id(call_id)
    if not existing:
        return {"success": False, "message": "Call record not found"}, 404

    _, err = execute_query("DELETE FROM calls WHERE id = %s", (call_id,), commit=True)
    if err:
        return {"success": False, "message": err}, 500

    log_activity(user_id, "call", call_id, "delete", f"Deleted call '{existing['purpose']}'")
    return {"success": True, "message": "Call deleted successfully"}, 200
