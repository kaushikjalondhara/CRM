# Apex CRM System

A modern, scalable Customer Relationship Management (CRM) platform engineered to streamline customer relationships, manage pipelines, track leads, and provide actionable analytics for sales and service teams.

---

## 🚀 Technology Stack

### Frontend
- **HTML5**: Semantic, accessible document markup.
- **CSS3**: Modern custom styling, CSS variables, mobile-first responsive grid and flexbox layout.
- **Vanilla JavaScript**: Lightweight, modular ES6+ architecture without heavy external frameworks.
- **Responsive Design**: Optimized across mobile, tablet, laptop, and desktop viewports.

### Backend
- **Python 3.10+** (tested on Python 3.14)
- **Flask**: Microframework for REST API endpoints.
- **Flask-CORS**: Cross-Origin Resource Sharing for seamless frontend-backend integration.
- **python-dotenv**: Environment configuration loader.
- **Werkzeug Security**: Cryptographic password hashing (`scrypt`).

### Database Layer
- **MySQL / MariaDB**: Relational database architecture (target DB: `crm_database`).
- **mysql-connector-python**: Native Python MySQL database driver with connection pooling, cursor context managers, and resilient error handling.

### Development & DevOps
- **Git & GitHub** version control
- **`.env`** secret management

---

## 📁 Project Folder Structure

```text
CRM-PROJECT/
│
├── frontend/
│   ├── index.html              # CRM Landing and overview page
│   ├── login.html              # Authentication UI
│   ├── dashboard.html          # Core dashboard layout skeleton
│   │
│   ├── css/
│   │   ├── style.css           # Global design system, variables & resets
│   │   ├── login.css           # Authentication-specific styles
│   │   ├── dashboard.css       # Sidebar, navbar, cards, and grid styles
│   │   └── responsive.css      # Responsive media queries & drawer navigation
│   │
│   ├── js/
│   │   ├── app.js              # Core UI interactions & status indicators
│   │   ├── api.js              # Reusable fetch API helper client
│   │   └── auth.js             # Authentication helper module
│   │
│   └── assets/
│       ├── images/             # Static imagery & brand logos
│       └── icons/              # Custom vector / UI icons
│
├── backend/
│   ├── app.py                  # Flask application factory and entry point
│   ├── config.py               # Environment configuration settings
│   ├── requirements.txt        # Backend dependencies
│   │
│   ├── routes/                 # REST API endpoints & blueprints
│   │   └── __init__.py
│   │
│   ├── models/                 # Database models & schemas
│   │   └── __init__.py
│   │
│   ├── services/               # Business logic services
│   │   └── __init__.py
│   │
│   └── utils/                  # Helper utilities & validators
│       └── __init__.py
│
├── database/
│   ├── __init__.py             # Database package exports
│   ├── database.py             # Reusable MySQL connection manager & query helpers
│   ├── schema.sql              # Complete 23-table CRM schema & seed data
│   └── test_db.py              # Automated schema, relationships & seed test suite
│
├── uploads/                    # User document & media storage
│   ├── customer_documents/     # Uploaded client documents
│   └── profile_images/         # User profile pictures
│
├── .env                        # Local environment variables (git-ignored)
├── .env.example                # Template environment variables
├── .gitignore                  # Git ignore rules
├── README.md                   # Project documentation
└── requirements.txt            # Root dependencies
```

---

## 🗄️ Database Architecture (Step 2)

The database schema (`database/schema.sql`) implements **23 core tables** with clean relational constraints, safe `ON DELETE` referential integrity (`RESTRICT`/`SET NULL` on core business data to prevent data loss), and specialized search indexes.

### Core Tables & Entities:
1. **Access Control & Identity**: `roles`, `permissions`, `role_permissions`, `users`
2. **Customer Management**: `customers`, `customer_documents`, `customer_notes`
3. **Sales Pipeline & Lead Tracking**: `leads`, `lead_activities`, `deals`, `deal_activities`
4. **Operations & Calendaring**: `tasks`, `calls`, `meetings`
5. **Product Catalog & Invoicing**: `products`, `invoices`, `invoice_items`, `payments`
6. **Communications & Messaging**: `emails`, `email_templates`
7. **System & Analytics**: `notifications`, `activities` (global audit trail), `settings`

---

## ⚙️ Complete Database & System Setup

### 1. Prerequisites
- **Python 3.10+** (Run `python --version` to confirm)
- **Git**
- **MySQL / MariaDB Server** (e.g. XAMPP, MySQL Community Server, or Docker)

