"""
CRM Invoice Routes
API endpoints for managing invoices and billing records.
"""

from flask import Blueprint, request, jsonify, g
from backend.utils.decorators import login_required, permission_required
from backend.services.invoice_service import (
    list_invoices,
    get_invoice,
    create_invoice,
    update_invoice,
    delete_invoice
)

invoice_blueprint = Blueprint("invoices", __name__, url_prefix="/api/invoices")


@invoice_blueprint.route("", methods=["GET"])
@login_required
@permission_required("invoices.view")
def get_all():
    """
    GET /api/invoices
    List invoices with search, status, customer, date filters, and pagination.
    """
    search = request.args.get("search")
    status = request.args.get("status")
    customer_id = request.args.get("customer_id")
    customer_id = int(customer_id) if customer_id and customer_id.isdigit() else None
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 20))))

    data, err = list_invoices(
        search=search, status=status, customer_id=customer_id,
        start_date=start_date, end_date=end_date, page=page, per_page=per_page
    )
    if err:
        return jsonify({"success": False, "message": "Failed to fetch invoices"}), 500

    return jsonify({"success": True, "data": data}), 200


@invoice_blueprint.route("/<int:invoice_id>", methods=["GET"])
@login_required
@permission_required("invoices.view")
def get_one(invoice_id):
    """
    GET /api/invoices/<id>
    Retrieve a single invoice with customer information, line items, and payment history.
    """
    inv, err = get_invoice(invoice_id)
    if err:
        return jsonify({"success": False, "message": err}), 404
    return jsonify({"success": True, "invoice": inv}), 200


@invoice_blueprint.route("", methods=["POST"])
@login_required
@permission_required("invoices.create")
def add_invoice():
    """
    POST /api/invoices
    Create a new invoice with line items.
    """
    data = request.get_json() or {}
    user_id = g.user["id"]
    invoice_id, err = create_invoice(data, user_id=user_id)
    if err:
        return jsonify({"success": False, "message": err}), 400

    inv, _ = get_invoice(invoice_id)
    return jsonify({"success": True, "message": "Invoice created successfully", "invoice": inv}), 201


@invoice_blueprint.route("/<int:invoice_id>", methods=["PUT"])
@login_required
@permission_required("invoices.update")
def edit_invoice(invoice_id):
    """
    PUT /api/invoices/<id>
    Update invoice details and line items.
    """
    data = request.get_json() or {}
    user_id = g.user["id"]
    ok, err = update_invoice(invoice_id, data, user_id=user_id)
    if err:
        return jsonify({"success": False, "message": err}), 400

    inv, _ = get_invoice(invoice_id)
    return jsonify({"success": True, "message": "Invoice updated successfully", "invoice": inv}), 200


@invoice_blueprint.route("/<int:invoice_id>", methods=["DELETE"])
@login_required
@permission_required("invoices.delete")
def remove_invoice(invoice_id):
    """
    DELETE /api/invoices/<id>
    Delete an invoice.
    """
    user_id = g.user["id"]
    ok, err = delete_invoice(invoice_id, user_id=user_id)
    if not ok:
        return jsonify({"success": False, "message": err or "Failed to delete invoice"}), 400

    return jsonify({"success": True, "message": "Invoice deleted successfully"}), 200


@invoice_blueprint.route("/bulk-action", methods=["POST"])
@login_required
@permission_required("invoices.update")
def bulk_invoices():
    """POST /api/invoices/bulk-action: Batch delete or status change."""
    from backend.services.invoice_service import bulk_action_invoices
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    ids = payload.get("ids", [])
    value = payload.get("value")

    result, err = bulk_action_invoices(action=action, ids=ids, value=value, user_id=g.user["id"])
    if err:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({"success": True, "message": "Bulk action completed", "result": result}), 200

