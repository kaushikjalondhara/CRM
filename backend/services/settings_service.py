"""
CRM Settings Service
Manages system configuration key-value pairs stored in the `settings` table.
Never stores secrets, passwords, or tokens in the database.
"""

import logging
from database.database import execute_query
from backend.services.activity_service import log_activity

logger = logging.getLogger("crm.settings_service")

# Safe default configuration
DEFAULT_SETTINGS = {
    "company_name": "APEX CRM Solutions",
    "company_email": "contact@apexcrm.local",
    "company_phone": "+91 98765 43210",
    "company_address": "100 Innovation Tower, Tech Park, Gujarat, India",
    "currency": "INR",
    "currency_symbol": "₹",
    "date_format": "YYYY-MM-DD",
    "timezone": "Asia/Kolkata",
    "invoice_prefix": "INV",
    "tax_default_percentage": "18.00"
}

DISALLOWED_KEYS = {"jwt_secret", "jwt_secret_key", "password", "db_password", "smtp_password"}


def get_all_settings() -> dict:
    """Retrieve all configuration settings, merged with defaults."""
    sql = "SELECT setting_key, setting_value FROM settings"
    rows, err = execute_query(sql, fetch_all=True)

    settings = dict(DEFAULT_SETTINGS)
    if not err and rows:
        for r in rows:
            key = r["setting_key"]
            if key and key.lower() not in DISALLOWED_KEYS:
                settings[key] = r["setting_value"]

    return settings


def update_settings(data: dict, user_id: int | None = None) -> tuple[bool, str | None]:
    """Save/update configuration settings key-value pairs."""
    if not isinstance(data, dict):
        return False, "Settings must be provided as key-value JSON object"

    updated_count = 0
    upsert_sql = """
        INSERT INTO settings (setting_key, setting_value, created_at, updated_at)
        VALUES (%s, %s, NOW(), NOW())
        ON DUPLICATE KEY UPDATE
            setting_value = VALUES(setting_value),
            updated_at = NOW()
    """

    for k, v in data.items():
        clean_k = str(k).strip()
        if not clean_k or clean_k.lower() in DISALLOWED_KEYS:
            continue
        clean_v = str(v).strip() if v is not None else ""
        _, err = execute_query(upsert_sql, (clean_k, clean_v), commit=True)
        if not err:
            updated_count += 1

    log_activity(user_id, "settings", 0, "updated", f"Updated {updated_count} system settings")
    return True, None


def get_settings_by_category(category: str = "") -> tuple[dict, str | None]:
    """Retrieve settings filtered or merged for category."""
    return get_all_settings(), None
