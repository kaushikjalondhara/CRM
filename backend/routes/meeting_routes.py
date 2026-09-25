"""
CRM Meeting Routes
Endpoints for organizing calendars, in-person/virtual meetings, and client follow-ups.
"""

from flask import Blueprint, request, jsonify, g
from backend.services.meeting_service import (
    list_meetings,
    get_meeting_by_id,
    schedule_meeting,
    update_meeting,
    delete_meeting
)
from backend.utils.decorators import login_required, permission_required

meeting_blueprint = Blueprint("meetings", __name__, url_prefix="/api/meetings")


@meeting_blueprint.route("", methods=["GET"])
@login_required
@permission_required("meetings.view")
def get_meetings():
    """GET /api/meetings: List and filter meetings."""
    search = request.args.get("search")
    status = request.args.get("status")
    assigned_to = request.args.get("assigned_to", type=int)
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    customer_id = request.args.get("customer_id", type=int)
    lead_id = request.args.get("lead_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 15, type=int)

    result = list_meetings(
        search=search, status=status, assigned_to=assigned_to,
        date_from=date_from, date_to=date_to, customer_id=customer_id,
        lead_id=lead_id, page=page, per_page=per_page
    )
    return jsonify(result), 200


@meeting_blueprint.route("", methods=["POST"])
@login_required
@permission_required("meetings.create")
def create():
    """POST /api/meetings: Schedule a meeting with time validation."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    result, status_code = schedule_meeting(data, user_id)
    return jsonify(result), status_code


@meeting_blueprint.route("/<int:meeting_id>", methods=["GET"])
@login_required
@permission_required("meetings.view")
def get_one(meeting_id):
    """GET /api/meetings/<id>: Retrieve single meeting details."""
    meeting = get_meeting_by_id(meeting_id)
    if not meeting:
        return jsonify({"success": False, "message": "Meeting not found"}), 404
    return jsonify({"success": True, "meeting": meeting}), 200


@meeting_blueprint.route("/<int:meeting_id>", methods=["PUT"])
@login_required
@permission_required("meetings.update")
def update(meeting_id):
    """PUT /api/meetings/<id>: Update meeting schedule or outcome."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    result, status_code = update_meeting(meeting_id, data, user_id)
    return jsonify(result), status_code


@meeting_blueprint.route("/<int:meeting_id>", methods=["DELETE"])
@login_required
@permission_required("meetings.delete")
def delete(meeting_id):
    """DELETE /api/meetings/<id>: Cancel or remove meeting."""
    user_id = g.current_user["id"]
    result, status_code = delete_meeting(meeting_id, user_id)
    return jsonify(result), status_code
