"""
CRM Reminder Routes
Endpoints for checking automated reminders and viewing alerts.
"""

from flask import Blueprint, request, jsonify, g
from backend.services.reminder_service import check_and_generate_reminders, list_reminders
from backend.utils.decorators import login_required

reminder_blueprint = Blueprint("reminders", __name__, url_prefix="/api/reminders")


@reminder_blueprint.route("/check", methods=["POST"])
@login_required
def trigger_reminder_check():
    """POST /api/reminders/check - Scan database and generate alerts."""
    result = check_and_generate_reminders()
    return jsonify({
        "success": True,
        "message": f"Reminder scan completed ({result['reminders_created']} new reminders generated)",
        "data": result
    }), 200


@reminder_blueprint.route("", methods=["GET"])
@login_required
def get_user_reminders():
    """GET /api/reminders - View active reminders for current user."""
    user_id = g.current_user["id"]
    limit = request.args.get("limit", 20, type=int)
    reminders = list_reminders(user_id=user_id, limit=limit)
    return jsonify({
        "success": True,
        "reminders": reminders,
        "count": len(reminders)
    }), 200
