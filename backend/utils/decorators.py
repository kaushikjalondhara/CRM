"""
CRM Authentication and Authorization Decorators
Provides @login_required, @permission_required, and @role_required for protecting API routes.
"""

from functools import wraps
from flask import request, jsonify, g
from backend.services.auth_service import decode_token, get_user_with_permissions


def extract_bearer_token():
    """Extract Bearer token from Authorization header or query parameter."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1], None

    # Fallback to query parameter for browser downloads / exports
    token_param = request.args.get("token")
    if token_param:
        return token_param.strip(), None

    return None, "Authorization header is missing"



def login_required(f):
    """
    Decorator requiring a valid JWT access token.
    Attaches user data and permissions to Flask request context `g.current_user`.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token, err = extract_bearer_token()
        if err:
            return jsonify({"success": False, "message": err}), 401

        payload, token_err = decode_token(token)
        if token_err:
            return jsonify({"success": False, "message": token_err}), 401

        user_id = payload.get("user_id")
        user_res, status_code = get_user_with_permissions(user_id)
        if status_code != 200 or not user_res.get("success"):
            return jsonify({
                "success": False,
                "message": user_res.get("message", "User account invalid or inaccessible")
            }), status_code

        # Attach authenticated user to request context
        g.current_user = user_res["user"]
        g.user = user_res["user"]
        g.token = token

        return f(*args, **kwargs)
    return decorated_function


def permission_required(permission_name: str):
    """
    Decorator requiring the user to hold a specific permission.
    Admins bypass individual permission checks.
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                return jsonify({"success": False, "message": "Authentication required"}), 401

            # Super admin has unconditional access
            if user.get("role") == "Admin":
                return f(*args, **kwargs)

            user_permissions = user.get("permissions", [])
            # Support both .update and .edit aliases seamlessly
            target_perms = [permission_name]
            if ".update" in permission_name:
                target_perms.append(permission_name.replace(".update", ".edit"))
            elif ".edit" in permission_name:
                target_perms.append(permission_name.replace(".edit", ".update"))

            if not any(p in user_permissions for p in target_perms):
                return jsonify({
                    "success": False,
                    "message": f"Access forbidden: requires '{permission_name}' permission"
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def role_required(*allowed_roles):
    """
    Decorator requiring the user to hold one of the specified roles.
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                return jsonify({"success": False, "message": "Authentication required"}), 401

            user_role = user.get("role")
            if user_role not in allowed_roles:
                return jsonify({
                    "success": False,
                    "message": f"Access forbidden: role '{user_role}' is not authorized. Allowed: {', '.join(allowed_roles)}"
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
