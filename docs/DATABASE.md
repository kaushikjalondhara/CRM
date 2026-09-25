# Database Architecture & Schema Documentation

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
