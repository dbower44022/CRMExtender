"""Unified settings system (system + user scopes)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .database import get_connection

# Hardcoded fallback defaults (last resort)
_HARDCODED_DEFAULTS = {
    "default_timezone": "UTC",
    "company_name": "CRM Extender",
    "sync_enabled": "true",
    "timezone": "UTC",
    "start_of_week": "monday",
    "date_format": "ISO",
    "default_phone_country": "US",
}


def get_setting(
    customer_id: str,
    name: str,
    *,
    user_id: str | None = None,
    db_path=None,
) -> str | None:
    """Resolve a setting value using the cascade:

    1. User-specific value (if user_id provided and value is set)
    2. System setting value (customer-wide)
    3. Setting default (from setting_default column)
    4. Hardcoded fallback
    """
    with get_connection(db_path) as conn:
        # 1. Check user-specific value
        if user_id:
            row = conn.execute(
                "SELECT setting_value, setting_default FROM settings "
                "WHERE customer_id = ? AND user_id = ? AND scope = 'user' "
                "AND setting_name = ?",
                (customer_id, user_id, name),
            ).fetchone()
            if row and row["setting_value"] is not None:
                return row["setting_value"]

        # 2. Check system setting value
        row = conn.execute(
            "SELECT setting_value, setting_default FROM settings "
            "WHERE customer_id = ? AND scope = 'system' AND setting_name = ?",
            (customer_id, name),
        ).fetchone()
        if row:
            if row["setting_value"] is not None:
                return row["setting_value"]
            if row["setting_default"] is not None:
                return row["setting_default"]

        # 3. Check user setting_default if we had a user row
        if user_id:
            row = conn.execute(
                "SELECT setting_default FROM settings "
                "WHERE customer_id = ? AND user_id = ? AND scope = 'user' "
                "AND setting_name = ?",
                (customer_id, user_id, name),
            ).fetchone()
            if row and row["setting_default"] is not None:
                return row["setting_default"]

    # 4. Hardcoded fallback
    return _HARDCODED_DEFAULTS.get(name)


def set_setting(
    customer_id: str,
    name: str,
    value: str | None,
    *,
    scope: str = "system",
    user_id: str | None = None,
    description: str | None = None,
    default: str | None = None,
    db_path=None,
) -> dict:
    """Set a setting value. Creates the row if it doesn't exist (upsert)."""
    now = datetime.now(timezone.utc).isoformat()

    with get_connection(db_path) as conn:
        if scope == "system":
            existing = conn.execute(
                "SELECT id FROM settings "
                "WHERE customer_id = ? AND scope = 'system' AND setting_name = ?",
                (customer_id, name),
            ).fetchone()
        else:
            existing = conn.execute(
                "SELECT id FROM settings "
                "WHERE customer_id = ? AND user_id = ? AND scope = 'user' AND setting_name = ?",
                (customer_id, user_id, name),
            ).fetchone()

        if existing:
            setting_id = existing["id"]
            conn.execute(
                "UPDATE settings SET setting_value = ?, updated_at = ? WHERE id = ?",
                (value, now, setting_id),
            )
        else:
            setting_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO settings "
                "(id, customer_id, user_id, scope, setting_name, setting_value, "
                "setting_description, setting_default, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (setting_id, customer_id, user_id if scope == "user" else None,
                 scope, name, value, description, default, now, now),
            )

    return {
        "id": setting_id,
        "customer_id": customer_id,
        "scope": scope,
        "setting_name": name,
        "setting_value": value,
    }


def list_settings(
    customer_id: str,
    *,
    scope: str | None = None,
    user_id: str | None = None,
    db_path=None,
) -> list[dict]:
    """List settings for a customer, optionally filtered by scope and user."""
    with get_connection(db_path) as conn:
        if scope == "user" and user_id:
            rows = conn.execute(
                "SELECT * FROM settings "
                "WHERE customer_id = ? AND scope = 'user' AND user_id = ? "
                "ORDER BY setting_name",
                (customer_id, user_id),
            ).fetchall()
        elif scope == "system":
            rows = conn.execute(
                "SELECT * FROM settings "
                "WHERE customer_id = ? AND scope = 'system' "
                "ORDER BY setting_name",
                (customer_id,),
            ).fetchall()
        else:
            params = [customer_id]
            query = "SELECT * FROM settings WHERE customer_id = ?"
            if user_id:
                query += " AND (scope = 'system' OR (scope = 'user' AND user_id = ?))"
                params.append(user_id)
            query += " ORDER BY scope, setting_name"
            rows = conn.execute(query, params).fetchall()

    return [dict(r) for r in rows]


def seed_default_settings(
    customer_id: str,
    *,
    user_id: str | None = None,
    db_path=None,
) -> dict:
    """Seed default system and optionally user settings. Returns counts."""
    system_settings = [
        ("default_timezone", "UTC", "Default timezone for new users"),
        ("company_name", "Default Organization", "Organization display name"),
        ("sync_enabled", "true", "Enable/disable automatic sync"),
        ("default_phone_country", "US", "Default country for phone numbers"),
    ]

    system_count = 0
    for name, default, desc in system_settings:
        result = set_setting(
            customer_id, name, default,
            scope="system", description=desc, default=default,
            db_path=db_path,
        )
        system_count += 1

    user_count = 0
    if user_id:
        user_settings = [
            ("timezone", None, "Preferred timezone"),
            ("start_of_week", "monday", "First day of week"),
            ("date_format", "ISO", "Date display format"),
            ("profile_photo", None, "Profile photo path or URL"),
            ("contact_id", None, "Link to own contact record"),
        ]

        for name, default, desc in user_settings:
            set_setting(
                customer_id, name, default,
                scope="user", user_id=user_id,
                description=desc, default=default,
                db_path=db_path,
            )
            user_count += 1

    return {"system": system_count, "user": user_count}
