"""
CRM Deal Service
Handles Deal CRUD, Kanban pipeline grouping, stage transitions,
and deal milestone tracking in `deal_activities`.
"""

from database.database import execute_query
from backend.services.activity_service import log_activity

VALID_STAGES = ("new", "qualification", "proposal", "negotiation", "won", "lost")
VALID_STATUSES = ("open", "won", "lost", "cancelled")


def generate_deal_code():
    """Generate sequential deal code."""
    res, _ = execute_query("SELECT id FROM deals ORDER BY id DESC LIMIT 1", fetch_one=True)
    next_id = (res["id"] + 1) if res and res.get("id") else 1
    return f"DEAL-{next_id + 1000}"


def list_deals(search=None, stage=None, status=None, customer_id=None, assigned_to=None, page=1, per_page=15):
    """List deals with search, stage/status filters, and pagination."""
    conditions = []
    params = []

    if search:
        search_term = f"%{search.strip()}%"
        conditions.append("(d.title LIKE %s OR d.deal_code LIKE %s OR c.first_name LIKE %s OR c.last_name LIKE %s OR c.company_name LIKE %s)")
        params.extend([search_term, search_term, search_term, search_term, search_term])

    if stage and stage != "all":
        conditions.append("d.stage = %s")
        params.append(stage)

    if status and status != "all":
        conditions.append("d.status = %s")
        params.append(status)

    if customer_id:
        conditions.append("d.customer_id = %s")
        params.append(customer_id)

    if assigned_to:
        conditions.append("d.assigned_to = %s")
        params.append(assigned_to)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Count
    count_sql = f"SELECT COUNT(*) as total FROM deals d LEFT JOIN customers c ON d.customer_id = c.id {where_sql}"
    count_res, _ = execute_query(count_sql, tuple(params), fetch_one=True)
    total_count = count_res["total"] if count_res else 0

    offset = (page - 1) * per_page

    query_sql = f"""
        SELECT d.*,
               c.first_name as customer_first_name, c.last_name as customer_last_name, c.company_name as customer_company,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name
        FROM deals d
        JOIN customers c ON d.customer_id = c.id
        LEFT JOIN users u ON d.assigned_to = u.id
        {where_sql}
        ORDER BY d.created_at DESC
        LIMIT %s OFFSET %s
    """
    query_params = list(params) + [per_page, offset]
    rows, err = execute_query(query_sql, tuple(query_params), fetch_all=True)

    deals = []
    for r in (rows or []):
        cust_name = f"{r['customer_first_name']} {r['customer_last_name']}".strip()
        if r.get("customer_company"):
            cust_name += f" ({r['customer_company']})"
        assigned_name = f"{r['assigned_first_name']} {r['assigned_last_name']}".strip() if r.get("assigned_first_name") else "Unassigned"

        deals.append({
            "id": r["id"],
            "deal_code": r["deal_code"],
            "title": r["title"],
            "description": r.get("description") or "",
            "customer_id": r["customer_id"],
            "customer_name": cust_name,
            "lead_id": r.get("lead_id"),
            "value": float(r["value"] or 0.0),
            "stage": r["stage"],
            "probability": int(r["probability"] or 0),
            "expected_close_date": r["expected_close_date"].isoformat() if r.get("expected_close_date") else None,
            "status": r["status"],
            "assigned_to": r.get("assigned_to"),
            "assigned_to_name": assigned_name,
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None
        })

    return {
        "success": True,
        "deals": deals,
        "pagination": {
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page if per_page else 1
        }
    }


