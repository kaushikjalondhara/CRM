"""
CRM Call Routes
Endpoints for logging phone interactions and scheduling future calls.
"""

from flask import Blueprint, request, jsonify, g
from backend.services.call_service import (
    list_calls,
    get_call_by_id,
    schedule_call,
    update_call,
    delete_call
)
from backend.utils.decorators import login_required, permission_required

call_blueprint = Blueprint("calls", __name__, url_prefix="/api/calls")


@call_blueprint.route("", methods=["GET"])
@login_required
@permission_required("calls.view")
def get_calls():
    """GET /api/calls: List and filter calls."""
    search = request.args.get("search")
    status = request.args.get("status")
    assigned_to = request.args.get("assigned_to", type=int)
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    customer_id = request.args.get("customer_id", type=int)
    lead_id = request.args.get("lead_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 15, type=int)

    result = list_calls(
        search=search, status=status, assigned_to=assigned_to,
        date_from=date_from, date_to=date_to, customer_id=customer_id,
        lead_id=lead_id, page=page, per_page=per_page
    )
    return jsonify(result), 200


@call_blueprint.route("", methods=["POST"])
@login_required
@permission_required("calls.create")
def create():
    """POST /api/calls: Schedule or log a new call."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    result, status_code = schedule_call(data, user_id)
    return jsonify(result), status_code


@call_blueprint.route("/<int:call_id>", methods=["GET"])
@login_required
@permission_required("calls.view")
def get_one(call_id):
    """GET /api/calls/<id>: Get single call record."""
    call = get_call_by_id(call_id)
    if not call:
        return jsonify({"success": False, "message": "Call record not found"}), 404
    return jsonify({"success": True, "call": call}), 200


@call_blueprint.route("/<int:call_id>", methods=["PUT"])
@login_required
@permission_required("calls.update")
def update(call_id):
    """PUT /api/calls/<id>: Update call details and outcome status."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    result, status_code = update_call(call_id, data, user_id)
    return jsonify(result), status_code


@call_blueprint.route("/<int:call_id>", methods=["DELETE"])
@login_required
@permission_required("calls.delete")
def delete(call_id):
    """DELETE /api/calls/<id>: Delete call record."""
    user_id = g.current_user["id"]
    result, status_code = delete_call(call_id, user_id)
    return jsonify(result), status_code
