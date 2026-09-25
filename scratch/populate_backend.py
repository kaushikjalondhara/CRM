import os
from pathlib import Path

crm_root = Path(r"c:\CRM")

def create_file_if_missing(path, content=""):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created file: {path.relative_to(crm_root)}")

# 1. Root run.py
create_file_if_missing(
    crm_root / "run.py",
    """import os
from backend.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=True)
"""
)

# 2. Backend Models (__init__.py and models)
models_dir = crm_root / "backend" / "models"
create_file_if_missing(models_dir / "__init__.py", "# Models package\n")

models_map = {
    "user_model.py": "class UserModel:\n    table_name = 'users'\n",
    "customer_model.py": "class CustomerModel:\n    table_name = 'customers'\n",
    "lead_model.py": "class LeadModel:\n    table_name = 'leads'\n",
    "deal_model.py": "class DealModel:\n    table_name = 'deals'\n",
    "task_model.py": "class TaskModel:\n    table_name = 'tasks'\n",
    "call_model.py": "class CallModel:\n    table_name = 'calls'\n",
    "meeting_model.py": "class MeetingModel:\n    table_name = 'meetings'\n",
    "product_model.py": "class ProductModel:\n    table_name = 'products'\n",
    "invoice_model.py": "class InvoiceModel:\n    table_name = 'invoices'\n",
    "payment_model.py": "class PaymentModel:\n    table_name = 'payments'\n",
    "notification_model.py": "class NotificationModel:\n    table_name = 'notifications'\n",
    "document_model.py": "class DocumentModel:\n    table_name = 'documents'\n",
}
for name, code in models_map.items():
    create_file_if_missing(models_dir / name, code)

# 3. Middleware
mw_dir = crm_root / "backend" / "middleware"
create_file_if_missing(mw_dir / "__init__.py", "# Middleware package\n")
create_file_if_missing(mw_dir / "auth_middleware.py", "from backend.utils.decorators import login_required\n")
create_file_if_missing(mw_dir / "role_middleware.py", "from backend.utils.decorators import permission_required, admin_required\n")
create_file_if_missing(mw_dir / "error_middleware.py", "# Global error handlers middleware\n")

# 4. Utils
utils_dir = crm_root / "backend" / "utils"
create_file_if_missing(utils_dir / "__init__.py", "# Utils package\n")
create_file_if_missing(utils_dir / "validators.py", "# Request data validators\n")
create_file_if_missing(utils_dir / "response.py", """from flask import jsonify

def api_response(success=True, message="", data=None, status_code=200):
    payload = {"success": success, "message": message}
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status_code
""")
create_file_if_missing(utils_dir / "pagination.py", "# Pagination helpers\n")
create_file_if_missing(utils_dir / "logger.py", "import logging\nlogger = logging.getLogger('crm')\n")
create_file_if_missing(utils_dir / "security.py", "from werkzeug.security import generate_password_hash, check_password_hash\n")

# 5. Database Seed & Migrations & Tests
db_dir = crm_root / "database"
create_file_if_missing(db_dir / "seed.sql", "-- Initial Seed SQL Data\n")
create_file_if_missing(db_dir / "migrations" / "README.md", "# Database Migrations Guide\n")

# 6. Scripts
scripts_dir = crm_root / "scripts"
create_file_if_missing(scripts_dir / "setup_database.py", "from database.database import init_db\nif __name__ == '__main__': init_db()\n")
create_file_if_missing(scripts_dir / "seed_database.py", "# Database Seeding Script\n")
create_file_if_missing(scripts_dir / "backup_database.py", "from backend.services.backup_service import create_database_backup\nif __name__ == '__main__': print(create_database_backup())\n")
create_file_if_missing(scripts_dir / "health_check.py", "from database.database import check_db_connection\nif __name__ == '__main__': print(check_db_connection())\n")

# 7. Logs
logs_dir = crm_root / "logs"
create_file_if_missing(logs_dir / "application.log", "")
create_file_if_missing(logs_dir / "error.log", "")
create_file_if_missing(logs_dir / "audit.log", "")

# 8. Docs
docs_dir = crm_root / "docs"
create_file_if_missing(docs_dir / "API.md", "# Apex CRM API Reference\n")
create_file_if_missing(docs_dir / "DATABASE.md", "# Database Architecture Documentation\n")
create_file_if_missing(docs_dir / "ARCHITECTURE.md", "# Apex CRM System Architecture\n")
create_file_if_missing(docs_dir / "DEPLOYMENT.md", "# Production Deployment Guide\n")
create_file_if_missing(docs_dir / "USER_GUIDE.md", "# User Operating Guide\n")

print("Backend files setup completed.")
