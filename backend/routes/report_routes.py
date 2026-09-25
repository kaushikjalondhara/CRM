"""
CRM Report Routes
API endpoints for system reports and business intelligence analytics.
"""

from flask import Blueprint, request, jsonify
from backend.utils.decorators import login_required, permission_required
from backend.services.report_service import (
    get_sales_report,
    get_revenue_report,
    get_customer_report,
    get_lead_report,
    get_task_report,
    get_invoice_report
)

report_blueprint = Blueprint("reports", __name__, url_prefix="/api/reports")


def _get_filter_params():
    return (
        request.args.get("date_filter"),
        request.args.get("start_date"),
        request.args.get("end_date")
    )


@report_blueprint.route("/sales", methods=["GET"])
@login_required
@permission_required("reports.view")
def sales_report():
    """GET /api/reports/sales"""
    df, s, e = _get_filter_params()
    data = get_sales_report(df, s, e)
    return jsonify({"success": True, "report": data}), 200


@report_blueprint.route("/revenue", methods=["GET"])
@login_required
@permission_required("reports.view")
def revenue_report():
    """GET /api/reports/revenue"""
    df, s, e = _get_filter_params()
    data = get_revenue_report(df, s, e)
    return jsonify({"success": True, "report": data}), 200


@report_blueprint.route("/customers", methods=["GET"])
@login_required
@permission_required("reports.view")
def customer_report():
    """GET /api/reports/customers"""
    df, s, e = _get_filter_params()
    data = get_customer_report(df, s, e)
    return jsonify({"success": True, "report": data}), 200


@report_blueprint.route("/leads", methods=["GET"])
@login_required
@permission_required("reports.view")
def lead_report():
    """GET /api/reports/leads"""
    df, s, e = _get_filter_params()
    data = get_lead_report(df, s, e)
    return jsonify({"success": True, "report": data}), 200


@report_blueprint.route("/tasks", methods=["GET"])
@login_required
@permission_required("reports.view")
def task_report():
    """GET /api/reports/tasks"""
    df, s, e = _get_filter_params()
    data = get_task_report(df, s, e)
    return jsonify({"success": True, "report": data}), 200


@report_blueprint.route("/invoices", methods=["GET"])
@login_required
@permission_required("reports.view")
def invoice_report():
    """GET /api/reports/invoices"""
    df, s, e = _get_filter_params()
    data = get_invoice_report(df, s, e)
    return jsonify({"success": True, "report": data}), 200


@report_blueprint.route("/employee-performance", methods=["GET"])
@login_required
@permission_required("reports.view")
def employee_performance():
    """GET /api/reports/employee-performance"""
    from backend.services.report_service import get_employee_performance
    df, s, e = _get_filter_params()
    result = get_employee_performance(s, e)
    return jsonify(result), 200

