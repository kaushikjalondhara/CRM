"""
CRM Database Backup Routes
Administrative endpoints for generating and downloading database backups.
"""

from flask import Blueprint, request, jsonify, send_file, g
from backend.services.backup_service import (
    create_database_backup,
    list_backups,
    get_backup,
    restore_database_backup,
    BACKUPS_FOLDER
)
from backend.utils.decorators import login_required, role_required

backup_blueprint = Blueprint("backup", __name__, url_prefix="/api/backup")


@backup_blueprint.route("/create", methods=["POST"])
@login_required
@role_required("Admin")
def trigger_backup():
    """POST /api/backup/create - Generate new database backup (Admin only)."""
    user_id = g.current_user["id"]
    backup_meta, err = create_database_backup(user_id=user_id)
    if err:
        return jsonify({"success": False, "message": err}), 500

    return jsonify({
        "success": True,
        "message": "Database backup completed successfully",
        "backup": backup_meta
    }), 201


@backup_blueprint.route("/list", methods=["GET"])
@login_required
@role_required("Admin")
def get_backup_history():
    """GET /api/backup/list - View backup history (Admin only)."""
    backups = list_backups()
    return jsonify({
        "success": True,
        "backups": backups,
        "count": len(backups)
    }), 200


@backup_blueprint.route("/<identifier>/download", methods=["GET"])
@login_required
@role_required("Admin")
def download_backup_file(identifier):
    """GET /api/backup/<identifier>/download - Download backup SQL file (Admin only)."""
    rec, err = get_backup(identifier)
    if err or not rec:
        return jsonify({"success": False, "message": err or "Backup not found"}), 404

    file_path = BACKUPS_FOLDER / rec["file_name"]
    if not file_path.exists():
        return jsonify({"success": False, "message": "File not found on storage"}), 404

    return send_file(
        str(file_path),
        as_attachment=True,
        download_name=rec["file_name"],
        mimetype="text/plain"
    )


@backup_blueprint.route("/<int:backup_id>/restore", methods=["POST"])
@login_required
@role_required("Admin")
def restore_backup(backup_id):
    """POST /api/backup/<id>/restore - Protected database restore."""
    data = request.get_json(silent=True) or {}
    code = data.get("confirmation_code", "")
    user_id = g.current_user["id"]

    ok, err = restore_database_backup(backup_id, user_id=user_id, confirmation_code=code)
    if not ok:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({
        "success": True,
        "message": "Database successfully restored from backup"
    }), 200