def get_pipeline_kanban():
    """
    Fetch deals organized by the 6 standard stages for Kanban presentation.
    """
    stages = ["new", "qualification", "proposal", "negotiation", "won", "lost"]
    kanban = {s: {"stage": s, "count": 0, "total_value": 0.0, "deals": []} for s in stages}

    sql = """
        SELECT d.*,
               c.first_name as customer_first_name, c.last_name as customer_last_name, c.company_name as customer_company,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name
        FROM deals d
        JOIN customers c ON d.customer_id = c.id
        LEFT JOIN users u ON d.assigned_to = u.id
        ORDER BY d.created_at DESC
    """
    rows, _ = execute_query(sql, fetch_all=True)

    for r in (rows or []):
        stg = r["stage"]
        if stg not in kanban:
            continue

        cust_name = f"{r['customer_first_name']} {r['customer_last_name']}".strip()
        if r.get("customer_company"):
            cust_name += f" ({r['customer_company']})"
        assigned_name = f"{r['assigned_first_name']} {r['assigned_last_name']}".strip() if r.get("assigned_first_name") else "Unassigned"

        deal_val = float(r["value"] or 0.0)
        kanban[stg]["count"] += 1
        kanban[stg]["total_value"] += deal_val

        kanban[stg]["deals"].append({
            "id": r["id"],
            "deal_code": r["deal_code"],
            "title": r["title"],
            "customer_id": r["customer_id"],
            "customer_name": cust_name,
            "value": deal_val,
            "stage": r["stage"],
            "probability": int(r["probability"] or 0),
            "expected_close_date": r["expected_close_date"].isoformat() if r.get("expected_close_date") else None,
            "status": r["status"],
            "assigned_to_name": assigned_name
        })

    stages_dict = {s: kanban[s]["deals"] for s in stages}
    stage_totals = {s: kanban[s]["total_value"] for s in stages}
    return {
        "success": True,
        "kanban": kanban,
        "stages": stages_dict,
        "stage_totals": stage_totals
    }


def get_deal_by_id(deal_id: int):
    """Fetch single deal details along with deal activities."""
    sql = """
        SELECT d.*,
               c.first_name as customer_first_name, c.last_name as customer_last_name, c.company_name as customer_company,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name
        FROM deals d
        JOIN customers c ON d.customer_id = c.id
        LEFT JOIN users u ON d.assigned_to = u.id
        WHERE d.id = %s
    """
    deal, err = execute_query(sql, (deal_id,), fetch_one=True)
    if err or not deal:
        return None

    cust_name = f"{deal['customer_first_name']} {deal['customer_last_name']}".strip()
    if deal.get("customer_company"):
        cust_name += f" ({deal['customer_company']})"
    assigned_name = f"{deal['assigned_first_name']} {deal['assigned_last_name']}".strip() if deal.get("assigned_first_name") else "Unassigned"

    # Deal activities
    act_sql = """
        SELECT da.id, da.deal_id, da.user_id, da.activity_type, da.description, da.created_at,
               u.first_name, u.last_name
        FROM deal_activities da
        LEFT JOIN users u ON da.user_id = u.id
        WHERE da.deal_id = %s
        ORDER BY da.created_at DESC
    """
    activities_rows, _ = execute_query(act_sql, (deal_id,), fetch_all=True)
    activities = []
    for a in (activities_rows or []):
        author = f"{a['first_name']} {a['last_name']}".strip() if a.get("first_name") else "Staff"
        activities.append({
            "id": a["id"],
            "author": author,
            "activity_type": a["activity_type"],
            "description": a["description"],
            "created_at": a["created_at"].isoformat() if a.get("created_at") else None
        })

    return {
        "id": deal["id"],
        "deal_code": deal["deal_code"],
        "title": deal["title"],
        "description": deal.get("description") or "",
        "customer_id": deal["customer_id"],
        "customer_name": cust_name,
        "lead_id": deal.get("lead_id"),
        "value": float(deal["value"] or 0.0),
        "stage": deal["stage"],
        "probability": int(deal["probability"] or 0),
        "expected_close_date": deal["expected_close_date"].isoformat() if deal.get("expected_close_date") else None,
        "status": deal["status"],
        "assigned_to": deal.get("assigned_to"),
        "assigned_to_name": assigned_name,
        "created_at": deal["created_at"].isoformat() if deal.get("created_at") else None,
        "updated_at": deal["updated_at"].isoformat() if deal.get("updated_at") else None,
        "activities": activities
    }


