import os
from pathlib import Path

crm_root = Path(r"c:\CRM")

def create_file_if_missing(path, content=""):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created file: {path.relative_to(crm_root)}")

# 1. CSS Files
css_dir = crm_root / "frontend" / "css"
css_files = {
    "variables.css": "/* CSS Custom Properties & Variables */\n:root {\n  --primary: #2563eb;\n  --primary-hover: #1d4ed8;\n  --bg-main: #f8fafc;\n  --text-primary: #0f172a;\n}\n",
    "layout.css": "/* Layout Structure & Grid */\n.dashboard-layout { display: flex; min-height: 100vh; }\n",
    "sidebar.css": "/* Sidebar Navigation Styles */\n.sidebar { width: 260px; flex-shrink: 0; }\n",
    "navbar.css": "/* Topbar Navigation Header */\n.topbar { height: 64px; display: flex; align-items: center; }\n",
    "tables.css": "/* Responsive Data Tables */\n.data-table-container { width: 100%; overflow-x: auto; }\n",
    "forms.css": "/* Form Controls & Inputs */\n.form-control { width: 100%; box-sizing: border-box; }\n",
    "modals.css": "/* Modal Window Overlay & Sticky Action Footer */\n.modal-body { max-height: calc(100vh - 130px); overflow-y: auto; }\n",
    "components.css": "/* UI Components: Toasts, Badges, Cards, Pagination */\n.card { background: #fff; border-radius: 8px; }\n",
}
for fname, code in css_files.items():
    create_file_if_missing(css_dir / fname, code)

# 2. JS Core
js_core = crm_root / "frontend" / "js" / "core"
create_file_if_missing(js_core / "config.js", "const CONFIG = { API_BASE_URL: 'http://127.0.0.1:5000' };\n")
create_file_if_missing(js_core / "api.js", "// Core ApiClient module\n")
create_file_if_missing(js_core / "auth.js", "// Core Auth module\n")
create_file_if_missing(js_core / "app.js", "// Core UI module\n")

# 3. JS Components
js_comp = crm_root / "frontend" / "js" / "components"
comp_files = ["sidebar.js", "navbar.js", "modal.js", "toast.js", "loader.js", "pagination.js"]
for c in comp_files:
    create_file_if_missing(js_comp / c, f"// Component: {c}\n")

# 4. JS Pages
js_pages = crm_root / "frontend" / "js" / "pages"
page_files = [
    "dashboard.js", "customers.js", "customer-details.js", "leads.js", "lead-details.js",
    "deals.js", "calendar.js", "tasks.js", "calls.js", "meetings.js", "products.js",
    "invoices.js", "payments.js", "emails.js", "notifications.js", "reports.js",
    "audit-logs.js", "users.js", "profile.js", "settings.js"
]
for p in page_files:
    create_file_if_missing(js_pages / p, f"// Page Controller: {p}\n")

# 5. JS Utils
js_utils = crm_root / "frontend" / "js" / "utils"
util_files = ["validation.js", "formatting.js", "storage.js", "helpers.js"]
for u in util_files:
    create_file_if_missing(js_utils / u, f"// Frontend Utility: {u}\n")

print("Frontend modular assets created.")
