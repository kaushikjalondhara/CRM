"""
CRM Task Service
Handles task assignment, status progression, due date reminders,
and polymorphic linking across Customers, Leads, and Deals.
"""

from database.database import execute_query
from backend.services.activity_service import log_activity

VALID_PRIORITIES = ("low", "medium", "high", "urgent")
VALID_STATUSES = ("pending", "in_progress", "completed", "cancelled")


def list_tasks(search=None, status=None, priority=None, assigned_to=None,
               customer_id=None, lead_id=None, deal_id=None, page=1, per_page=15):
    """List tasks with multi-field filtering and pagination."""
    conditions = []
    params = []

    if search:
        search_term = f"%{search.strip()}%"
        conditions.append("(t.title LIKE %s OR t.description LIKE %s)")
        params.extend([search_term, search_term])

    if status and status != "all":
        conditions.append("t.status = %s")
        params.append(status)

    if priority and priority != "all":
        conditions.append("t.priority = %s")
        params.append(priority)

    if assigned_to:
        conditions.append("t.assigned_to = %s")
        params.append(assigned_to)

    if customer_id:
        conditions.append("t.customer_id = %s")
        params.append(customer_id)

    if lead_id:
        conditions.append("t.lead_id = %s")
        params.append(lead_id)

    if deal_id:
        conditions.append("t.deal_id = %s")
        params.append(deal_id)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_sql = f"SELECT COUNT(*) as total FROM tasks t {where_sql}"
    count_res, _ = execute_query(count_sql, tuple(params), fetch_one=True)
    total_count = count_res["total"] if count_res else 0

    offset = (page - 1) * per_page

    query_sql = f"""
        SELECT t.*,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name,
               creator.first_name as creator_first_name, creator.last_name as creator_last_name,
               c.first_name as cust_first_name, c.last_name as cust_last_name, c.company_name as cust_company,
               l.lead_code, l.first_name as lead_first_name, l.last_name as lead_last_name,
               d.deal_code, d.title as deal_title
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to = u.id
        LEFT JOIN users creator ON t.created_by = creator.id
        LEFT JOIN customers c ON t.customer_id = c.id
        LEFT JOIN leads l ON t.lead_id = l.id
        LEFT JOIN deals d ON t.deal_id = d.id
        {where_sql}
        ORDER BY 
            CASE WHEN t.status IN ('pending', 'in_progress') THEN 0 ELSE 1 END ASC,
            t.due_date ASC, t.created_at DESC
        LIMIT %s OFFSET %s
    """
    query_params = list(params) + [per_page, offset]
    rows, err = execute_query(query_sql, tuple(query_params), fetch_all=True)

    tasks = []
    for r in (rows or []):
        assigned_name = f"{r['assigned_first_name']} {r['assigned_last_name']}".strip() if r.get("assigned_first_name") else "Unassigned"
        creator_name = f"{r['creator_first_name']} {r['creator_last_name']}".strip() if r.get("creator_first_name") else "System"

        linked_label = ""
        if r.get("customer_id"):
            linked_label = f"Customer: {r['cust_first_name']} {r['cust_last_name']}"
        elif r.get("lead_id"):
            linked_label = f"Lead: {r['lead_first_name']} {r['lead_last_name']}"
        elif r.get("deal_id"):
            linked_label = f"Deal: {r['deal_title']}"

        tasks.append({
            "id": r["id"],
            "title": r["title"],
            "description": r.get("description") or "",
            "customer_id": r.get("customer_id"),
            "lead_id": r.get("lead_id"),
            "deal_id": r.get("deal_id"),
            "linked_label": linked_label,
            "assigned_to": r.get("assigned_to"),
            "assigned_to_name": assigned_name,
            "creator_name": creator_name,
            "priority": r["priority"],
            "status": r["status"],
            "due_date": r["due_date"].isoformat() if r.get("due_date") else None,
            "completed_at": r["completed_at"].isoformat() if r.get("completed_at") else None,
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None
        })

    return {
        "success": True,
        "tasks": tasks,
        "pagination": {
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page if per_page else 1
        }
    }


