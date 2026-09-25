"""
CRM Product / Service Catalog Service
Provides CRUD, search, filter, and validation logic for products and services.
"""

import random
import logging
from database.database import execute_query
from backend.services.activity_service import log_activity

logger = logging.getLogger("crm.product_service")

VALID_STATUSES = {"active", "inactive", "out_of_stock"}


def _generate_product_code() -> str:
    """Generate a unique product code like PROD-12345."""
    for _ in range(10):
        code = f"PROD-{random.randint(10000, 99999)}"
        existing, _ = execute_query("SELECT id FROM products WHERE product_code = %s", (code,), fetch_one=True)
        if not existing:
            return code
    return f"PROD-{random.randint(100000, 999999)}"


def validate_product_data(data: dict, is_update: bool = False) -> tuple[dict | None, str | None]:
    """Validate and sanitize product fields."""
    name = data.get("name")
    if not is_update or "name" in data:
        if not name or not str(name).strip():
            return None, "Product name is required"

    price = data.get("price", 0.0)
    try:
        price = float(price)
        if price < 0:
            return None, "Price must be greater than or equal to 0"
    except (ValueError, TypeError):
        return None, "Invalid price value"

    tax = data.get("tax_percentage", 0.0)
    try:
        tax = float(tax)
        if tax < 0 or tax > 100:
            return None, "Tax percentage must be between 0 and 100"
    except (ValueError, TypeError):
        return None, "Invalid tax percentage value"

    discount = data.get("discount_percentage", 0.0)
    try:
        discount = float(discount)
        if discount < 0 or discount > 100:
            return None, "Discount percentage must be between 0 and 100"
    except (ValueError, TypeError):
        return None, "Invalid discount percentage value"

    stock = data.get("stock", 0)
    try:
        stock = int(stock)
        if stock < 0:
            return None, "Stock must be greater than or equal to 0"
    except (ValueError, TypeError):
        return None, "Invalid stock value"

    status = data.get("status", "active")
    if status not in VALID_STATUSES:
        status = "active" if stock > 0 else "out_of_stock"

    return {
        "name": str(name).strip() if name else "",
        "price": price,
        "tax_percentage": tax,
        "discount_percentage": discount,
        "stock": stock,
        "status": status,
        "category": (data.get("category") or "").strip() or None,
        "description": (data.get("description") or "").strip() or None,
        "product_code": (data.get("product_code") or "").strip() or None
    }, None


