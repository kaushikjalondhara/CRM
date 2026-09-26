"""
CRM Product / Service Routes
API endpoints for product catalog management.
"""

from flask import Blueprint, request, jsonify, g
from backend.utils.decorators import login_required, permission_required
from backend.services.product_service import (
    list_products,
    get_product,
    create_product,
    update_product,
    delete_product
)

product_blueprint = Blueprint("products", __name__, url_prefix="/api/products")


@product_blueprint.route("", methods=["GET"])
@login_required
@permission_required("products.view")
def get_all():
    """
    GET /api/products
    List products with search, category, status filters, and pagination.
    """
    search = request.args.get("search")
    category = request.args.get("category")
    status = request.args.get("status")
    page_raw = request.args.get("page", "1")

    per_page_raw = request.args.get("per_page", "20")
    page = int(page_raw) if page_raw and str(page_raw).isdigit() else 1
    per_page = int(per_page_raw) if per_page_raw and str(per_page_raw).isdigit() else 20
    page = max(1, page)
    per_page = min(100, max(1, per_page))


    data, err = list_products(search=search, category=category, status=status, page=page, per_page=per_page)
    if err:
        return jsonify({"success": False, "message": "Failed to fetch products"}), 500

    return jsonify({"success": True, "data": data}), 200


@product_blueprint.route("/<int:product_id>", methods=["GET"])
@login_required
@permission_required("products.view")
def get_one(product_id):
    """
    GET /api/products/<id>
    Retrieve a single product by ID.
    """
    prod, err = get_product(product_id)
    if err:
        return jsonify({"success": False, "message": err}), 404
    return jsonify({"success": True, "product": prod}), 200


@product_blueprint.route("", methods=["POST"])
@login_required
@permission_required("products.create")
def add_product():
    """
    POST /api/products
    Create a new product.
    """
    data = request.get_json() or {}
    user_id = g.user["id"]
    product_id, err = create_product(data, user_id=user_id)
    if err:
        return jsonify({"success": False, "message": err}), 400

    prod, _ = get_product(product_id)
    return jsonify({"success": True, "message": "Product created successfully", "product": prod}), 201


@product_blueprint.route("/<int:product_id>", methods=["PUT"])
@login_required
@permission_required("products.update")
def edit_product(product_id):
    """
    PUT /api/products/<id>
    Update product details.
    """
    data = request.get_json() or {}
    user_id = g.user["id"]
    ok, err = update_product(product_id, data, user_id=user_id)
    if err:
        return jsonify({"success": False, "message": err}), 400

    prod, _ = get_product(product_id)
    return jsonify({"success": True, "message": "Product updated successfully", "product": prod}), 200


@product_blueprint.route("/<int:product_id>", methods=["DELETE"])
@login_required
@permission_required("products.delete")
def remove_product(product_id):
    """
    DELETE /api/products/<id>
    Delete or archive a product.
    """
    user_id = g.user["id"]
    ok, msg = delete_product(product_id, user_id=user_id)
    if not ok:
        return jsonify({"success": False, "message": msg or "Failed to delete product"}), 400

    return jsonify({"success": True, "message": msg or "Product deleted successfully"}), 200


@product_blueprint.route("/bulk-action", methods=["POST"])
@login_required
@permission_required("products.update")
def bulk_products():
    """POST /api/products/bulk-action: Batch delete, status, or category update."""
    from backend.services.product_service import bulk_action_products
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    ids = payload.get("ids", [])
    value = payload.get("value")

    result, err = bulk_action_products(action=action, ids=ids, value=value, user_id=g.user["id"])
    if err:
        return jsonify({"success": False, "message": err}), 400

    return jsonify({"success": True, "message": "Bulk action completed", "result": result}), 200

