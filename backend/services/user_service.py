"""
CRM User & Employee Management Service
Handles user CRUD, role assignments, password hashing, and user activation/deactivation.
Never leaks password hashes or raw secrets.
"""

import re
import logging
import os
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from database.database import execute_query, get_db_cursor
from backend.services.auth_service import hash_password, verify_password
from backend.services.activity_service import log_activity

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROFILE_UPLOAD_DIR = BASE_DIR / "uploads" / "profile_images"
PROFILE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


logger = logging.getLogger("crm.user_service")

EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$")
VALID_STATUSES = {"active", "inactive", "suspended"}


def list_users(search: str | None = None, role_id: int | None = None,
               status: str | None = None, page: int = 1, per_page: int = 20) -> tuple[dict | None, str | None]:
    """List users with role name, search, status filtering, and pagination."""
    where_clauses = []
    params: list = []

    if search:
        term = f"%{search.strip()}%"
        where_clauses.append("(u.first_name LIKE %s OR u.last_name LIKE %s OR u.email LIKE %s OR u.phone LIKE %s)")
        params.extend([term, term, term, term])

    if role_id:
        where_clauses.append("u.role_id = %s")
        params.append(role_id)

    if status and status in VALID_STATUSES:
        where_clauses.append("u.status = %s")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_sql = f"""
        SELECT COUNT(*) as total
        FROM users u
        JOIN roles r ON u.role_id = r.id
        {where_sql}
    """
    count_res, err = execute_query(count_sql, tuple(params), fetch_one=True)
    if err:
        return None, err
    total = count_res["total"] if count_res else 0

    offset = max(0, (page - 1) * per_page)
    fetch_sql = f"""
        SELECT u.id, u.role_id, u.first_name, u.last_name, u.email, u.phone,
               u.profile_image, u.status, u.last_login, u.created_at, u.updated_at,
               r.name as role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        {where_sql}
        ORDER BY u.id ASC
        LIMIT %s OFFSET %s
    """
    fetch_params = list(params) + [per_page, offset]
    rows, err = execute_query(fetch_sql, tuple(fetch_params), fetch_all=True)
    if err:
        return None, err

    users = []
    for r in (rows or []):
        users.append({
            "id": r["id"],
            "role_id": r["role_id"],
            "role": r["role_name"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "name": f"{r['first_name']} {r['last_name']}".strip(),
            "email": r["email"],
            "phone": r["phone"],
            "profile_image": r["profile_image"],
            "status": r["status"],
            "last_login": r["last_login"].strftime("%Y-%m-%d %H:%M:%S") if r["last_login"] else None,
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None
        })

    # Available roles
    roles_rows, _ = execute_query("SELECT id, name, description FROM roles ORDER BY id ASC", fetch_all=True)

    return {
        "users": users,
        "roles": roles_rows or [],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 1
    }, None


def get_user(user_id: int) -> tuple[dict | None, str | None]:
    """Retrieve a single user without password hash."""
    sql = """
        SELECT u.id, u.role_id, u.first_name, u.last_name, u.email, u.phone,
               u.profile_image, u.status, u.last_login, u.created_at, u.updated_at,
               r.name as role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.id = %s
    """
    r, err = execute_query(sql, (user_id,), fetch_one=True)
    if err:
        return None, err
    if not r:
        return None, "User not found"

    return {
        "id": r["id"],
        "role_id": r["role_id"],
        "role": r["role_name"],
        "first_name": r["first_name"],
        "last_name": r["last_name"],
        "name": f"{r['first_name']} {r['last_name']}".strip(),
        "email": r["email"],
        "phone": r["phone"],
        "profile_image": r["profile_image"],
        "status": r["status"],
        "last_login": r["last_login"].strftime("%Y-%m-%d %H:%M:%S") if r["last_login"] else None,
        "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None
    }, None


def create_user(data: dict, current_user_id: int | None = None) -> tuple[int | None, str | None]:
    """Create a new employee/user record with hashed password."""
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip() or None
    password = data.get("password", "")

    if not first_name:
        return None, "First name is required"
    if not last_name:
        return None, "Last name is required"
    if not email or not EMAIL_REGEX.match(email):
        return None, "A valid email address is required"
    if not password or len(password) < 6:
        return None, "Password must be at least 6 characters"

    role_id = data.get("role_id")
    try:
        role_id = int(role_id)
        role_chk, _ = execute_query("SELECT id FROM roles WHERE id = %s", (role_id,), fetch_one=True)
        if not role_chk:
            return None, "Invalid role selected"
    except (ValueError, TypeError):
        return None, "Valid role ID is required"

    status = data.get("status", "active")
    if status not in VALID_STATUSES:
        status = "active"

    # Check email duplicate
    dup, _ = execute_query("SELECT id FROM users WHERE email = %s", (email,), fetch_one=True)
    if dup:
        return None, f"Email '{email}' is already registered to another account"

    hashed_pw = hash_password(password)

    sql = """
        INSERT INTO users (role_id, first_name, last_name, email, phone, password_hash, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    """
    res, err = execute_query(sql, (role_id, first_name, last_name, email, phone, hashed_pw, status), commit=True)
    if err:
        return None, err
    user_id = res.get("last_id") if isinstance(res, dict) else res

    log_activity(current_user_id, "user", user_id, "created", f"Created user account for {first_name} {last_name} ({email})")
    return user_id, None


def update_user(user_id: int, data: dict, current_user_id: int | None = None) -> tuple[bool, str | None]:
    """Update user information, role, or password."""
    existing, err = get_user(user_id)
    if err or not existing:
        return False, "User not found"

    first_name = (data.get("first_name") or existing["first_name"]).strip()
    last_name = (data.get("last_name") or existing["last_name"]).strip()
    email = (data.get("email") or existing["email"]).strip().lower()
    phone = (data.get("phone") or existing["phone"] or "").strip() or None
    status = data.get("status", existing["status"])
    if status not in VALID_STATUSES:
        status = existing["status"]

    if not EMAIL_REGEX.match(email):
        return False, "Invalid email address format"

    if email != existing["email"]:
        dup, _ = execute_query("SELECT id FROM users WHERE email = %s AND id != %s", (email, user_id), fetch_one=True)
        if dup:
            return False, f"Email '{email}' is already registered to another user"

    role_id = data.get("role_id", existing["role_id"])
    try:
        role_id = int(role_id)
    except (ValueError, TypeError):
        role_id = existing["role_id"]

    new_password = data.get("password")
    if new_password and len(str(new_password).strip()) > 0:
        if len(str(new_password).strip()) < 6:
            return False, "New password must be at least 6 characters"
        hashed = hash_password(str(new_password).strip())
        sql = """
            UPDATE users
            SET first_name = %s, last_name = %s, email = %s, phone = %s,
                role_id = %s, status = %s, password_hash = %s, updated_at = NOW()
            WHERE id = %s
        """
        params = (first_name, last_name, email, phone, role_id, status, hashed, user_id)
    else:
        sql = """
            UPDATE users
            SET first_name = %s, last_name = %s, email = %s, phone = %s,
                role_id = %s, status = %s, updated_at = NOW()
            WHERE id = %s
        """
        params = (first_name, last_name, email, phone, role_id, status, user_id)

    _, err = execute_query(sql, params, commit=True)
    if err:
        return False, err

    log_activity(current_user_id, "user", user_id, "updated", f"Updated profile for user {first_name} {last_name}")
    return True, None


def set_user_status(user_id: int, status: str, current_user_id: int | None = None) -> tuple[bool, str | None]:
    """Toggle user active / inactive status."""
    if status not in VALID_STATUSES:
        return False, f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"

    if current_user_id and int(user_id) == int(current_user_id):
        return False, "You cannot deactivate or suspend your own account"

    sql = "UPDATE users SET status = %s, updated_at = NOW() WHERE id = %s"
    _, err = execute_query(sql, (status, user_id), commit=True)
    if err:
        return False, err

    log_activity(current_user_id, "user", user_id, "status_changed", f"Changed status of user #{user_id} to {status}")
    return True, None


def delete_user(user_id: int, current_user_id: int | None = None) -> tuple[bool, str | None]:
    """Safely deactivate or delete user."""
    if current_user_id and int(user_id) == int(current_user_id):
        return False, "You cannot delete your own account"

    existing, err = get_user(user_id)
    if err or not existing:
        return False, "User not found"

    # Soft deactivate rather than breaking foreign keys if assigned items exist
    sql = "UPDATE users SET status = 'inactive', updated_at = NOW() WHERE id = %s"
    _, err = execute_query(sql, (user_id,), commit=True)
    if err:
        return False, err

    log_activity(current_user_id, "user", user_id, "deactivated", f"Deactivated user {existing['name']}")
    return True, None


def get_user_profile(user_id: int) -> tuple[dict | None, str | None]:
    """Retrieve full user profile with permissions and recent login history."""
    sql = """
        SELECT u.id, u.role_id, u.first_name, u.last_name, u.email, u.phone,
               u.profile_image, u.status, u.last_login, u.created_at, u.updated_at,
               r.name as role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.id = %s
    """
    u, err = execute_query(sql, (user_id,), fetch_one=True)
    if err:
        return None, err
    if not u:
        return None, "User not found"

    # Fetch user's permissions
    perm_sql = """
        SELECT DISTINCT p.name
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        WHERE rp.role_id = %s
        ORDER BY p.name ASC
    """
    perm_rows, _ = execute_query(perm_sql, (u["role_id"],), fetch_all=True)
    permissions = [r["name"] for r in (perm_rows or [])]

    # Fetch recent login history (last 10)
    lh_sql = """
        SELECT id, ip_address, user_agent, status, failure_reason, created_at
        FROM login_history
        WHERE user_id = %s OR email = %s
        ORDER BY id DESC
        LIMIT 10
    """
    lh_rows, _ = execute_query(lh_sql, (user_id, u["email"]), fetch_all=True)
    login_history = []
    for row in (lh_rows or []):
        login_history.append({
            "id": row["id"],
            "ip_address": row["ip_address"],
            "user_agent": row["user_agent"],
            "status": row["status"],
            "failure_reason": row["failure_reason"],
            "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("created_at") else None
        })

    profile = {
        "id": u["id"],
        "role_id": u["role_id"],
        "role": u["role_name"],
        "first_name": u["first_name"],
        "last_name": u["last_name"],
        "name": f"{u['first_name']} {u['last_name']}".strip(),
        "email": u["email"],
        "phone": u["phone"] or "",
        "profile_image": u["profile_image"] or "",
        "status": u["status"],
        "last_login": u["last_login"].strftime("%Y-%m-%d %H:%M:%S") if u["last_login"] else None,
        "created_at": u["created_at"].strftime("%Y-%m-%d %H:%M:%S") if u["created_at"] else None,
        "permissions": permissions,
        "login_history": login_history
    }
    return profile, None


def update_user_profile(user_id: int, data: dict) -> tuple[bool, str | None]:
    """Update profile information (first_name, last_name, email, phone) for logged-in user."""
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip() or None

    if not first_name:
        return False, "First name is required"
    if not last_name:
        return False, "Last name is required"
    if not email or not EMAIL_REGEX.match(email):
        return False, "A valid email address is required"

    # Check email duplicate across other users
    dup, _ = execute_query("SELECT id FROM users WHERE email = %s AND id != %s", (email, user_id), fetch_one=True)
    if dup:
        return False, f"Email '{email}' is already in use by another account"

    sql = """
        UPDATE users
        SET first_name = %s, last_name = %s, email = %s, phone = %s, updated_at = NOW()
        WHERE id = %s
    """
    _, err = execute_query(sql, (first_name, last_name, email, phone, user_id), commit=True)
    if err:
        return False, err

    log_activity(user_id, "user", user_id, "profile_update", f"User {first_name} {last_name} updated their profile")
    return True, None


def change_user_password(user_id: int, old_password: str, new_password: str) -> tuple[bool, str | None]:
    """Verify old password and set a new password."""
    if not old_password:
        return False, "Current password is required"
    if not new_password or len(str(new_password).strip()) < 6:
        return False, "New password must be at least 6 characters"

    u, err = execute_query("SELECT password_hash FROM users WHERE id = %s", (user_id,), fetch_one=True)
    if err or not u:
        return False, "User not found"

    if not verify_password(old_password, u["password_hash"]):
        return False, "Current password is incorrect"

    new_hash = hash_password(str(new_password).strip())
    sql = "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s"
    _, err = execute_query(sql, (new_hash, user_id), commit=True)
    if err:
        return False, err

    log_activity(user_id, "user", user_id, "password_change", "User changed their password")
    return True, None


def upload_user_photo(user_id: int, file_obj) -> tuple[str | None, str | None]:
    """Upload and set user profile photo."""
    if not file_obj or not file_obj.filename:
        return None, "No file provided"

    filename = secure_filename(file_obj.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed_exts = {"jpg", "jpeg", "png", "webp", "gif"}
    if ext not in allowed_exts:
        return None, f"Invalid image format. Allowed: {', '.join(allowed_exts)}"

    unique_filename = f"avatar_{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
    dest_path = PROFILE_UPLOAD_DIR / unique_filename
    file_obj.save(str(dest_path))

    photo_url = f"/uploads/profile_images/{unique_filename}"
    sql = "UPDATE users SET profile_image = %s, updated_at = NOW() WHERE id = %s"
    _, err = execute_query(sql, (photo_url, user_id), commit=True)
    if err:
        return None, err

    log_activity(user_id, "user", user_id, "photo_update", "Updated profile picture")
    return photo_url, None

