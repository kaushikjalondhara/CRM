"""
CRM Settings Routes
API endpoints for viewing and updating system settings.
"""

from flask import Blueprint, request, jsonify, g
from backend.utils.decorators import login_required, permission_required
from backend.services.settings_service import get_all_settings, update_settings

settings_blueprint = Blueprint("settings", __name__, url_prefix="/api/settings")


@settings_blueprint.route("", methods=["GET"])
@login_required
@permission_required("settings.view")
def get_settings():
    """
    GET /api/settings
    Retrieve system configuration settings.
    """
    settings = get_all_settings()
    return jsonify({"success": True, "settings": settings}), 200


@settings_blueprint.route("", methods=["PUT"])
@login_required
@permission_required("settings.update")
def save_settings():
    """
    PUT /api/settings
    Update system configuration settings.
    """
    data = request.get_json() or {}
    user_id = g.current_user["id"]
    ok, err = update_settings(data, user_id=user_id)
    if not ok:
        return jsonify({"success": False, "message": err or "Failed to update settings"}), 400

    settings = get_all_settings()
    return jsonify({"success": True, "message": "Settings updated successfully", "settings": settings}), 200
