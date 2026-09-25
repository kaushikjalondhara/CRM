# Apex CRM – REST API Reference

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
