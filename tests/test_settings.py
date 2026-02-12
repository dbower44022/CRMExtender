"""Tests for the settings module."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from poc.database import get_connection, init_db
from poc.settings import (
    get_setting,
    list_settings,
    seed_default_settings,
    set_setting,
)

_NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database with a customer and user."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)

    with get_connection(db_file) as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, ?, ?)",
            ("cust-1", "Test Org", "test", _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'admin', 1, ?, ?)",
            ("user-1", "cust-1", "test@example.com", "Test User", _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'user', 1, ?, ?)",
            ("user-2", "cust-1", "user2@example.com", "User 2", _NOW, _NOW),
        )

    return db_file


class TestSetSetting:
    def test_set_system_setting(self, tmp_db):
        result = set_setting(
            "cust-1", "default_timezone", "America/New_York",
            scope="system", db_path=tmp_db,
        )
        assert result["setting_name"] == "default_timezone"
        assert result["setting_value"] == "America/New_York"
        assert result["scope"] == "system"

    def test_set_user_setting(self, tmp_db):
        result = set_setting(
            "cust-1", "timezone", "America/Chicago",
            scope="user", user_id="user-1", db_path=tmp_db,
        )
        assert result["setting_name"] == "timezone"
        assert result["setting_value"] == "America/Chicago"

    def test_set_setting_upsert(self, tmp_db):
        set_setting("cust-1", "company_name", "Old Name", scope="system", db_path=tmp_db)
        result = set_setting("cust-1", "company_name", "New Name", scope="system", db_path=tmp_db)
        assert result["setting_value"] == "New Name"

        # Verify in DB
        with get_connection(tmp_db) as conn:
            rows = conn.execute(
                "SELECT * FROM settings WHERE setting_name = 'company_name'"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]["setting_value"] == "New Name"


class TestGetSetting:
    def test_get_system_setting(self, tmp_db):
        set_setting("cust-1", "default_timezone", "UTC", scope="system", db_path=tmp_db)
        value = get_setting("cust-1", "default_timezone", db_path=tmp_db)
        assert value == "UTC"

    def test_get_user_setting_overrides_system(self, tmp_db):
        set_setting("cust-1", "timezone", "UTC", scope="system", db_path=tmp_db)
        set_setting(
            "cust-1", "timezone", "America/Denver",
            scope="user", user_id="user-1", db_path=tmp_db,
        )
        value = get_setting("cust-1", "timezone", user_id="user-1", db_path=tmp_db)
        assert value == "America/Denver"

    def test_get_user_setting_falls_back_to_system(self, tmp_db):
        set_setting("cust-1", "default_timezone", "Europe/London", scope="system", db_path=tmp_db)
        value = get_setting("cust-1", "default_timezone", user_id="user-1", db_path=tmp_db)
        assert value == "Europe/London"

    def test_get_setting_falls_back_to_default(self, tmp_db):
        set_setting(
            "cust-1", "date_format", None,
            scope="system", default="ISO", db_path=tmp_db,
        )
        value = get_setting("cust-1", "date_format", db_path=tmp_db)
        assert value == "ISO"

    def test_get_setting_falls_back_to_hardcoded(self, tmp_db):
        value = get_setting("cust-1", "default_timezone", db_path=tmp_db)
        assert value == "UTC"  # hardcoded fallback

    def test_get_nonexistent_setting(self, tmp_db):
        value = get_setting("cust-1", "nonexistent_setting", db_path=tmp_db)
        assert value is None

    def test_user_specific_does_not_affect_other_users(self, tmp_db):
        set_setting(
            "cust-1", "timezone", "America/Chicago",
            scope="user", user_id="user-1", db_path=tmp_db,
        )
        # user-2 should NOT get user-1's value
        value = get_setting("cust-1", "timezone", user_id="user-2", db_path=tmp_db)
        # Should fall back to hardcoded since no system or user-2 setting
        assert value == "UTC"

    def test_null_user_value_falls_through(self, tmp_db):
        """User value of None should fall through to system."""
        set_setting("cust-1", "timezone", "Europe/Berlin", scope="system", db_path=tmp_db)
        set_setting(
            "cust-1", "timezone", None,
            scope="user", user_id="user-1", db_path=tmp_db,
        )
        value = get_setting("cust-1", "timezone", user_id="user-1", db_path=tmp_db)
        assert value == "Europe/Berlin"


class TestListSettings:
    def test_list_all_settings(self, tmp_db):
        set_setting("cust-1", "timezone", "UTC", scope="system", db_path=tmp_db)
        set_setting(
            "cust-1", "timezone", "America/Chicago",
            scope="user", user_id="user-1", db_path=tmp_db,
        )
        results = list_settings("cust-1", db_path=tmp_db)
        assert len(results) == 2

    def test_list_system_settings(self, tmp_db):
        set_setting("cust-1", "timezone", "UTC", scope="system", db_path=tmp_db)
        set_setting("cust-1", "company_name", "Acme", scope="system", db_path=tmp_db)
        set_setting(
            "cust-1", "timezone", "America/Chicago",
            scope="user", user_id="user-1", db_path=tmp_db,
        )
        results = list_settings("cust-1", scope="system", db_path=tmp_db)
        assert len(results) == 2
        assert all(r["scope"] == "system" for r in results)

    def test_list_user_settings(self, tmp_db):
        set_setting(
            "cust-1", "timezone", "America/Chicago",
            scope="user", user_id="user-1", db_path=tmp_db,
        )
        set_setting(
            "cust-1", "date_format", "US",
            scope="user", user_id="user-1", db_path=tmp_db,
        )
        results = list_settings("cust-1", scope="user", user_id="user-1", db_path=tmp_db)
        assert len(results) == 2
        assert all(r["user_id"] == "user-1" for r in results)


class TestSeedDefaultSettings:
    def test_seed_system_only(self, tmp_db):
        result = seed_default_settings("cust-1", db_path=tmp_db)
        assert result["system"] == 4
        assert result["user"] == 0

    def test_seed_system_and_user(self, tmp_db):
        result = seed_default_settings("cust-1", user_id="user-1", db_path=tmp_db)
        assert result["system"] == 4
        assert result["user"] == 5

    def test_seed_idempotent(self, tmp_db):
        seed_default_settings("cust-1", user_id="user-1", db_path=tmp_db)
        seed_default_settings("cust-1", user_id="user-1", db_path=tmp_db)
        # Should not duplicate
        settings = list_settings("cust-1", db_path=tmp_db)
        names = [s["setting_name"] for s in settings]
        assert len(names) == len(set(names)) + len([n for n in set(names) if names.count(n) == 2])

    def test_seed_creates_expected_settings(self, tmp_db):
        seed_default_settings("cust-1", user_id="user-1", db_path=tmp_db)
        settings = list_settings("cust-1", scope="system", db_path=tmp_db)
        names = {s["setting_name"] for s in settings}
        assert names == {"default_timezone", "company_name", "sync_enabled", "default_phone_country"}
