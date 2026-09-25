"""
CRM Customer Service
Handles Customer CRUD, search, filter, pagination, notes, document attachments,
and full 360° relationship aggregation.
"""

import os
import re
import time
from pathlib import Path
from werkzeug.utils import secure_filename
from database.database import execute_query
from backend.config import Config
from backend.services.activity_service import log_activity

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "csv", "txt", "png", "jpg", "jpeg"}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB


def generate_customer_code():
    """Generate a unique sequential customer code."""
    res, _ = execute_query("SELECT id FROM customers ORDER BY id DESC LIMIT 1", fetch_one=True)
    next_id = (res["id"] + 1) if res and res.get("id") else 1
    return f"CUST-{next_id + 1000}"


def list_customers(search=None, status=None, assigned_to=None, sort_by="created_at", order="DESC", page=1, per_page=10):
    """
    Query customers with search, status filtering, employee assignment, sorting, and pagination.
    """
    conditions = []
    params = []

    if search:
        search_term = f"%{search.strip()}%"
        conditions.append("(c.first_name LIKE %s OR c.last_name LIKE %s OR c.company_name LIKE %s OR c.email LIKE %s OR c.phone LIKE %s OR c.customer_code LIKE %s)")
        params.extend([search_term, search_term, search_term, search_term, search_term, search_term])

    if status and status != "all":
        conditions.append("c.status = %s")
        params.append(status)

    if assigned_to:
        conditions.append("c.assigned_to = %s")
        params.append(assigned_to)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Count total
    count_sql = f"SELECT COUNT(*) as total FROM customers c {where_sql}"
    count_res, _ = execute_query(count_sql, tuple(params), fetch_one=True)
    total_count = count_res["total"] if count_res else 0

    # Sanitize sort column
    valid_sorts = {
        "created_at": "c.created_at",
        "first_name": "c.first_name",
        "company_name": "c.company_name",
        "customer_code": "c.customer_code",
        "status": "c.status"
    }
    sort_column = valid_sorts.get(sort_by, "c.created_at")
    sort_order = "ASC" if str(order).upper() == "ASC" else "DESC"

    offset = (page - 1) * per_page

    query_sql = f"""
        SELECT c.*, 
               u.first_name AS assigned_first_name, u.last_name AS assigned_last_name, u.email AS assigned_email
        FROM customers c
        LEFT JOIN users u ON c.assigned_to = u.id
        {where_sql}
        ORDER BY {sort_column} {sort_order}
        LIMIT %s OFFSET %s
    """
    query_params = list(params) + [per_page, offset]
    rows, err = execute_query(query_sql, tuple(query_params), fetch_all=True)

    customers = []
    for r in (rows or []):
        assigned_name = f"{r['assigned_first_name']} {r['assigned_last_name']}".strip() if r.get("assigned_first_name") else "Unassigned"
        customers.append({
            "id": r["id"],
            "customer_code": r["customer_code"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "full_name": f"{r['first_name']} {r['last_name']}",
            "company_name": r.get("company_name") or "",
            "email": r.get("email") or "",
            "phone": r.get("phone") or "",
            "alternate_phone": r.get("alternate_phone") or "",
            "city": r.get("city") or "",
            "state": r.get("state") or "",
            "country": r.get("country") or "",
            "industry": r.get("industry") or "",
            "customer_type": r.get("customer_type") or "",
            "status": r["status"],
            "assigned_to": r["assigned_to"],
            "assigned_to_name": assigned_name,
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None,
        })

    return {
        "success": True,
        "customers": customers,
        "pagination": {
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": (total_count + per_page - 1) // per_page if per_page else 1
        }
    }


def get_customer_by_id(customer_id: int):
    """Fetch single customer by ID."""
    sql = """
        SELECT c.*, 
               u.first_name AS assigned_first_name, u.last_name AS assigned_last_name, u.email AS assigned_email
        FROM customers c
        LEFT JOIN users u ON c.assigned_to = u.id
        WHERE c.id = %s
    """
    customer, err = execute_query(sql, (customer_id,), fetch_one=True)
    if err or not customer:
        return None

    assigned_name = f"{customer['assigned_first_name']} {customer['assigned_last_name']}".strip() if customer.get("assigned_first_name") else "Unassigned"
    return {
        "id": customer["id"],
        "customer_code": customer["customer_code"],
        "first_name": customer["first_name"],
        "last_name": customer["last_name"],
        "full_name": f"{customer['first_name']} {customer['last_name']}",
        "company_name": customer.get("company_name") or "",
        "email": customer.get("email") or "",
        "phone": customer.get("phone") or "",
        "alternate_phone": customer.get("alternate_phone") or "",
        "address": customer.get("address") or "",
        "city": customer.get("city") or "",
        "state": customer.get("state") or "",
        "country": customer.get("country") or "",
        "pincode": customer.get("pincode") or "",
        "industry": customer.get("industry") or "",
        "customer_type": customer.get("customer_type") or "",
        "status": customer["status"],
        "assigned_to": customer["assigned_to"],
        "assigned_to_name": assigned_name,
        "created_at": customer["created_at"].isoformat() if customer.get("created_at") else None,
        "updated_at": customer["updated_at"].isoformat() if customer.get("updated_at") else None,
    }


def get_customer_details(customer_id: int):
    """
    Fetch comprehensive 360° customer overview including notes, documents,
    leads, deals, tasks, calls, meetings, and activity timeline.
    """
    customer = get_customer_by_id(customer_id)
    if not customer:
        return None

    # Notes
    notes = list_customer_notes(customer_id)

    # Documents
    documents = list_customer_documents(customer_id)

    # Leads
    lead_sql = """
        SELECT id, lead_code, first_name, last_name, status, priority, expected_value, created_at
        FROM leads WHERE converted_customer_id = %s OR company_name = %s
        ORDER BY created_at DESC
    """
    leads, _ = execute_query(lead_sql, (customer_id, customer.get("company_name") or ""), fetch_all=True)

    # Deals
    deal_sql = """
        SELECT id, deal_code, title, value, stage, status, expected_close_date, created_at
        FROM deals WHERE customer_id = %s
        ORDER BY created_at DESC
    """
    deals, _ = execute_query(deal_sql, (customer_id,), fetch_all=True)

    # Tasks
    task_sql = """
        SELECT t.id, t.title, t.priority, t.status, t.due_date, u.first_name, u.last_name
        FROM tasks t
        LEFT JOIN users u ON t.assigned_to = u.id
        WHERE t.customer_id = %s
        ORDER BY t.created_at DESC
    """
    tasks, _ = execute_query(task_sql, (customer_id,), fetch_all=True)

    # Calls
    call_sql = """
        SELECT c.id, c.call_date, c.call_time, c.purpose, c.status, c.notes, u.first_name, u.last_name
        FROM calls c
        LEFT JOIN users u ON c.assigned_to = u.id
        WHERE c.customer_id = %s
        ORDER BY c.call_date DESC, c.call_time DESC
    """
    calls, _ = execute_query(call_sql, (customer_id,), fetch_all=True)

    # Meetings
    meeting_sql = """
        SELECT m.id, m.title, m.meeting_date, m.start_time, m.end_time, m.location, m.status, u.first_name, u.last_name
        FROM meetings m
        LEFT JOIN users u ON m.assigned_to = u.id
        WHERE m.customer_id = %s
        ORDER BY m.meeting_date DESC, m.start_time DESC
    """
    meetings, _ = execute_query(meeting_sql, (customer_id,), fetch_all=True)

    # Activities
    from backend.services.activity_service import get_recent_activities
    activities = get_recent_activities(limit=15, entity_type="customer", entity_id=customer_id)

    return {
        "customer": customer,
        "notes": notes,
        "documents": documents,
        "leads": leads or [],
        "deals": deals or [],
        "tasks": tasks or [],
        "calls": calls or [],
        "meetings": meetings or [],
        "activities": activities
    }


def create_customer(data: dict, user_id: int):
    """Create a new customer."""
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()

    if not first_name or not last_name:
        return {"success": False, "message": "First Name and Last Name are required"}, 400

    customer_code = data.get("customer_code", "").strip() or generate_customer_code()
    status = data.get("status", "prospect")
    if status not in ("active", "inactive", "prospect", "blocked"):
        status = "prospect"

    assigned_to = data.get("assigned_to") or None

    sql = """
        INSERT INTO customers (
            customer_code, first_name, last_name, company_name, email, phone,
            alternate_phone, address, city, state, country, pincode,
            industry, customer_type, status, assigned_to, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, NOW()
        )
    """
    params = (
        customer_code, first_name, last_name, data.get("company_name", ""),
        data.get("email", ""), data.get("phone", ""), data.get("alternate_phone", ""),
        data.get("address", ""), data.get("city", ""), data.get("state", ""),
        data.get("country", ""), data.get("pincode", ""), data.get("industry", ""),
        data.get("customer_type", ""), status, assigned_to
    )

    res, err = execute_query(sql, params, commit=True)
    if err:
        return {"success": False, "message": f"Database error: {err}"}, 500

    new_id = res.get("last_id")
    log_activity(user_id, "customer", new_id, "create", f"Created new customer '{first_name} {last_name}' ({customer_code})")

    created = get_customer_by_id(new_id)
    return {"success": True, "message": "Customer created successfully", "customer": created, "customer_id": new_id}, 201


def update_customer(customer_id: int, data: dict, user_id: int):
    """Update customer information."""
    existing = get_customer_by_id(customer_id)
    if not existing:
        return {"success": False, "message": "Customer not found"}, 404

    first_name = data.get("first_name", existing["first_name"]).strip()
    last_name = data.get("last_name", existing["last_name"]).strip()
    status = data.get("status", existing["status"])
    if status not in ("active", "inactive", "prospect", "blocked"):
        status = existing["status"]

    assigned_to = data.get("assigned_to") if "assigned_to" in data else existing["assigned_to"]
    assigned_to = assigned_to or None

    sql = """
        UPDATE customers SET
            first_name = %s, last_name = %s, company_name = %s, email = %s,
            phone = %s, alternate_phone = %s, address = %s, city = %s,
            state = %s, country = %s, pincode = %s, industry = %s,
            customer_type = %s, status = %s, assigned_to = %s, updated_at = NOW()
        WHERE id = %s
    """
    params = (
        first_name, last_name, data.get("company_name", existing["company_name"]),
        data.get("email", existing["email"]), data.get("phone", existing["phone"]),
        data.get("alternate_phone", existing["alternate_phone"]),
        data.get("address", existing.get("address", "")),
        data.get("city", existing["city"]), data.get("state", existing["state"]),
        data.get("country", existing["country"]), data.get("pincode", existing.get("pincode", "")),
        data.get("industry", existing["industry"]), data.get("customer_type", existing["customer_type"]),
        status, assigned_to, customer_id
    )

    _, err = execute_query(sql, params, commit=True)
    if err:
        return {"success": False, "message": f"Database error: {err}"}, 500

    log_activity(user_id, "customer", customer_id, "update", f"Updated customer '{first_name} {last_name}' details")
    updated = get_customer_by_id(customer_id)
    return {"success": True, "message": "Customer updated successfully", "customer": updated}, 200


def delete_customer(customer_id: int, user_id: int):
    """Delete a customer with safety checks."""
    existing = get_customer_by_id(customer_id)
    if not existing:
        return {"success": False, "message": "Customer not found"}, 404

    # Check for linked deals or invoices
    deals_check, _ = execute_query("SELECT COUNT(*) as count FROM deals WHERE customer_id = %s", (customer_id,), fetch_one=True)
    if deals_check and deals_check["count"] > 0:
        return {
            "success": False,
            "message": f"Cannot delete customer: they are linked to {deals_check['count']} deal(s). Please archive or remove deals first."
        }, 400

    inv_check, _ = execute_query("SELECT COUNT(*) as count FROM invoices WHERE customer_id = %s", (customer_id,), fetch_one=True)
    if inv_check and inv_check["count"] > 0:
        return {
            "success": False,
            "message": f"Cannot delete customer: they are linked to {inv_check['count']} invoice(s). Financial records must be preserved."
        }, 400

    _, err = execute_query("DELETE FROM customers WHERE id = %s", (customer_id,), commit=True)
    if err:
        return {"success": False, "message": f"Delete error: {err}"}, 500

    log_activity(user_id, "customer", customer_id, "delete", f"Deleted customer '{existing['full_name']}'")
    return {"success": True, "message": "Customer deleted successfully"}, 200


# -------------------------------------------------------------
# Customer Notes
# -------------------------------------------------------------
def list_customer_notes(customer_id: int):
    """List notes for a customer."""
    sql = """
        SELECT cn.id, cn.customer_id, cn.user_id, cn.note, cn.created_at, cn.updated_at,
               u.first_name, u.last_name, u.email
        FROM customer_notes cn
        LEFT JOIN users u ON cn.user_id = u.id
        WHERE cn.customer_id = %s
        ORDER BY cn.created_at DESC
    """
    rows, _ = execute_query(sql, (customer_id,), fetch_all=True)
    notes = []
    for r in (rows or []):
        author = f"{r['first_name']} {r['last_name']}".strip() if r.get("first_name") else "Staff"
        notes.append({
            "id": r["id"],
            "customer_id": r["customer_id"],
            "user_id": r["user_id"],
            "author": author,
            "note": r["note"],
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None
        })
    return notes


def add_customer_note(customer_id: int, user_id: int, note_text: str):
    """Add a note to a customer."""
    if not note_text or not note_text.strip():
        return {"success": False, "message": "Note content cannot be empty"}, 400

    sql = "INSERT INTO customer_notes (customer_id, user_id, note, created_at) VALUES (%s, %s, %s, NOW())"
    res, err = execute_query(sql, (customer_id, user_id, note_text.strip()), commit=True)
    if err:
        return {"success": False, "message": err}, 500

    log_activity(user_id, "customer", customer_id, "note", "Added a customer interaction note")
    return {"success": True, "message": "Note added successfully", "note_id": res.get("last_id")}, 201


def update_customer_note(note_id: int, user_id: int, note_text: str):
    """Update an existing note."""
    if not note_text or not note_text.strip():
        return {"success": False, "message": "Note content cannot be empty"}, 400

    sql = "UPDATE customer_notes SET note = %s, updated_at = NOW() WHERE id = %s"
    _, err = execute_query(sql, (note_text.strip(), note_id), commit=True)
    if err:
        return {"success": False, "message": err}, 500
    return {"success": True, "message": "Note updated successfully"}, 200


def delete_customer_note(note_id: int, user_id: int):
    """Delete a customer note."""
    _, err = execute_query("DELETE FROM customer_notes WHERE id = %s", (note_id,), commit=True)
    if err:
        return {"success": False, "message": err}, 500
    return {"success": True, "message": "Note deleted successfully"}, 200


# -------------------------------------------------------------
# Customer Documents
# -------------------------------------------------------------
def list_customer_documents(customer_id: int):
    """List documents uploaded for a customer."""
    sql = """
        SELECT cd.id, cd.customer_id, cd.file_name, cd.file_path, cd.file_type, cd.file_size, cd.created_at,
               u.first_name, u.last_name
        FROM customer_documents cd
        LEFT JOIN users u ON cd.uploaded_by = u.id
        WHERE cd.customer_id = %s
        ORDER BY cd.created_at DESC
    """
    rows, _ = execute_query(sql, (customer_id,), fetch_all=True)
    docs = []
    for r in (rows or []):
        uploader = f"{r['first_name']} {r['last_name']}".strip() if r.get("first_name") else "Staff"
        docs.append({
            "id": r["id"],
            "customer_id": r["customer_id"],
            "file_name": r["file_name"],
            "file_path": r["file_path"],
            "file_type": r["file_type"],
            "file_size": r["file_size"],
            "uploader": uploader,
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None
        })
    return docs


def upload_customer_document(customer_id: int, user_id: int, file_obj):
    """Securely upload and store a customer document."""
    if not file_obj or file_obj.filename == "":
        return {"success": False, "message": "No file provided"}, 400

    filename = secure_filename(file_obj.filename)
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return {"success": False, "message": f"Invalid file type .{ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}, 400

    # Ensure uploads directory exists
    upload_dir = Path(Config.CUSTOMER_DOCUMENTS_FOLDER)
    upload_dir.mkdir(parents=True, exist_ok=True)

    unique_filename = f"cust_{customer_id}_{int(time.time())}_{filename}"
    save_path = upload_dir / unique_filename

    file_obj.save(str(save_path))
    file_size = save_path.stat().st_size

    if file_size > MAX_FILE_SIZE:
        save_path.unlink(missing_ok=True)
        return {"success": False, "message": "File exceeds maximum permitted size of 16MB"}, 400

    rel_path = f"uploads/customer_documents/{unique_filename}"
    sql = """
        INSERT INTO customer_documents (customer_id, file_name, file_path, file_type, file_size, uploaded_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
    """
    res, err = execute_query(sql, (customer_id, filename, rel_path, ext, file_size, user_id), commit=True)
    if err:
        save_path.unlink(missing_ok=True)
        return {"success": False, "message": err}, 500

    log_activity(user_id, "customer", customer_id, "document", f"Uploaded document '{filename}'")
    return {"success": True, "message": "Document uploaded successfully", "document_id": res.get("last_id")}, 201


def delete_customer_document(doc_id: int, user_id: int):
    """Delete a document record and file on disk."""
    doc, _ = execute_query("SELECT id, customer_id, file_path, file_name FROM customer_documents WHERE id = %s", (doc_id,), fetch_one=True)
    if not doc:
        return {"success": False, "message": "Document not found"}, 404

    # Remove physical file safely
    disk_path = Path(Config.BASE_DIR) / doc["file_path"]
    try:
        if disk_path.exists():
            disk_path.unlink()
    except Exception:
        pass

    _, err = execute_query("DELETE FROM customer_documents WHERE id = %s", (doc_id,), commit=True)
    if err:
        return {"success": False, "message": err}, 500

    log_activity(user_id, "customer", doc["customer_id"], "document_delete", f"Deleted document '{doc['file_name']}'")
    return {"success": True, "message": "Document deleted successfully"}, 200


# -------------------------------------------------------------
# Customer 360° Comprehensive Profile
# -------------------------------------------------------------
def get_customer_360(customer_id: int) -> tuple[dict | None, str | None]:
    """
    Fetch comprehensive 360° view of customer across all entities:
    Profile, Deals, Invoices, Payments, Tasks, Calls, Meetings, Emails, Notes, Documents, and Timeline.
    """
    customer_res = get_customer_by_id(customer_id)
    if not customer_res:
        return None, "Customer not found"

    # 1. Deals
    d_sql = """
        SELECT id, deal_code, title, value, stage, probability, expected_close_date, status
        FROM deals WHERE customer_id = %s ORDER BY id DESC
    """
    deals, _ = execute_query(d_sql, (customer_id,), fetch_all=True)

    # 2. Invoices
    inv_sql = """
        SELECT id, invoice_number, invoice_date, due_date, total_amount, paid_amount, remaining_amount, status
        FROM invoices WHERE customer_id = %s ORDER BY id DESC
    """
    invoices, _ = execute_query(inv_sql, (customer_id,), fetch_all=True)

    # 3. Payments
    p_sql = """
        SELECT p.id, p.transaction_reference, p.amount, p.payment_method, p.payment_date, i.invoice_number
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        WHERE p.customer_id = %s ORDER BY p.id DESC
    """
    payments, _ = execute_query(p_sql, (customer_id,), fetch_all=True)

    # 4. Tasks
    t_sql = """
        SELECT id, title, priority, status, due_date
        FROM tasks WHERE customer_id = %s ORDER BY id DESC
    """
    tasks, _ = execute_query(t_sql, (customer_id,), fetch_all=True)

    # 5. Calls
    c_sql = """
        SELECT id, purpose as subject, call_date, call_time, status, notes
        FROM calls WHERE customer_id = %s ORDER BY call_date DESC, call_time DESC
    """
    calls, _ = execute_query(c_sql, (customer_id,), fetch_all=True)

    # 6. Meetings
    m_sql = """
        SELECT id, title, meeting_date, start_time, status, location
        FROM meetings WHERE customer_id = %s ORDER BY meeting_date DESC, start_time DESC
    """
    meetings, _ = execute_query(m_sql, (customer_id,), fetch_all=True)

    # 7. Emails
    e_sql = """
        SELECT id, recipient_email, subject, status, sent_at, created_at
        FROM emails WHERE customer_id = %s ORDER BY created_at DESC
    """
    emails, _ = execute_query(e_sql, (customer_id,), fetch_all=True)

    # 8. Notes & Documents
    notes = list_customer_notes(customer_id)
    documents = list_customer_documents(customer_id)

    # 9. Activities timeline
    act_sql = """
        SELECT a.id, a.user_id, a.activity_type as action, a.description, a.created_at,
               u.first_name, u.last_name
        FROM activities a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE a.entity_type = 'customer' AND a.entity_id = %s
        ORDER BY a.created_at DESC LIMIT 50
    """
    act_rows, _ = execute_query(act_sql, (customer_id,), fetch_all=True)
    timeline = []
    for a in (act_rows or []):
        author = f"{a['first_name']} {a['last_name']}".strip() if a.get("first_name") else "System"
        timeline.append({
            "id": a["id"],
            "author": author,
            "action": a["action"],
            "description": a["description"],
            "created_at": a["created_at"].strftime("%Y-%m-%d %H:%M:%S") if a.get("created_at") else None
        })

    # Summary metrics
    total_deals_val = sum(float(d.get("value") or 0) for d in (deals or []))
    total_invoiced = sum(float(i.get("total_amount") or 0) for i in (invoices or []))
    total_paid = sum(float(i.get("paid_amount") or 0) for i in (invoices or []))
    outstanding = sum(float(i.get("remaining_amount") or 0) for i in (invoices or []))

    return {
        "customer": customer_res,
        "deals": deals or [],
        "invoices": invoices or [],
        "payments": payments or [],
        "tasks": tasks or [],
        "calls": calls or [],
        "meetings": meetings or [],
        "emails": emails or [],
        "notes": notes or [],
        "documents": documents or [],
        "timeline": timeline or [],
        "summary": {
            "total_deals_value": total_deals_val,
            "deals_count": len(deals or []),
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "outstanding_balance": outstanding
        }
    }, None


# -------------------------------------------------------------
# Bulk Actions for Customers
# -------------------------------------------------------------
def bulk_action_customers(action: str, ids: list, value=None, user_id: int | None = None) -> tuple[dict | None, str | None]:
    """Execute bulk operations on multiple customers."""
    if not ids or not isinstance(ids, list):
        return None, "No customer IDs provided"

    clean_ids = [int(i) for i in ids if str(i).isdigit()]
    if not clean_ids:
        return None, "Invalid ID list"

    id_placeholders = ", ".join(["%s"] * len(clean_ids))

    if action == "delete":
        # Check if invoices are linked
        check_sql = f"SELECT customer_id FROM invoices WHERE customer_id IN ({id_placeholders}) LIMIT 1"
        has_inv, _ = execute_query(check_sql, tuple(clean_ids), fetch_one=True)
        if has_inv:
            return None, "Cannot delete selected customers: one or more have active invoices"

        del_sql = f"DELETE FROM customers WHERE id IN ({id_placeholders})"
        _, err = execute_query(del_sql, tuple(clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "customer", None, "bulk_delete", f"Bulk deleted {len(clean_ids)} customers")
        return {"action": "delete", "affected": len(clean_ids)}, None

    elif action == "status":
        valid_statuses = {"active", "inactive", "prospect", "blocked"}
        if value not in valid_statuses:
            return None, f"Invalid status '{value}'. Allowed: {', '.join(valid_statuses)}"

        up_sql = f"UPDATE customers SET status = %s, updated_at = NOW() WHERE id IN ({id_placeholders})"
        _, err = execute_query(up_sql, tuple([value] + clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "customer", None, "bulk_status", f"Bulk updated status of {len(clean_ids)} customers to '{value}'")
        return {"action": "status", "affected": len(clean_ids), "new_status": value}, None

    elif action == "assign":
        assign_id = int(value) if value else None
        up_sql = f"UPDATE customers SET assigned_to = %s, updated_at = NOW() WHERE id IN ({id_placeholders})"
        _, err = execute_query(up_sql, tuple([assign_id] + clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "customer", None, "bulk_assign", f"Bulk assigned {len(clean_ids)} customers to user #{assign_id}")
        return {"action": "assign", "affected": len(clean_ids), "assigned_to": assign_id}, None

    return None, f"Unsupported bulk action '{action}'"
