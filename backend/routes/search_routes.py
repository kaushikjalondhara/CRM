"""
CRM Global Search Routes
Endpoint for querying across all CRM modules.
"""

from flask import Blueprint, request, jsonify, g
from backend.services.search_service import global_search
from backend.utils.decorators import login_required

search_blueprint = Blueprint("search", __name__, url_prefix="/api/search")


@search_blueprint.route("", methods=["GET"])
@login_required
def search_crm():
    """
    GET /api/search?q=<query>
    Performs global CRM search across modules with current user's permissions.
    """
    query = request.args.get("q", "").strip()
    limit = request.args.get("limit", 5, type=int)

    result = global_search(query=query, current_user=g.current_user, limit_per_entity=limit)
    return jsonify({
        "success": True,
        "data": result
    }), 200
