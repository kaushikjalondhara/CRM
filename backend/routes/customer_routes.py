"""
CRM Customer Routes
Endpoints for Customer management, notes, documents, and 360-degree profile.
"""

import os
from pathlib import Path
from flask import Blueprint, request, jsonify, g, send_file
from backend.services.customer_service import (
    list_customers,
    get_customer_by_id,
    get_customer_details,
    create_customer,
    update_customer,
    delete_customer,
    list_customer_notes,
    add_customer_note,
    update_customer_note,
    delete_customer_note,
    list_customer_documents,
    upload_customer_document,
    delete_customer_document
)
from backend.utils.decorators import login_required, permission_required
from backend.config import Config
from database.database import execute_query

customer_blueprint = Blueprint("customers", __name__, url_prefix="/api/customers")


@customer_blueprint.route("", methods=["GET"])
@login_required
@permission_required("customers.view")
def get_customers():
    """GET /api/customers: List, search, filter, and paginate customers."""
    search = request.args.get("search")
    status = request.args.get("status")
    assigned_to = request.args.get("assigned_to", type=int)
    sort_by = request.args.get("sort_by", "created_at")
    order = request.args.get("order", "DESC")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    result = list_customers(
        search=search, status=status, assigned_to=assigned_to,
        sort_by=sort_by, order=order, page=page, per_page=per_page
    )
    return jsonify(result), 200


@customer_blueprint.route("", methods=["POST"])
@login_required
@permission_required("customers.create")
def create():
    """POST /api/customers: Create a new customer."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    result, status_code = create_customer(data, user_id)
    return jsonify(result), status_code


@customer_blueprint.route("/<int:customer_id>", methods=["GET"])
@customer_blueprint.route("/<int:customer_id>/details", methods=["GET"])
@login_required
@permission_required("customers.view")
def get_one(customer_id):
    """GET /api/customers/<id>: Get customer profile or comprehensive 360 details."""
    is_details_route = request.path.rstrip("/").endswith("/details")
    include_details = is_details_route or (request.args.get("details", "0") in ("1", "true", "yes"))

    if include_details:
        data = get_customer_details(customer_id)
        if not data:
            return jsonify({"success": False, "message": "Customer not found"}), 404
        return jsonify({"success": True, **data}), 200

    customer = get_customer_by_id(customer_id)
    if not customer:
        return jsonify({"success": False, "message": "Customer not found"}), 404
    return jsonify({"success": True, "customer": customer}), 200


@customer_blueprint.route("/<int:customer_id>", methods=["PUT"])
@login_required
@permission_required("customers.update")
def update(customer_id):
    """PUT /api/customers/<id>: Update customer information."""
    data = request.get_json(silent=True) or {}
    user_id = g.current_user["id"]
    result, status_code = update_customer(customer_id, data, user_id)
    return jsonify(result), status_code


@customer_blueprint.route("/<int:customer_id>", methods=["DELETE"])
@login_required
@permission_required("customers.delete")
def delete(customer_id):
    """DELETE /api/customers/<id>: Delete customer with cascade safety checks."""
    user_id = g.current_user["id"]
    result, status_code = delete_customer(customer_id, user_id)
    return jsonify(result), status_code


# -------------------------------------------------------------
# Notes Sub-endpoints
# -------------------------------------------------------------
@customer_blueprint.route("/<int:customer_id>/notes", methods=["GET"])
@login_required
@permission_required("customers.view")
def get_notes(customer_id):
    notes = list_customer_notes(customer_id)
    return jsonify({"success": True, "notes": notes}), 200


@customer_blueprint.route("/<int:customer_id>/notes", methods=["POST"])
@login_required
@permission_required("customers.update")
def add_note(customer_id):
    data = request.get_json(silent=True) or {}
    note_text = data.get("note", "")
    user_id = g.current_user["id"]
    result, status_code = add_customer_note(customer_id, user_id, note_text)
    return jsonify(result), status_code


@customer_blueprint.route("/notes/<int:note_id>", methods=["PUT"])
@login_required
@permission_required("customers.update")
def update_note(note_id):
    data = request.get_json(silent=True) or {}
    note_text = data.get("note", "")
    user_id = g.current_user["id"]
    result, status_code = update_customer_note(note_id, user_id, note_text)
    return jsonify(result), status_code


@customer_blueprint.route("/notes/<int:note_id>", methods=["DELETE"])
@login_required
@permission_required("customers.update")
def delete_note(note_id):
    user_id = g.current_user["id"]
    result, status_code = delete_customer_note(note_id, user_id)
    return jsonify(result), status_code


# -------------------------------------------------------------
# Documents Sub-endpoints
# -------------------------------------------------------------
@customer_blueprint.route("/<int:customer_id>/documents", methods=["GET"])
@login_required
@permission_required("customers.view")
def get_documents(customer_id):
    docs = list_customer_documents(customer_id)
    return jsonify({"success": True, "documents": docs}), 200


@customer_blueprint.route("/<int:customer_id>/documents", methods=["POST"])
@login_required
@permission_required("customers.update")
def upload_doc(customer_id):
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"}), 400
    file_obj = request.files["file"]
    user_id = g.current_user["id"]
    result, status_code = upload_customer_document(customer_id, user_id, file_obj)
    return jsonify(result), status_code


@customer_blueprint.route("/documents/<int:doc_id>", methods=["DELETE"])
@login_required
@permission_required("customers.update")
def delete_doc(doc_id):
    user_id = g.current_user["id"]
    result, status_code = delete_customer_document(doc_id, user_id)
    return jsonify(result), status_code


@customer_blueprint.route("/documents/<int:doc_id>/download", methods=["GET"])
@login_required
@permission_required("customers.view")
def download_doc(doc_id):
    doc, _ = execute_query("SELECT file_path, file_name FROM customer_documents WHERE id = %s", (doc_id,), fetch_one=True)
    if not doc or not doc.get("file_path"):
        return jsonify({"success": False, "message": "Document record not found"}), 404

    file_path = doc["file_path"]
    if not os.path.exists(file_path):
        return jsonify({"success": False, "message": "File not found on server storage"}), 404

    return send_file(file_path, as_attachment=True, download_name=doc["file_name"])


@customer_blueprint.route("/<int:customer_id>/360", methods=["GET"])
@login_required
@permission_required("customers.view")
def customer_360(customer_id):
    """GET /api/customers/<id>/360 - Unified comprehensive customer profile."""
    from backend.services.customer_service import get_customer_360
    data, err = get_customer_360(customer_id)
    if err:
        return jsonify({"success": False, "message": err}), 404
    return jsonify({"success": True, "data": data}), 200


@customer_blueprint.route("/bulk-action", methods=["POST"])
@login_required
@permission_required("customers.update")
def bulk_customers():
    """POST /api/customers/bulk-action - Execute batch operations."""
    from backend.services.customer_service import bulk_action_customers
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    ids = payload.get("ids", [])
    value = payload.get("value")

    result, err = bulk_action_customers(action=action, ids=ids, value=value, user_id=g.current_user["id"])
    if err:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({"success": True, "message": "Bulk action completed", "result": result}), 200

