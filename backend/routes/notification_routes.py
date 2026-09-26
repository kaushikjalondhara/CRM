"""
CRM Notification Routes
API endpoints for user notifications.
"""

from flask import Blueprint, request, jsonify, g
from backend.utils.decorators import login_required
from backend.services.notification_service import (
    list_notifications,
    get_unread_count,
    mark_as_read,
    mark_all_as_read,
    delete_notification
)

notification_blueprint = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notification_blueprint.route("", methods=["GET"])
@login_required
def get_notifications():
    """
    GET /api/notifications
    List notifications for current user with optional query params:
    is_read (0 or 1), type, page, per_page
    """
    user_id = g.user["id"]
    is_read_param = request.args.get("is_read")
    is_read = int(is_read_param) if is_read_param in ("0", "1") else None
    notif_type = request.args.get("type")
    page_raw = request.args.get("page", "1")

    per_page_raw = request.args.get("per_page", "20")
    page = int(page_raw) if page_raw and str(page_raw).isdigit() else 1
    per_page = int(per_page_raw) if per_page_raw and str(per_page_raw).isdigit() else 20
    page = max(1, page)
    per_page = min(100, max(1, per_page))


    data, err = list_notifications(user_id=user_id, is_read=is_read, notif_type=notif_type, page=page, per_page=per_page)
    if err:
        return jsonify({"success": False, "message": "Failed to fetch notifications"}), 500

    return jsonify({"success": True, "data": data}), 200


@notification_blueprint.route("/unread-count", methods=["GET"])
@login_required
def get_count():
    """
    GET /api/notifications/unread-count
    Returns unread count for navbar badge.
    """
    user_id = g.user["id"]
    count = get_unread_count(user_id)
    return jsonify({"success": True, "unread_count": count}), 200


@notification_blueprint.route("/<int:notif_id>/read", methods=["PUT"])
@login_required
def mark_read(notif_id):
    """
    PUT /api/notifications/<id>/read
    Mark notification as read.
    """
    user_id = g.user["id"]
    ok, err = mark_as_read(notif_id, user_id)
    if err:
        return jsonify({"success": False, "message": "Failed to update notification"}), 500
    return jsonify({"success": True, "message": "Notification marked as read"}), 200


@notification_blueprint.route("/read-all", methods=["PUT"])
@login_required
def read_all():
    """
    PUT /api/notifications/read-all
    Mark all notifications as read for current user.
    """
    user_id = g.user["id"]
    _, err = mark_all_as_read(user_id)
    if err:
        return jsonify({"success": False, "message": "Failed to mark all as read"}), 500
    return jsonify({"success": True, "message": "All notifications marked as read"}), 200


@notification_blueprint.route("/<int:notif_id>", methods=["DELETE"])
@login_required
def delete_notif(notif_id):
    """
    DELETE /api/notifications/<id>
    Delete notification.
    """
    user_id = g.user["id"]
    ok, err = delete_notification(notif_id, user_id)
    if err:
        return jsonify({"success": False, "message": "Failed to delete notification"}), 500
    return jsonify({"success": True, "message": "Notification deleted"}), 200
