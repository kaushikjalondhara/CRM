"""
CRM User / Employee Routes
API endpoints for managing employees, assignable dropdowns, and user status.
"""

from flask import Blueprint, request, jsonify, g
from database.database import execute_query
from backend.utils.decorators import login_required, permission_required
from backend.services.user_service import (
    list_users,
    get_user,
    create_user,
    update_user,
    set_user_status,
    delete_user,
    get_user_profile,
    update_user_profile,
    change_user_password,
    upload_user_photo
)

user_blueprint = Blueprint("users", __name__, url_prefix="/api/users")


# -------------------------------------------------------------
# Current User Profile & Account Management
# -------------------------------------------------------------
@user_blueprint.route("/profile", methods=["GET"])
@login_required
def my_profile():
    """GET /api/users/profile - View currently authenticated user profile & login history."""
    uid = g.user.get("id") or g.current_user.get("id")
    profile, err = get_user_profile(uid)
    if err:
        return jsonify({"success": False, "message": err}), 404
    return jsonify({"success": True, "profile": profile}), 200


@user_blueprint.route("/profile", methods=["PUT"])
@login_required
def update_my_profile():
    """PUT /api/users/profile - Update personal profile info."""
    uid = g.user.get("id") or g.current_user.get("id")
    data = request.get_json(silent=True) or {}
    ok, err = update_user_profile(uid, data)
    if err or not ok:
        return jsonify({"success": False, "message": err or "Failed to update profile"}), 400
    profile, _ = get_user_profile(uid)
    return jsonify({"success": True, "message": "Profile updated successfully", "profile": profile}), 200


@user_blueprint.route("/profile/password", methods=["PUT"])
@login_required
def update_my_password():
    """PUT /api/users/profile/password - Change user password with old password verification."""
    uid = g.user.get("id") or g.current_user.get("id")
    data = request.get_json(silent=True) or {}
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")
    ok, err = change_user_password(uid, old_password, new_password)
    if err or not ok:
        return jsonify({"success": False, "message": err or "Failed to change password"}), 400
    return jsonify({"success": True, "message": "Password changed successfully"}), 200


@user_blueprint.route("/profile/photo", methods=["POST"])
@login_required
def update_my_photo():
    """POST /api/users/profile/photo - Upload and update profile photo."""
    uid = g.user.get("id") or g.current_user.get("id")
    file_obj = request.files.get("photo") or request.files.get("file")
    if not file_obj:
        return jsonify({"success": False, "message": "No photo file provided"}), 400
    photo_url, err = upload_user_photo(uid, file_obj)
    if err:
        return jsonify({"success": False, "message": err}), 400
    return jsonify({"success": True, "message": "Profile photo updated", "profile_image": photo_url}), 200




@user_blueprint.route("/assignable", methods=["GET"])
@login_required
def get_assignable_users():
    """
    GET /api/users/assignable
    Returns active employees to populate assignment dropdowns across CRM modules.
    """
    sql = """
        SELECT u.id, u.first_name, u.last_name, u.email, r.name as role
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.status = 'active'
        ORDER BY u.first_name ASC, u.last_name ASC
    """
    rows, err = execute_query(sql, fetch_all=True)
    if err:
        return jsonify({"success": False, "message": "Failed to fetch users"}), 500

    users = [{
        "id": r["id"],
        "name": f"{r['first_name']} {r['last_name']}".strip(),
        "first_name": r["first_name"],
        "last_name": r["last_name"],
        "email": r["email"],
        "role": r["role"]
    } for r in (rows or [])]

    return jsonify({"success": True, "users": users}), 200


@user_blueprint.route("", methods=["GET"])
@login_required
@permission_required("users.view")
def get_all_users():
    """
    GET /api/users
    List all employees/users with search and filtering.
    """
    search = request.args.get("search")
    role_id = request.args.get("role_id")
    role_id = int(role_id) if role_id and role_id.isdigit() else None
    status = request.args.get("status")
    page_raw = request.args.get("page", "1")

    per_page_raw = request.args.get("per_page", "20")
    page = int(page_raw) if page_raw and str(page_raw).isdigit() else 1
    per_page = int(per_page_raw) if per_page_raw and str(per_page_raw).isdigit() else 20
    page = max(1, page)
    per_page = min(100, max(1, per_page))


    data, err = list_users(search=search, role_id=role_id, status=status, page=page, per_page=per_page)
    if err:
        return jsonify({"success": False, "message": "Failed to fetch users"}), 500

    return jsonify({"success": True, "data": data}), 200


@user_blueprint.route("/<int:user_id>", methods=["GET"])
@login_required
@permission_required("users.view")
def get_single_user(user_id):
    """
    GET /api/users/<id>
    View user details.
    """
    user, err = get_user(user_id)
    if err:
        return jsonify({"success": False, "message": err}), 404
    return jsonify({"success": True, "user": user}), 200


@user_blueprint.route("", methods=["POST"])
@login_required
@permission_required("users.create")
def add_user():
    """
    POST /api/users
    Create a new employee account.
    """
    data = request.get_json() or {}
    current_uid = g.user["id"]
    user_id, err = create_user(data, current_user_id=current_uid)
    if err:
        return jsonify({"success": False, "message": err}), 400

    user, _ = get_user(user_id)
    return jsonify({"success": True, "message": "User created successfully", "user": user}), 201


@user_blueprint.route("/<int:user_id>", methods=["PUT"])
@login_required
@permission_required("users.update")
def edit_user(user_id):
    """
    PUT /api/users/<id>
    Update user profile, role, or password.
    """
    data = request.get_json() or {}
    current_uid = g.user["id"]
    ok, err = update_user(user_id, data, current_user_id=current_uid)
    if err:
        return jsonify({"success": False, "message": err}), 400

    user, _ = get_user(user_id)
    return jsonify({"success": True, "message": "User updated successfully", "user": user}), 200


@user_blueprint.route("/<int:user_id>/status", methods=["PUT"])
@login_required
@permission_required("users.update")
def toggle_status(user_id):
    """
    PUT /api/users/<id>/status
    Update user active / inactive status.
    """
    data = request.get_json() or {}
    status = data.get("status")
    current_uid = g.user["id"]
    ok, err = set_user_status(user_id, status, current_user_id=current_uid)
    if not ok:
        return jsonify({"success": False, "message": err or "Failed to update status"}), 400

    user, _ = get_user(user_id)
    return jsonify({"success": True, "message": f"User status set to {status}", "user": user}), 200


@user_blueprint.route("/<int:user_id>", methods=["DELETE"])
@login_required
@permission_required("users.delete")
def remove_user(user_id):
    """
    DELETE /api/users/<id>
    Deactivate/delete user.
    """
    current_uid = g.user["id"]
    ok, err = delete_user(user_id, current_user_id=current_uid)
    if not ok:
        return jsonify({"success": False, "message": err or "Failed to deactivate user"}), 400

    return jsonify({"success": True, "message": "User account deactivated successfully"}), 200