def get_task_by_id(task_id: int):
    """Fetch single task details."""
    sql = """
        SELECT t.*,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to = u.id
        WHERE t.id = %s
    """
    task, err = execute_query(sql, (task_id,), fetch_one=True)
    if err or not task:
        return None

    assigned_name = f"{task['assigned_first_name']} {task['assigned_last_name']}".strip() if task.get("assigned_first_name") else "Unassigned"
    return {
        "id": task["id"],
        "title": task["title"],
        "description": task.get("description") or "",
        "customer_id": task.get("customer_id"),
        "lead_id": task.get("lead_id"),
        "deal_id": task.get("deal_id"),
        "assigned_to": task.get("assigned_to"),
        "assigned_to_name": assigned_name,
        "priority": task["priority"],
        "status": task["status"],
        "due_date": task["due_date"].isoformat() if task.get("due_date") else None,
        "completed_at": task["completed_at"].isoformat() if task.get("completed_at") else None,
        "created_at": task["created_at"].isoformat() if task.get("created_at") else None,
        "updated_at": task["updated_at"].isoformat() if task.get("updated_at") else None
    }


def create_task(data: dict, user_id: int):
    """Create task."""
    title = data.get("title", "").strip()
    if not title:
        return {"success": False, "message": "Task title is required"}, 400

    priority = data.get("priority", "medium")
    if priority not in VALID_PRIORITIES:
        priority = "medium"

    status = data.get("status", "pending")
    if status not in VALID_STATUSES:
        status = "pending"

    due_date = data.get("due_date") or None
    assigned_to = data.get("assigned_to") or None
    customer_id = data.get("customer_id") or None
    lead_id = data.get("lead_id") or None
    deal_id = data.get("deal_id") or None

    completed_at = "NOW()" if status == "completed" else "NULL"

    sql = f"""
        INSERT INTO tasks (
            title, description, customer_id, lead_id, deal_id, assigned_to,
            priority, status, due_date, completed_at, created_by, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, {completed_at}, %s, NOW()
        )
    """
    params = (
        title, data.get("description", ""), customer_id, lead_id, deal_id,
        assigned_to, priority, status, due_date, user_id
    )
    res, err = execute_query(sql, params, commit=True)
    if err:
        return {"success": False, "message": f"Database error: {err}"}, 500

    new_id = res.get("last_id")
    log_activity(user_id, "task", new_id, "create", f"Created task '{title}' [Priority: {priority}]")

    created = get_task_by_id(new_id)
    return {"success": True, "message": "Task created successfully", "task": created, "task_id": new_id}, 201


def update_task(task_id: int, data: dict, user_id: int):
    """Update task information."""
    existing = get_task_by_id(task_id)
    if not existing:
        return {"success": False, "message": "Task not found"}, 404

    title = data.get("title", existing["title"]).strip()
    priority = data.get("priority", existing["priority"])
    status = data.get("status", existing["status"])

    due_date = data.get("due_date", existing["due_date"]) or None
    assigned_to = data.get("assigned_to") if "assigned_to" in data else existing["assigned_to"]
    assigned_to = assigned_to or None
    customer_id = data.get("customer_id", existing["customer_id"]) or None
    lead_id = data.get("lead_id", existing["lead_id"]) or None
    deal_id = data.get("deal_id", existing["deal_id"]) or None

    completed_clause = ", completed_at = NOW()" if status == "completed" and existing["status"] != "completed" else ("", completed_at := "NULL" if status != "completed" else "")

    sql = f"""
        UPDATE tasks SET
            title = %s, description = %s, customer_id = %s, lead_id = %s,
            deal_id = %s, assigned_to = %s, priority = %s, status = %s,
            due_date = %s, updated_at = NOW()
            {", completed_at = NOW()" if status == "completed" and existing["status"] != "completed" else (", completed_at = NULL" if status != "completed" else "")}
        WHERE id = %s
    """
    params = (
        title, data.get("description", existing["description"]), customer_id,
        lead_id, deal_id, assigned_to, priority, status, due_date, task_id
    )
    _, err = execute_query(sql, params, commit=True)
    if err:
        return {"success": False, "message": f"Database error: {err}"}, 500

    if status == "completed" and existing["status"] != "completed":
        log_activity(user_id, "task", task_id, "complete", f"Marked task '{title}' as completed")
    else:
        log_activity(user_id, "task", task_id, "update", f"Updated task '{title}'")

    updated = get_task_by_id(task_id)
    return {"success": True, "message": "Task updated successfully", "task": updated}, 200


