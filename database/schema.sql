-- ==========================================================
-- CRM System — Complete Production Database Schema (Step 2)
-- Database: crm_database
-- Character Set: utf8mb4, Collation: utf8mb4_unicode_ci
-- ==========================================================

CREATE DATABASE IF NOT EXISTS `crm_database`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `crm_database`;

-- Disable foreign key checks during schema generation
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------------------------------------
-- 1. ROLES TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `roles`;
CREATE TABLE `roles` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(50) NOT NULL UNIQUE,
  `description` VARCHAR(255) NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 2. PERMISSIONS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `permissions`;
CREATE TABLE `permissions` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(100) NOT NULL UNIQUE,
  `description` VARCHAR(255) NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 3. ROLE PERMISSIONS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `role_permissions`;
CREATE TABLE `role_permissions` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `role_id` INT NOT NULL,
  `permission_id` INT NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `unique_role_permission` (`role_id`, `permission_id`),
  CONSTRAINT `fk_role_permissions_role` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_role_permissions_permission` FOREIGN KEY (`permission_id`) REFERENCES `permissions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 4. USERS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `role_id` INT NOT NULL,
  `first_name` VARCHAR(100) NOT NULL,
  `last_name` VARCHAR(100) NOT NULL,
  `email` VARCHAR(191) NOT NULL UNIQUE,
  `phone` VARCHAR(25) NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `profile_image` VARCHAR(255) NULL,
  `status` ENUM('active', 'inactive', 'suspended') NOT NULL DEFAULT 'active',
  `last_login` DATETIME NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_users_role` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE RESTRICT,
  INDEX `idx_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 5. CUSTOMERS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `customers`;