### 2. Start MySQL Server (Windows / XAMPP)
If using XAMPP on Windows, start MySQL from PowerShell:
```powershell
C:\xampp\mysql\bin\mysqld.exe --defaults-file=C:\xampp\mysql\bin\my.ini --standalone
```
Or use the XAMPP Control Panel.

### 3. Create Virtual Environment & Install Dependencies
Open PowerShell in `c:\CRM`:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4. Configure Environment Variables (`.env`)
Verify your `.env` file contains the target database settings:
```ini
# Flask Core
SECRET_KEY=crm_secret_key_development_only_change_in_prod
FLASK_ENV=development
FLASK_DEBUG=True
PORT=5000
HOST=127.0.0.1

# MySQL Database Settings
DB_HOST=localhost
DB_PORT=3306
DB_NAME=crm_database
DB_USER=root
DB_PASSWORD=
```

### 5. Initialize Schema and Seed Data
You can initialize the database using the Python database runner:
```powershell
python -c "from database import init_db; success, msg = init_db(); print(msg)"
```
Or directly import via MySQL command line:
```powershell
mysql -u root -p < database/schema.sql
```

### 6. Verify Database with Automated Test Suite
Run the 10-point database verification suite:
```powershell
python database/test_db.py
```
This tests:
- Database connectivity & error masking
- Existence of all 23 tables
- Default roles (`Admin`, `Manager`, `Sales Employee`, `Staff`)
- Default permissions (45 granular permissions)
- Role-permission assignments
- Demo Admin user creation and password hash validation
- 47 Foreign key constraints and safe cascade policies
- 22 Performance search indexes
- Baseline system settings

---

## 🔑 Development Seed Logins

For development and testing across all RBAC role tiers, initial seed accounts are available:

