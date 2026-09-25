"""
CRM Global Search Service
Searches across all major CRM entities with permission enforcement.
"""

from database.database import execute_query


def global_search(query: str, current_user: dict, limit_per_entity: int = 5) -> dict:
    """
    Search across CRM entities: Customers, Leads, Deals, Invoices, Payments,
    Tasks, Calls, Meetings, Products, and Users.
    Enforces user permissions before querying each entity.
    """
    q = (query or "").strip()
    if len(q) < 2:
        return {
            "query": q,
            "total_results": 0,
            "results": {}
        }

    like_term = f"%{q}%"
    results = {}
    total_count = 0

    permissions = set(current_user.get("permissions") or [])
    is_admin = current_user.get("role") == "Admin"

    # Helper permission checker
    def can(perm: str) -> bool:
        return is_admin or perm in permissions

    # 1. Customers
    if can("customers.view"):
        sql = """
            SELECT id, customer_code, first_name, last_name, company_name, email, phone
            FROM customers
            WHERE customer_code LIKE %s OR first_name LIKE %s OR last_name LIKE %s
               OR company_name LIKE %s OR email LIKE %s OR phone LIKE %s
            ORDER BY id DESC LIMIT %s
        """
        rows, _ = execute_query(sql, (like_term, like_term, like_term, like_term, like_term, like_term, limit_per_entity), fetch_all=True)
        if rows:
            items = []
            for r in rows:
                name = f"{r['first_name']} {r['last_name']}".strip()
                sub = r.get("company_name") or r.get("email") or r.get("customer_code")
                items.append({
                    "id": r["id"],
                    "title": name,
                    "subtitle": sub,
                    "code": r.get("customer_code"),
                    "url": f"customer-details.html?id={r['id']}"
                })
            results["customers"] = items
            total_count += len(items)

    # 2. Leads
    if can("leads.view"):
        sql = """
            SELECT id, lead_code, first_name, last_name, company_name, email, phone, status
            FROM leads
            WHERE lead_code LIKE %s OR first_name LIKE %s OR last_name LIKE %s
               OR company_name LIKE %s OR email LIKE %s OR phone LIKE %s
            ORDER BY id DESC LIMIT %s
        """
        rows, _ = execute_query(sql, (like_term, like_term, like_term, like_term, like_term, like_term, limit_per_entity), fetch_all=True)
        if rows:
            items = []
            for r in rows:
                name = f"{r['first_name']} {r['last_name']}".strip()
                sub = f"{r.get('company_name') or 'Lead'} • {r.get('status', 'new').capitalize()}"
                items.append({
                    "id": r["id"],
                    "title": name,
                    "subtitle": sub,
                    "code": r.get("lead_code"),
                    "url": f"lead-details.html?id={r['id']}"
                })
            results["leads"] = items
            total_count += len(items)

    # 3. Deals
    if can("deals.view"):
        sql = """
            SELECT id, deal_code, title, value, stage
            FROM deals
            WHERE deal_code LIKE %s OR title LIKE %s
            ORDER BY id DESC LIMIT %s
        """
        rows, _ = execute_query(sql, (like_term, like_term, limit_per_entity), fetch_all=True)
        if rows:
            items = []
            for r in rows:
                items.append({
                    "id": r["id"],
                    "title": r["title"],
                    "subtitle": f"₹{float(r.get('value', 0)):,.2f} • {r.get('stage', 'new').capitalize()}",
                    "code": r.get("deal_code"),
                    "url": f"deals.html?deal_id={r['id']}"
                })
            results["deals"] = items
            total_count += len(items)

    # 4. Invoices
    if can("invoices.view"):
        sql = """
            SELECT i.id, i.invoice_number, i.total_amount, i.status, c.first_name, c.last_name
            FROM invoices i
            LEFT JOIN customers c ON i.customer_id = c.id
            WHERE i.invoice_number LIKE %s OR c.first_name LIKE %s OR c.last_name LIKE %s
            ORDER BY i.id DESC LIMIT %s
        """
        rows, _ = execute_query(sql, (like_term, like_term, like_term, limit_per_entity), fetch_all=True)
        if rows:
            items = []
            for r in rows:
                cname = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
                items.append({
                    "id": r["id"],
                    "title": r["invoice_number"],
                    "subtitle": f"{cname or 'Client'} • ₹{float(r.get('total_amount', 0)):,.2f} • {r.get('status', 'draft').capitalize()}",
                    "code": r["invoice_number"],
                    "url": f"invoices.html?invoice_id={r['id']}"
                })
            results["invoices"] = items
            total_count += len(items)

    # 5. Payments
    if can("payments.view"):
        sql = """
            SELECT p.id, p.transaction_reference, p.amount, p.payment_method, i.invoice_number
            FROM payments p
            LEFT JOIN invoices i ON p.invoice_id = i.id
            WHERE p.transaction_reference LIKE %s OR i.invoice_number LIKE %s
            ORDER BY p.id DESC LIMIT %s
        """
        rows, _ = execute_query(sql, (like_term, like_term, limit_per_entity), fetch_all=True)
        if rows:
            items = []
            for r in rows:
                items.append({
                    "id": r["id"],
                    "title": r.get("transaction_reference") or f"Payment #{r['id']}",
                    "subtitle": f"₹{float(r.get('amount', 0)):,.2f} • {r.get('payment_method', 'N/A')} • Inv: {r.get('invoice_number', 'N/A')}",
                    "url": f"payments.html?payment_id={r['id']}"
                })
            results["payments"] = items
            total_count += len(items)

    # 6. Tasks
    if can("tasks.view"):
        sql = """
            SELECT id, title, priority, status, due_date
            FROM tasks
            WHERE title LIKE %s OR description LIKE %s
            ORDER BY id DESC LIMIT %s
        """
        rows, _ = execute_query(sql, (like_term, like_term, limit_per_entity), fetch_all=True)
        if rows:
            items = []
            for r in rows:
                items.append({
                    "id": r["id"],
                    "title": r["title"],
                    "subtitle": f"Priority: {r.get('priority', 'medium').capitalize()} • Status: {r.get('status', 'pending').capitalize()}",
                    "url": f"tasks.html?task_id={r['id']}"
                })
            results["tasks"] = items
            total_count += len(items)

    # 7. Calls
    if can("calls.view"):
        sql = """
            SELECT id, purpose as subject, call_date, call_time, status
            FROM calls
            WHERE purpose LIKE %s OR notes LIKE %s
            ORDER BY id DESC LIMIT %s
        """
        rows, _ = execute_query(sql, (like_term, like_term, limit_per_entity), fetch_all=True)
        if rows:
            items = []
            for r in rows:
                items.append({
                    "id": r["id"],
                    "title": r.get("subject") or "Call",
                    "subtitle": f"Date: {r.get('call_date')} • Status: {r.get('status', 'scheduled').capitalize()}",
                    "url": f"calls.html?call_id={r['id']}"
                })
            results["calls"] = items
            total_count += len(items)

    # 8. Meetings
    if can("meetings.view"):
        sql = """
            SELECT id, title, meeting_date, start_time, status
            FROM meetings
            WHERE title LIKE %s OR notes LIKE %s
            ORDER BY id DESC LIMIT %s
        """
        rows, _ = execute_query(sql, (like_term, like_term, limit_per_entity), fetch_all=True)
        if rows:
            items = []
            for r in rows:
                items.append({
                    "id": r["id"],
                    "title": r["title"],
                    "subtitle": f"Meeting • Status: {r.get('status', 'scheduled').capitalize()}",
                    "url": f"meetings.html?meeting_id={r['id']}"
                })
            results["meetings"] = items
            total_count += len(items)

    # 9. Products
    if can("products.view"):
        sql = """
            SELECT id, product_code, name, price, category
            FROM products
            WHERE product_code LIKE %s OR name LIKE %s OR category LIKE %s
            ORDER BY id DESC LIMIT %s
        """
        rows, _ = execute_query(sql, (like_term, like_term, like_term, limit_per_entity), fetch_all=True)
        if rows:
            items = []
            for r in rows:
                items.append({
                    "id": r["id"],
                    "title": r["name"],
                    "subtitle": f"Code: {r.get('product_code')} • ₹{float(r.get('price', 0)):,.2f} • {r.get('category', 'General')}",
                    "code": r.get("product_code"),
                    "url": f"products.html?product_id={r['id']}"
                })
            results["products"] = items
            total_count += len(items)

    # 10. Users
    if can("users.view"):
        sql = """
            SELECT u.id, u.first_name, u.last_name, u.email, r.name as role_name
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            WHERE u.first_name LIKE %s OR u.last_name LIKE %s OR u.email LIKE %s
            ORDER BY u.id DESC LIMIT %s
        """
        rows, _ = execute_query(sql, (like_term, like_term, like_term, limit_per_entity), fetch_all=True)
        if rows:
            items = []
            for r in rows:
                items.append({
                    "id": r["id"],
                    "title": f"{r['first_name']} {r['last_name']}".strip(),
                    "subtitle": f"Role: {r.get('role_name', 'User')} • {r.get('email')}",
                    "url": f"users.html?user_id={r['id']}"
                })
            results["users"] = items
            total_count += len(items)

    return {
        "query": q,
        "total_results": total_count,
        "results": results
    }
