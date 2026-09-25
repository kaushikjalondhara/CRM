"""
CRM Payment Processing Service
Handles recording payments, overpayment validation, invoice balance updates, and transaction safety.
"""

import datetime
import logging
from database.database import get_db_cursor, execute_query
from backend.services.activity_service import log_activity
from backend.services.notification_service import create_notification

logger = logging.getLogger("crm.payment_service")

VALID_PAYMENT_METHODS = {"cash", "upi", "card", "bank_transfer", "other"}


def list_payments(search: str | None = None, invoice_id: int | None = None,
                  customer_id: int | None = None, payment_method: str | None = None,
                  start_date: str | None = None, end_date: str | None = None,
                  page: int = 1, per_page: int = 20) -> tuple[dict | None, str | None]:
    """
    List payments with search, filters, and pagination.
    """
    where_clauses = []
    params: list = []

    if search:
        term = f"%{search.strip()}%"
        where_clauses.append("(p.transaction_reference LIKE %s OR i.invoice_number LIKE %s OR c.first_name LIKE %s OR c.last_name LIKE %s OR c.company_name LIKE %s)")
        params.extend([term, term, term, term, term])

    if invoice_id:
        where_clauses.append("p.invoice_id = %s")
        params.append(invoice_id)

    if customer_id:
        where_clauses.append("p.customer_id = %s")
        params.append(customer_id)

    if payment_method and payment_method in VALID_PAYMENT_METHODS:
        where_clauses.append("p.payment_method = %s")
        params.append(payment_method)

    if start_date:
        where_clauses.append("p.payment_date >= %s")
        params.append(start_date)

    if end_date:
        where_clauses.append("p.payment_date <= %s")
        params.append(end_date)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_sql = f"""
        SELECT COUNT(*) as total
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        JOIN customers c ON p.customer_id = c.id
        {where_sql}
    """
    count_res, err = execute_query(count_sql, tuple(params), fetch_one=True)
    if err:
        return None, err
    total = count_res["total"] if count_res else 0

    offset = max(0, (page - 1) * per_page)
    fetch_sql = f"""
        SELECT p.id, p.invoice_id, p.customer_id, p.amount, p.payment_method,
               p.transaction_reference, p.payment_date, p.notes, p.created_at,
               i.invoice_number, i.total_amount, i.remaining_amount,
               c.first_name, c.last_name, c.company_name,
               u.first_name as recorded_by_fn, u.last_name as recorded_by_ln
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        JOIN customers c ON p.customer_id = c.id
        LEFT JOIN users u ON p.created_by = u.id
        {where_sql}
        ORDER BY p.payment_date DESC, p.id DESC
        LIMIT %s OFFSET %s
    """
    fetch_params = list(params) + [per_page, offset]
    rows, err = execute_query(fetch_sql, tuple(fetch_params), fetch_all=True)
    if err:
        return None, err

    payments = []
    for r in (rows or []):
        payments.append({
            "id": r["id"],
            "invoice_id": r["invoice_id"],
            "invoice_number": r["invoice_number"],
            "customer_id": r["customer_id"],
            "customer_name": f"{r['first_name']} {r['last_name']}".strip(),
            "company_name": r["company_name"],
            "amount": float(r["amount"] or 0.0),
            "payment_method": r["payment_method"],
            "transaction_reference": r["transaction_reference"],
            "payment_date": r["payment_date"].strftime("%Y-%m-%d") if r["payment_date"] else None,
            "notes": r["notes"],
            "recorded_by": f"{r['recorded_by_fn']} {r['recorded_by_ln']}".strip() if r["recorded_by_fn"] else None,
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None
        })

    # Summary metrics
    sum_sql = f"""
        SELECT COALESCE(SUM(p.amount), 0) as total_collected, COUNT(*) as count
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        JOIN customers c ON p.customer_id = c.id
        {where_sql}
    """
    sum_res, _ = execute_query(sum_sql, tuple(params), fetch_one=True)
    total_collected = float(sum_res["total_collected"] or 0.0) if sum_res else 0.0

    return {
        "payments": payments,
        "total_collected": total_collected,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 1
    }, None


def get_payment(payment_id: int) -> tuple[dict | None, str | None]:
    """Retrieve details for a single payment record."""
    sql = """
        SELECT p.id, p.invoice_id, p.customer_id, p.amount, p.payment_method,
               p.transaction_reference, p.payment_date, p.notes, p.created_at,
               i.invoice_number, i.total_amount, i.remaining_amount,
               c.first_name, c.last_name, c.company_name,
               u.first_name as recorded_by_fn, u.last_name as recorded_by_ln
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        JOIN customers c ON p.customer_id = c.id
        LEFT JOIN users u ON p.created_by = u.id
        WHERE p.id = %s
    """
    r, err = execute_query(sql, (payment_id,), fetch_one=True)
    if err:
        return None, err
    if not r:
        return None, "Payment record not found"

    return {
        "id": r["id"],
        "invoice_id": r["invoice_id"],
        "invoice_number": r["invoice_number"],
        "customer_id": r["customer_id"],
        "customer_name": f"{r['first_name']} {r['last_name']}".strip(),
        "company_name": r["company_name"],
        "amount": float(r["amount"] or 0.0),
        "payment_method": r["payment_method"],
        "transaction_reference": r["transaction_reference"],
        "payment_date": r["payment_date"].strftime("%Y-%m-%d") if r["payment_date"] else None,
        "notes": r["notes"],
        "recorded_by": f"{r['recorded_by_fn']} {r['recorded_by_ln']}".strip() if r["recorded_by_fn"] else None,
        "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None
    }, None


