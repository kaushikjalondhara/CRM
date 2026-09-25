"""
CRM Lead Service
Handles Lead CRUD, search, filter, touchpoint activity tracking,
and atomic lead-to-customer conversion.
"""

from database.database import execute_query, get_db_cursor
from backend.services.activity_service import log_activity
from backend.services.customer_service import generate_customer_code


def generate_lead_code():
    """Generate sequential lead code."""
    res, _ = execute_query("SELECT id FROM leads ORDER BY id DESC LIMIT 1", fetch_one=True)
    next_id = (res["id"] + 1) if res and res.get("id") else 1
    return f"LEAD-{next_id + 1000}"


def list_leads(search=None, status=None, priority=None, assigned_to=None, page=1, per_page=10):
    """List leads with search and filter parameters."""
    conditions = []
    params = []

    if search:
        search_term = f"%{search.strip()}%"
        conditions.append("(l.first_name LIKE %s OR l.last_name LIKE %s OR l.company_name LIKE %s OR l.email LIKE %s OR l.phone LIKE %s OR l.lead_code LIKE %s)")
        params.extend([search_term, search_term, search_term, search_term, search_term, search_term])

    if status and status != "all":
        conditions.append("l.status = %s")
        params.append(status)

    if priority and priority != "all":
        conditions.append("l.priority = %s")
        params.append(priority)

    if assigned_to:
        conditions.append("l.assigned_to = %s")
        params.append(assigned_to)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Count
    count_sql = f"SELECT COUNT(*) as total FROM leads l {where_sql}"
    count_res, _ = execute_query(count_sql, tuple(params), fetch_one=True)
    total_count = count_res["total"] if count_res else 0

    offset = (page - 1) * per_page

    query_sql = f"""
        SELECT l.*,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name,
               c.customer_code as converted_customer_code
        FROM leads l
        LEFT JOIN users u ON l.assigned_to = u.id
        LEFT JOIN customers c ON l.converted_customer_id = c.id
        {where_sql}
        ORDER BY l.created_at DESC
        LIMIT %s OFFSET %s
    """
    query_params = list(params) + [per_page, offset]
    rows, err = execute_query(query_sql, tuple(query_params), fetch_all=True)

    leads = []
    for r in (rows or []):
        assigned_name = f"{r['assigned_first_name']} {r['assigned_last_name']}".strip() if r.get("assigned_first_name") else "Unassigned"
        leads.append({
            "id": r["id"],
            "lead_code": r["lead_code"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "full_name": f"{r['first_name']} {r['last_name']}",
            "company_name": r.get("company_name") or "",
            "email": r.get("email") or "",
            "phone": r.get("phone") or "",
            "source": r.get("source") or "",
            "industry": r.get("industry") or "",
            "status": r["status"],
            "priority": r["priority"],
            "expected_value": float(r["expected_value"] or 0.0),
            "assigned_to": r["assigned_to"],
            "assigned_to_name": assigned_name,
            "follow_up_date": r["follow_up_date"].isoformat() if r.get("follow_up_date") else None,
            "notes": r.get("notes") or "",
            "converted_customer_id": r["converted_customer_id"],
            "converted_customer_code": r.get("converted_customer_code") or None,
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None
        })

    return {
        "success": True,
        "leads": leads,
        "pagination": {
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page if per_page else 1
        }
    }


def get_lead_by_id(lead_id: int):
    """Fetch single lead by ID."""
    sql = """
        SELECT l.*,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name,
               c.customer_code as converted_customer_code
        FROM leads l
        LEFT JOIN users u ON l.assigned_to = u.id
        LEFT JOIN customers c ON l.converted_customer_id = c.id
        WHERE l.id = %s
    """
    lead, err = execute_query(sql, (lead_id,), fetch_one=True)
    if err or not lead:
        return None

    assigned_name = f"{lead['assigned_first_name']} {lead['assigned_last_name']}".strip() if lead.get("assigned_first_name") else "Unassigned"
    return {
        "id": lead["id"],
        "lead_code": lead["lead_code"],
        "first_name": lead["first_name"],
        "last_name": lead["last_name"],
        "full_name": f"{lead['first_name']} {lead['last_name']}",
        "company_name": lead.get("company_name") or "",
        "email": lead.get("email") or "",
        "phone": lead.get("phone") or "",
        "source": lead.get("source") or "",
        "industry": lead.get("industry") or "",
        "status": lead["status"],
        "priority": lead["priority"],
        "expected_value": float(lead["expected_value"] or 0.0),
        "assigned_to": lead["assigned_to"],
        "assigned_to_name": assigned_name,
        "follow_up_date": lead["follow_up_date"].isoformat() if lead.get("follow_up_date") else None,
        "notes": lead.get("notes") or "",
        "converted_customer_id": lead["converted_customer_id"],
        "converted_customer_code": lead.get("converted_customer_code") or None,
        "created_at": lead["created_at"].isoformat() if lead.get("created_at") else None,
        "updated_at": lead["updated_at"].isoformat() if lead.get("updated_at") else None
    }


def get_lead_details(lead_id: int):
    """Fetch lead profile plus touchpoint activities."""
    lead = get_lead_by_id(lead_id)
    if not lead:
        return None

    # Activities from lead_activities
    act_sql = """
        SELECT la.id, la.lead_id, la.user_id, la.activity_type, la.description, la.created_at,
               u.first_name, u.last_name
        FROM lead_activities la
        LEFT JOIN users u ON la.user_id = u.id
        WHERE la.lead_id = %s
        ORDER BY la.created_at DESC
    """
    rows, _ = execute_query(act_sql, (lead_id,), fetch_all=True)
    activities = []
    for r in (rows or []):
        author = f"{r['first_name']} {r['last_name']}".strip() if r.get("first_name") else "Staff"
        activities.append({
            "id": r["id"],
            "lead_id": r["lead_id"],
            "user_id": r["user_id"],
            "author": author,
            "activity_type": r["activity_type"],
            "description": r["description"],
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None
        })

    return {
        "lead": lead,
        "activities": activities
    }


def create_lead(data: dict, user_id: int):
    """Create a new lead."""
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()

    if not first_name or not last_name:
        return {"success": False, "message": "First Name and Last Name are required"}, 400

    lead_code = data.get("lead_code", "").strip() or generate_lead_code()
    status = data.get("status", "new")
    if status not in ("new", "contacted", "qualified", "proposal", "negotiation", "converted", "lost"):
        status = "new"

    priority = data.get("priority", "medium")
    if priority not in ("low", "medium", "high", "urgent"):
        priority = "medium"

    expected_value = float(data.get("expected_value") or 0.0)
    assigned_to = data.get("assigned_to") or None
    follow_up_date = data.get("follow_up_date") or None

    sql = """
        INSERT INTO leads (
            lead_code, first_name, last_name, company_name, email, phone,
            source, industry, status, priority, expected_value, assigned_to,
            follow_up_date, notes, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, NOW()
        )
    """
    params = (
        lead_code, first_name, last_name, data.get("company_name", ""),
        data.get("email", ""), data.get("phone", ""), data.get("source", ""),
        data.get("industry", ""), status, priority, expected_value, assigned_to,
        follow_up_date, data.get("notes", "")
    )

    res, err = execute_query(sql, params, commit=True)
    if err:
        return {"success": False, "message": f"Database error: {err}"}, 500

    new_id = res.get("last_id")
    log_activity(user_id, "lead", new_id, "create", f"Created lead '{first_name} {last_name}' ({lead_code})")

    # Add initial creation lead activity
    add_lead_activity(new_id, user_id, "note", "Lead captured in CRM")

    created = get_lead_by_id(new_id)
    return {"success": True, "message": "Lead created successfully", "lead": created, "lead_id": new_id}, 201


def update_lead(lead_id: int, data: dict, user_id: int):
    """Update lead details."""
    existing = get_lead_by_id(lead_id)
    if not existing:
        return {"success": False, "message": "Lead not found"}, 404

    first_name = data.get("first_name", existing["first_name"]).strip()
    last_name = data.get("last_name", existing["last_name"]).strip()
    status = data.get("status", existing["status"])
    priority = data.get("priority", existing["priority"])
    expected_value = float(data.get("expected_value", existing["expected_value"]) or 0.0)
    assigned_to = data.get("assigned_to") if "assigned_to" in data else existing["assigned_to"]
    assigned_to = assigned_to or None
    follow_up_date = data.get("follow_up_date", existing["follow_up_date"]) or None

    sql = """
        UPDATE leads SET
            first_name = %s, last_name = %s, company_name = %s, email = %s,
            phone = %s, source = %s, industry = %s, status = %s,
            priority = %s, expected_value = %s, assigned_to = %s,
            follow_up_date = %s, notes = %s, updated_at = NOW()
        WHERE id = %s
    """
    params = (
        first_name, last_name, data.get("company_name", existing["company_name"]),
        data.get("email", existing["email"]), data.get("phone", existing["phone"]),
        data.get("source", existing["source"]), data.get("industry", existing["industry"]),
        status, priority, expected_value, assigned_to, follow_up_date,
        data.get("notes", existing["notes"]), lead_id
    )

    _, err = execute_query(sql, params, commit=True)
    if err:
        return {"success": False, "message": f"Database error: {err}"}, 500

    # If status changed, log activity
    if status != existing["status"]:
        add_lead_activity(lead_id, user_id, "status_change", f"Status changed from {existing['status']} to {status}")
        log_activity(user_id, "lead", lead_id, "status_change", f"Lead '{first_name} {last_name}' status updated to {status}")

    updated = get_lead_by_id(lead_id)
    return {"success": True, "message": "Lead updated successfully", "lead": updated}, 200


def delete_lead(lead_id: int, user_id: int):
    """Delete a lead."""
    existing = get_lead_by_id(lead_id)
    if not existing:
        return {"success": False, "message": "Lead not found"}, 404

    _, err = execute_query("DELETE FROM leads WHERE id = %s", (lead_id,), commit=True)
    if err:
        return {"success": False, "message": err}, 500

    log_activity(user_id, "lead", lead_id, "delete", f"Deleted lead '{existing['full_name']}'")
    return {"success": True, "message": "Lead deleted successfully"}, 200


def add_lead_activity(lead_id: int, user_id: int, activity_type: str, description: str):
    """Record touchpoint activity for a lead."""
    valid_types = ("call", "email", "meeting", "note", "status_change", "follow_up")
    if activity_type not in valid_types:
        activity_type = "note"

    sql = "INSERT INTO lead_activities (lead_id, user_id, activity_type, description, created_at) VALUES (%s, %s, %s, %s, NOW())"
    res, err = execute_query(sql, (lead_id, user_id, activity_type, description), commit=True)
    if err:
        return {"success": False, "message": err}, 500
    return {"success": True, "message": "Activity recorded", "id": res.get("last_id")}, 201


def convert_lead_to_customer(lead_id: int, user_id: int):
    """
    Convert a lead to an active Customer using a safe transaction.
    Creates Customer, sets converted_customer_id on Lead, updates Lead status to converted.
    """
    lead = get_lead_by_id(lead_id)
    if not lead:
        return {"success": False, "message": "Lead not found"}, 404

    if lead.get("converted_customer_id") or lead["status"] == "converted":
        return {
            "success": False,
            "message": f"Lead is already converted (Customer ID: {lead.get('converted_customer_id')})"
        }, 400

    customer_code = generate_customer_code()

    try:
        with get_db_cursor(commit=True) as cursor:
            # 1. Insert into customers
            cust_sql = """
                INSERT INTO customers (
                    customer_code, first_name, last_name, company_name, email, phone,
                    industry, status, assigned_to, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, 'active', %s, NOW()
                )
            """
            cursor.execute(cust_sql, (
                customer_code, lead["first_name"], lead["last_name"],
                lead["company_name"], lead["email"], lead["phone"],
                lead["industry"], lead["assigned_to"]
            ))
            customer_id = cursor.lastrowid

            # 2. Update lead record
            lead_update_sql = """
                UPDATE leads
                SET status = 'converted', converted_customer_id = %s, updated_at = NOW()
                WHERE id = %s
            """
            cursor.execute(lead_update_sql, (customer_id, lead_id))

            # 3. Log touchpoint activity on lead
            cursor.execute("""
                INSERT INTO lead_activities (lead_id, user_id, activity_type, description, created_at)
                VALUES (%s, %s, 'status_change', %s, NOW())
            """, (lead_id, user_id, f"Lead converted to Customer {customer_code}"))

        # 4. Log global activity
        log_activity(user_id, "lead", lead_id, "convert", f"Converted lead '{lead['full_name']}' to Customer {customer_code}")
        log_activity(user_id, "customer", customer_id, "create", f"Customer created via conversion from Lead {lead['lead_code']}")

        return {
            "success": True,
            "message": f"Lead successfully converted to customer {customer_code}",
            "customer_id": customer_id,
            "customer_code": customer_code
        }, 200

    except Exception as e:
        return {"success": False, "message": f"Conversion failed: {str(e)}"}, 500


def bulk_action_leads(action: str, ids: list, value=None, user_id: int | None = None) -> tuple[dict | None, str | None]:
    """Execute bulk operations on multiple leads."""
    if not ids or not isinstance(ids, list):
        return None, "No lead IDs provided"

    clean_ids = [int(i) for i in ids if str(i).isdigit()]
    if not clean_ids:
        return None, "Invalid ID list"

    id_placeholders = ", ".join(["%s"] * len(clean_ids))

    if action == "delete":
        del_sql = f"DELETE FROM leads WHERE id IN ({id_placeholders})"
        _, err = execute_query(del_sql, tuple(clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "lead", None, "bulk_delete", f"Bulk deleted {len(clean_ids)} leads")
        return {"action": "delete", "affected": len(clean_ids)}, None

    elif action == "status":
        valid_statuses = {"new", "contacted", "qualified", "proposal", "converted", "lost"}
        if value not in valid_statuses:
            return None, f"Invalid status '{value}'. Allowed: {', '.join(valid_statuses)}"

        up_sql = f"UPDATE leads SET status = %s, updated_at = NOW() WHERE id IN ({id_placeholders})"
        _, err = execute_query(up_sql, tuple([value] + clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "lead", None, "bulk_status", f"Bulk updated status of {len(clean_ids)} leads to '{value}'")
        return {"action": "status", "affected": len(clean_ids), "new_status": value}, None

    elif action == "assign":
        assign_id = int(value) if value else None
        up_sql = f"UPDATE leads SET assigned_to = %s, updated_at = NOW() WHERE id IN ({id_placeholders})"
        _, err = execute_query(up_sql, tuple([assign_id] + clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "lead", None, "bulk_assign", f"Bulk assigned {len(clean_ids)} leads to user #{assign_id}")
        return {"action": "assign", "affected": len(clean_ids), "assigned_to": assign_id}, None

    return None, f"Unsupported bulk action '{action}'"
