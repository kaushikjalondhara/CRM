"""
CRM Invoice Service
Handles invoice creation, multi-item calculation, status transitions, and queries.
"""

import random
import datetime
import logging
from database.database import get_db_cursor, execute_query
from backend.services.activity_service import log_activity
from backend.services.notification_service import create_notification

logger = logging.getLogger("crm.invoice_service")

VALID_INVOICE_STATUSES = {"draft", "sent", "paid", "partially_paid", "overdue", "cancelled"}


def _generate_invoice_number() -> str:
    """Generate unique invoice number like INV-202609-1234."""
    prefix = datetime.date.today().strftime("INV-%Y%m")
    for _ in range(10):
        num = f"{prefix}-{random.randint(1000, 9999)}"
        exists, _ = execute_query("SELECT id FROM invoices WHERE invoice_number = %s", (num,), fetch_one=True)
        if not exists:
            return num
    return f"{prefix}-{random.randint(10000, 99999)}"


def calculate_invoice_totals(items: list, current_paid: float = 0.0) -> tuple[dict, list, str | None]:
    """
    Recalculates line item totals, subtotal, tax amount, discount amount, total amount,
    and remaining balance strictly on the backend.
    """
    if not items or not isinstance(items, list):
        return {}, [], "Invoice must contain at least one item"

    subtotal = 0.0
    tax_amount = 0.0
    discount_amount = 0.0
    validated_items = []

    for idx, itm in enumerate(items, start=1):
        try:
            qty = int(itm.get("quantity", 1))
            if qty <= 0:
                return {}, [], f"Item #{idx}: Quantity must be at least 1"
        except (ValueError, TypeError):
            return {}, [], f"Item #{idx}: Invalid quantity"

        try:
            unit_price = round(float(itm.get("unit_price", 0.0)), 2)
            if unit_price < 0:
                return {}, [], f"Item #{idx}: Unit price cannot be negative"
        except (ValueError, TypeError):
            return {}, [], f"Item #{idx}: Invalid unit price"

        try:
            tax_pct = round(float(itm.get("tax_percentage", 0.0)), 2)
            if tax_pct < 0 or tax_pct > 100:
                return {}, [], f"Item #{idx}: Tax percentage must be between 0 and 100"
        except (ValueError, TypeError):
            return {}, [], f"Item #{idx}: Invalid tax percentage"

        try:
            disc_pct = round(float(itm.get("discount_percentage", 0.0)), 2)
            if disc_pct < 0 or disc_pct > 100:
                return {}, [], f"Item #{idx}: Discount percentage must be between 0 and 100"
        except (ValueError, TypeError):
            return {}, [], f"Item #{idx}: Invalid discount percentage"

        line_base = round(qty * unit_price, 2)
        line_tax = round(line_base * (tax_pct / 100.0), 2)
        line_disc = round(line_base * (disc_pct / 100.0), 2)
        line_total = round(line_base + line_tax - line_disc, 2)

        subtotal += line_base
        tax_amount += line_tax
        discount_amount += line_disc

        prod_id = itm.get("product_id")
        if prod_id:
            try:
                prod_id = int(prod_id)
            except (ValueError, TypeError):
                prod_id = None

        validated_items.append({
            "product_id": prod_id,
            "description": (itm.get("description") or "").strip() or None,
            "quantity": qty,
            "unit_price": unit_price,
            "tax_percentage": tax_pct,
            "discount_percentage": disc_pct,
            "total": line_total
        })

    subtotal = round(subtotal, 2)
    tax_amount = round(tax_amount, 2)
    discount_amount = round(discount_amount, 2)
    total_amount = round(subtotal + tax_amount - discount_amount, 2)
    paid_amount = round(float(current_paid or 0.0), 2)
    remaining_amount = round(max(0.0, total_amount - paid_amount), 2)

    totals = {
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "discount_amount": discount_amount,
        "total_amount": total_amount,
        "paid_amount": paid_amount,
        "remaining_amount": remaining_amount
    }
    return totals, validated_items, None