def create_deal(data: dict, user_id: int):
    """Create a new deal."""
    title = data.get("title", "").strip()
    customer_id = data.get("customer_id")

    if not title:
        return {"success": False, "message": "Deal Title is required"}, 400
    if not customer_id:
        return {"success": False, "message": "Associated Customer is required"}, 400

    deal_code = data.get("deal_code", "").strip() or generate_deal_code()
    value = float(data.get("value") or 0.0)
    stage = data.get("stage", "new")
    if stage not in VALID_STAGES:
        stage = "new"

    probability = int(data.get("probability", 10))
    probability = max(0, min(100, probability))

    status = "won" if stage == "won" else ("lost" if stage == "lost" else "open")
    expected_close_date = data.get("expected_close_date") or None
    assigned_to = data.get("assigned_to") or None
    lead_id = data.get("lead_id") or None

    sql = """
        INSERT INTO deals (
            deal_code, lead_id, customer_id, title, description, value,
            stage, probability, expected_close_date, assigned_to, status, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, NOW()
        )
    """
    params = (
        deal_code, lead_id, customer_id, title, data.get("description", ""),
        value, stage, probability, expected_close_date, assigned_to, status
    )
    res, err = execute_query(sql, params, commit=True)
    if err:
        return {"success": False, "message": f"Database error: {err}"}, 500

    new_id = res.get("last_id")
    log_activity(user_id, "deal", new_id, "create", f"Created deal '{title}' (${value:,.2f}) at stage {stage}")

    # Add milestone in deal_activities
    execute_query(
        "INSERT INTO deal_activities (deal_id, user_id, activity_type, description, created_at) VALUES (%s, %s, 'created', %s, NOW())",
        (new_id, user_id, f"Deal opportunity created at stage '{stage}'"),
        commit=True
    )

    created = get_deal_by_id(new_id)
    return {"success": True, "message": "Deal created successfully", "deal": created, "deal_id": new_id}, 201


def update_deal(deal_id: int, data: dict, user_id: int):
    """Update deal parameters."""
    existing = get_deal_by_id(deal_id)
    if not existing:
        return {"success": False, "message": "Deal not found"}, 404

    title = data.get("title", existing["title"]).strip()
    value = float(data.get("value", existing["value"]) or 0.0)
    stage = data.get("stage", existing["stage"])
    if stage not in VALID_STAGES:
        stage = existing["stage"]

    probability = int(data.get("probability", existing["probability"]))
    probability = max(0, min(100, probability))

    status = data.get("status", existing["status"])
    if stage == "won":
        status = "won"
    elif stage == "lost":
        status = "lost"

    expected_close_date = data.get("expected_close_date", existing["expected_close_date"]) or None
    assigned_to = data.get("assigned_to") if "assigned_to" in data else existing["assigned_to"]
    assigned_to = assigned_to or None
    customer_id = data.get("customer_id", existing["customer_id"])

    sql = """
        UPDATE deals SET
            customer_id = %s, title = %s, description = %s, value = %s,
            stage = %s, probability = %s, expected_close_date = %s,
            assigned_to = %s, status = %s, updated_at = NOW()
        WHERE id = %s
    """
    params = (
        customer_id, title, data.get("description", existing["description"]),
        value, stage, probability, expected_close_date, assigned_to, status, deal_id
    )
    _, err = execute_query(sql, params, commit=True)
    if err:
        return {"success": False, "message": f"Database error: {err}"}, 500

    # If stage changed, record activity
    if stage != existing["stage"]:
        execute_query(
            "INSERT INTO deal_activities (deal_id, user_id, activity_type, description, created_at) VALUES (%s, %s, 'stage_change', %s, NOW())",
            (deal_id, user_id, f"Stage advanced from '{existing['stage']}' to '{stage}'"),
            commit=True
        )
        log_activity(user_id, "deal", deal_id, "stage_change", f"Deal '{title}' stage transitioned to '{stage}'")

    updated = get_deal_by_id(deal_id)
    return {"success": True, "message": "Deal updated successfully", "deal": updated}, 200


