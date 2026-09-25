import datetime
from database.database import execute_query
from backend.services.activity_service import get_recent_activities


def _get_date_filter_sql(field: str, date_range: str | None, start_date: str | None, end_date: str | None) -> tuple[str, list]:
    """Helper to return SQL condition and params for date filtering."""
    if not date_range or date_range == "all":
        return "", []

    if date_range == "today":
        return f"{field} >= CURDATE()", []
    elif date_range == "this_week":
        return f"{field} >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)", []
    elif date_range == "this_month":
        return f"{field} >= DATE_FORMAT(CURDATE(), '%%Y-%%m-01')", []
    elif date_range == "this_quarter":
        return f"{field} >= MAKEDATE(YEAR(CURDATE()), 1) + INTERVAL (QUARTER(CURDATE())-1)*3 MONTH", []
    elif date_range == "this_year":
        return f"{field} >= DATE_FORMAT(CURDATE(), '%%Y-01-01')", []
    elif date_range == "custom" and start_date and end_date:
        return f"DATE({field}) BETWEEN %s AND %s", [start_date, end_date]
    return "", []


def get_dashboard_summary(date_range: str | None = None, start_date: str | None = None,
                          end_date: str | None = None, entity_filter: str | None = None):
    """
    Query real counts and aggregations across all CRM modules with date filtering,
    executive conversion funnels, 6-month trends, and staff leaderboards.
    """
    c_cond, c_params = _get_date_filter_sql("created_at", date_range, start_date, end_date)
    where_c = f"WHERE {c_cond}" if c_cond else ""

    # 1. Customers metrics
    cust_sql = f"""
        SELECT 
            COUNT(*) AS total_customers,
            SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) AS new_customers
        FROM customers
        {where_c}
    """
    cust_res, _ = execute_query(cust_sql, tuple(c_params), fetch_one=True)
    total_customers = int(cust_res["total_customers"] or 0) if cust_res else 0
    new_customers = int(cust_res["new_customers"] or 0) if cust_res else 0

    # 2. Leads metrics
    lead_sql = f"""
        SELECT 
            COUNT(*) AS total_leads,
            SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) AS new_leads
        FROM leads
        {where_c}
    """
    lead_res, _ = execute_query(lead_sql, tuple(c_params), fetch_one=True)
    total_leads = int(lead_res["total_leads"] or 0) if lead_res else 0
    new_leads = int(lead_res["new_leads"] or 0) if lead_res else 0

    # 3. Deals metrics & pipeline value
    d_cond, d_params = _get_date_filter_sql("created_at", date_range, start_date, end_date)
    where_d = f"WHERE {d_cond}" if d_cond else ""
    deal_sql = f"""
        SELECT 
            COUNT(*) AS total_deals,
            SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS active_deals,
            SUM(CASE WHEN status = 'won' THEN 1 ELSE 0 END) AS won_deals,
            SUM(CASE WHEN status = 'won' THEN value ELSE 0 END) AS won_revenue,
            SUM(CASE WHEN status = 'open' THEN value ELSE 0 END) AS open_pipeline_value
        FROM deals
        {where_d}
    """
    deal_res, _ = execute_query(deal_sql, tuple(d_params), fetch_one=True)
    total_deals = int(deal_res["total_deals"] or 0) if deal_res else 0
    active_deals = int(deal_res["active_deals"] or 0) if deal_res else 0
    won_deals = int(deal_res["won_deals"] or 0) if deal_res else 0
    total_revenue = float(deal_res["won_revenue"] or 0.0) if deal_res else 0.0
    open_pipeline_value = float(deal_res["open_pipeline_value"] or 0.0) if deal_res else 0.0

    # 4. Invoices & Payments metrics
    p_cond, p_params = _get_date_filter_sql("payment_date", date_range, start_date, end_date)
    where_p = f"WHERE {p_cond}" if p_cond else ""
    pay_sql = f"SELECT COALESCE(SUM(amount), 0) as total_collected, COUNT(*) as total_payments FROM payments {where_p}"
    pay_res, _ = execute_query(pay_sql, tuple(p_params), fetch_one=True)
    total_collected_payments = float(pay_res["total_collected"] or 0.0) if pay_res else 0.0
    total_payments_count = int(pay_res["total_payments"] or 0) if pay_res else 0

    i_cond, i_params = _get_date_filter_sql("invoice_date", date_range, start_date, end_date)
    where_i = f"WHERE {i_cond}" if i_cond else ""
    inv_sql = f"""
        SELECT 
            COUNT(*) AS total_invoices,
            COALESCE(SUM(paid_amount), 0) AS total_paid,
            COALESCE(SUM(remaining_amount), 0) AS pending_payments,
            COALESCE(SUM(CASE WHEN status NOT IN ('paid', 'cancelled') THEN remaining_amount ELSE 0 END), 0) AS outstanding_amount
        FROM invoices
        {where_i}
    """
    inv_res, _ = execute_query(inv_sql, tuple(i_params), fetch_one=True)
    total_invoices_count = int(inv_res["total_invoices"] or 0) if inv_res else 0
    pending_payments = float(inv_res["pending_payments"] or 0.0) if inv_res else 0.0
    invoice_paid = float(inv_res["total_paid"] or 0.0) if inv_res else 0.0
    effective_revenue = total_collected_payments if total_collected_payments > 0 else max(total_revenue, invoice_paid)

    # 4b. Products count
    prod_res, _ = execute_query("SELECT COUNT(*) as total_products FROM products", fetch_one=True)
    total_products = int(prod_res["total_products"] or 0) if prod_res else 0

    # 5. Pending tasks
    task_sql = """
        SELECT COUNT(*) AS pending_tasks
        FROM tasks
        WHERE status IN ('pending', 'in_progress')
    """
    task_res, _ = execute_query(task_sql, fetch_one=True)
    pending_tasks = int(task_res["pending_tasks"] or 0) if task_res else 0

    # 6. Today's calls
    call_sql = """
        SELECT COUNT(*) AS today_calls
        FROM calls
        WHERE call_date = CURDATE()
    """
    call_res, _ = execute_query(call_sql, fetch_one=True)
    today_calls = int(call_res["today_calls"] or 0) if call_res else 0

    # 7. Upcoming meetings
    meeting_sql = """
        SELECT COUNT(*) AS upcoming_meetings
        FROM meetings
        WHERE meeting_date >= CURDATE() AND status = 'scheduled'
    """
    meeting_res, _ = execute_query(meeting_sql, fetch_one=True)
    upcoming_meetings = int(meeting_res["upcoming_meetings"] or 0) if meeting_res else 0

    # 8. Lead status breakdown
    lead_status_sql = f"""
        SELECT status, COUNT(*) AS count
        FROM leads
        {where_c}
        GROUP BY status
    """
    lead_status_rows, _ = execute_query(lead_status_sql, tuple(c_params), fetch_all=True)
    lead_status_summary = {r["status"]: int(r["count"]) for r in (lead_status_rows or [])}

    # 9. Deal pipeline stage breakdown
    deal_stage_sql = f"""
        SELECT stage, COUNT(*) AS count, COALESCE(SUM(value), 0) AS total_value
        FROM deals
        {where_d}
        GROUP BY stage
    """
    deal_stage_rows, _ = execute_query(deal_stage_sql, tuple(d_params), fetch_all=True)
    deal_pipeline_summary = [
        {"stage": r["stage"], "count": int(r["count"]), "value": float(r["total_value"])}
        for r in (deal_stage_rows or [])
    ]

    # 10. Lead Conversion Funnel
    # Stages: Total Leads -> Contacted -> Qualified -> Proposal/Deals -> Won
    lead_stats, _ = execute_query("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status IN ('contacted', 'qualified', 'converted') THEN 1 ELSE 0 END) as contacted,
            SUM(CASE WHEN status IN ('qualified', 'converted') THEN 1 ELSE 0 END) as qualified
        FROM leads
    """, fetch_one=True)
    fl_total = int(lead_stats["total"] or 0) if lead_stats else 0
    fl_contacted = int(lead_stats["contacted"] or 0) if lead_stats else 0
    fl_qualified = int(lead_stats["qualified"] or 0) if lead_stats else 0

    deal_stats, _ = execute_query("""
        SELECT
            COUNT(*) as total_deals,
            SUM(CASE WHEN stage IN ('proposal', 'negotiation', 'won') THEN 1 ELSE 0 END) as proposal_sent,
            SUM(CASE WHEN status = 'won' OR stage = 'won' THEN 1 ELSE 0 END) as won
        FROM deals
    """, fetch_one=True)
    fl_proposals = int(deal_stats["proposal_sent"] or 0) if deal_stats else 0
    fl_won = int(deal_stats["won"] or 0) if deal_stats else 0

    base_count = max(1, fl_total)
    funnel = [
        {"stage": "Total Leads", "count": fl_total, "percentage": 100.0, "color": "#4361ee"},
        {"stage": "Contacted", "count": fl_contacted, "percentage": round((fl_contacted / base_count) * 100, 1), "color": "#3a0ca3"},
        {"stage": "Qualified", "count": fl_qualified, "percentage": round((fl_qualified / base_count) * 100, 1), "color": "#7209b7"},
        {"stage": "Proposal Sent", "count": fl_proposals, "percentage": round((fl_proposals / base_count) * 100, 1), "color": "#f72585"},
        {"stage": "Deals Won", "count": fl_won, "percentage": round((fl_won / base_count) * 100, 1), "color": "#10b981"}
    ]

    # 11. Monthly Revenue Trend (Last 6 Months)
    trend_sql = """
        SELECT 
            DATE_FORMAT(payment_date, '%b %Y') as month_label,
            DATE_FORMAT(payment_date, '%Y-%m') as month_key,
            COALESCE(SUM(amount), 0) as total_amount,
            COUNT(*) as payment_count
        FROM payments
        WHERE payment_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY month_key, month_label
        ORDER BY month_key ASC
    """
    trend_rows, _ = execute_query(trend_sql, fetch_all=True)
    trend_map = {r["month_key"]: float(r["total_amount"]) for r in (trend_rows or [])}

    # Generate complete last 6 calendar months
    revenue_trend = []
    now = datetime.datetime.now()
    for i in range(5, -1, -1):
        # Calculate year and month
        y = now.year
        m = now.month - i
        while m <= 0:
            m += 12
            y -= 1
        m_key = f"{y:04d}-{m:02d}"
        d_sample = datetime.date(y, m, 1)
        m_label = d_sample.strftime("%b %Y")
        revenue_trend.append({
            "month_key": m_key,
            "month_label": m_label,
            "amount": trend_map.get(m_key, 0.0)
        })

    # 12. Top Performing Sales Reps Leaderboard
    rep_sql = """
        SELECT 
            u.id, u.first_name, u.last_name, u.email, u.profile_image,
            COUNT(d.id) as won_deals_count,
            COALESCE(SUM(d.value), 0) as won_revenue
        FROM users u
        JOIN deals d ON d.assigned_to = u.id AND d.status = 'won'
        GROUP BY u.id, u.first_name, u.last_name, u.email, u.profile_image
        ORDER BY won_revenue DESC, won_deals_count DESC
        LIMIT 5
    """
    rep_rows, _ = execute_query(rep_sql, fetch_all=True)
    top_reps = []
    for r in (rep_rows or []):
        top_reps.append({
            "id": r["id"],
            "name": f"{r['first_name']} {r['last_name']}".strip(),
            "email": r["email"],
            "profile_image": r["profile_image"] or "",
            "won_deals": int(r["won_deals_count"]),
            "revenue": float(r["won_revenue"])
        })

    # 13. Payment Status Breakdown from Invoices
    inv_stat_sql = """
        SELECT status, COUNT(*) as count, COALESCE(SUM(total_amount), 0) as total_amount
        FROM invoices
        GROUP BY status
    """
    inv_stat_rows, _ = execute_query(inv_stat_sql, fetch_all=True)
    payment_status_breakdown = [
        {
            "status": r["status"],
            "count": int(r["count"]),
            "total_amount": float(r["total_amount"])
        }
        for r in (inv_stat_rows or [])
    ]

    # 14. Recent activities
    recent_activities = get_recent_activities(limit=10, entity_type=entity_filter)

    summary_dict = {
        "total_customers": total_customers,
        "new_customers_30d": new_customers,
        "new_customers": new_customers,
        "total_leads": total_leads,
        "new_leads_30d": new_leads,
        "new_leads": new_leads,
        "active_deals": active_deals,
        "won_deals": won_deals,
        "total_revenue": effective_revenue,
        "total_collected_payments": total_collected_payments,
        "total_payments_count": total_payments_count,
        "total_invoices": total_invoices_count,
        "total_products": total_products,
        "pipeline_value": open_pipeline_value,
        "open_pipeline_value": open_pipeline_value,
        "pending_payments": pending_payments,
        "pending_tasks": pending_tasks,
        "today_calls": today_calls,
        "upcoming_meetings": upcoming_meetings,
        "lead_status_breakdown": [{"status": k, "count": v} for k, v in lead_status_summary.items()],
        "deal_pipeline_breakdown": deal_pipeline_summary,
        "recent_activities": recent_activities
    }

    return {
        "success": True,
        "cards": summary_dict,
        "summary": summary_dict,
        "date_range": date_range or "all",
        "lead_status_summary": lead_status_summary,
        "deal_pipeline_summary": deal_pipeline_summary,
        "revenue_summary": {
            "won_revenue": total_revenue,
            "total_collected": total_collected_payments,
            "total_invoiced": invoice_paid + pending_payments,
            "pending_payments": pending_payments,
            "open_pipeline": open_pipeline_value
        },
        "conversion_funnel": funnel,
        "revenue_trend": revenue_trend,
        "top_sales_reps": top_reps,
        "payment_status_breakdown": payment_status_breakdown,
        "recent_activities": recent_activities
    }

