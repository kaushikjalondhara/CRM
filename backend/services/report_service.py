"""
CRM Reports and Analytics Service
Executes database queries to calculate real CRM metrics and performance reports.
Zero fake data: when records are empty, returns exact 0 metrics and clean empty states.
"""

from database.database import execute_query


def _build_date_clause(date_col: str, date_filter: str | None, start_date: str | None, end_date: str | None) -> tuple[str, list]:
    """Helper to generate parameterized SQL where clause for date ranges."""
    date_filter = (date_filter or "all").lower()
    params = []

    if date_filter == "today":
        return f"DATE({date_col}) = CURDATE()", []
    elif date_filter == "week":
        return f"{date_col} >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)", []
    elif date_filter == "month":
        return f"{date_col} >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)", []
    elif date_filter == "year":
        return f"{date_col} >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)", []
    elif date_filter == "custom":
        clauses = []
        if start_date:
            clauses.append(f"DATE({date_col}) >= %s")
            params.append(start_date)
        if end_date:
            clauses.append(f"DATE({date_col}) <= %s")
            params.append(end_date)
        if clauses:
            return " AND ".join(clauses), params
    return "1=1", []


# -------------------------------------------------------------
# 1. Sales Report
# -------------------------------------------------------------
def get_sales_report(date_filter: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Sales report: deal values, won/lost metrics, and stage breakdown."""
    clause, params = _build_date_clause("created_at", date_filter, start_date, end_date)

    sql = f"""
        SELECT
            COUNT(*) as total_deals,
            COALESCE(SUM(value), 0) as total_deal_value,
            COUNT(CASE WHEN stage = 'Won' THEN 1 END) as won_deals_count,
            COALESCE(SUM(CASE WHEN stage = 'Won' THEN value ELSE 0 END), 0) as won_deals_value,
            COUNT(CASE WHEN stage = 'Lost' THEN 1 END) as lost_deals_count,
            COALESCE(SUM(CASE WHEN stage = 'Lost' THEN value ELSE 0 END), 0) as lost_deals_value,
            COUNT(CASE WHEN stage NOT IN ('Won', 'Lost') THEN 1 END) as pipeline_deals_count,
            COALESCE(SUM(CASE WHEN stage NOT IN ('Won', 'Lost') THEN value ELSE 0 END), 0) as pipeline_value
        FROM deals
        WHERE {clause}
    """
    row, _ = execute_query(sql, tuple(params), fetch_one=True)
    summary = {
        "total_deals": row["total_deals"] if row else 0,
        "total_deal_value": float(row["total_deal_value"] or 0.0) if row else 0.0,
        "won_deals_count": row["won_deals_count"] if row else 0,
        "won_deals_value": float(row["won_deals_value"] or 0.0) if row else 0.0,
        "lost_deals_count": row["lost_deals_count"] if row else 0,
        "lost_deals_value": float(row["lost_deals_value"] or 0.0) if row else 0.0,
        "pipeline_deals_count": row["pipeline_deals_count"] if row else 0,
        "pipeline_value": float(row["pipeline_value"] or 0.0) if row else 0.0,
    }

    # Stage breakdown
    stage_sql = f"""
        SELECT stage, COUNT(*) as count, COALESCE(SUM(value), 0) as value
        FROM deals
        WHERE {clause}
        GROUP BY stage
        ORDER BY count DESC
    """
    stage_rows, _ = execute_query(stage_sql, tuple(params), fetch_all=True)
    stages = [{
        "stage": r["stage"],
        "count": r["count"],
        "value": float(r["value"] or 0.0)
    } for r in (stage_rows or [])]

    return {
        "summary": summary,
        "stage_breakdown": stages,
        "date_filter": date_filter or "all"
    }


# -------------------------------------------------------------
# 2. Revenue Report
# -------------------------------------------------------------
def get_revenue_report(date_filter: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Revenue report: total payments, payment method breakdown, and monthly collections."""
    clause, params = _build_date_clause("payment_date", date_filter, start_date, end_date)

    sql = f"""
        SELECT
            COUNT(*) as total_transactions,
            COALESCE(SUM(amount), 0) as total_revenue,
            COALESCE(AVG(amount), 0) as average_payment
        FROM payments
        WHERE {clause}
    """
    row, _ = execute_query(sql, tuple(params), fetch_one=True)
    summary = {
        "total_transactions": row["total_transactions"] if row else 0,
        "total_revenue": float(row["total_revenue"] or 0.0) if row else 0.0,
        "average_payment": float(row["average_payment"] or 0.0) if row else 0.0
    }

    # By payment method
    method_sql = f"""
        SELECT payment_method, COUNT(*) as count, COALESCE(SUM(amount), 0) as total
        FROM payments
        WHERE {clause}
        GROUP BY payment_method
        ORDER BY total DESC
    """
    method_rows, _ = execute_query(method_sql, tuple(params), fetch_all=True)
    methods = [{
        "method": r["payment_method"],
        "count": r["count"],
        "total": float(r["total"] or 0.0)
    } for r in (method_rows or [])]

    # Monthly revenue trend (last 6-12 months)
    monthly_sql = """
        SELECT DATE_FORMAT(payment_date, '%Y-%m') as month,
               COUNT(*) as count,
               COALESCE(SUM(amount), 0) as total
        FROM payments
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
    """
    monthly_rows, _ = execute_query(monthly_sql, fetch_all=True)
    monthly_trend = [{
        "month": r["month"],
        "count": r["count"],
        "total": float(r["total"] or 0.0)
    } for r in (monthly_rows or [])]

    return {
        "summary": summary,
        "method_breakdown": methods,
        "monthly_trend": monthly_trend,
        "date_filter": date_filter or "all"
    }


# -------------------------------------------------------------
# 3. Customer Report
# -------------------------------------------------------------
def get_customer_report(date_filter: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Customer analytics: total, new in period, status breakdown, industry breakdown."""
    clause, params = _build_date_clause("created_at", date_filter, start_date, end_date)

    # Total in system vs new in range
    tot_row, _ = execute_query("SELECT COUNT(*) as total FROM customers", fetch_one=True)
    new_sql = f"SELECT COUNT(*) as new_customers FROM customers WHERE {clause}"
    new_row, _ = execute_query(new_sql, tuple(params), fetch_one=True)

    summary = {
        "total_customers": tot_row["total"] if tot_row else 0,
        "new_customers": new_row["new_customers"] if new_row else 0
    }

    # By status
    status_sql = f"""
        SELECT status, COUNT(*) as count
        FROM customers
        WHERE {clause}
        GROUP BY status
        ORDER BY count DESC
    """
    status_rows, _ = execute_query(status_sql, tuple(params), fetch_all=True)
    status_breakdown = [{
        "status": r["status"],
        "count": r["count"]
    } for r in (status_rows or [])]

    # By industry
    ind_sql = f"""
        SELECT COALESCE(NULLIF(TRIM(industry), ''), 'Unspecified') as industry, COUNT(*) as count
        FROM customers
        WHERE {clause}
        GROUP BY industry
        ORDER BY count DESC
        LIMIT 10
    """
    ind_rows, _ = execute_query(ind_sql, tuple(params), fetch_all=True)
    industry_breakdown = [{
        "industry": r["industry"],
        "count": r["count"]
    } for r in (ind_rows or [])]

    return {
        "summary": summary,
        "status_breakdown": status_breakdown,
        "industry_breakdown": industry_breakdown,
        "date_filter": date_filter or "all"
    }


# -------------------------------------------------------------
# 4. Lead Report
# -------------------------------------------------------------
def get_lead_report(date_filter: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Lead report: total leads, status, source distribution, conversion rate."""
    clause, params = _build_date_clause("created_at", date_filter, start_date, end_date)

    sql = f"""
        SELECT
            COUNT(*) as total_leads,
            COUNT(CASE WHEN status = 'converted' THEN 1 END) as converted_leads,
            COUNT(CASE WHEN status = 'lost' THEN 1 END) as lost_leads,
            COUNT(CASE WHEN status = 'new' THEN 1 END) as new_leads,
            COUNT(CASE WHEN status NOT IN ('converted', 'lost') THEN 1 END) as open_leads
        FROM leads
        WHERE {clause}
    """
    row, _ = execute_query(sql, tuple(params), fetch_one=True)
    tot = row["total_leads"] if row else 0
    conv = row["converted_leads"] if row else 0
    rate = round((conv / tot * 100.0), 1) if tot > 0 else 0.0

    summary = {
        "total_leads": tot,
        "converted_leads": conv,
        "lost_leads": row["lost_leads"] if row else 0,
        "new_leads": row["new_leads"] if row else 0,
        "open_leads": row["open_leads"] if row else 0,
        "conversion_rate": rate
    }

    # By status
    status_sql = f"""
        SELECT status, COUNT(*) as count
        FROM leads
        WHERE {clause}
        GROUP BY status
        ORDER BY count DESC
    """
    status_rows, _ = execute_query(status_sql, tuple(params), fetch_all=True)
    status_breakdown = [{
        "status": r["status"],
        "count": r["count"]
    } for r in (status_rows or [])]

    # By source
    src_sql = f"""
        SELECT COALESCE(NULLIF(TRIM(source), ''), 'Direct') as source, COUNT(*) as count
        FROM leads
        WHERE {clause}
        GROUP BY source
        ORDER BY count DESC
    """
    src_rows, _ = execute_query(src_sql, tuple(params), fetch_all=True)
    source_breakdown = [{
        "source": r["source"],
        "count": r["count"]
    } for r in (src_rows or [])]

    return {
        "summary": summary,
        "status_breakdown": status_breakdown,
        "source_breakdown": source_breakdown,
        "date_filter": date_filter or "all"
    }


# -------------------------------------------------------------
# 5. Task Report
# -------------------------------------------------------------
def get_task_report(date_filter: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Task report: pending, in progress, completed, cancelled, and overdue tasks."""
    clause, params = _build_date_clause("created_at", date_filter, start_date, end_date)

    sql = f"""
        SELECT
            COUNT(*) as total_tasks,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_tasks,
            COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_tasks,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_tasks,
            COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_tasks,
            COUNT(CASE WHEN status NOT IN ('completed', 'cancelled') AND due_date IS NOT NULL AND due_date < CURDATE() THEN 1 END) as overdue_tasks
        FROM tasks
        WHERE {clause}
    """
    row, _ = execute_query(sql, tuple(params), fetch_one=True)
    summary = {
        "total_tasks": row["total_tasks"] if row else 0,
        "pending_tasks": row["pending_tasks"] if row else 0,
        "in_progress_tasks": row["in_progress_tasks"] if row else 0,
        "completed_tasks": row["completed_tasks"] if row else 0,
        "cancelled_tasks": row["cancelled_tasks"] if row else 0,
        "overdue_tasks": row["overdue_tasks"] if row else 0
    }

    # Priority breakdown
    prio_sql = f"""
        SELECT priority, COUNT(*) as count
        FROM tasks
        WHERE {clause}
        GROUP BY priority
        ORDER BY count DESC
    """
    prio_rows, _ = execute_query(prio_sql, tuple(params), fetch_all=True)
    priority_breakdown = [{
        "priority": r["priority"],
        "count": r["count"]
    } for r in (prio_rows or [])]

    return {
        "summary": summary,
        "priority_breakdown": priority_breakdown,
        "date_filter": date_filter or "all"
    }


# -------------------------------------------------------------
# 6. Invoice Report
# -------------------------------------------------------------
def get_invoice_report(date_filter: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Invoice report: counts and amounts for paid, partially paid, sent, overdue, draft."""
    clause, params = _build_date_clause("invoice_date", date_filter, start_date, end_date)

    sql = f"""
        SELECT
            COUNT(*) as total_invoices,
            COALESCE(SUM(total_amount), 0) as total_invoiced_amount,
            COALESCE(SUM(paid_amount), 0) as total_collected_amount,
            COALESCE(SUM(remaining_amount), 0) as total_outstanding_amount,

            COUNT(CASE WHEN status = 'paid' THEN 1 END) as paid_count,
            COALESCE(SUM(CASE WHEN status = 'paid' THEN total_amount ELSE 0 END), 0) as paid_amount,

            COUNT(CASE WHEN status = 'partially_paid' THEN 1 END) as partially_paid_count,
            COALESCE(SUM(CASE WHEN status = 'partially_paid' THEN remaining_amount ELSE 0 END), 0) as partially_paid_amount,

            COUNT(CASE WHEN status = 'sent' THEN 1 END) as sent_count,
            COALESCE(SUM(CASE WHEN status = 'sent' THEN total_amount ELSE 0 END), 0) as sent_amount,

            COUNT(CASE WHEN status = 'draft' THEN 1 END) as draft_count,
            COALESCE(SUM(CASE WHEN status = 'draft' THEN total_amount ELSE 0 END), 0) as draft_amount,

            COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_count,

            COUNT(CASE WHEN status NOT IN ('paid', 'cancelled') AND due_date < CURDATE() THEN 1 END) as overdue_count,
            COALESCE(SUM(CASE WHEN status NOT IN ('paid', 'cancelled') AND due_date < CURDATE() THEN remaining_amount ELSE 0 END), 0) as overdue_amount
        FROM invoices
        WHERE {clause}
    """
    row, _ = execute_query(sql, tuple(params), fetch_one=True)
    summary = {
        "total_invoices": row["total_invoices"] if row else 0,
        "total_invoiced_amount": float(row["total_invoiced_amount"] or 0.0) if row else 0.0,
        "total_collected_amount": float(row["total_collected_amount"] or 0.0) if row else 0.0,
        "total_outstanding_amount": float(row["total_outstanding_amount"] or 0.0) if row else 0.0,
        "paid_count": row["paid_count"] if row else 0,
        "paid_amount": float(row["paid_amount"] or 0.0) if row else 0.0,
        "partially_paid_count": row["partially_paid_count"] if row else 0,
        "partially_paid_amount": float(row["partially_paid_amount"] or 0.0) if row else 0.0,
        "sent_count": row["sent_count"] if row else 0,
        "sent_amount": float(row["sent_amount"] or 0.0) if row else 0.0,
        "draft_count": row["draft_count"] if row else 0,
        "draft_amount": float(row["draft_amount"] or 0.0) if row else 0.0,
        "overdue_count": row["overdue_count"] if row else 0,
        "overdue_amount": float(row["overdue_amount"] or 0.0) if row else 0.0,
        "cancelled_count": row["cancelled_count"] if row else 0
    }

    return {
        "summary": summary,
        "date_filter": date_filter or "all"
    }


# -------------------------------------------------------------
# 7. Employee Performance Report
# -------------------------------------------------------------
def get_employee_performance(start_date: str | None = None, end_date: str | None = None) -> dict:
    """
    Employee performance analytics: Leads, Deals, Won Deals, Revenue, Tasks, Calls, Meetings per staff.
    """
    sql_users = """
        SELECT u.id, CONCAT(u.first_name, ' ', u.last_name) AS full_name, u.email, r.name as role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.status = 'active'
        ORDER BY u.first_name ASC
    """
    users, _ = execute_query(sql_users, fetch_all=True)

    performance = []
    for u in (users or []):
        uid = u["id"]

        # Leads
        l_sql = "SELECT COUNT(*) as total, SUM(CASE WHEN status = 'converted' THEN 1 ELSE 0 END) as converted FROM leads WHERE assigned_to = %s"
        l_res, _ = execute_query(l_sql, (uid,), fetch_one=True)
        total_leads = int(l_res["total"] or 0) if l_res else 0
        converted_leads = int(l_res["converted"] or 0) if l_res else 0
        conv_rate = round((converted_leads / total_leads * 100), 1) if total_leads > 0 else 0.0

        # Deals
        d_sql = "SELECT COUNT(*) as total, SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) as won_count, COALESCE(SUM(CASE WHEN status = 'won' THEN value ELSE 0 END), 0) as won_val FROM deals WHERE assigned_to = %s"
        d_res, _ = execute_query(d_sql, (uid,), fetch_one=True)
        total_deals = int(d_res["total"] or 0) if d_res else 0
        won_deals = int(d_res["won_count"] or 0) if d_res else 0
        won_revenue = float(d_res["won_val"] or 0.0) if d_res else 0.0

        # Tasks
        t_sql = "SELECT COUNT(*) as total, SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed FROM tasks WHERE assigned_to = %s"
        t_res, _ = execute_query(t_sql, (uid,), fetch_one=True)
        total_tasks = int(t_res["total"] or 0) if t_res else 0
        completed_tasks = int(t_res["completed"] or 0) if t_res else 0

        # Calls & Meetings
        cl_sql = "SELECT COUNT(*) as total FROM calls WHERE created_by = %s"
        cl_res, _ = execute_query(cl_sql, (uid,), fetch_one=True)
        calls_count = int(cl_res["total"] or 0) if cl_res else 0

        m_sql = "SELECT COUNT(*) as total FROM meetings WHERE created_by = %s"
        m_res, _ = execute_query(m_sql, (uid,), fetch_one=True)
        meetings_count = int(m_res["total"] or 0) if m_res else 0

        performance.append({
            "id": uid,
            "name": u["full_name"],
            "email": u["email"],
            "role": u["role_name"],
            "leads": total_leads,
            "converted_leads": converted_leads,
            "conversion_rate": conv_rate,
            "deals": total_deals,
            "won_deals": won_deals,
            "revenue": won_revenue,
            "tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "calls": calls_count,
            "meetings": meetings_count
        })

    # Sort by revenue descending
    performance.sort(key=lambda x: x["revenue"], reverse=True)

    return {
        "success": True,
        "performance": performance,
        "count": len(performance)
    }

