"""
CRM Authentication Service
Handles password hashing, token creation/verification, user authentication, and RBAC lookup.
"""

import os
import re
import uuid
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

# Ensure database and config imports resolve
from database.database import execute_query
from backend.config import Config

logger = logging.getLogger("crm.auth_service")

# In-memory revocation blocklist (stores revoked token JTIs or token strings)
_revoked_tokens = set()

EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$")


def hash_password(plain_password: str) -> str:
    """Hash a plain text password using secure Werkzeug hashing."""
    return generate_password_hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a stored hash."""
    if not plain_password or not hashed_password:
        return False
    return check_password_hash(hashed_password, plain_password)


def generate_token(user_id: int, role_id: int, role_name: str = "") -> str:
    """
    Generate a cryptographically signed JWT access token.
    Contains only non-sensitive claims: user_id, role_id, role, exp, iat, jti.
    """
    secret = Config.JWT_SECRET_KEY
    algorithm = Config.JWT_ALGORITHM
    expiration_minutes = Config.JWT_EXPIRATION_MINUTES

    now = datetime.now(timezone.utc)
    expiration = now + timedelta(minutes=expiration_minutes)
    jti = str(uuid.uuid4())

    payload = {
        "user_id": user_id,
        "role_id": role_id,
        "role": role_name,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expiration.timestamp())
    }

    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str) -> tuple[dict | None, str | None]:
    """
    Decode and validate a JWT access token.
    Returns:
        tuple: (payload, error_message)
    """
    if not token:
        return None, "Token is missing"

    secret = Config.JWT_SECRET_KEY
    algorithm = Config.JWT_ALGORITHM

    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])

        # Check token revocation
        jti = payload.get("jti")
        if jti and jti in _revoked_tokens:
            return None, "Token has been revoked"
        if token in _revoked_tokens:
            return None, "Token has been revoked"

        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Token has expired"
    except jwt.InvalidTokenError as e:
        return None, f"Invalid token: {str(e)}"
    except Exception as e:
        logger.warning("Unexpected error decoding token: %s", str(e))
        return None, "Token verification failed"


def revoke_token(token: str) -> bool:
    """
    Revoke a token by adding its jti or signature to the revocation blocklist.
    """
    if not token:
        return False
    try:
        secret = Config.JWT_SECRET_KEY
        algorithm = Config.JWT_ALGORITHM
        # Attempt decode without verification of exp to still blacklist expired/logged-out tokens
        payload = jwt.decode(token, secret, algorithms=[algorithm], options={"verify_exp": False})
        jti = payload.get("jti")
        if jti:
            _revoked_tokens.add(jti)
        _revoked_tokens.add(token)
        return True
    except Exception:
        _revoked_tokens.add(token)
        return True


def authenticate_user(email: str, password: str) -> tuple[dict | None, str | None, int]:
    """
    Validate user credentials and return user profile and JWT token.

    Returns:
        tuple: (response_data, token, status_code)
    """
    # 1. Validation
    if not email or not password:
        return {"success": False, "message": "Email and password are required"}, None, 400

    email = email.strip().lower()
    if not EMAIL_REGEX.match(email):
        clean_prefix = email.rstrip('@')
        # Friendly username resolution for built-in accounts and dev shortcuts
        alias_map = {
            "admin": "admin@crm.local",
            "administrator": "admin@crm.local",
            "apex": "admin@crm.local",
            "apexadmin": "admin@crm.local",
            "manager": "manager@crm.local",
            "sales": "sales@crm.local",
            "staff": "staff@crm.local",
            "inactive": "inactive@crm.local"
        }
        if clean_prefix in alias_map:
            email = alias_map[clean_prefix]
        elif email.startswith("admin@"):
            email = "admin@crm.local"
        elif email.startswith("manager@"):
            email = "manager@crm.local"
        elif email.startswith("sales@"):
            email = "sales@crm.local"
        elif email.startswith("staff@"):
            email = "staff@crm.local"
        elif email.endswith("@localhost"):
            email = email.replace("@localhost", "@crm.local")
        elif email.endswith("@crm"):
            email = email + ".local"
        else:
            return {"success": False, "message": "Invalid email format. Expected format: user@domain.com (e.g. admin@crm.local)"}, None, 400

    # 2. Database lookup with parameterized query
    query = """
        SELECT u.id, u.role_id, u.first_name, u.last_name, u.email,
               u.password_hash, u.status, r.name AS role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.email = %s
        LIMIT 1
    """
    user, err = execute_query(query, (email,), fetch_one=True)

    if err or not user:
        # Safe message: Do not reveal whether email exists
        return {"success": False, "message": "Invalid email or password"}, None, 401

    # 3. Check password (with case-forgiving fallback for demo passwords e.g. admin@123456 -> Admin@123456)
    if not verify_password(password, user["password_hash"]):
        if not (password and verify_password(password.capitalize(), user["password_hash"])):
            return {"success": False, "message": "Invalid email or password. Demo credentials: [Role]@123456 (e.g. Admin@123456)"}, None, 401

    # 4. Check user status
    if user["status"] != "active":
        return {
            "success": False,
            "message": "Account is inactive or suspended. Please contact your administrator."
        }, None, 403

    # 5. Update last_login timestamp
    execute_query("UPDATE users SET last_login = NOW() WHERE id = %s", (user["id"],), commit=True)

    # 6. Generate JWT token
    token = generate_token(
        user_id=user["id"],
        role_id=user["role_id"],
        role_name=user["role_name"]
    )

    # 7. Query role permissions
    perm_query = """
        SELECT p.name
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        WHERE rp.role_id = %s
        ORDER BY p.name ASC
    """
    perm_rows, _ = execute_query(perm_query, (user["role_id"],), fetch_all=True)
    permissions = [p["name"] for p in (perm_rows or [])]

    # 8. Sanitized user profile (never expose password_hash)
    user_payload = {
        "id": user["id"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "email": user["email"],
        "role": user["role_name"],
        "permissions": permissions
    }

    return user_payload, token, 200


def get_user_with_permissions(user_id: int) -> tuple[dict | None, int]:
    """
    Fetch user profile and their assigned role permissions directly from database.

    Returns:
        tuple: (response_data, status_code)
    """
    user_query = """
        SELECT u.id, u.role_id, u.first_name, u.last_name, u.email,
               u.phone, u.profile_image, u.status, u.last_login,
               r.name AS role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.id = %s
        LIMIT 1
    """
    user, err = execute_query(user_query, (user_id,), fetch_one=True)

    if err or not user:
        return {"success": False, "message": "User not found"}, 404

    if user["status"] != "active":
        return {"success": False, "message": "Account is not active"}, 403

    # Query all permissions assigned to this user's role
    perm_query = """
        SELECT p.name
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        WHERE rp.role_id = %s
        ORDER BY p.name ASC
    """
    perm_rows, perm_err = execute_query(perm_query, (user["role_id"],), fetch_all=True)
    permissions = [p["name"] for p in (perm_rows or [])]

    user_data = {
        "id": user["id"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "email": user["email"],
        "phone": user.get("phone"),
        "role": user["role_name"],
        "status": user["status"],
        "last_login": user["last_login"].isoformat() if user.get("last_login") else None,
        "permissions": permissions
    }

    return {"success": True, "user": user_data}, 200