| Role | Email | Development Password | Permissions Summary |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@crm.local` | `Admin@123456` | Full system access (45 permissions + administrative bypass) |
| **Manager** | `manager@crm.local` | `Manager@123456` | Operations, pipelines, reports, analytics & user viewing (32 permissions) |
| **Sales Employee** | `sales@crm.local` | `Sales@123456` | Leads, customers, deals, tasks, calls, meetings (22 permissions) |
| **Staff** | `staff@crm.local` | `Staff@123456` | Task execution, view customers/products (7 permissions) |
| **Inactive User** | `inactive@crm.local` | `Inactive@123456` | Account inactive (returns `403 Forbidden` on sign-in) |

> [!WARNING]
> Development passwords are for local testing only and are **never** stored in plain text. Only cryptographic hashes (`scrypt`) are stored in `crm_database`.

---

## 🔐 Authentication & RBAC API (Step 3)

### Endpoints
- **`POST /api/auth/login`**: Authenticates email and password, updates `users.last_login`, and returns a signed JWT access token.
- **`POST /api/auth/logout`**: Server-side JWT token revocation via token blocklist.
- **`GET /api/auth/me`**: Protected route (requires `Authorization: Bearer <token>`); returns current authenticated user profile and real-time database permissions array.

---

## 💼 Core CRM Modules (Step 4)

Complete implementation of the core CRM business modules connected to live MySQL data with zero hardcoded numbers.

### 1. Dashboard (`/api/dashboard/summary`)
- Live dynamic metrics: Total customers, New 30d customers, Active leads, Pipeline value, Won deals count, Pending tasks, Today's calls, Upcoming meetings.
- Deal stage breakdown and lead status aggregation.
- Real-time audit timeline from `activities` table.

### 2. Customers (`/api/customers`)
- **CRUD Operations**: Search, pagination, status filtering (`active`, `inactive`, `prospect`), sort.
- **Notes Feed**: `GET/POST /api/customers/<id>/notes`.
- **Secure File Storage**: `POST /api/customers/<id>/documents` with extension validation and 16MB cap.
- **360° Comprehensive Profile**: `GET /api/customers/<id>/details` aggregating customer overview, associated deals, tasks, calls, meetings, notes, and documents.

### 3. Leads & Conversion (`/api/leads`)
- Full lead lifecycle: `new` ➔ `contacted` ➔ `qualified` ➔ `proposal` ➔ `negotiation` ➔ `converted` / `lost`.
- Priority flags, estimated deal values, and source tracking.
- Touchpoint activity history: `GET/POST /api/leads/<id>/activities`.
- **Atomic Lead Conversion**: `POST /api/leads/<id>/convert` generates an active customer record and updates lead status.

### 4. Deals & Sales Pipeline Kanban (`/api/deals`)
- Interactive 6-stage Kanban board (`new`, `qualification`, `proposal`, `negotiation`, `won`, `lost`).
- `GET /api/deals/pipeline`: Computes counts and cumulative monetary value per stage.
- `PUT /api/deals/<id>/stage`: Stage transition with audit logging to `deal_activities`.

### 5. Tasks Management (`/api/tasks`)
- Priority and status filtering (`pending`, `in_progress`, `completed`, `cancelled`).
- Polymorphic relations (`customer`, `lead`, `deal`).
- Fast status toggle: `PUT /api/tasks/<id>/status` with completion timestamps.

### 6. Phone Calls (`/api/calls`)
- Log and schedule calls with customers or leads.
- Statuses: `scheduled`, `completed`, `missed`, `cancelled`.

### 7. Meetings & Consultations (`/api/meetings`)
- Schedule appointments with automated time validation (`end_time > start_time`).
- Location, type, and participant tracking.

---

## 📊 Business Modules & Financials (Step 5)

Full implementation of business, billing, reporting, notifications, and system administration modules:

### 1. Products & Services Catalog (`/api/products`)
- Product catalog management: Code, Name, Category, Price, Tax Rate, Discount, Inventory Stock, Status.
- Client search, category tabs, and validation (stock, price, tax 0–100%).

### 2. Invoices & Billing (`/api/invoices`)
- Invoices linked to customers and deals with auto-generated identifiers (`INV-YYYYMM-XXXX`).
- Server-side multi-item line item computations (subtotal, line discount, tax amount, total, balance).
- Real-time balance calculations and status tracking (`draft`, `sent`, `paid`, `partially_paid`, `overdue`, `cancelled`).

### 3. Payments Module (`/api/payments`)
- Payment records against invoices with payment methods (`cash`, `bank_transfer`, `credit_card`, `check`, `upi`, `online`).
- Auto payment numbers (`PAY-YYYYMM-XXXX`) and transaction reference numbers.
- **Overpayment Protection**: Strictly verifies payment does not exceed outstanding invoice balance.
- Automated invoice status updates to `paid` or `partially_paid`.

### 4. Emails & Templates (`/api/emails`)
- Communication history logging and template engine with merge tags (`{{customer_name}}`, `{{company}}`, `{{invoice_number}}`).
- **Safe Development Mode**: When SMTP credentials are unconfigured, saves message as draft with clear user notification.

### 5. Notifications Center (`/api/notifications`)
- In-app notification center with real-time unread counts and badge indicators in top navigation.
- Mark as read, mark all read, and entity association.

### 6. Reports & Analytics Engine (`/api/reports`)
- Comprehensive real-time reporting queried from database:
  - `GET /api/reports/sales`: Revenue trends, paid vs. unpaid metrics.
  - `GET /api/reports/pipeline`: Deals conversion rates and stage breakdown.
  - `GET /api/reports/leads`: Lead sources and status distributions.
  - `GET /api/reports/team`: Sales employee leaderboard and performance.

### 7. Users & Roles Administration (`/api/users`, `/api/roles`, `/api/permissions`)
- User employee management, activation/deactivation, and role management.
- Dynamic permission matrix inspection across 45 database permissions.

### 8. System Settings (`/api/settings`)
- Global CRM configuration: Company details, default currency, tax number, invoice prefix, date format.

---

## 🧪 Automated Testing

Apex CRM includes complete automated verification suites:

```powershell
# 1. Database Schema & Seed Verification (Step 2)
python database/test_db.py

# 2. Authentication, JWT & RBAC Verification (Step 3)
python backend/test_auth.py

# 3. Core CRM Modules Verification (Step 4)
python backend/test_step4_crm.py

# 4. Business Modules & Financials Verification (Step 5)
python backend/test_step5_crm.py

# 5. Full Production E2E Verification Suite (Step 6)
python backend/test_production_suite.py

# 6. Master Upgrade 20 Advanced Features Suite (Master Upgrade)
python backend/test_master_upgrade_suite.py
```

---

## 🚀 Running the Server & Frontend

### Development Mode:
```powershell
python backend/app.py
```
*(Listening at `http://127.0.0.1:5000`)*

### Production WSGI Mode (Gunicorn):
```bash
gunicorn -c backend/gunicorn_conf.py backend.app:app
```

