# Apex CRM Architecture Overview

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