def update_deal_stage(deal_id: int, new_stage: str, user_id: int):
    """Transition deal stage (used by Kanban board)."""
    if new_stage not in VALID_STAGES:
        return {"success": False, "message": f"Invalid stage '{new_stage}'"}, 400

    existing = get_deal_by_id(deal_id)
    if not existing:
        return {"success": False, "message": "Deal not found"}, 404

    status = "won" if new_stage == "won" else ("lost" if new_stage == "lost" else "open")

    sql = "UPDATE deals SET stage = %s, status = %s, updated_at = NOW() WHERE id = %s"
    _, err = execute_query(sql, (new_stage, status, deal_id), commit=True)
    if err:
        return {"success": False, "message": err}, 500

    execute_query(
        "INSERT INTO deal_activities (deal_id, user_id, activity_type, description, created_at) VALUES (%s, %s, 'stage_change', %s, NOW())",
        (deal_id, user_id, f"Deal moved to '{new_stage}' stage"),
        commit=True
    )
    log_activity(user_id, "deal", deal_id, "stage_change", f"Deal '{existing['title']}' moved to '{new_stage}'")

    return {"success": True, "message": f"Stage updated to {new_stage}", "stage": new_stage, "status": status}, 200


def delete_deal(deal_id: int, user_id: int):
    """Delete deal."""
    existing = get_deal_by_id(deal_id)
    if not existing:
        return {"success": False, "message": "Deal not found"}, 404

    _, err = execute_query("DELETE FROM deals WHERE id = %s", (deal_id,), commit=True)
    if err:
        return {"success": False, "message": err}, 500

    log_activity(user_id, "deal", deal_id, "delete", f"Deleted deal '{existing['title']}'")
    return {"success": True, "message": "Deal deleted successfully"}, 200


def bulk_action_deals(action: str, ids: list, value=None, user_id: int | None = None) -> tuple[dict | None, str | None]:
    """Execute bulk operations on multiple deals."""
    if not ids or not isinstance(ids, list):
        return None, "No deal IDs provided"

    clean_ids = [int(i) for i in ids if str(i).isdigit()]
    if not clean_ids:
        return None, "Invalid ID list"

    id_placeholders = ", ".join(["%s"] * len(clean_ids))

    if action == "delete":
        del_sql = f"DELETE FROM deals WHERE id IN ({id_placeholders})"
        _, err = execute_query(del_sql, tuple(clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "deal", None, "bulk_delete", f"Bulk deleted {len(clean_ids)} deals")
        return {"action": "delete", "affected": len(clean_ids)}, None

    elif action == "stage":
        if value not in VALID_STAGES:
            return None, f"Invalid stage '{value}'"
        status = "won" if value == "won" else ("lost" if value == "lost" else "open")
        up_sql = f"UPDATE deals SET stage = %s, status = %s, updated_at = NOW() WHERE id IN ({id_placeholders})"
        _, err = execute_query(up_sql, tuple([value, status] + clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "deal", None, "bulk_stage", f"Bulk updated stage of {len(clean_ids)} deals to '{value}'")
        return {"action": "stage", "affected": len(clean_ids), "new_stage": value}, None

    elif action == "assign":
        assign_id = int(value) if value else None
        up_sql = f"UPDATE deals SET assigned_to = %s, updated_at = NOW() WHERE id IN ({id_placeholders})"
        _, err = execute_query(up_sql, tuple([assign_id] + clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "deal", None, "bulk_assign", f"Bulk assigned {len(clean_ids)} deals to user #{assign_id}")
        return {"action": "assign", "affected": len(clean_ids), "assigned_to": assign_id}, None

    return None, f"Unsupported bulk action '{action}'"