def list_products(search: str | None = None, category: str | None = None,
                  status: str | None = None, page: int = 1, per_page: int = 20) -> tuple[dict | None, str | None]:
    """List products with search and filtering."""
    where_clauses = []
    params: list = []

    if search:
        term = f"%{search.strip()}%"
        where_clauses.append("(name LIKE %s OR product_code LIKE %s OR category LIKE %s OR description LIKE %s)")
        params.extend([term, term, term, term])

    if category:
        where_clauses.append("category = %s")
        params.append(category.strip())

    if status and status in VALID_STATUSES:
        where_clauses.append("status = %s")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_sql = f"SELECT COUNT(*) as total FROM products {where_sql}"
    count_res, err = execute_query(count_sql, tuple(params), fetch_one=True)
    if err:
        return None, err
    total = count_res["total"] if count_res else 0

    offset = max(0, (page - 1) * per_page)
    fetch_sql = f"""
        SELECT id, product_code, name, category, description, price,
               tax_percentage, discount_percentage, stock, status,
               created_at, updated_at
        FROM products
        {where_sql}
        ORDER BY name ASC
        LIMIT %s OFFSET %s
    """
    fetch_params = list(params) + [per_page, offset]
    rows, err = execute_query(fetch_sql, tuple(fetch_params), fetch_all=True)
    if err:
        return None, err

    products = []
    for r in (rows or []):
        products.append({
            "id": r["id"],
            "product_code": r["product_code"],
            "name": r["name"],
            "category": r["category"],
            "description": r["description"],
            "price": float(r["price"] or 0.0),
            "tax_percentage": float(r["tax_percentage"] or 0.0),
            "discount_percentage": float(r["discount_percentage"] or 0.0),
            "stock": r["stock"],
            "status": r["status"],
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else None,
            "updated_at": r["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if r["updated_at"] else None
        })

    # Fetch unique categories for dropdown
    cat_rows, _ = execute_query("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != '' ORDER BY category ASC", fetch_all=True)
    categories = [c["category"] for c in (cat_rows or [])]

    return {
        "products": products,
        "categories": categories,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 1
    }, None


def get_product(product_id: int) -> tuple[dict | None, str | None]:
    """Fetch product details by ID."""
    sql = """
        SELECT id, product_code, name, category, description, price,
               tax_percentage, discount_percentage, stock, status,
               created_at, updated_at
        FROM products
        WHERE id = %s
    """
    row, err = execute_query(sql, (product_id,), fetch_one=True)
    if err:
        return None, err
    if not row:
        return None, "Product not found"

    return {
        "id": row["id"],
        "product_code": row["product_code"],
        "name": row["name"],
        "category": row["category"],
        "description": row["description"],
        "price": float(row["price"] or 0.0),
        "tax_percentage": float(row["tax_percentage"] or 0.0),
        "discount_percentage": float(row["discount_percentage"] or 0.0),
        "stock": row["stock"],
        "status": row["status"],
        "created_at": row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row["created_at"] else None,
        "updated_at": row["updated_at"].strftime("%Y-%m-%d %H:%M:%S") if row["updated_at"] else None
    }, None


def create_product(data: dict, user_id: int | None = None) -> tuple[int | None, str | None]:
    """Create a new product record."""
    clean, err = validate_product_data(data)
    if err:
        return None, err

    code = clean["product_code"]
    if not code:
        code = _generate_product_code()
    else:
        # Check uniqueness
        dup, _ = execute_query("SELECT id FROM products WHERE product_code = %s", (code,), fetch_one=True)
        if dup:
            return None, f"Product code '{code}' is already in use"

    sql = """
        INSERT INTO products (product_code, name, category, description, price,
                             tax_percentage, discount_percentage, stock, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """
    params = (
        code, clean["name"], clean["category"], clean["description"],
        clean["price"], clean["tax_percentage"], clean["discount_percentage"],
        clean["stock"], clean["status"]
    )
    res, err = execute_query(sql, params, commit=True)
    if err:
        return None, err
    product_id = res.get("last_id") if isinstance(res, dict) else res

    log_activity(user_id, "product", product_id, "created", f"Created product '{clean['name']}' ({code})")
    return product_id, None


def update_product(product_id: int, data: dict, user_id: int | None = None) -> tuple[bool, str | None]:
    """Update an existing product."""
    existing, err = get_product(product_id)
    if err or not existing:
        return False, "Product not found"

    clean, err = validate_product_data(data, is_update=True)
    if err:
        return False, err

    code = clean["product_code"] or existing["product_code"]
    if code != existing["product_code"]:
        dup, _ = execute_query("SELECT id FROM products WHERE product_code = %s AND id != %s", (code, product_id), fetch_one=True)
        if dup:
            return False, f"Product code '{code}' is already in use"

    sql = """
        UPDATE products
        SET product_code = %s, name = %s, category = %s, description = %s,
            price = %s, tax_percentage = %s, discount_percentage = %s,
            stock = %s, status = %s, updated_at = NOW()
        WHERE id = %s
    """
    params = (
        code, clean["name"], clean["category"], clean["description"],
        clean["price"], clean["tax_percentage"], clean["discount_percentage"],
        clean["stock"], clean["status"], product_id
    )
    _, err = execute_query(sql, params, commit=True)
    if err:
        return False, err

    log_activity(user_id, "product", product_id, "updated", f"Updated product '{clean['name']}' ({code})")
    return True, None


def delete_product(product_id: int, user_id: int | None = None) -> tuple[bool, str | None]:
    """Delete a product after checking invoice constraints."""
    existing, err = get_product(product_id)
    if err or not existing:
        return False, "Product not found"

    # Check if used in invoices
    in_inv, _ = execute_query("SELECT id FROM invoice_items WHERE product_id = %s LIMIT 1", (product_id,), fetch_one=True)
    if in_inv:
        # Rather than hard deleting which breaks invoice item linkage or sets null, soft-deactivate or notify
        # Let's set status to inactive
        execute_query("UPDATE products SET status = 'inactive' WHERE id = %s", (product_id,), commit=True)
        log_activity(user_id, "product", product_id, "deactivated", f"Product '{existing['name']}' archived/deactivated (referenced in invoices)")
        return True, "Product is referenced in existing invoices and has been marked as inactive instead of permanently deleted"

    sql = "DELETE FROM products WHERE id = %s"
    _, err = execute_query(sql, (product_id,), commit=True)
    if err:
        return False, err

    log_activity(user_id, "product", product_id, "deleted", f"Deleted product '{existing['name']}'")
    return True, None


def bulk_action_products(action: str, ids: list, value=None, user_id: int | None = None) -> tuple[dict | None, str | None]:
    """Execute bulk operations on multiple products."""
    if not ids or not isinstance(ids, list):
        return None, "No product IDs provided"

    clean_ids = [int(i) for i in ids if str(i).isdigit()]
    if not clean_ids:
        return None, "Invalid ID list"

    id_placeholders = ", ".join(["%s"] * len(clean_ids))

    if action == "delete":
        # Check if any products are in invoices
        chk_sql = f"SELECT DISTINCT product_id FROM invoice_items WHERE product_id IN ({id_placeholders})"
        in_inv_rows, _ = execute_query(chk_sql, tuple(clean_ids), fetch_all=True)
        in_inv_ids = {r["product_id"] for r in (in_inv_rows or [])}

        deletable = [i for i in clean_ids if i not in in_inv_ids]
        deactivated = [i for i in clean_ids if i in in_inv_ids]

        if deletable:
            d_placeholders = ", ".join(["%s"] * len(deletable))
            execute_query(f"DELETE FROM products WHERE id IN ({d_placeholders})", tuple(deletable), commit=True)

        if deactivated:
            a_placeholders = ", ".join(["%s"] * len(deactivated))
            execute_query(f"UPDATE products SET status = 'inactive' WHERE id IN ({a_placeholders})", tuple(deactivated), commit=True)

        log_activity(user_id, "product", None, "bulk_delete", f"Bulk processed {len(clean_ids)} products ({len(deletable)} deleted, {len(deactivated)} marked inactive)")
        return {"action": "delete", "deleted": len(deletable), "deactivated": len(deactivated)}, None

    elif action == "status":
        valid_statuses = {"active", "inactive"}
        if value not in valid_statuses:
            return None, f"Invalid status '{value}'. Allowed: {', '.join(valid_statuses)}"

        up_sql = f"UPDATE products SET status = %s, updated_at = NOW() WHERE id IN ({id_placeholders})"
        _, err = execute_query(up_sql, tuple([value] + clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "product", None, "bulk_status", f"Bulk updated {len(clean_ids)} products status to '{value}'")
        return {"action": "status", "affected": len(clean_ids), "new_status": value}, None

    elif action == "category":
        category = str(value).strip() if value else "General"
        up_sql = f"UPDATE products SET category = %s, updated_at = NOW() WHERE id IN ({id_placeholders})"
        _, err = execute_query(up_sql, tuple([category] + clean_ids), commit=True)
        if err:
            return None, err
        log_activity(user_id, "product", None, "bulk_category", f"Bulk updated {len(clean_ids)} products category to '{category}'")
        return {"action": "category", "affected": len(clean_ids), "new_category": category}, None

    return None, f"Unsupported bulk action '{action}'"

