"""
CRM Deal Routes
Endpoints for sales opportunities, Kanban pipeline visualization, and stage progression.
"""

from flask import Blueprint, request, jsonify, g
from backend.services.deal_service import (
    list_deals,
    get_pipeline_kanban,
    get_deal_by_id,
    create_deal,
    update_deal,
    update_deal_stage,
    delete_deal
)
from backend.utils.decorators import login_required, permission_required

deal_blueprint = Blueprint("deals", __name__, url_prefix="/api/deals")


@deal_blueprint.route("", methods=["GET"])
@login_required
@permission_required("deals.view")
def get_deals():
    """GET /api/deals: List and filter deals."""
    search = request.args.get("search")
    stage = request.args.get("stage")
    status = request.args.get("status")
    customer_id = request.args.get("customer_id", type=int)
    assigned_to = request.args.get("assigned_to", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 15, type=int)

    result = list_deals(
        search=search, stage=stage, status=status,
        customer_id=customer_id, assigned_to=assigned_to,
        page=page, per_page=per_page
    )
    return jsonify(result), 200


@deal_blueprint.route("/pipeline", methods=["GET"])
@login_required
@permission_required("deals.view")
def pipeline():
    """GET /api/deals/pipeline: Aggregate deals into 6 Kanban stages."""
    result = get_pipeline_kanban()
    return jsonify(result), 200


@deal_blueprint.route("", methods=["POST"])
@login_required
@permission_required("deals.create")
def create():
    """POST /api/deals: Create new deal opportunity."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    result, status_code = create_deal(data, user_id)
    return jsonify(result), status_code


@deal_blueprint.route("/<int:deal_id>", methods=["GET"])
@login_required
@permission_required("deals.view")
def get_one(deal_id):
    """GET /api/deals/<id>: Get deal details and activity history."""
    deal = get_deal_by_id(deal_id)
    if not deal:
        return jsonify({"success": False, "message": "Deal not found"}), 404
    return jsonify({"success": True, "deal": deal}), 200


@deal_blueprint.route("/<int:deal_id>", methods=["PUT"])
@login_required
@permission_required("deals.update")
def update(deal_id):
    """PUT /api/deals/<id>: Update deal parameters."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    result, status_code = update_deal(deal_id, data, user_id)
    return jsonify(result), status_code


@deal_blueprint.route("/<int:deal_id>/stage", methods=["PUT"])
@login_required
@permission_required("deals.update")
def update_stage(deal_id):
    """PUT /api/deals/<id>/stage: Transition deal to another stage."""
    data = request.get_json(silent=True) or {}
    new_stage = data.get("stage")
    user_id = g.current_user["id"]
    result, status_code = update_deal_stage(deal_id, new_stage, user_id)
    return jsonify(result), status_code


@deal_blueprint.route("/<int:deal_id>", methods=["DELETE"])
@login_required
@permission_required("deals.delete")
def delete(deal_id):
    """DELETE /api/deals/<id>: Remove deal."""
    user_id = g.current_user["id"]
    result, status_code = delete_deal(deal_id, user_id)
    return jsonify(result), status_code


@deal_blueprint.route("/bulk-action", methods=["POST"])
@login_required
@permission_required("deals.update")
def bulk_deals():
    """POST /api/deals/bulk-action - Execute batch operations on deals."""
    from backend.services.deal_service import bulk_action_deals
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    ids = payload.get("ids", [])
    value = payload.get("value")

    result, err = bulk_action_deals(action=action, ids=ids, value=value, user_id=g.current_user["id"])
    if err:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({"success": True, "message": "Bulk action completed", "result": result}), 200

