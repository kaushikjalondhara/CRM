import os
from pathlib import Path

crm_root = Path(r"c:\CRM")

docs = {
    "docs/API.md": """# Apex CRM – REST API Reference

## Base URL
`http://127.0.0.1:5000/api`

## Authentication
All protected routes require the `Authorization` header with a valid JWT Bearer token:
`Authorization: Bearer <your_jwt_token>`

## Endpoints Overview

### Authentication (`/api/auth`)
- `POST /api/auth/login`: Authenticates user credentials and returns a signed JWT token.
- `POST /api/auth/logout`: Revokes active JWT token via server-side blocklist.
- `GET /api/auth/me`: Returns profile and permissions matrix for the authenticated user.

### Customer Management (`/api/customers`)
- `GET /api/customers`: Search, filter, and list customer records.
- `POST /api/customers`: Create new customer record.
- `GET /api/customers/<id>/360`: Unified 360° profile view aggregating deals, invoices, tasks, calls, meetings, notes, and documents.
- `POST /api/customers/<id>/notes`: Add customer note.
- `POST /api/customers/<id>/documents`: Upload client document.

### Lead Pipeline (`/api/leads`)
- `GET /api/leads`: List lead records with filtering.
- `POST /api/leads`: Create new lead.
- `POST /api/leads/<id>/convert`: Convert qualified lead into Customer and Deal records.

### Deals Pipeline (`/api/deals`)
- `GET /api/deals`: List deal records.
- `GET /api/deals/pipeline`: Returns stage breakdown counts and cumulative monetary value.
- `PUT /api/deals/<id>/stage`: Update deal pipeline stage with audit trail logging.

### Operations (`/api/tasks`, `/api/calls`, `/api/meetings`)
- `GET/POST /api/tasks`: Operations task manager and quick status updates (`PUT /api/tasks/<id>/status`).
- `GET/POST /api/calls`: Scheduled phone call logging and outcomes.
- `GET/POST /api/meetings`: Appointment scheduler with time validation.

### Financials (`/api/products`, `/api/invoices`, `/api/payments`)
- `GET/POST /api/products`: Catalog management, pricing models, inventory stock.
- `GET/POST /api/invoices`: Multi-line item invoices and ReportLab PDF export (`GET /api/invoices/<id>/pdf`).
- `GET/POST /api/payments`: Payment records with server-side overpayment protection.

### Analytics & System (`/api/reports`, `/api/calendar`, `/api/audit-logs`, `/api/backup`, `/api/search`)
- `GET /api/reports/sales`: Revenue trends and employee leaderboards.
- `GET /api/calendar/events`: Aggregated agenda events for monthly CRM calendar.
- `GET /api/audit-logs`: Immutable security audit trail explorer.
- `POST /api/backup/create`: On-demand SQL backup creation and download.
- `GET /api/search?q=...`: Global instant search across 10 core entities.
""",

    "docs/DATABASE.md": """# Database Architecture & Schema Documentation

## Database System
- Engine: MySQL 8.0+ / MariaDB
- Database Name: `crm_database`
- Character Set: `utf8mb4`
- Collation: `utf8mb4_unicode_ci`

## Relational Schema (23 Core Tables)
1. `roles`: Access control roles (`Admin`, `Manager`, `Sales Employee`, `Staff`).
2. `permissions`: 45 granular permission definitions.
3. `role_permissions`: Role-permission matrix mappings.
4. `users`: User accounts with `scrypt` hashed passwords.
5. `login_history`: User sign-in audit logs.
6. `customers`: Customer entity profiles.
7. `customer_notes`: Customer internal notes.
8. `customer_documents`: Uploaded client documents metadata.
9. `leads`: Prospect leads pipeline tracking.
10. `lead_activities`: Touchpoints and interaction history for leads.
11. `deals`: Sales deals pipeline records.
12. `deal_activities`: Stage transition audit trails.
13. `tasks`: Action items and polymorphic entity assignments.
14. `calls`: Scheduled and logged phone conversations.
15. `meetings`: Appointment and consultation records.
16. `products`: Catalog items, pricing models, and stock counts.
17. `invoices`: Billing statements and line-item totals.
18. `invoice_items`: Line items breakdown per invoice.
19. `payments`: Invoice payment receipts with transaction IDs.
20. `emails`: Email communication records.
21. `email_templates`: Jinja placeholder merge templates.
22. `notifications`: Real-time user alert notifications.
23. `audit_logs`: Immutable security event ledger.
""",

    "docs/ARCHITECTURE.md": """# Apex CRM Architecture Overview

## Layered Design Pattern

```text
[ Browser / Frontend ]
          │
    REST API Calls (JWT Bearer Token)
          │
          ▼
[ Flask Application Factory (backend/app.py) ]
          │
          ├── Middleware (@login_required, @permission_required)
          ├── Route Controllers (backend/routes/*.py)
          ├── Service Business Logic (backend/services/*.py)
          └── Models & Data Wrappers (backend/models/*.py)
          │
          ▼
[ Database Connection Manager (database/database.py) ]
          │
          ▼
[ MySQL Database (crm_database) ]
```

## Security Design
- Passwords stored as Werkzeug `scrypt` cryptographic hashes.
- Server-side JWT blocklisting on logout.
- Parameterized SQL prepared statements preventing SQL injection.
- Role-Based Access Control (RBAC) enforced at both route and database query levels.
""",

    "docs/DEPLOYMENT.md": """# Production Deployment Guide

## Prerequisites
- Linux / Windows Server
- Python 3.10+
- MySQL 8.0+ / MariaDB
- Gunicorn WSGI Server

## Running with Gunicorn WSGI
```bash
gunicorn -c backend/gunicorn_conf.py backend.app:app
```

## Environment File Setup (`.env`)
```ini
FLASK_ENV=production
PORT=5000
SECRET_KEY=generate_a_random_32_byte_secret_key_here
DB_HOST=localhost
DB_PORT=3306
DB_NAME=crm_database
DB_USER=crm_user
DB_PASSWORD=strong_password_here
```
""",

    "docs/USER_GUIDE.md": """# Apex CRM User Guide

## Logging In
Navigate to `login.html` and sign in with your role account:
- Admin: `admin@crm.local` / `Admin@123456`
- Manager: `manager@crm.local` / `Manager@123456`
- Sales Rep: `sales@crm.local` / `Sales@123456`
- Staff: `staff@crm.local` / `Staff@123456`

## Core Workflows
1. **Managing Customers**: Use `customers.html` to add, view 360° details, or upload documents.
2. **Converting Leads**: Use `leads.html` to track prospects and click "Convert Lead" to generate a Customer and Deal record instantly.
3. **Deals Kanban**: Use `deals.html` to drag and drop deals across pipeline stages (`New`, `Qualification`, `Proposal`, `Negotiation`, `Won`, `Lost`).
4. **Invoicing & Payments**: Use `invoices.html` to create bills, download ReportLab PDF receipts, and record payments with overpayment safety.
5. **Global Search**: Press `Ctrl + K` on any page to open instant search across all entities.
"""
}

for rel_path, content in docs.items():
    full_path = crm_root / rel_path
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated doc: {rel_path}")

print("Docs generation completed.")
