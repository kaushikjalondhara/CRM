"""
CRM Database Package
Contains database connection management, schema definitions, and migration utilities.
"""
from .database import (
    get_db_config,
    get_db_connection,
    get_db_cursor,
    execute_query,
    init_db,
    check_db_connection,
)

__all__ = [
    "get_db_config",
    "get_db_connection",
    "get_db_cursor",
    "execute_query",
    "init_db",
    "check_db_connection",
]