### Open Frontend:
Run via local HTTP server:
```powershell
python -m http.server 8000 --directory frontend
```
Navigate to `http://localhost:8000`:
- **Landing Page**: `http://localhost:8000/index.html`
- **Login**: `http://localhost:8000/login.html`
- **Dashboard**: `http://localhost:8000/dashboard.html`
- **Customers**: `http://localhost:8000/customers.html`
- **Customer 360° Profile**: `http://localhost:8000/customer-details.html?id=1`
- **Leads**: `http://localhost:8000/leads.html`
- **Lead Details**: `http://localhost:8000/lead-details.html?id=1`
- **Deals Drag-and-Drop Pipeline**: `http://localhost:8000/deals.html`
- **Calendar (Aggregated)**: `http://localhost:8000/calendar.html`
- **Tasks**: `http://localhost:8000/tasks.html`
- **Calls**: `http://localhost:8000/calls.html`
- **Meetings**: `http://localhost:8000/meetings.html`
- **Products**: `http://localhost:8000/products.html`
- **Invoices**: `http://localhost:8000/invoices.html`
- **Payments**: `http://localhost:8000/payments.html`
- **Emails**: `http://localhost:8000/emails.html`
- **Notifications**: `http://localhost:8000/notifications.html`
- **Reports & Performance**: `http://localhost:8000/reports.html`
- **Audit Logs**: `http://localhost:8000/audit-logs.html`
- **Profile & Account**: `http://localhost:8000/profile.html`
- **Users**: `http://localhost:8000/users.html`
- **Settings & Backups**: `http://localhost:8000/settings.html`

---

## 🏆 CRM Master Upgrade – 20 Advanced Features

1. **Global Search (`GET /api/search?q=...`)**: Instant search across 10 modules with debounced dropdown & `Ctrl+K`.
2. **Advanced Multi-Filter System**: Filter, sort, and save named filter presets (`/api/filters`).
3. **Export Engine (CSV, Excel `.xlsx`, PDF)**: Styled OpenPyXL spreadsheets and ReportLab documents (`/api/export/<module>?format=...`).
4. **Print Optimization**: Clean `@media print` CSS layout for cards, profiles, tables, and invoice statements.
5. **ReportLab PDF Invoices**: Pixel-perfect invoice generation with company branding, tax breakdowns, and payment history.
6. **Email Engine**: 6 professional Jinja-compatible email templates with dynamic placeholder merge and SMTP delivery.
7. **Real-time Notification Center**: Filterable badge, mark read/unread, and priority alerting (`/api/notifications`).
8. **Unified CRM Calendar**: Interactive monthly agenda consolidating meetings, calls, tasks, and custom events (`/api/calendar/events`).
9. **Drag & Drop Deal Pipeline**: HTML5 interactive Kanban board with stage progression, probabilities, and revenue metrics.
10. **Customer 360° Profile**: Unified customer dashboard with lifetime value, outstanding balance, invoice history, and activity timeline (`/api/customers/<id>/360`).
11. **Security Audit Log Explorer**: Immutable security event ledger logging all mutations, previous/new value diffs, and IP addresses (`/api/audit-logs`).
12. **Document & File Management**: Whitelisted document uploads, secure UUID storage, and metadata indexing (`/api/documents`).
13. **Database Backup & Disaster Recovery**: On-demand SQL dumps, download, and double-confirmation restore (`/api/backup`).
14. **Bulk Import System**: CSV/Excel uploads with header mapping, error diagnostics, preview, and transactional commit (`/api/import`).
15. **Bulk Action Operations**: Batch delete, status change, and representative assignment on tables (`/api/<module>/bulk-action`).
16. **Executive Analytics Dashboard**: Conversion funnel, 6-month revenue trend, representative leaderboard, and date range filters (`/api/dashboard/summary?period=...`).
17. **Employee Performance Analytics**: Closed revenue, won deals, completed tasks, and logged calls per staff member (`/api/reports/employee-performance`).
18. **Automated Reminders**: Non-blocking background daemon thread actively monitoring meetings, tasks, and invoices (`/api/reminders`).
19. **Profile & Account Management**: Personal details editor, password updates, avatar uploader, and login history audit (`/api/users/profile`).
20. **Production Deployment Ready**: Environment configurations (`.env.example`), `.gitignore`, Gunicorn WSGI setup (`gunicorn_conf.py`), and end-to-end verification test suite.

---

## 📌 Implementation Roadmap
- [x] **Step 1: Project Setup & Professional Folder Structure**
- [x] **Step 2: MySQL Database + Complete CRM Database Schema**
- [x] **Step 3: User Authentication & Role-Based Access Control**
- [x] **Step 4: Core CRM Modules (Dashboard, Customers, Leads, Deals Pipeline, Tasks, Calls, Meetings)**
- [x] **Step 5: Business Modules (Products, Invoices, Payments, Emails, Notifications, Reports, Users, Settings)**
- [x] **Step 6: Finalization & Production Ready (Full Project Audit, Error Handlers, Responsive Design across 375px-1920px, Security Hardening)**
- [x] **Step 7: CRM Master Upgrade – 20 Advanced Features (Global Search, Bulk Actions, Calendar, 360° View, Audit Logs, Backups, PDF Engine, Import/Export, Analytics, WSGI)**


