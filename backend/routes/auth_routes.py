"""
CRM Authentication Routes
Provides API endpoints for user login, logout, and fetching current authenticated profile.
"""

from flask import Blueprint, request, jsonify, g
from backend.services.auth_service import (
    authenticate_user,
    revoke_token,
    get_user_with_permissions
)
from backend.utils.decorators import login_required, extract_bearer_token

auth_blueprint = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_blueprint.route("/login", methods=["POST"])
def login():
    """
    POST /api/auth/login
    Authenticate user credentials, update last_login, and return signed JWT token.
    """
    data = request.get_json(silent=True, force=True)
    if not data or not isinstance(data, dict):
        # Fallback to manual JSON parse if raw text body was sent
        try:
            raw_text = request.get_data(as_text=True)
            if raw_text:
                import json
                data = json.loads(raw_text)
        except Exception:
            pass

    if not data or not isinstance(data, dict):
        if request.form:
            data = request.form.to_dict()
        else:
            raw_body = request.get_data(as_text=True)
            print(f"[LOGIN FAIL 400] Not JSON. type={request.content_type}, body={repr(raw_body)}", flush=True)
            return jsonify({
                "success": False,
                "message": "Invalid JSON request body. Expected 'email' and 'password'."
            }), 400

    email = data.get("email")
    password = data.get("password")
    print(f"[LOGIN ATTEMPT] email={repr(email)}, has_pass={bool(password and str(password).strip())}", flush=True)

    user_payload, token, status_code = authenticate_user(email, password)
    print(f"[LOGIN RESULT] status={status_code}, resp={user_payload}", flush=True)

    if status_code != 200:
        return jsonify(user_payload), status_code

    return jsonify({
        "success": True,
        "message": "Login successful",
        "token": token,
        "user": user_payload
    }), 200


@auth_blueprint.route("/logout", methods=["POST"])
def logout():
    """
    POST /api/auth/logout
    Revoke current JWT access token on the server and confirm logout.
    """
    token, err = extract_bearer_token()
    if token:
        revoke_token(token)

    return jsonify({
        "success": True,
        "message": "Logged out successfully"
    }), 200


@auth_blueprint.route("/me", methods=["GET"])
@login_required
def me():
    """
    GET /api/auth/me
    Return full profile of the authenticated user, including role and database permissions.
    """
    # g.current_user is populated by @login_required with database permissions
    return jsonify({
        "success": True,
        "user": g.current_user
    }), 200


@auth_blueprint.route("/test-permission/<permission_name>", methods=["GET"])
@login_required
def test_permission(permission_name):
    """
    GET /api/auth/test-permission/<permission_name>
    Diagnostic helper to test backend permission checks without building CRUD modules.
    """
    user = g.current_user
    if user.get("role") == "Admin" or permission_name in user.get("permissions", []):
        return jsonify({
            "success": True,
            "message": f"Permission '{permission_name}' granted",
            "user": user["email"],
            "role": user["role"]
        }), 200
    return jsonify({
        "success": False,
        "message": f"Access forbidden: requires '{permission_name}' permission"
    }), 403