def create_invoice(data: dict, user_id: int | None = None) -> tuple[int | None, str | None]:
    """
    Create an invoice and its line items inside a database transaction.
    """
    customer_id = data.get("customer_id")
    if not customer_id:
        return None, "Customer is required"
    try:
        customer_id = int(customer_id)
    except (ValueError, TypeError):
        return None, "Invalid customer ID"

    # Verify customer exists
    cust, _ = execute_query("SELECT id, first_name, last_name, assigned_to FROM customers WHERE id = %s", (customer_id,), fetch_one=True)
    if not cust:
        return None, "Customer not found"

    deal_id = data.get("deal_id")
    if deal_id:
        try:
            deal_id = int(deal_id)
        except (ValueError, TypeError):
            deal_id = None

    inv_date = data.get("invoice_date") or datetime.date.today().strftime("%Y-%m-%d")
    due_date = data.get("due_date") or (datetime.date.today() + datetime.timedelta(days=15)).strftime("%Y-%m-%d")

    items = data.get("items", [])
    totals, validated_items, err = calculate_invoice_totals(items, current_paid=0.0)
    if err:
        return None, err

    inv_number = (data.get("invoice_number") or "").strip()
    if not inv_number:
        inv_number = _generate_invoice_number()
    else:
        dup, _ = execute_query("SELECT id FROM invoices WHERE invoice_number = %s", (inv_number,), fetch_one=True)
        if dup:
            return None, f"Invoice number '{inv_number}' already exists"

    status = data.get("status", "draft")
    if status not in VALID_INVOICE_STATUSES:
        status = "draft"

    notes = (data.get("notes") or "").strip() or None

    # Perform transactional insert
    invoice_id = None
    try:
        with get_db_cursor(commit=True) as cursor:
            insert_inv = """
                INSERT INTO invoices (
                    invoice_number, customer_id, deal_id, invoice_date, due_date,
                    subtotal, tax_amount, discount_amount, total_amount, paid_amount,
                    remaining_amount, status, notes, created_by, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            cursor.execute(insert_inv, (
                inv_number, customer_id, deal_id, inv_date, due_date,
                totals["subtotal"], totals["tax_amount"], totals["discount_amount"],
                totals["total_amount"], totals["paid_amount"], totals["remaining_amount"],
                status, notes, user_id
            ))
            invoice_id = cursor.lastrowid

            insert_item = """
                INSERT INTO invoice_items (
                    invoice_id, product_id, description, quantity,
                    unit_price, tax_percentage, discount_percentage, total, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            for itm in validated_items:
                cursor.execute(insert_item, (
                    invoice_id, itm["product_id"], itm["description"],
                    itm["quantity"], itm["unit_price"], itm["tax_percentage"],
                    itm["discount_percentage"], itm["total"]
                ))
    except Exception as ex:
        logger.error("Failed to create invoice with items: %s", str(ex))
        return None, f"Database error creating invoice: {str(ex)}"

    log_activity(user_id, "invoice", invoice_id, "created", f"Created invoice {inv_number} for customer {cust['first_name']} {cust['last_name']} (Total: ₹{totals['total_amount']:.2f})")

    # Notify customer assignee if different
    if cust.get("assigned_to") and cust["assigned_to"] != user_id:
        create_notification(
            user_id=cust["assigned_to"],
            title="New Invoice Generated",
            message=f"Invoice {inv_number} of ₹{totals['total_amount']:.2f} generated for your customer.",
            notif_type="invoice",
            related_type="invoice",
            related_id=invoice_id
        )

    return invoice_id, None


def update_invoice(invoice_id: int, data: dict, user_id: int | None = None) -> tuple[bool, str | None]:
    """
    Update invoice header and replace invoice items in a transaction.
    """
    existing, err = get_invoice(invoice_id)
    if err or not existing:
        return False, "Invoice not found"

    customer_id = data.get("customer_id", existing["customer_id"])
    try:
        customer_id = int(customer_id)
    except (ValueError, TypeError):
        return False, "Invalid customer ID"

    deal_id = data.get("deal_id", existing.get("deal_id"))
    if deal_id:
        try:
            deal_id = int(deal_id)
        except (ValueError, TypeError):
            deal_id = None

    inv_date = data.get("invoice_date", existing["invoice_date"])
    due_date = data.get("due_date", existing["due_date"])
    notes = (data.get("notes") or "").strip() or None

    items = data.get("items")
    if items is None:
        # Keep existing items
        items = existing.get("items", [])

    current_paid = float(existing.get("paid_amount", 0.0))
    totals, validated_items, err = calculate_invoice_totals(items, current_paid=current_paid)
    if err:
        return False, err

    # Status handling
    status = data.get("status", existing["status"])
    if totals["paid_amount"] >= totals["total_amount"] and totals["total_amount"] > 0:
        status = "paid"
    elif totals["paid_amount"] > 0:
        status = "partially_paid"
    elif status not in VALID_INVOICE_STATUSES:
        status = existing["status"]

    try:
        with get_db_cursor(commit=True) as cursor:
            # Update invoice header
            update_sql = """
                UPDATE invoices
                SET customer_id = %s, deal_id = %s, invoice_date = %s, due_date = %s,
                    subtotal = %s, tax_amount = %s, discount_amount = %s, total_amount = %s,
                    paid_amount = %s, remaining_amount = %s, status = %s, notes = %s,
                    updated_at = NOW()
                WHERE id = %s
            """
            cursor.execute(update_sql, (
                customer_id, deal_id, inv_date, due_date,
                totals["subtotal"], totals["tax_amount"], totals["discount_amount"],
                totals["total_amount"], totals["paid_amount"], totals["remaining_amount"],
                status, notes, invoice_id
            ))

            # Delete old items and insert updated items
            cursor.execute("DELETE FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
            insert_item = """
                INSERT INTO invoice_items (
                    invoice_id, product_id, description, quantity,
                    unit_price, tax_percentage, discount_percentage, total, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            for itm in validated_items:
                cursor.execute(insert_item, (
                    invoice_id, itm["product_id"], itm["description"],
                    itm["quantity"], itm["unit_price"], itm["tax_percentage"],
                    itm["discount_percentage"], itm["total"]
                ))
    except Exception as ex:
        logger.error("Failed to update invoice: %s", str(ex))
        return False, f"Database error updating invoice: {str(ex)}"

    log_activity(user_id, "invoice", invoice_id, "updated", f"Updated invoice {existing['invoice_number']}")
    return True, None


def delete_invoice(invoice_id: int, user_id: int | None = None) -> tuple[bool, str | None]:
    """
    Delete invoice if no payments are logged against it.
    """
    existing, err = get_invoice(invoice_id)
    if err or not existing:
        return False, "Invoice not found"

    # Check for payments
    pay, _ = execute_query("SELECT id FROM payments WHERE invoice_id = %s LIMIT 1", (invoice_id,), fetch_one=True)
    if pay:
        return False, "Cannot delete invoice because payments are linked to it. Delete or void payments first."

    # Delete invoice (invoice_items cascade delete automatically)
    sql = "DELETE FROM invoices WHERE id = %s"
    _, err = execute_query(sql, (invoice_id,), commit=True)
    if err:
        return False, err

    log_activity(user_id, "invoice", invoice_id, "deleted", f"Deleted invoice {existing['invoice_number']}")
    return True, None


def get_invoice(invoice_id: int) -> tuple[dict | None, str | None]:
    """
    Fetch full invoice details including its customer info, items, and payments.
    """
    sql = """
        SELECT i.id, i.invoice_number, i.customer_id, i.deal_id, i.invoice_date, i.due_date,
               i.subtotal, i.tax_amount, i.discount_amount, i.total_amount, i.paid_amount,
               i.remaining_amount, i.status, i.notes, i.created_by, i.created_at, i.updated_at,
               c.first_name, c.last_name, c.company_name, c.email as customer_email, c.phone as customer_phone,
               d.title as deal_title,
               u.first_name as creator_first_name, u.last_name as creator_last_name
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        LEFT JOIN deals d ON i.deal_id = d.id
        LEFT JOIN users u ON i.created_by = u.id
        WHERE i.id = %s
    """
    row, err = execute_query(sql, (invoice_id,), fetch_one=True)
    if err:
        return None, err
    if not row:
        return None, "Invoice not found"

    # Fetch items
    item_sql = """
        SELECT it.id, it.product_id, it.description, it.quantity, it.unit_price,
               it.tax_percentage, it.discount_percentage, it.total,
               p.name as product_name, p.product_code
        FROM invoice_items it
        LEFT JOIN products p ON it.product_id = p.id
        WHERE it.invoice_id = %s
        ORDER BY it.id ASC
    """
    item_rows, _ = execute_query(item_sql, (invoice_id,), fetch_all=True)
    items = []
    for it in (item_rows or []):
        items.append({
            "id": it["id"],
            "product_id": it["product_id"],
            "product_name": it["product_name"] or "Custom Item",
            "product_code": it["product_code"],
            "description": it["description"],
            "quantity": it["quantity"],
            "unit_price": float(it["unit_price"] or 0.0),
            "tax_percentage": float(it["tax_percentage"] or 0.0),
            "discount_percentage": float(it["discount_percentage"] or 0.0),
            "total": float(it["total"] or 0.0)
        })

    # Fetch linked payments
    pay_sql = """
        SELECT id, amount, payment_method, transaction_reference, payment_date, notes, created_at
        FROM payments
        WHERE invoice_id = %s
        ORDER BY payment_date DESC, id DESC
    """
    pay_rows, _ = execute_query(pay_sql, (invoice_id,), fetch_all=True)
    payments = []
    for p in (pay_rows or []):
        payments.append({
            "id": p["id"],
            "amount": float(p["amount"] or 0.0),
            "payment_method": p["payment_method"],
            "transaction_reference": p["transaction_reference"],
            "payment_date": p["payment_date"].strftime("%Y-%m-%d") if p["payment_date"] else None,
            "notes": p["notes"],
            "created_at": p["created_at"].strftime("%Y-%m-%d %H:%M:%S") if p["created_at"] else None
        })

    return {
        "id": row["id"],
        "invoice_number": row["invoice_number"],
        "customer_id": row["customer_id"],
        "customer_name": f"{row['first_name']} {row['last_name']}".strip(),
        "company_name": row["company_name"],
        "customer_email": row["customer_email"],
        "customer_phone": row["customer_phone"],
        "deal_id": row["deal_id"],
        "deal_title": row["deal_title"],
        "invoice_date": row["invoice_date"].strftime("%Y-%m-%d") if row["invoice_date"] else None,
        "due_date": row["due_date"].strftime("%Y-%m-%d") if row["due_date"] else None,
        "subtotal": float(row["subtotal"] or 0.0),
        "tax_amount": float(row["tax_amount"] or 0.0),
        "discount_amount": float(row["discount_amount"] or 0.0),
        "total_amount": float(row["total_amount"] or 0.0),
        "paid_amount": float(row["paid_amount"] or 0.0),
        "remaining_amount": float(row["remaining_amount"] or 0.0),
        "status": row["status"],
        "notes": row["notes"],
        "created_by": row["created_by"],
        "creator_name": f"{row['creator_first_name']} {row['creator_last_name']}".strip() if row["creator_first_name"] else None,
        "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row["created_at"] else None,
        "items": items,
        "payments": payments
    }, None


def list_invoices(search: str | None = None, status: str | None = None,
                  customer_id: int | None = None, start_date: str | None = None,
                  end_date: str | None = None, page: int = 1, per_page: int = 20) -> tuple[dict | None, str | None]:
    """
    List invoices with search, filters, and pagination.
    """
    where_clauses = []
    params: list = []

    if search:
        term = f"%{search.strip()}%"
        where_clauses.append("(i.invoice_number LIKE %s OR c.first_name LIKE %s OR c.last_name LIKE %s OR c.company_name LIKE %s)")
        params.extend([term, term, term, term])

    if status and status in VALID_INVOICE_STATUSES:
        where_clauses.append("i.status = %s")
        params.append(status)

    if customer_id:
        where_clauses.append("i.customer_id = %s")
        params.append(customer_id)

    if start_date:
        where_clauses.append("i.invoice_date >= %s")
        params.append(start_date)

    if end_date:
        where_clauses.append("i.invoice_date <= %s")
        params.append(end_date)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_sql = f"""
        SELECT COUNT(*) as total
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        {where_sql}
    """
    count_res, err = execute_query(count_sql, tuple(params), fetch_one=True)
    if err:
        return None, err
    total = count_res["total"] if count_res else 0

    offset = max(0, (page - 1) * per_page)
    fetch_sql = f"""
        SELECT i.id, i.invoice_number, i.customer_id, i.invoice_date, i.due_date,
               i.subtotal, i.tax_amount, i.discount_amount, i.total_amount,
               i.paid_amount, i.remaining_amount, i.status, i.created_at,
               c.first_name, c.last_name, c.company_name
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        {where_sql}
        ORDER BY i.invoice_date DESC, i.id DESC
        LIMIT %s OFFSET %s
    """
    fetch_params = list(params) + [per_page, offset]
    rows, err = execute_query(fetch_sql, tuple(fetch_params), fetch_all=True)
    if err:
        return None, err

    invoices = []
    for r in (rows or []):
        invoices.append({
            "id": r["id"],
            "invoice_number": r["invoice_number"],
            "customer_id": r["customer_id"],
            "customer_name": f"{r['first_name']} {r['last_name']}".strip(),
            "company_name": r["company_name"],
            "invoice_date": r["invoice_date"].strftime("%Y-%m-%d") if r["invoice_date"] else None,
            "due_date": r["due_date"].strftime("%Y-%m-%d") if r["due_date"] else None,
            "subtotal": float(r["subtotal"] or 0.0),
            "tax_amount": float(r["tax_amount"] or 0.0),
            "discount_amount": float(r["discount_amount"] or 0.0),
            "total_amount": float(r["total_amount"] or 0.0),
            "paid_amount": float(r["paid_amount"] or 0.0),
            "remaining_amount": float(r["remaining_amount"] or 0.0),
            "status": r["status"],
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None
        })

    # Summary metrics
    summary_sql = f"""
        SELECT
            COALESCE(SUM(total_amount), 0) as total_invoiced,
            COALESCE(SUM(paid_amount), 0) as total_paid,
            COALESCE(SUM(remaining_amount), 0) as total_outstanding,
            COUNT(*) as total_count
        FROM invoices i
        JOIN customers c ON i.customer_id = c.id
        {where_sql}
    """
    summary_res, _ = execute_query(summary_sql, tuple(params), fetch_one=True)
    summary = {
        "total_invoiced": float(summary_res["total_invoiced"] or 0.0) if summary_res else 0.0,
        "total_paid": float(summary_res["total_paid"] or 0.0) if summary_res else 0.0,
        "total_outstanding": float(summary_res["total_outstanding"] or 0.0) if summary_res else 0.0,
        "total_count": summary_res["total_count"] if summary_res else 0
    }

    return {
        "invoices": invoices,
        "summary": summary,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 1
    }, None


def bulk_action_invoices(action: str, ids: list, value=None, user_id: int | None = None) -> tuple[dict | None, str | None]:
    """Execute bulk operations on multiple invoices."""
    if not ids or not isinstance(ids, list):
        return None, "No invoice IDs provided"

    clean_ids = [int(i) for i in ids if str(i).isdigit()]
    if not clean_ids:
        return None, "Invalid ID list"

    id_placeholders = ", ".join(["%s"] * len(clean_ids))

    if action == "delete":
        # Check payments constraint
        chk_sql = f"SELECT DISTINCT invoice_id FROM payments WHERE invoice_id IN ({id_placeholders})"
        paid_rows, _ = execute_query(chk_sql, tuple(clean_ids), fetch_all=True)
        if paid_rows:
            return None, "Cannot delete invoices that have recorded payments. Please cancel them instead."

        # Delete invoice_items first
        execute_query(f"DELETE FROM invoice_items WHERE invoice_id IN ({id_placeholders})", tuple(clean_ids), commit=True)
        execute_query(f"DELETE FROM invoices WHERE id IN ({id_placeholders})", tuple(clean_ids), commit=True)

        log_activity(user_id, "invoice", None, "bulk_delete", f"Bulk deleted {len(clean_ids)} invoices")
        return {"action": "delete", "affected": len(clean_ids)}, None

    elif action == "status":
        valid_statuses = {"draft", "sent", "paid", "partially_paid", "overdue", "cancelled"}
        if value not in valid_statuses:
            return None, f"Invalid status '{value}'. Allowed: {', '.join(valid_statuses)}"

        up_sql = f"UPDATE invoices SET status = %s, updated_at = NOW() WHERE id IN ({id_placeholders})"
        _, err = execute_query(up_sql, tuple([value] + clean_ids), commit=True)
        if err:
            return None, err

        log_activity(user_id, "invoice", None, "bulk_status", f"Bulk updated {len(clean_ids)} invoices status to '{value}'")
        return {"action": "status", "affected": len(clean_ids), "new_status": value}, None

    return None, f"Unsupported bulk action '{action}'"