def create_payment(data: dict, user_id: int | None = None) -> tuple[int | None, str | None]:
    """
    Record payment against an invoice inside a database transaction.
    Protects against overpayment and updates invoice status atomically.
    """
    invoice_id = data.get("invoice_id")
    if not invoice_id:
        return None, "Invoice is required"
    try:
        invoice_id = int(invoice_id)
    except (ValueError, TypeError):
        return None, "Invalid invoice ID"

    try:
        amount = round(float(data.get("amount", 0.0)), 2)
        if amount <= 0:
            return None, "Payment amount must be greater than 0"
    except (ValueError, TypeError):
        return None, "Invalid payment amount"

    method = data.get("payment_method", "cash")
    if method not in VALID_PAYMENT_METHODS:
        return None, f"Invalid payment method. Must be one of: {', '.join(VALID_PAYMENT_METHODS)}"

    pay_date = data.get("payment_date") or datetime.date.today().strftime("%Y-%m-%d")
    tx_ref = (data.get("transaction_reference") or "").strip() or None
    notes = (data.get("notes") or "").strip() or None

    payment_id = None
    invoice_number = None
    customer_id = None
    customer_assignee = None

    try:
        with get_db_cursor(commit=True) as cursor:
            # Lock invoice row for update
            cursor.execute(
                "SELECT id, invoice_number, customer_id, total_amount, paid_amount, remaining_amount, status FROM invoices WHERE id = %s FOR UPDATE",
                (invoice_id,)
            )
            inv = cursor.fetchone()
            if not inv:
                return None, "Invoice not found"

            invoice_number = inv["invoice_number"]
            customer_id = inv["customer_id"]
            current_remaining = float(inv["remaining_amount"] or 0.0)
            current_paid = float(inv["paid_amount"] or 0.0)
            total_amount = float(inv["total_amount"] or 0.0)

            # Strict overpayment protection (with 1 cent rounding grace)
            if amount > current_remaining + 0.009:
                return None, f"Payment amount (₹{amount:.2f}) exceeds remaining balance of ₹{current_remaining:.2f}"

            new_paid = round(current_paid + amount, 2)
            new_remaining = round(max(0.0, total_amount - new_paid), 2)

            new_status = "paid" if new_remaining <= 0.005 else "partially_paid"

            # Insert payment
            insert_pay = """
                INSERT INTO payments (
                    invoice_id, customer_id, amount, payment_method,
                    transaction_reference, payment_date, notes, created_by, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            cursor.execute(insert_pay, (
                invoice_id, customer_id, amount, method, tx_ref, pay_date, notes, user_id
            ))
            payment_id = cursor.lastrowid

            # Update invoice balance and status
            update_inv = """
                UPDATE invoices
                SET paid_amount = %s, remaining_amount = %s, status = %s, updated_at = NOW()
                WHERE id = %s
            """
            cursor.execute(update_inv, (new_paid, new_remaining, new_status, invoice_id))

            # Fetch customer assignee for notification
            cursor.execute("SELECT assigned_to, first_name, last_name FROM customers WHERE id = %s", (customer_id,))
            cust = cursor.fetchone()
            if cust:
                customer_assignee = cust.get("assigned_to")

    except Exception as ex:
        logger.error("Failed to record payment: %s", str(ex))
        return None, f"Database error recording payment: {str(ex)}"

    log_activity(
        user_id, "payment", payment_id, "created",
        f"Recorded payment of ₹{amount:.2f} ({method.upper()}) for Invoice {invoice_number}"
    )

    # Notification to customer assigned user
    if customer_assignee:
        create_notification(
            user_id=customer_assignee,
            title="Payment Received",
            message=f"Received payment of ₹{amount:.2f} for Invoice {invoice_number}.",
            notif_type="payment",
            related_type="invoice",
            related_id=invoice_id
        )

    return payment_id, None


def delete_payment(payment_id: int, user_id: int | None = None) -> tuple[bool, str | None]:
    """
    Void/delete a payment and automatically recalculate invoice paid/remaining balances in a transaction.
    """
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT * FROM payments WHERE id = %s FOR UPDATE", (payment_id,))
            pay = cursor.fetchone()
            if not pay:
                return False, "Payment record not found"

            inv_id = pay["invoice_id"]
            amount = float(pay["amount"] or 0.0)

            cursor.execute(
                "SELECT total_amount, paid_amount, remaining_amount, invoice_number FROM invoices WHERE id = %s FOR UPDATE",
                (inv_id,)
            )
            inv = cursor.fetchone()
            if not inv:
                return False, "Linked invoice not found"

            total_amount = float(inv["total_amount"] or 0.0)
            current_paid = float(inv["paid_amount"] or 0.0)

            new_paid = round(max(0.0, current_paid - amount), 2)
            new_remaining = round(max(0.0, total_amount - new_paid), 2)

            if new_paid <= 0:
                new_status = "sent"
            elif new_remaining <= 0.005:
                new_status = "paid"
            else:
                new_status = "partially_paid"

            # Delete payment
            cursor.execute("DELETE FROM payments WHERE id = %s", (payment_id,))

            # Update invoice
            cursor.execute("""
                UPDATE invoices
                SET paid_amount = %s, remaining_amount = %s, status = %s, updated_at = NOW()
                WHERE id = %s
            """, (new_paid, new_remaining, new_status, inv_id))

    except Exception as ex:
        logger.error("Failed to delete payment: %s", str(ex))
        return False, f"Database error reverting payment: {str(ex)}"

    log_activity(user_id, "payment", payment_id, "deleted", f"Voided/Deleted payment #{payment_id} of ₹{amount:.2f}")
    return True, None
