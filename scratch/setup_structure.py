import os
import shutil
from pathlib import Path

crm_root = Path(r"c:\CRM")

# 1. Create missing directory structure
directories = [
    crm_root / "backend" / "models",
    crm_root / "backend" / "middleware",
    crm_root / "backend" / "utils",
    crm_root / "backend" / "tests",
    crm_root / "database" / "migrations",
    crm_root / "database" / "tests",
    crm_root / "frontend" / "assets" / "images",
    crm_root / "frontend" / "assets" / "icons",
    crm_root / "frontend" / "assets" / "fonts",
    crm_root / "frontend" / "css",
    crm_root / "frontend" / "js" / "core",
    crm_root / "frontend" / "js" / "components",
    crm_root / "frontend" / "js" / "pages",
    crm_root / "frontend" / "js" / "utils",
    crm_root / "uploads" / "customer_documents",
    crm_root / "uploads" / "profile_images",
    crm_root / "uploads" / "invoices",
    crm_root / "uploads" / "backups",
    crm_root / "logs",
    crm_root / "scripts",
    crm_root / "docs",
]

for d in directories:
    d.mkdir(parents=True, exist_ok=True)
    print(f"Directory verified: {d}")

print("Directory structure setup completed.")
