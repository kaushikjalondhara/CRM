"""
CRM Dashboard Routes
Provides summary aggregation endpoint for live CRM overview.
"""

from flask import Blueprint, request, jsonify
from backend.services.dashboard_service import get_dashboard_summary
from backend.utils.decorators import login_required, permission_required

dashboard_blueprint = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_blueprint.route("/summary", methods=["GET"])
@login_required
@permission_required("dashboard.view")
def summary():
    """
    GET /api/dashboard/summary
    Returns real statistics, lead stages, pipeline values, funnels, 6-mo trends, and leaderboard.
    Query params: range (today, this_week, this_month, this_quarter, this_year, custom, all),
    start_date, end_date, entity
    """
    date_range = request.args.get("range") or request.args.get("date_range")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    entity = request.args.get("entity")

    data = get_dashboard_summary(
        date_range=date_range,
        start_date=start_date,
        end_date=end_date,
        entity_filter=entity
    )
    return jsonify(data), 200

