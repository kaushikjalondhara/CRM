"""
CRM Lead Routes
Endpoints for Lead pipeline, qualification touchpoints, and conversion to Customer.
"""

from flask import Blueprint, request, jsonify, g
from backend.services.lead_service import (
    list_leads,
    get_lead_by_id,
    get_lead_details,
    create_lead,
    update_lead,
    delete_lead,
    add_lead_activity,
    convert_lead_to_customer
)
from backend.utils.decorators import login_required, permission_required

lead_blueprint = Blueprint("leads", __name__, url_prefix="/api/leads")


@lead_blueprint.route("", methods=["GET"])
@login_required
@permission_required("leads.view")
def get_leads():
    """GET /api/leads: List, search, filter by status/priority, and paginate."""
    search = request.args.get("search")
    status = request.args.get("status")
    priority = request.args.get("priority")
    assigned_to = request.args.get("assigned_to", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    result = list_leads(
        search=search, status=status, priority=priority,
        assigned_to=assigned_to, page=page, per_page=per_page
    )
    return jsonify(result), 200


@lead_blueprint.route("", methods=["POST"])
@login_required
@permission_required("leads.create")
def create():
    """POST /api/leads: Create a new prospect lead."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    result, status_code = create_lead(data, user_id)
    return jsonify(result), status_code


@lead_blueprint.route("/<int:lead_id>", methods=["GET"])
@lead_blueprint.route("/<int:lead_id>/details", methods=["GET"])
@login_required
@permission_required("leads.view")
def get_one(lead_id):
    """GET /api/leads/<id>: Get lead record or details."""
    is_details_route = request.path.rstrip("/").endswith("/details")
    include_details = is_details_route or (request.args.get("details", "0") in ("1", "true", "yes"))

    if include_details:
        data = get_lead_details(lead_id)
        if not data:
            return jsonify({"success": False, "message": "Lead not found"}), 404
        return jsonify({"success": True, **data}), 200

    lead = get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"success": False, "message": "Lead not found"}), 404
    return jsonify({"success": True, "lead": lead}), 200


@lead_blueprint.route("/<int:lead_id>", methods=["PUT"])
@login_required
@permission_required("leads.update")
def update(lead_id):
    """PUT /api/leads/<id>: Update lead details or pipeline status."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    result, status_code = update_lead(lead_id, data, user_id)
    return jsonify(result), status_code


@lead_blueprint.route("/<int:lead_id>", methods=["DELETE"])
@login_required
@permission_required("leads.delete")
def delete(lead_id):
    """DELETE /api/leads/<id>: Remove lead."""
    user_id = g.current_user["id"]
    result, status_code = delete_lead(lead_id, user_id)
    return jsonify(result), status_code


@lead_blueprint.route("/<int:lead_id>/convert", methods=["POST"])
@login_required
@permission_required("leads.convert")
def convert(lead_id):
    """POST /api/leads/<id>/convert: Atomically convert lead to customer."""
    user_id = g.current_user["id"]
    result, status_code = convert_lead_to_customer(lead_id, user_id)
    return jsonify(result), status_code


@lead_blueprint.route("/<int:lead_id>/activities", methods=["GET"])
@login_required
@permission_required("leads.view")
def list_activities(lead_id):
    """GET /api/leads/<id>/activities: List touchpoint activities."""
    data = get_lead_details(lead_id)
    if not data:
        return jsonify({"success": False, "message": "Lead not found"}), 404
    return jsonify({"success": True, "activities": data.get("activities", [])}), 200


@lead_blueprint.route("/<int:lead_id>/activities", methods=["POST"])
@login_required
@permission_required("leads.update")
def add_activity(lead_id):
    """POST /api/leads/<id>/activities: Log a call, email, meeting, note or follow-up."""
    data = request.get_json(silent=True) or {}
    activity_type = data.get("activity_type", "note")
    description = (data.get("description") or data.get("notes") or "").strip()
    if not description:
        return jsonify({"success": False, "message": "Activity description is required"}), 400

    user_id = g.current_user["id"]
    result, status_code = add_lead_activity(lead_id, user_id, activity_type, description)
    return jsonify(result), status_code


@lead_blueprint.route("/bulk-action", methods=["POST"])
@login_required
@permission_required("leads.update")
def bulk_leads():
    """POST /api/leads/bulk-action - Execute batch operations on leads."""
    from backend.services.lead_service import bulk_action_leads
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    ids = payload.get("ids", [])
    value = payload.get("value")

    result, err = bulk_action_leads(action=action, ids=ids, value=value, user_id=g.current_user["id"])
    if err:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({"success": True, "message": "Bulk action completed", "result": result}), 200

