"""
CRM Audit Log Routes
Endpoints for querying system audit history.
"""

from flask import Blueprint, request, jsonify
from backend.services.audit_service import list_audit_logs
from backend.utils.decorators import login_required, role_required

audit_blueprint = Blueprint("audit_logs", __name__, url_prefix="/api/audit-logs")


@audit_blueprint.route("", methods=["GET"])
@login_required
@role_required("Admin", "Manager")
def get_audit_trail():
    """
    GET /api/audit-logs
    Retrieves paginated immutable audit trail (Admin & Manager only).
    """
    search = request.args.get("search")
    entity = request.args.get("entity") or request.args.get("entity_type")
    action = request.args.get("action")
    user_id = request.args.get("user_id", type=int)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    page = request.args.get("page", 1, type=int) or 1
    per_page = request.args.get("per_page", 25, type=int) or 25

    result, err = list_audit_logs(
        search=search, entity=entity, action=action,
        user_id=user_id, start_date=start_date, end_date=end_date,
        page=page, per_page=per_page
    )

    if err:
        return jsonify({"success": False, "message": str(err)}), 400

    return jsonify({
        "success": True,
        "data": result
    }), 200