def update_task_status(task_id: int, status: str, user_id: int):
    """Quickly update status (e.g., mark completed)."""
    if status not in VALID_STATUSES:
        return {"success": False, "message": f"Invalid status '{status}'"}, 400

    existing = get_task_by_id(task_id)
    if not existing:
        return {"success": False, "message": "Task not found"}, 404

    completed_sql = ", completed_at = NOW()" if status == "completed" else ", completed_at = NULL"
    sql = f"UPDATE tasks SET status = %s {completed_sql}, updated_at = NOW() WHERE id = %s"
    _, err = execute_query(sql, (status, task_id), commit=True)
    if err:
        return {"success": False, "message": err}, 500

    log_activity(user_id, "task", task_id, "status_change", f"Task '{existing['title']}' changed status to {status}")
    return {"success": True, "message": f"Task status updated to {status}", "status": status}, 200


def delete_task(task_id: int, user_id: int):
    """Delete a task."""
    existing = get_task_by_id(task_id)
    if not existing:
        return {"success": False, "message": "Task not found"}, 404

    _, err = execute_query("DELETE FROM tasks WHERE id = %s", (task_id,), commit=True)
    if err:
        return {"success": False, "message": err}, 500

    log_activity(user_id, "task", task_id, "delete", f"Deleted task '{existing['title']}'")
    return {"success": True, "message": "Task deleted successfully"}, 200


def bulk_action_tasks(action: str, ids: list, value=None, user_id: int | None = None) -> tuple[dict | None, str | None]:
    """Execute bulk operations on multiple tasks."""
    if not ids or not isinstance(ids, list):
        return None, "No task IDs provided"

    clean_ids = [int(i) for i in ids if str(i).isdigit()]
    if not clean_ids:
        return None, "Invalid ID list"

    id_placeholders = ", ".join(["%s"] * len(clean_ids))

    if action == "delete":
        del_sql = f"DELETE FROM tasks WHERE id IN ({id_placeholders})"
        _, err = execute_query(del_sql, tuple(clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "task", None, "bulk_delete", f"Bulk deleted {len(clean_ids)} tasks")
        return {"action": "delete", "affected": len(clean_ids)}, None

    elif action == "status":
        if value not in VALID_STATUSES:
            return None, f"Invalid status '{value}'. Allowed: {', '.join(VALID_STATUSES)}"

        comp_sql = ", completed_at = NOW()" if value == "completed" else ", completed_at = NULL"
        up_sql = f"UPDATE tasks SET status = %s {comp_sql}, updated_at = NOW() WHERE id IN ({id_placeholders})"
        _, err = execute_query(up_sql, tuple([value] + clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "task", None, "bulk_status", f"Bulk set status of {len(clean_ids)} tasks to '{value}'")
        return {"action": "status", "affected": len(clean_ids), "new_status": value}, None

    elif action == "priority":
        if value not in VALID_PRIORITIES:
            return None, f"Invalid priority '{value}'. Allowed: {', '.join(VALID_PRIORITIES)}"
        up_sql = f"UPDATE tasks SET priority = %s, updated_at = NOW() WHERE id IN ({id_placeholders})"
        _, err = execute_query(up_sql, tuple([value] + clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "task", None, "bulk_priority", f"Bulk set priority of {len(clean_ids)} tasks to '{value}'")
        return {"action": "priority", "affected": len(clean_ids), "new_priority": value}, None

    elif action == "assign":
        assign_id = int(value) if value else None
        up_sql = f"UPDATE tasks SET assigned_to = %s, updated_at = NOW() WHERE id IN ({id_placeholders})"
        _, err = execute_query(up_sql, tuple([assign_id] + clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "task", None, "bulk_assign", f"Bulk assigned {len(clean_ids)} tasks to user #{assign_id}")
        return {"action": "assign", "affected": len(clean_ids), "assigned_to": assign_id}, None

    return None, f"Unsupported bulk action '{action}'"

