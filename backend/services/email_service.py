"""
CRM Email Management & Template Service
Handles email composition, linked entities (customers, leads, deals),
email template management, and safe development SMTP handling.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from database.database import execute_query
from backend.services.activity_service import log_activity

logger = logging.getLogger("crm.email_service")


def is_smtp_configured() -> bool:
    """Check if real SMTP server credentials are provided in environment."""
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    return bool(host and user and password)


def _send_smtp_email(to_email: str, subject: str, message: str) -> tuple[bool, str | None]:
    """Attempt actual SMTP transmission if configured."""
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", user)

    try:
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "html"))

        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return True, None
    except Exception as ex:
        logger.error("SMTP delivery failed: %s", str(ex))
        return False, str(ex)


DEFAULT_TEMPLATES = [
    {
        "name": "Invoice Email",
        "subject": "Invoice {{invoice_number}} from Apex CRM",
        "body": "<p>Dear {{customer_name}},</p><p>Please find attached your invoice <b>{{invoice_number}}</b> for <b>₹{{total_amount}}</b> due on <b>{{due_date}}</b>.</p><p>Thank you for your business!</p>"
    },
    {
        "name": "Payment Received",
        "subject": "Payment Receipt for Invoice {{invoice_number}}",
        "body": "<p>Dear {{customer_name}},</p><p>We have successfully received your payment of <b>₹{{amount}}</b> for invoice <b>{{invoice_number}}</b>. Reference: <b>{{transaction_reference}}</b>.</p><p>Thank you!</p>"
    },
    {
        "name": "Payment Reminder",
        "subject": "Reminder: Outstanding Balance on Invoice {{invoice_number}}",
        "body": "<p>Dear {{customer_name}},</p><p>This is a friendly reminder that an outstanding balance of <b>₹{{remaining_amount}}</b> is due on <b>{{due_date}}</b> for invoice <b>{{invoice_number}}</b>.</p>"
    },
    {
        "name": "Lead Follow-up",
        "subject": "Following up on your inquiry with Apex CRM",
        "body": "<p>Hello {{lead_name}},</p><p>Thank you for expressing interest in Apex CRM. We would love to schedule a brief discussion to explore how we can support your business requirements.</p>"
    },
    {
        "name": "Meeting Reminder",
        "subject": "Reminder: Scheduled Meeting '{{meeting_title}}'",
        "body": "<p>Dear {{attendee_name}},</p><p>This is a reminder for our scheduled meeting <b>{{meeting_title}}</b> on <b>{{meeting_time}}</b>.</p>"
    },
    {
        "name": "Task Reminder",
        "subject": "Task Assigned: {{task_title}}",
        "body": "<p>Hello {{assignee_name}},</p><p>You have a pending task <b>{{task_title}}</b> with priority <b>{{priority}}</b> due on <b>{{due_date}}</b>.</p>"
    }
]


def seed_default_templates():
    """Seed initial email templates if missing."""
    for t in DEFAULT_TEMPLATES:
        dup, _ = execute_query("SELECT id FROM email_templates WHERE name = %s", (t["name"],), fetch_one=True)
        if not dup:
            execute_query(
                "INSERT INTO email_templates (name, subject, body, created_at) VALUES (%s, %s, %s, NOW())",
                (t["name"], t["subject"], t["body"]),
                commit=True
            )


def list_templates() -> tuple[list | None, str | None]:
    """List all email templates."""
    seed_default_templates()
    sql = """
        SELECT t.id, t.name, t.subject, t.body, t.created_by, t.created_at, t.updated_at,
               u.first_name, u.last_name
        FROM email_templates t
        LEFT JOIN users u ON t.created_by = u.id
        ORDER BY t.name ASC
    """
    rows, err = execute_query(sql, fetch_all=True)
    if err:
        return None, err

    templates = []
    for r in (rows or []):
        templates.append({
            "id": r["id"],
            "name": r["name"],
            "subject": r["subject"],
            "body": r["body"],
            "created_by": r["created_by"],
            "creator_name": f"{r['first_name']} {r['last_name']}".strip() if r["first_name"] else None,
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None,
            "updated_at": r["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if r["updated_at"] else None
        })
    return templates, None


def get_template(template_id: int) -> tuple[dict | None, str | None]:
    """Get single email template."""
    sql = "SELECT id, name, subject, body, created_by, created_at, updated_at FROM email_templates WHERE id = %s"
    r, err = execute_query(sql, (template_id,), fetch_one=True)
    if err:
        return None, err
    if not r:
        return None, "Template not found"

    return {
        "id": r["id"],
        "name": r["name"],
        "subject": r["subject"],
        "body": r["body"],
        "created_by": r["created_by"],
        "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None,
        "updated_at": r["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if r["updated_at"] else None
    }, None


def create_template(data: dict, user_id: int | None = None) -> tuple[int | None, str | None]:
    """Create a new reusable email template."""
    name = (data.get("name") or "").strip()
    if not name:
        return None, "Template name is required"

    subject = (data.get("subject") or "").strip()
    if not subject:
        return None, "Template subject is required"

    body = (data.get("body") or "").strip()
    if not body:
        return None, "Template body is required"

    dup, _ = execute_query("SELECT id FROM email_templates WHERE name = %s", (name,), fetch_one=True)
    if dup:
        return None, f"Template name '{name}' already exists"

    sql = """
        INSERT INTO email_templates (name, subject, body, created_by, created_at)
        VALUES (%s, %s, %s, %s, NOW())
    """
    res, err = execute_query(sql, (name, subject, body, user_id), commit=True)
    if err:
        return None, err
    tmpl_id = res.get("last_id") if isinstance(res, dict) else res

    log_activity(user_id, "email_template", tmpl_id, "created", f"Created email template '{name}'")
    return tmpl_id, None


def update_template(template_id: int, data: dict, user_id: int | None = None) -> tuple[bool, str | None]:
    """Update an existing email template."""
    existing, err = get_template(template_id)
    if err or not existing:
        return False, "Template not found"

    name = (data.get("name") or existing["name"]).strip()
    subject = (data.get("subject") or existing["subject"]).strip()
    body = (data.get("body") or existing["body"]).strip()

    if name != existing["name"]:
        dup, _ = execute_query("SELECT id FROM email_templates WHERE name = %s AND id != %s", (name, template_id), fetch_one=True)
        if dup:
            return False, f"Template name '{name}' already exists"

    sql = """
        UPDATE email_templates
        SET name = %s, subject = %s, body = %s, updated_at = NOW()
        WHERE id = %s
    """
    _, err = execute_query(sql, (name, subject, body, template_id), commit=True)
    if err:
        return False, err

    log_activity(user_id, "email_template", template_id, "updated", f"Updated email template '{name}'")
    return True, None


def delete_template(template_id: int, user_id: int | None = None) -> tuple[bool, str | None]:
    """Delete an email template."""
    existing, err = get_template(template_id)
    if err or not existing:
        return False, "Template not found"

    sql = "DELETE FROM email_templates WHERE id = %s"
    _, err = execute_query(sql, (template_id,), commit=True)
    if err:
        return False, err

    log_activity(user_id, "email_template", template_id, "deleted", f"Deleted email template '{existing['name']}'")
    return True, None


# -------------------------------------------------------------
# Emails Log & Compose
# -------------------------------------------------------------

def list_emails(search: str | None = None, customer_id: int | None = None,
                lead_id: int | None = None, deal_id: int | None = None,
                status: str | None = None, page: int = 1, per_page: int = 20) -> tuple[dict | None, str | None]:
    """List sent and draft emails with filters and pagination."""
    where_clauses = []
    params: list = []

    if search:
        term = f"%{search.strip()}%"
        where_clauses.append("(e.recipient_email LIKE %s OR e.subject LIKE %s OR e.message LIKE %s)")
        params.extend([term, term, term])

    if customer_id:
        where_clauses.append("e.customer_id = %s")
        params.append(customer_id)

    if lead_id:
        where_clauses.append("e.lead_id = %s")
        params.append(lead_id)

    if deal_id:
        where_clauses.append("e.deal_id = %s")
        params.append(deal_id)

    if status and status in {"draft", "sent", "failed"}:
        where_clauses.append("e.status = %s")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_sql = f"SELECT COUNT(*) as total FROM emails e {where_sql}"
    count_res, err = execute_query(count_sql, tuple(params), fetch_one=True)
    if err:
        return None, err
    total = count_res["total"] if count_res else 0

    offset = max(0, (page - 1) * per_page)
    fetch_sql = f"""
        SELECT e.id, e.customer_id, e.lead_id, e.deal_id, e.sender_id,
               e.recipient_email, e.subject, e.message, e.status, e.sent_at, e.created_at,
               c.first_name as cust_fn, c.last_name as cust_ln, c.company_name as cust_company,
               l.first_name as lead_fn, l.last_name as lead_ln,
               d.title as deal_title,
               u.first_name as sender_fn, u.last_name as sender_ln
        FROM emails e
        LEFT JOIN customers c ON e.customer_id = c.id
        LEFT JOIN leads l ON e.lead_id = l.id
        LEFT JOIN deals d ON e.deal_id = d.id
        LEFT JOIN users u ON e.sender_id = u.id
        {where_sql}
        ORDER BY e.created_at DESC
        LIMIT %s OFFSET %s
    """
    fetch_params = list(params) + [per_page, offset]
    rows, err = execute_query(fetch_sql, tuple(fetch_params), fetch_all=True)
    if err:
        return None, err

    emails = []
    for r in (rows or []):
        cust_name = f"{r['cust_fn']} {r['cust_ln']}".strip() if r["cust_fn"] else None
        lead_name = f"{r['lead_fn']} {r['lead_ln']}".strip() if r["lead_fn"] else None
        sender_name = f"{r['sender_fn']} {r['sender_ln']}".strip() if r["sender_fn"] else None

        emails.append({
            "id": r["id"],
            "customer_id": r["customer_id"],
            "customer_name": cust_name,
            "company_name": r["cust_company"],
            "lead_id": r["lead_id"],
            "lead_name": lead_name,
            "deal_id": r["deal_id"],
            "deal_title": r["deal_title"],
            "sender_id": r["sender_id"],
            "sender_name": sender_name,
            "recipient_email": r["recipient_email"],
            "subject": r["subject"],
            "message": r["message"],
            "status": r["status"],
            "sent_at": r["sent_at"].strftime("%Y-%m-%d %H:%M:%S") if r["sent_at"] else None,
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None
        })

    return {
        "emails": emails,
        "is_smtp_configured": is_smtp_configured(),
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 1
    }, None


def get_email(email_id: int) -> tuple[dict | None, str | None]:
    """Retrieve full details of an email."""
    sql = """
        SELECT e.id, e.customer_id, e.lead_id, e.deal_id, e.sender_id,
               e.recipient_email, e.subject, e.message, e.status, e.sent_at, e.created_at,
               c.first_name as cust_fn, c.last_name as cust_ln, c.company_name as cust_company,
               l.first_name as lead_fn, l.last_name as lead_ln,
               d.title as deal_title,
               u.first_name as sender_fn, u.last_name as sender_ln
        FROM emails e
        LEFT JOIN customers c ON e.customer_id = c.id
        LEFT JOIN leads l ON e.lead_id = l.id
        LEFT JOIN deals d ON e.deal_id = d.id
        LEFT JOIN users u ON e.sender_id = u.id
        WHERE e.id = %s
    """
    r, err = execute_query(sql, (email_id,), fetch_one=True)
    if err:
        return None, err
    if not r:
        return None, "Email not found"

    cust_name = f"{r['cust_fn']} {r['cust_ln']}".strip() if r["cust_fn"] else None
    lead_name = f"{r['lead_fn']} {r['lead_ln']}".strip() if r["lead_fn"] else None
    sender_name = f"{r['sender_fn']} {r['sender_ln']}".strip() if r["sender_fn"] else None

    return {
        "id": r["id"],
        "customer_id": r["customer_id"],
        "customer_name": cust_name,
        "company_name": r["cust_company"],
        "lead_id": r["lead_id"],
        "lead_name": lead_name,
        "deal_id": r["deal_id"],
        "deal_title": r["deal_title"],
        "sender_id": r["sender_id"],
        "sender_name": sender_name,
        "recipient_email": r["recipient_email"],
        "subject": r["subject"],
        "message": r["message"],
        "status": r["status"],
        "sent_at": r["sent_at"].strftime("%Y-%m-%d %H:%M:%S") if r["sent_at"] else None,
        "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None
    }, None


def compose_email(data: dict, user_id: int | None = None) -> tuple[dict | None, str | None]:
    """
    Compose and send or draft an email.
    If SMTP is not configured, clearly records as draft and notifies the client without faking delivery.
    """
    to_email = (data.get("recipient_email") or "").strip()
    if not to_email or "@" not in to_email:
        return None, "Valid recipient email address is required"

    subject = (data.get("subject") or "").strip()
    if not subject:
        return None, "Subject line is required"

    message = (data.get("message") or "").strip()
    if not message:
        return None, "Message body cannot be empty"

    customer_id = data.get("customer_id")
    customer_id = int(customer_id) if customer_id else None

    lead_id = data.get("lead_id")
    lead_id = int(lead_id) if lead_id else None

    deal_id = data.get("deal_id")
    deal_id = int(deal_id) if deal_id else None

    smtp_ready = is_smtp_configured()
    status = "draft"
    sent_at_val = None
    user_notice = None

    if smtp_ready:
        sent_ok, smtp_err = _send_smtp_email(to_email, subject, message)
        if sent_ok:
            status = "sent"
            sent_at_val = "NOW()"
            user_notice = "Email sent successfully via configured SMTP server."
        else:
            status = "failed"
            user_notice = f"SMTP transmission failed: {smtp_err}. Email record saved as failed."
    else:
        status = "draft"
        sent_at_val = None
        user_notice = "Email sending is not configured (SMTP settings missing in .env). Email saved as draft."

    # Insert email record
    if sent_at_val:
        sql = """
            INSERT INTO emails (customer_id, lead_id, deal_id, sender_id, recipient_email, subject, message, status, sent_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params = (customer_id, lead_id, deal_id, user_id, to_email, subject, message, status)
    else:
        sql = """
            INSERT INTO emails (customer_id, lead_id, deal_id, sender_id, recipient_email, subject, message, status, sent_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, NOW())
        """
        params = (customer_id, lead_id, deal_id, user_id, to_email, subject, message, status)

    res, err = execute_query(sql, params, commit=True)
    if err:
        return None, err
    email_id = res.get("last_id") if isinstance(res, dict) else res

    log_activity(user_id, "email", email_id, "sent" if status == "sent" else "drafted", f"Composed email to {to_email}: '{subject}' ({status})")

    return {
        "email_id": email_id,
        "status": status,
        "message": user_notice,
        "is_smtp_configured": smtp_ready
    }, None
