"""
CRM Calendar Routes
Endpoints for calendar event feed and custom scheduling.
"""

from flask import Blueprint, request, jsonify, g
from backend.services.calendar_service import (
    get_calendar_events,
    create_calendar_event,
    update_calendar_event,
    delete_calendar_event
)
from backend.utils.decorators import login_required

calendar_blueprint = Blueprint("calendar", __name__, url_prefix="/api/calendar")


@calendar_blueprint.route("/events", methods=["GET"])
@login_required
def list_events():
    """
    GET /api/calendar/events?start=...&end=...&type=...
    Retrieves unified calendar event stream.
    """
    start_date = request.args.get("start")
    end_date = request.args.get("end")
    event_type = request.args.get("type")

    events = get_calendar_events(start_date=start_date, end_date=end_date, event_type=event_type, current_user=g.current_user)
    return jsonify({
        "success": True,
        "events": events,
        "count": len(events)
    }), 200


@calendar_blueprint.route("/events", methods=["POST"])
@login_required
def add_event():
    """POST /api/calendar/events - Create new event."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    event_id, err = create_calendar_event(data, user_id=user_id)
    if err:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({
        "success": True,
        "message": "Calendar event created successfully",
        "event_id": event_id,
        "id": event_id,
        "data": {"id": event_id}
    }), 201


@calendar_blueprint.route("/events/<int:event_id>", methods=["PUT"])
@login_required
def edit_event(event_id):
    """PUT /api/calendar/events/<id> - Update event."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    ok, err = update_calendar_event(event_id, data, user_id=user_id)
    if not ok:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({
        "success": True,
        "message": "Calendar event updated successfully"
    }), 200


@calendar_blueprint.route("/events/<int:event_id>", methods=["DELETE"])
@login_required
def remove_event(event_id):
    """DELETE /api/calendar/events/<id> - Remove event."""
    user_id = g.current_user["id"]
    ok, err = delete_calendar_event(event_id, user_id=user_id)
    if not ok:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({
        "success": True,
        "message": "Calendar event deleted successfully"
    }), 200
