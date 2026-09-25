"""
CRM Bulk Import Routes
Endpoints for previewing and confirming batch CSV/Excel imports.
"""

from flask import Blueprint, request, jsonify, send_file, g
from backend.services.import_service import (
    preview_import,
    confirm_import,
    generate_sample_template
)
from backend.utils.decorators import login_required, permission_required

import_blueprint = Blueprint("import", __name__, url_prefix="/api/import")


@import_blueprint.route("/preview", methods=["POST"])
@login_required
def preview():
    """
    POST /api/import/preview
    Parses CSV/XLSX and returns validated preview + error diagnostic list.
    """
    file_obj = request.files.get("file")
    module = request.form.get("module", "customers").lower().strip()

    if not file_obj or not file_obj.filename:
        return jsonify({"success": False, "message": "No import file provided"}), 400

    result, err = preview_import(file_obj=file_obj, filename=file_obj.filename, module=module)
    if err:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({
        "success": True,
        "data": result
    }), 200


@import_blueprint.route("/confirm", methods=["POST"])
@login_required
def confirm():
    """
    POST /api/import/confirm
    Executes transactional database insert of confirmed rows.
    """
    data = request.get_json(silent=True) or {}
    module = data.get("module", "customers").lower().strip()
    rows = data.get("rows", [])
    filename = data.get("filename", "import_batch")

    result, err = confirm_import(
        module=module,
        rows_data=rows,
        user_id=g.current_user["id"],
        filename=filename
    )
    if err:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({
        "success": True,
        "message": f"Successfully imported {result['imported_count']} {module} records",
        "data": result
    }), 200


@import_blueprint.route("/template/<module>", methods=["GET"])
@login_required
def download_template(module):
    """
    GET /api/import/template/<module>?format=csv|xlsx
    Provides a downloadable sample template for bulk import.
    """
    fmt = request.args.get("format", "csv").lower().strip()
    buf, filename, mimetype, err = generate_sample_template(module, export_format=fmt)
    if err:
        return jsonify({"success": False, "message": err}), 400

    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype
    )
