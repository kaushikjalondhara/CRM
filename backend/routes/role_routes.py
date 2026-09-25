"""
CRM Roles and Permissions Routes
API endpoints for viewing and managing system roles and role permission matrix.
Protected: Only Admins can modify permissions.
"""

from flask import Blueprint, request, jsonify, g
from database.database import execute_query, get_db_cursor
from backend.utils.decorators import login_required, role_required
from backend.services.activity_service import log_activity

role_blueprint = Blueprint("roles", __name__, url_prefix="/api")


@role_blueprint.route("/roles", methods=["GET"])
@login_required
def get_all_roles():
    """
    GET /api/roles
    List all system roles with count of active users and assigned permissions.
    """
    sql = """
        SELECT r.id, r.name, r.description, r.created_at,
               (SELECT COUNT(*) FROM users u WHERE u.role_id = r.id) as user_count,
               (SELECT COUNT(*) FROM role_permissions rp WHERE rp.role_id = r.id) as permission_count
        FROM roles r
        ORDER BY r.id ASC
    """
    rows, err = execute_query(sql, fetch_all=True)
    if err:
        return jsonify({"success": False, "message": "Failed to fetch roles"}), 500

    roles = [{
        "id": r["id"],
        "name": r["name"],
        "description": r["description"],
        "user_count": r["user_count"],
        "permission_count": r["permission_count"],
        "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None
    } for r in (rows or [])]

    return jsonify({"success": True, "roles": roles}), 200


@role_blueprint.route("/permissions", methods=["GET"])
@login_required
def get_all_permissions():
    """
    GET /api/permissions
    List all available permissions grouped by functional module.
    """
    sql = "SELECT id, name, description FROM permissions ORDER BY name ASC"
    rows, err = execute_query(sql, fetch_all=True)
    if err:
        return jsonify({"success": False, "message": "Failed to fetch permissions"}), 500

    permissions = []
    modules = {}
    for r in (rows or []):
        mod = r["name"].split(".")[0] if "." in r["name"] else "general"
        perm = {
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "module": mod
        }
        permissions.append(perm)
        modules.setdefault(mod, []).append(perm)

    return jsonify({
        "success": True,
        "permissions": permissions,
        "grouped_permissions": modules
    }), 200


@role_blueprint.route("/roles/<int:role_id>/permissions", methods=["GET"])
@login_required
def get_role_permissions(role_id):
    """
    GET /api/roles/<id>/permissions
    Get list of permission IDs and names assigned to a role.
    """
    role, _ = execute_query("SELECT id, name, description FROM roles WHERE id = %s", (role_id,), fetch_one=True)
    if not role:
        return jsonify({"success": False, "message": "Role not found"}), 404

    sql = """
        SELECT p.id, p.name, p.description
        FROM role_permissions rp
        JOIN permissions p ON rp.permission_id = p.id
        WHERE rp.role_id = %s
        ORDER BY p.name ASC
    """
    rows, err = execute_query(sql, (role_id,), fetch_all=True)
    if err:
        return jsonify({"success": False, "message": "Failed to fetch role permissions"}), 500

    perm_ids = [r["id"] for r in (rows or [])]
    perms = [{
        "id": r["id"],
        "name": r["name"],
        "description": r["description"]
    } for r in (rows or [])]

    return jsonify({
        "success": True,
        "role": {
            "id": role["id"],
            "name": role["name"],
            "description": role["description"]
        },
        "permission_ids": perm_ids,
        "permissions": perms
    }), 200


@role_blueprint.route("/roles/<int:role_id>/permissions", methods=["PUT"])
@login_required
@role_required("Admin")
def update_role_permissions(role_id):
    """
    PUT /api/roles/<id>/permissions
    Update the set of permissions assigned to a role (Admin only).
    """
    role, _ = execute_query("SELECT id, name FROM roles WHERE id = %s", (role_id,), fetch_one=True)
    if not role:
        return jsonify({"success": False, "message": "Role not found"}), 404

    data = request.get_json() or {}
    permission_ids = data.get("permission_ids", [])
    if not isinstance(permission_ids, list):
        return jsonify({"success": False, "message": "permission_ids must be an array of integers"}), 400

    # Ensure valid IDs
    clean_ids = []
    for pid in permission_ids:
        try:
            clean_ids.append(int(pid))
        except (ValueError, TypeError):
            pass

    # Safety: Cannot strip all permissions from Admin role
    if role["name"] == "Admin" and len(clean_ids) == 0:
        return jsonify({"success": False, "message": "Cannot revoke all permissions from the Admin role"}), 400

    try:
        with get_db_cursor(commit=True) as cursor:
            # Delete existing assignments
            cursor.execute("DELETE FROM role_permissions WHERE role_id = %s", (role_id,))

            if clean_ids:
                # Filter against valid permissions
                format_strings = ','.join(['%s'] * len(clean_ids))
                cursor.execute(f"SELECT id FROM permissions WHERE id IN ({format_strings})", tuple(clean_ids))
                valid_rows = cursor.fetchall()
                valid_ids = [r["id"] for r in valid_rows]

                insert_sql = "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)"
                for pid in valid_ids:
                    cursor.execute(insert_sql, (role_id, pid))
    except Exception as ex:
        return jsonify({"success": False, "message": f"Database transaction failed: {str(ex)}"}), 500

    user_id = g.current_user["id"]
    log_activity(user_id, "role", role_id, "permissions_updated", f"Updated permissions for role '{role['name']}' ({len(clean_ids)} permissions assigned)")

    return jsonify({
        "success": True,
        "message": f"Permissions updated successfully for role '{role['name']}'"
    }), 200