CREATE TABLE `customers` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `customer_code` VARCHAR(50) NOT NULL UNIQUE,
  `first_name` VARCHAR(100) NOT NULL,
  `last_name` VARCHAR(100) NOT NULL,
  `company_name` VARCHAR(150) NULL,
  `email` VARCHAR(191) NULL,
  `phone` VARCHAR(25) NULL,
  `alternate_phone` VARCHAR(25) NULL,
  `address` TEXT NULL,
  `city` VARCHAR(100) NULL,
  `state` VARCHAR(100) NULL,
  `country` VARCHAR(100) NULL,
  `pincode` VARCHAR(20) NULL,
  `industry` VARCHAR(100) NULL,
  `customer_type` VARCHAR(50) NULL,
  `status` ENUM('active', 'inactive', 'prospect', 'blocked') NOT NULL DEFAULT 'prospect',
  `assigned_to` INT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_customers_assigned_to` FOREIGN KEY (`assigned_to`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  INDEX `idx_customers_email` (`email`),
  INDEX `idx_customers_phone` (`phone`),
  INDEX `idx_customers_company_name` (`company_name`),
  INDEX `idx_customers_status` (`status`),
  INDEX `idx_customers_assigned_to` (`assigned_to`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 6. CUSTOMER DOCUMENTS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `customer_documents`;
CREATE TABLE `customer_documents` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `customer_id` INT NOT NULL,
  `file_name` VARCHAR(255) NOT NULL,
  `file_path` VARCHAR(255) NOT NULL,
  `file_type` VARCHAR(50) NULL,
  `file_size` INT NULL,
  `uploaded_by` INT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_cust_docs_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_cust_docs_uploader` FOREIGN KEY (`uploaded_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 7. CUSTOMER NOTES TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `customer_notes`;
CREATE TABLE `customer_notes` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `customer_id` INT NOT NULL,
  `user_id` INT NULL,
  `note` TEXT NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_cust_notes_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_cust_notes_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 8. LEADS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `leads`;
CREATE TABLE `leads` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `lead_code` VARCHAR(50) NOT NULL UNIQUE,
  `first_name` VARCHAR(100) NOT NULL,
  `last_name` VARCHAR(100) NOT NULL,
  `company_name` VARCHAR(150) NULL,
  `email` VARCHAR(191) NULL,
  `phone` VARCHAR(25) NULL,
  `source` VARCHAR(100) NULL,
  `industry` VARCHAR(100) NULL,
  `status` ENUM('new', 'contacted', 'qualified', 'proposal', 'negotiation', 'converted', 'lost') NOT NULL DEFAULT 'new',
  `priority` ENUM('low', 'medium', 'high', 'urgent') NOT NULL DEFAULT 'medium',
  `expected_value` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  `assigned_to` INT NULL,
  `follow_up_date` DATE NULL,
  `notes` TEXT NULL,
  `converted_customer_id` INT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_leads_assigned_to` FOREIGN KEY (`assigned_to`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_leads_converted_cust` FOREIGN KEY (`converted_customer_id`) REFERENCES `customers` (`id`) ON DELETE SET NULL,
  INDEX `idx_leads_email` (`email`),
  INDEX `idx_leads_phone` (`phone`),
  INDEX `idx_leads_status` (`status`),
  INDEX `idx_leads_assigned_to` (`assigned_to`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 9. LEAD ACTIVITIES TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `lead_activities`;
CREATE TABLE `lead_activities` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `lead_id` INT NOT NULL,
  `user_id` INT NULL,
  `activity_type` ENUM('call', 'email', 'meeting', 'note', 'status_change', 'follow_up') NOT NULL,
  `description` TEXT NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_lead_act_lead` FOREIGN KEY (`lead_id`) REFERENCES `leads` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_lead_act_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 10. DEALS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `deals`;
CREATE TABLE `deals` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `deal_code` VARCHAR(50) NOT NULL UNIQUE,
  `lead_id` INT NULL,
  `customer_id` INT NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `description` TEXT NULL,
  `value` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  `stage` ENUM('new', 'qualification', 'proposal', 'negotiation', 'won', 'lost') NOT NULL DEFAULT 'new',
  `probability` INT NOT NULL DEFAULT 0,
  `expected_close_date` DATE NULL,
  `assigned_to` INT NULL,
  `status` ENUM('open', 'won', 'lost', 'cancelled') NOT NULL DEFAULT 'open',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_deals_lead` FOREIGN KEY (`lead_id`) REFERENCES `leads` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_deals_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_deals_assigned_to` FOREIGN KEY (`assigned_to`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  INDEX `idx_deals_stage` (`stage`),
  INDEX `idx_deals_status` (`status`),
  INDEX `idx_deals_assigned_to` (`assigned_to`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 11. DEAL ACTIVITIES TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `deal_activities`;
CREATE TABLE `deal_activities` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `deal_id` INT NOT NULL,
  `user_id` INT NULL,
  `activity_type` VARCHAR(50) NOT NULL,
  `description` TEXT NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_deal_act_deal` FOREIGN KEY (`deal_id`) REFERENCES `deals` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_deal_act_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 12. TASKS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `tasks`;
CREATE TABLE `tasks` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `title` VARCHAR(200) NOT NULL,
  `description` TEXT NULL,
  `customer_id` INT NULL,
  `lead_id` INT NULL,
  `deal_id` INT NULL,
  `assigned_to` INT NULL,
  `priority` ENUM('low', 'medium', 'high', 'urgent') NOT NULL DEFAULT 'medium',
  `status` ENUM('pending', 'in_progress', 'completed', 'cancelled') NOT NULL DEFAULT 'pending',
  `due_date` DATETIME NULL,
  `completed_at` DATETIME NULL,
  `created_by` INT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_tasks_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_tasks_lead` FOREIGN KEY (`lead_id`) REFERENCES `leads` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_tasks_deal` FOREIGN KEY (`deal_id`) REFERENCES `deals` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_tasks_assigned_to` FOREIGN KEY (`assigned_to`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_tasks_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  INDEX `idx_tasks_status` (`status`),
  INDEX `idx_tasks_due_date` (`due_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 13. CALLS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `calls`;
CREATE TABLE `calls` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `customer_id` INT NULL,
  `lead_id` INT NULL,
  `deal_id` INT NULL,
  `assigned_to` INT NULL,
  `call_date` DATE NOT NULL,
  `call_time` TIME NULL,
  `purpose` VARCHAR(255) NULL,
  `status` ENUM('scheduled', 'completed', 'missed', 'cancelled') NOT NULL DEFAULT 'scheduled',
  `notes` TEXT NULL,
  `created_by` INT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_calls_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_calls_lead` FOREIGN KEY (`lead_id`) REFERENCES `leads` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_calls_deal` FOREIGN KEY (`deal_id`) REFERENCES `deals` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_calls_assigned_to` FOREIGN KEY (`assigned_to`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_calls_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 14. MEETINGS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `meetings`;
CREATE TABLE `meetings` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `title` VARCHAR(200) NOT NULL,
  `customer_id` INT NULL,
  `lead_id` INT NULL,
  `deal_id` INT NULL,
  `assigned_to` INT NULL,
  `meeting_date` DATE NOT NULL,
  `start_time` TIME NOT NULL,
  `end_time` TIME NULL,
  `location` VARCHAR(255) NULL,
  `meeting_type` VARCHAR(50) NULL,
  `participants` TEXT NULL,
  `status` ENUM('scheduled', 'completed', 'cancelled') NOT NULL DEFAULT 'scheduled',
  `notes` TEXT NULL,
  `created_by` INT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_meetings_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_meetings_lead` FOREIGN KEY (`lead_id`) REFERENCES `leads` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_meetings_deal` FOREIGN KEY (`deal_id`) REFERENCES `deals` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_meetings_assigned_to` FOREIGN KEY (`assigned_to`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_meetings_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 15. PRODUCTS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `products`;
CREATE TABLE `products` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `product_code` VARCHAR(50) NOT NULL UNIQUE,
  `name` VARCHAR(200) NOT NULL,
  `category` VARCHAR(100) NULL,
  `description` TEXT NULL,
  `price` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  `tax_percentage` DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
  `discount_percentage` DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
  `stock` INT NOT NULL DEFAULT 0,
  `status` ENUM('active', 'inactive', 'out_of_stock') NOT NULL DEFAULT 'active',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 16. INVOICES TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `invoices`;
CREATE TABLE `invoices` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `invoice_number` VARCHAR(50) NOT NULL UNIQUE,
  `customer_id` INT NOT NULL,
  `deal_id` INT NULL,
  `invoice_date` DATE NOT NULL,
  `due_date` DATE NOT NULL,
  `subtotal` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  `tax_amount` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  `discount_amount` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  `total_amount` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  `paid_amount` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  `remaining_amount` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  `status` ENUM('draft', 'sent', 'paid', 'partially_paid', 'overdue', 'cancelled') NOT NULL DEFAULT 'draft',
  `notes` TEXT NULL,
  `created_by` INT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_invoices_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_invoices_deal` FOREIGN KEY (`deal_id`) REFERENCES `deals` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_invoices_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  INDEX `idx_invoices_number` (`invoice_number`),
  INDEX `idx_invoices_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 17. INVOICE ITEMS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `invoice_items`;
CREATE TABLE `invoice_items` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `invoice_id` INT NOT NULL,
  `product_id` INT NULL,
  `description` VARCHAR(255) NULL,
  `quantity` INT NOT NULL DEFAULT 1,
  `unit_price` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  `tax_percentage` DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
  `discount_percentage` DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
  `total` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_inv_items_invoice` FOREIGN KEY (`invoice_id`) REFERENCES `invoices` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_inv_items_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 18. PAYMENTS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `payments`;
CREATE TABLE `payments` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `invoice_id` INT NOT NULL,
  `customer_id` INT NOT NULL,
  `amount` DECIMAL(15, 2) NOT NULL,
  `payment_method` ENUM('cash', 'upi', 'card', 'bank_transfer', 'other') NOT NULL,
  `transaction_reference` VARCHAR(100) NULL,
  `payment_date` DATE NOT NULL,
  `notes` TEXT NULL,
  `created_by` INT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_payments_invoice` FOREIGN KEY (`invoice_id`) REFERENCES `invoices` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_payments_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_payments_created_by` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  INDEX `idx_payments_date` (`payment_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 19. EMAILS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `emails`;
CREATE TABLE `emails` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `customer_id` INT NULL,
  `lead_id` INT NULL,
  `deal_id` INT NULL,
  `sender_id` INT NULL,
  `recipient_email` VARCHAR(191) NOT NULL,
  `subject` VARCHAR(255) NOT NULL,
  `message` TEXT NOT NULL,
  `status` ENUM('draft', 'sent', 'failed') NOT NULL DEFAULT 'draft',
  `sent_at` DATETIME NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_emails_customer` FOREIGN KEY (`customer_id`) REFERENCES `customers` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_emails_lead` FOREIGN KEY (`lead_id`) REFERENCES `leads` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_emails_deal` FOREIGN KEY (`deal_id`) REFERENCES `deals` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_emails_sender` FOREIGN KEY (`sender_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 20. EMAIL TEMPLATES TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `email_templates`;
CREATE TABLE `email_templates` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(100) NOT NULL UNIQUE,
  `subject` VARCHAR(255) NOT NULL,
  `body` TEXT NOT NULL,
  `created_by` INT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT `fk_email_templates_creator` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 21. NOTIFICATIONS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `notifications`;
CREATE TABLE `notifications` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `title` VARCHAR(200) NOT NULL,
  `message` TEXT NOT NULL,
  `type` ENUM('task', 'meeting', 'call', 'payment', 'invoice', 'lead', 'deal', 'system') NOT NULL,
  `related_type` VARCHAR(50) NULL,
  `related_id` INT NULL,
  `is_read` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_notifications_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  INDEX `idx_notifications_user_id` (`user_id`),
  INDEX `idx_notifications_is_read` (`is_read`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 22. ACTIVITIES TABLE (Global Timeline)
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `activities`;
CREATE TABLE `activities` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NULL,
  `entity_type` VARCHAR(50) NOT NULL,
  `entity_id` INT NOT NULL,
  `activity_type` VARCHAR(50) NOT NULL,
  `description` TEXT NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_activities_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  INDEX `idx_activities_entity` (`entity_type`, `entity_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------
-- 23. SETTINGS TABLE
-- ----------------------------------------------------------
DROP TABLE IF EXISTS `settings`;
CREATE TABLE `settings` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `setting_key` VARCHAR(100) NOT NULL UNIQUE,
  `setting_value` TEXT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;


-- ==========================================================
-- SEED DATA
-- ==========================================================

-- ----------------------------------------------------------
-- A. Default Roles
-- ----------------------------------------------------------
INSERT INTO `roles` (`name`, `description`) VALUES
('Admin', 'System administrator with full system and security access'),
('Manager', 'Sales and operations manager with team management and reporting access'),
('Sales Employee', 'Sales representative handling leads, customers, deals, and tasks'),
('Staff', 'Operational staff member with standard task and record viewing access')
ON DUPLICATE KEY UPDATE `description` = VALUES(`description`);

-- ----------------------------------------------------------
-- B. Permissions
-- ----------------------------------------------------------
INSERT INTO `permissions` (`name`, `description`) VALUES
('dashboard.view', 'View executive analytics dashboard'),

('customers.view', 'View customer records and documents'),
('customers.create', 'Create new customer records'),
('customers.update', 'Update customer records'),
('customers.delete', 'Delete customer records'),

('leads.view', 'View leads and lead activities'),
('leads.create', 'Create new leads'),
('leads.update', 'Update lead records'),
('leads.delete', 'Delete leads'),
('leads.convert', 'Convert lead to customer'),

('deals.view', 'View deals and pipelines'),
('deals.create', 'Create new deal opportunities'),
('deals.update', 'Update deal stages and values'),
('deals.delete', 'Delete deals'),

('tasks.view', 'View task lists and calendars'),
('tasks.create', 'Create new tasks'),
('tasks.update', 'Update task progress and status'),
('tasks.delete', 'Delete tasks'),

('calls.view', 'View call logs'),
('calls.create', 'Schedule and record calls'),
('calls.update', 'Update call logs'),
('calls.delete', 'Delete call logs'),

('meetings.view', 'View meetings schedule'),
('meetings.create', 'Schedule new meetings'),
('meetings.update', 'Update meeting details'),
('meetings.delete', 'Cancel or delete meetings'),

('products.view', 'View product catalog and pricing'),
('products.create', 'Create products in catalog'),
('products.update', 'Update product information and stock'),
('products.delete', 'Delete products from catalog'),

('invoices.view', 'View invoices and billing'),
('invoices.create', 'Generate invoices'),
('invoices.update', 'Update invoice details'),
('invoices.delete', 'Delete or void invoices'),

('payments.view', 'View payment transaction history'),
('payments.create', 'Record new customer payments'),
('payments.update', 'Update payment records'),
('payments.delete', 'Delete payment records'),

('reports.view', 'Generate and view CRM analytics reports'),

('users.view', 'View user profiles'),
('users.create', 'Create user accounts'),
('users.update', 'Update user profiles and statuses'),
('users.delete', 'Deactivate or delete user accounts'),

('settings.view', 'View system settings'),
('settings.update', 'Modify system settings')
ON DUPLICATE KEY UPDATE `description` = VALUES(`description`);

-- ----------------------------------------------------------
-- C. Role Permissions Matrix
-- ----------------------------------------------------------

-- 1. Admin: Receives ALL permissions
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id
FROM `roles` r
CROSS JOIN `permissions` p
WHERE r.name = 'Admin';

-- 2. Manager: Dashboard, Customers, Leads, Deals, Tasks, Calls, Meetings, Products View, Invoices View, Payments View, Reports View, Users View, Settings View
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id
FROM `roles` r
CROSS JOIN `permissions` p
WHERE r.name = 'Manager'
  AND (
    p.name LIKE 'dashboard.%' OR
    p.name LIKE 'customers.%' OR
    p.name LIKE 'leads.%' OR
    p.name LIKE 'deals.%' OR
    p.name LIKE 'tasks.%' OR
    p.name LIKE 'calls.%' OR
    p.name LIKE 'meetings.%' OR
    p.name IN ('products.view', 'invoices.view', 'payments.view', 'reports.view', 'users.view', 'settings.view')
  );

-- 3. Sales Employee: Dashboard, Customers (view, create, update), Leads (all), Deals (all), Tasks (view, create, update), Calls (all), Meetings (all), Products View, Invoices View
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id
FROM `roles` r
CROSS JOIN `permissions` p
WHERE r.name = 'Sales Employee'
  AND p.name IN (
    'dashboard.view',
    'customers.view', 'customers.create', 'customers.update',
    'leads.view', 'leads.create', 'leads.update', 'leads.convert',
    'deals.view', 'deals.create', 'deals.update',
    'tasks.view', 'tasks.create', 'tasks.update',
    'calls.view', 'calls.create', 'calls.update',
    'meetings.view', 'meetings.create', 'meetings.update',
    'products.view',
    'invoices.view'
  );

-- 4. Staff: Dashboard View, Customers View, Tasks (view, update), Calls View, Meetings View, Products View
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id
FROM `roles` r
CROSS JOIN `permissions` p
WHERE r.name = 'Staff'
  AND p.name IN (
    'dashboard.view',
    'customers.view',
    'tasks.view', 'tasks.update',
    'calls.view',
    'meetings.view',
    'products.view'
  );

-- ----------------------------------------------------------
-- D. Default Demo Users Across Roles
-- Passwords (development only):
--   Admin:          Admin@123456
--   Manager:        Manager@123456
--   Sales Employee: Sales@123456
--   Staff:          Staff@123456
--   Inactive User:  Inactive@123456
-- Hashed using secure Werkzeug scrypt format
-- ----------------------------------------------------------
INSERT INTO `users` (`role_id`, `first_name`, `last_name`, `email`, `phone`, `password_hash`, `status`)
SELECT r.id, 'Super', 'Admin', 'admin@crm.local', '+1-555-0100',
  'scrypt:32768:8:1$VZM2MFSG2uskfIj1$0cc66b74a71d7115a88b773b5ee0b3758b62ffe60528e3b14b3d75e2e859429aecbb6e901a59ac73000f6272fbd2c8b93a78a9686c06fbd10feaeb506b61e745',
  'active'
FROM `roles` r WHERE r.name = 'Admin'
ON DUPLICATE KEY UPDATE `first_name` = VALUES(`first_name`), `last_name` = VALUES(`last_name`);

INSERT INTO `users` (`role_id`, `first_name`, `last_name`, `email`, `phone`, `password_hash`, `status`)
SELECT r.id, 'Morgan', 'Manager', 'manager@crm.local', '+1-555-0101',
  'scrypt:32768:8:1$9Lgz4WXIwcQa237s$7dcdd649b636bd3c6da151bcb12e2302cc31d5b62e73a78875874f720e0130d3a74f15cf7e7c2357d05439ad1767bbedceddc901b7842401fa94c06346af7b5b',
  'active'
FROM `roles` r WHERE r.name = 'Manager'
ON DUPLICATE KEY UPDATE `first_name` = VALUES(`first_name`), `last_name` = VALUES(`last_name`);

INSERT INTO `users` (`role_id`, `first_name`, `last_name`, `email`, `phone`, `password_hash`, `status`)
SELECT r.id, 'Sarah', 'Sales', 'sales@crm.local', '+1-555-0102',
  'scrypt:32768:8:1$z0YMyL53aXDrpsgX$4cff470149fff1c06fdcbeef582a94d15d0df0fa6ed9dc6ffc9ec143032970276c4d563f7d17ca84141116db9762ab54d174da476fa56899865bde2f819afe10',
  'active'
FROM `roles` r WHERE r.name = 'Sales Employee'
ON DUPLICATE KEY UPDATE `first_name` = VALUES(`first_name`), `last_name` = VALUES(`last_name`);

INSERT INTO `users` (`role_id`, `first_name`, `last_name`, `email`, `phone`, `password_hash`, `status`)
SELECT r.id, 'Steve', 'Staff', 'staff@crm.local', '+1-555-0103',
  'scrypt:32768:8:1$LttrBHLXnQjMf9ME$e82bc44299ea637147a2da2c8786b680817482cb84f0db559e876cab637e2b153a4e0fe9764b720727e5e92c2f9c447ad73c99ec53473bd66c1a7b74545c13ab',
  'active'
FROM `roles` r WHERE r.name = 'Staff'
ON DUPLICATE KEY UPDATE `first_name` = VALUES(`first_name`), `last_name` = VALUES(`last_name`);

INSERT INTO `users` (`role_id`, `first_name`, `last_name`, `email`, `phone`, `password_hash`, `status`)
SELECT r.id, 'Ian', 'Inactive', 'inactive@crm.local', '+1-555-0104',
  'scrypt:32768:8:1$dbDt7mrhmtNM6atu$b2dcd0d8afc8f5d38a3652bc4974889fdf31b75ca368b49a38382393879eb728a2f44da80d642a8fb67547f99c38efef6b992943d4b79523df21c82b447ca6b1',
  'inactive'
FROM `roles` r WHERE r.name = 'Staff'
ON DUPLICATE KEY UPDATE `first_name` = VALUES(`first_name`), `last_name` = VALUES(`last_name`);

-- ----------------------------------------------------------
-- E. System Settings Seed
-- ----------------------------------------------------------
INSERT INTO `settings` (`setting_key`, `setting_value`) VALUES
('system_name', 'Apex Enterprise CRM'),
('company_name', 'Apex Dynamics Inc.'),
('default_currency', 'USD'),
('default_timezone', 'UTC'),
('lead_auto_assignment', 'true'),
('invoice_due_days', '30')
ON DUPLICATE KEY UPDATE `setting_value` = VALUES(`setting_value`);
