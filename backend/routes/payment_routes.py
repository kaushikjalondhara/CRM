"""
CRM Payment Routes
API endpoints for managing payment transactions.
"""

from flask import Blueprint, request, jsonify, g
from backend.utils.decorators import login_required, permission_required
from backend.services.payment_service import (
    list_payments,
    get_payment,
    create_payment,
    delete_payment
)

payment_blueprint = Blueprint("payments", __name__, url_prefix="/api/payments")


@payment_blueprint.route("", methods=["GET"])
@login_required
@permission_required("payments.view")
def get_all():
    """
    GET /api/payments
    List payments with search, filters (invoice_id, customer_id, method, date), and pagination.
    """
    search = request.args.get("search")
    invoice_id_raw = request.args.get("invoice_id")
    invoice_id = int(invoice_id_raw) if invoice_id_raw and str(invoice_id_raw).isdigit() else None

    customer_id_raw = request.args.get("customer_id")
    customer_id = int(customer_id_raw) if customer_id_raw and str(customer_id_raw).isdigit() else None

    method = request.args.get("payment_method")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    page_raw = request.args.get("page", "1")
    per_page_raw = request.args.get("per_page", "20")

    page = int(page_raw) if page_raw and str(page_raw).isdigit() else 1
    per_page = int(per_page_raw) if per_page_raw and str(per_page_raw).isdigit() else 20

    page = max(1, page)
    per_page = min(100, max(1, per_page))


    data, err = list_payments(
        search=search, invoice_id=invoice_id, customer_id=customer_id,
        payment_method=method, start_date=start_date, end_date=end_date,
        page=page, per_page=per_page
    )
    if err:
        return jsonify({"success": False, "message": "Failed to fetch payments"}), 500

    return jsonify({"success": True, "data": data}), 200


@payment_blueprint.route("/<int:payment_id>", methods=["GET"])
@login_required
@permission_required("payments.view")
def get_one(payment_id):
    """
    GET /api/payments/<id>
    Retrieve a single payment details.
    """
    pay, err = get_payment(payment_id)
    if err:
        return jsonify({"success": False, "message": err}), 404
    return jsonify({"success": True, "payment": pay}), 200


@payment_blueprint.route("", methods=["POST"])
@login_required
@permission_required("payments.create")
def add_payment():
    """
    POST /api/payments
    Record a payment against an invoice.
    """
    data = request.get_json() or {}
    user_id = g.user["id"]
    payment_id, err = create_payment(data, user_id=user_id)
    if err:
        return jsonify({"success": False, "message": err}), 400

    pay, _ = get_payment(payment_id)
    return jsonify({"success": True, "message": "Payment recorded successfully", "payment": pay}), 201


@payment_blueprint.route("/<int:payment_id>", methods=["DELETE"])
@login_required
@permission_required("payments.delete")
def remove_payment(payment_id):
    """
    DELETE /api/payments/<id>
    Void or delete a payment record.
    """
    user_id = g.user["id"]
    ok, err = delete_payment(payment_id, user_id=user_id)
    if not ok:
        return jsonify({"success": False, "message": err or "Failed to delete payment"}), 400

    return jsonify({"success": True, "message": "Payment voided and invoice balance restored successfully"}), 200
