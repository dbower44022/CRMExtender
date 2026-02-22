"""Tests for enhanced Google contact sync (Phase 20).

Covers:
- Phone/address type mappers from contacts_client
- Contact group (label) fetching and system group filtering
- Full extraction of new fields from mock API responses
- Sync of phones, addresses, titles, biographies, labels into DB
- Migration v13→v14 (contact_tags table)
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from poc.contacts_client import (
    _extract_addresses,
    _extract_labels,
    _extract_phones,
    _map_google_address_type,
    _map_google_phone_type,
    fetch_contact_groups,
    fetch_contacts,
)
from poc.database import get_connection, init_db
from poc.models import KnownContact, _now_iso
from poc.sync import (
    _add_address_if_new,
    _store_contact_labels,
    sync_contacts,
)

_NOW = datetime.now(timezone.utc).isoformat()
CUST_ID = "cust-test"
USER_ID = "user-admin"
ACCOUNT_EMAIL = "me@mycompany.com"


def _uid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES (?, 'Test Org', 'test', 1, ?, ?)",
            (CUST_ID, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES (?, ?, ?, 'Admin', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, ACCOUNT_EMAIL, _NOW, _NOW),
        )
        # Seed Employee role
        conn.execute(
            "INSERT INTO contact_company_roles "
            "(id, customer_id, name, is_system, created_at, updated_at) "
            "VALUES (?, ?, 'Employee', 1, ?, ?)",
            ("role-emp", CUST_ID, _NOW, _NOW),
        )
    return db_file


def _create_contact(name: str, email: str, *, customer_id: str = CUST_ID) -> str:
    """Insert a contact + email identifier and return contact_id."""
    cid = _uid()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO contacts "
            "(id, customer_id, name, source, status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'test', 'active', ?, ?)",
            (cid, customer_id, name, _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO contact_identifiers "
            "(id, contact_id, type, value, is_primary, created_at, updated_at) "
            "VALUES (?, ?, 'email', ?, 1, ?, ?)",
            (_uid(), cid, email.lower(), _NOW, _NOW),
        )
    return cid


# ===========================================================================
# TestGoogleTypeMappers
# ===========================================================================

class TestGoogleTypeMappers:
    """Phone and address type mapping from Google API to CRM types."""

    def test_phone_mobile(self):
        assert _map_google_phone_type("mobile") == "mobile"

    def test_phone_work(self):
        assert _map_google_phone_type("work") == "work"

    def test_phone_home(self):
        assert _map_google_phone_type("home") == "home"

    def test_phone_home_fax(self):
        assert _map_google_phone_type("homeFax") == "fax"

    def test_phone_work_fax(self):
        assert _map_google_phone_type("workFax") == "fax"

    def test_phone_other_fax(self):
        assert _map_google_phone_type("otherFax") == "fax"

    def test_phone_main(self):
        assert _map_google_phone_type("main") == "main"

    def test_phone_pager(self):
        assert _map_google_phone_type("pager") == "pager"

    def test_phone_unknown(self):
        assert _map_google_phone_type("satellite") == "other"

    def test_phone_empty(self):
        assert _map_google_phone_type("") == "other"

    def test_address_work(self):
        assert _map_google_address_type("work") == "work"

    def test_address_home(self):
        assert _map_google_address_type("home") == "home"

    def test_address_unknown(self):
        assert _map_google_address_type("vacation") == "other"

    def test_address_empty(self):
        assert _map_google_address_type("") == "other"


# ===========================================================================
# TestExtractHelpers
# ===========================================================================

class TestExtractHelpers:
    """Test _extract_phones, _extract_addresses, _extract_labels."""

    def test_extract_phones_basic(self):
        person = {
            "phoneNumbers": [
                {"value": "+1 555-0100", "type": "mobile"},
                {"value": "555-0200", "type": "work"},
            ],
        }
        phones = _extract_phones(person)
        assert len(phones) == 2
        assert phones[0] == {"number": "+1 555-0100", "type": "mobile"}
        assert phones[1] == {"number": "555-0200", "type": "work"}

    def test_extract_phones_empty_value_skipped(self):
        person = {"phoneNumbers": [{"value": "", "type": "mobile"}]}
        assert _extract_phones(person) == []

    def test_extract_phones_no_key(self):
        assert _extract_phones({}) == []

    def test_extract_addresses_basic(self):
        person = {
            "addresses": [
                {
                    "type": "work",
                    "streetAddress": "123 Main St",
                    "city": "Springfield",
                    "region": "IL",
                    "postalCode": "62704",
                    "country": "US",
                },
            ],
        }
        addrs = _extract_addresses(person)
        assert len(addrs) == 1
        assert addrs[0]["street"] == "123 Main St"
        assert addrs[0]["state"] == "IL"
        assert addrs[0]["type"] == "work"

    def test_extract_addresses_empty_fields_skipped(self):
        """An address with no substantive fields is skipped."""
        person = {"addresses": [{"type": "home"}]}
        assert _extract_addresses(person) == []

    def test_extract_labels(self):
        group_map = {
            "contactGroups/abc": "VIP Clients",
            "contactGroups/def": "Friends",
        }
        person = {
            "memberships": [
                {"contactGroupMembership": {"contactGroupResourceName": "contactGroups/abc"}},
                {"contactGroupMembership": {"contactGroupResourceName": "contactGroups/xyz"}},  # not in map
                {"contactGroupMembership": {"contactGroupResourceName": "contactGroups/def"}},
            ],
        }
        labels = _extract_labels(person, group_map)
        assert labels == ["VIP Clients", "Friends"]

    def test_extract_labels_empty(self):
        assert _extract_labels({}, {}) == []


# ===========================================================================
# TestFetchContactGroups
# ===========================================================================

class TestFetchContactGroups:
    """Contact group fetching and system group filtering."""

    def test_user_groups_returned(self):
        mock_service = MagicMock()
        mock_service.contactGroups.return_value.list.return_value.execute.return_value = {
            "contactGroups": [
                {
                    "resourceName": "contactGroups/abc",
                    "name": "VIP Clients",
                    "groupType": "USER_CONTACT_GROUP",
                },
                {
                    "resourceName": "contactGroups/myContacts",
                    "name": "myContacts",
                    "groupType": "SYSTEM_CONTACT_GROUP",
                },
                {
                    "resourceName": "contactGroups/def",
                    "name": "Friends",
                    "groupType": "USER_CONTACT_GROUP",
                },
            ],
        }

        with patch("poc.contacts_client.build", return_value=mock_service):
            groups = fetch_contact_groups(MagicMock())

        assert groups == {
            "contactGroups/abc": "VIP Clients",
            "contactGroups/def": "Friends",
        }

    def test_empty_groups(self):
        mock_service = MagicMock()
        mock_service.contactGroups.return_value.list.return_value.execute.return_value = {
            "contactGroups": [],
        }
        with patch("poc.contacts_client.build", return_value=mock_service):
            groups = fetch_contact_groups(MagicMock())
        assert groups == {}


# ===========================================================================
# TestFetchContactsEnhanced
# ===========================================================================

class TestFetchContactsEnhanced:
    """Full extraction from mock API response including new fields."""

    def _mock_api_response(self):
        return {
            "connections": [
                {
                    "resourceName": "people/123",
                    "names": [{"displayName": "Jane Doe"}],
                    "emailAddresses": [{"value": "jane@acme.com"}],
                    "organizations": [{"name": "Acme Corp", "title": "VP Engineering"}],
                    "phoneNumbers": [
                        {"value": "+1-555-0100", "type": "mobile"},
                        {"value": "555-0200", "type": "work"},
                    ],
                    "addresses": [
                        {
                            "type": "work",
                            "streetAddress": "100 Main St",
                            "city": "Portland",
                            "region": "OR",
                            "postalCode": "97201",
                            "country": "US",
                        },
                    ],
                    "biographies": [{"value": "Engineering leader at Acme."}],
                    "memberships": [
                        {"contactGroupMembership": {"contactGroupResourceName": "contactGroups/abc"}},
                    ],
                },
            ],
        }

    def test_all_fields_extracted(self):
        mock_service = MagicMock()
        mock_service.people.return_value.connections.return_value.list.return_value.execute.return_value = (
            self._mock_api_response()
        )

        group_map = {"contactGroups/abc": "VIP Clients"}

        with patch("poc.contacts_client.build", return_value=mock_service):
            contacts = fetch_contacts(MagicMock(), group_map=group_map)

        assert len(contacts) == 1
        kc = contacts[0]
        assert kc.email == "jane@acme.com"
        assert kc.name == "Jane Doe"
        assert kc.company == "Acme Corp"
        assert kc.title == "VP Engineering"
        assert kc.biography == "Engineering leader at Acme."
        assert kc.labels == ["VIP Clients"]
        assert len(kc.phones) == 2
        assert kc.phones[0]["number"] == "+1-555-0100"
        assert kc.phones[0]["type"] == "mobile"
        assert len(kc.addresses) == 1
        assert kc.addresses[0]["city"] == "Portland"

    def test_no_optional_fields(self):
        """Contact with only name+email should have empty optional fields."""
        mock_service = MagicMock()
        mock_service.people.return_value.connections.return_value.list.return_value.execute.return_value = {
            "connections": [
                {
                    "resourceName": "people/456",
                    "names": [{"displayName": "Bob"}],
                    "emailAddresses": [{"value": "bob@example.com"}],
                },
            ],
        }

        with patch("poc.contacts_client.build", return_value=mock_service):
            contacts = fetch_contacts(MagicMock())

        assert len(contacts) == 1
        kc = contacts[0]
        assert kc.title == ""
        assert kc.phones == []
        assert kc.addresses == []
        assert kc.biography == ""
        assert kc.labels == []


# ===========================================================================
# TestSyncContactsPhones
# ===========================================================================

class TestSyncContactsPhones:
    """Phone numbers stored during sync, with dedup."""

    def _make_kc(self, email="alice@acme.com", phones=None):
        return KnownContact(
            email=email,
            name="Alice",
            company="Acme",
            phones=phones or [{"number": "+15550100", "type": "mobile"}],
        )

    def test_phone_stored(self, tmp_db):
        kc = self._make_kc()

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            phones = conn.execute(
                "SELECT * FROM phone_numbers WHERE entity_type = 'contact'"
            ).fetchall()
        assert len(phones) >= 1
        numbers = [p["number"] for p in phones]
        assert any("+15550100" in n for n in numbers)

    def test_phone_dedup(self, tmp_db):
        """Running sync twice with same phone should not duplicate."""
        kc = self._make_kc()

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            phones = conn.execute(
                "SELECT * FROM phone_numbers WHERE entity_type = 'contact'"
            ).fetchall()
        # Dedup means at most 1 row for this number
        matching = [p for p in phones if "+15550100" in p["number"]]
        assert len(matching) == 1

    def test_multiple_phones(self, tmp_db):
        kc = self._make_kc(phones=[
            {"number": "+15550100", "type": "mobile"},
            {"number": "+15550200", "type": "work"},
        ])

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            phones = conn.execute(
                "SELECT * FROM phone_numbers WHERE entity_type = 'contact'"
            ).fetchall()
        assert len(phones) >= 2


# ===========================================================================
# TestSyncContactsAddresses
# ===========================================================================

class TestSyncContactsAddresses:
    """Addresses stored during sync, with dedup."""

    def _make_kc(self, email="bob@acme.com", addresses=None):
        return KnownContact(
            email=email,
            name="Bob",
            company="Acme",
            addresses=addresses or [
                {
                    "type": "work",
                    "street": "100 Main St",
                    "city": "Portland",
                    "state": "OR",
                    "postal_code": "97201",
                    "country": "US",
                },
            ],
        )

    def test_address_stored(self, tmp_db):
        kc = self._make_kc()

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            addrs = conn.execute(
                "SELECT * FROM addresses WHERE entity_type = 'contact'"
            ).fetchall()
        assert len(addrs) == 1
        assert addrs[0]["street"] == "100 Main St"
        assert addrs[0]["city"] == "Portland"

    def test_address_dedup(self, tmp_db):
        """Same address twice should not duplicate."""
        kc = self._make_kc()

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            addrs = conn.execute(
                "SELECT * FROM addresses WHERE entity_type = 'contact'"
            ).fetchall()
        assert len(addrs) == 1

    def test_different_addresses_both_stored(self, tmp_db):
        kc = self._make_kc(addresses=[
            {"type": "work", "street": "100 Main St", "city": "Portland",
             "state": "OR", "postal_code": "97201", "country": "US"},
            {"type": "home", "street": "200 Oak Ave", "city": "Eugene",
             "state": "OR", "postal_code": "97401", "country": "US"},
        ])

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            addrs = conn.execute(
                "SELECT * FROM addresses WHERE entity_type = 'contact'"
            ).fetchall()
        assert len(addrs) == 2


# ===========================================================================
# TestSyncContactsTitle
# ===========================================================================

class TestSyncContactsTitle:
    """Title stored on affiliation."""

    def test_title_set_on_new_affiliation(self, tmp_db):
        kc = KnownContact(
            email="carol@acme.com",
            name="Carol",
            company="Acme Corp",
            title="VP Sales",
        )

        # Create a company for domain resolution to find
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO companies (id, name, domain, status, customer_id, created_at, updated_at) "
                "VALUES ('co-acme', 'Acme Corp', 'acme.com', 'active', ?, ?, ?)",
                (CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO company_identifiers (id, company_id, type, value, is_primary, created_at, updated_at) "
                "VALUES (?, 'co-acme', 'domain', 'acme.com', 1, ?, ?)",
                (_uid(), _NOW, _NOW),
            )

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            cc = conn.execute(
                "SELECT title FROM contact_companies WHERE company_id = 'co-acme'"
            ).fetchone()
        assert cc is not None
        assert cc["title"] == "VP Sales"

    def test_title_not_overwritten_if_existing(self, tmp_db):
        """If a title already exists on the affiliation, it should not be overwritten."""
        # Create company
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO companies (id, name, domain, status, customer_id, created_at, updated_at) "
                "VALUES ('co-acme2', 'Acme', 'acme2.com', 'active', ?, ?, ?)",
                (CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO company_identifiers (id, company_id, type, value, is_primary, created_at, updated_at) "
                "VALUES (?, 'co-acme2', 'domain', 'acme2.com', 1, ?, ?)",
                (_uid(), _NOW, _NOW),
            )

        # First sync sets title
        kc1 = KnownContact(email="dan@acme2.com", name="Dan", company="Acme", title="CTO")
        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc1]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        # Second sync with different title should NOT overwrite
        kc2 = KnownContact(email="dan@acme2.com", name="Dan", company="Acme", title="VP Engineering")
        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc2]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            cc = conn.execute(
                "SELECT title FROM contact_companies WHERE company_id = 'co-acme2'"
            ).fetchone()
        assert cc["title"] == "CTO"


# ===========================================================================
# TestSyncContactsBiography
# ===========================================================================

class TestSyncContactsBiography:
    """Biography creates a note for new contacts only."""

    def test_biography_note_created(self, tmp_db):
        kc = KnownContact(
            email="eve@example.com",
            name="Eve",
            biography="Senior architect with 10 years experience.",
        )

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            notes = conn.execute("SELECT * FROM notes").fetchall()
            assert len(notes) == 1
            assert notes[0]["title"] == "Google Biography"

            # Check note_entities link
            ne = conn.execute(
                "SELECT * FROM note_entities WHERE entity_type = 'contact'"
            ).fetchall()
            assert len(ne) == 1

    def test_biography_not_duplicated_on_resync(self, tmp_db):
        """Re-syncing an existing contact should not create another note."""
        kc = KnownContact(
            email="frank@example.com",
            name="Frank",
            biography="Consultant.",
        )

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            notes = conn.execute("SELECT * FROM notes").fetchall()
        assert len(notes) == 1

    def test_no_biography_no_note(self, tmp_db):
        kc = KnownContact(email="grace@example.com", name="Grace")

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            notes = conn.execute("SELECT * FROM notes").fetchall()
        assert len(notes) == 0


# ===========================================================================
# TestSyncContactsLabels
# ===========================================================================

class TestSyncContactsLabels:
    """Labels create tags + contact_tags."""

    def test_labels_stored(self, tmp_db):
        kc = KnownContact(
            email="heidi@example.com",
            name="Heidi",
            labels=["VIP Clients", "Partners"],
        )

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            tags = conn.execute("SELECT * FROM tags ORDER BY name").fetchall()
            ct = conn.execute("SELECT * FROM contact_tags").fetchall()

        tag_names = {t["name"] for t in tags}
        assert "vip clients" in tag_names
        assert "partners" in tag_names
        assert len(ct) == 2

    def test_labels_case_normalized(self, tmp_db):
        kc = KnownContact(
            email="ivan@example.com",
            name="Ivan",
            labels=["VIP Clients"],
        )

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            tag = conn.execute("SELECT name FROM tags").fetchone()
        assert tag["name"] == "vip clients"

    def test_labels_dedup_on_resync(self, tmp_db):
        kc = KnownContact(
            email="judy@example.com",
            name="Judy",
            labels=["Team Alpha"],
        )

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)
            sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        with get_connection() as conn:
            ct = conn.execute("SELECT * FROM contact_tags").fetchall()
        assert len(ct) == 1


# ===========================================================================
# TestAddAddressIfNew
# ===========================================================================

class TestAddAddressIfNew:
    """Direct tests for the _add_address_if_new helper."""

    def test_new_address_added(self, tmp_db):
        cid = _create_contact("Test", "test@example.com")
        result = _add_address_if_new(cid, {
            "type": "home",
            "street": "50 Oak Lane",
            "city": "Austin",
            "state": "TX",
            "postal_code": "78701",
            "country": "US",
        })
        assert result is not None
        assert result["street"] == "50 Oak Lane"

    def test_duplicate_address_skipped(self, tmp_db):
        cid = _create_contact("Test2", "test2@example.com")
        addr = {
            "type": "home",
            "street": "50 Oak Lane",
            "city": "Austin",
            "state": "TX",
            "postal_code": "78701",
            "country": "US",
        }
        first = _add_address_if_new(cid, addr)
        second = _add_address_if_new(cid, addr)
        assert first is not None
        assert second is None


# ===========================================================================
# TestStoreContactLabels
# ===========================================================================

class TestStoreContactLabels:
    """Direct tests for the _store_contact_labels helper."""

    def test_creates_tags_and_links(self, tmp_db):
        cid = _create_contact("Label Test", "lt@example.com")
        count = _store_contact_labels(cid, ["Alpha", "Beta"], customer_id=CUST_ID)
        assert count == 2

        with get_connection() as conn:
            ct = conn.execute(
                "SELECT * FROM contact_tags WHERE contact_id = ?", (cid,)
            ).fetchall()
        assert len(ct) == 2

    def test_empty_labels_ignored(self, tmp_db):
        cid = _create_contact("Empty", "empty@example.com")
        count = _store_contact_labels(cid, ["", "  "], customer_id=CUST_ID)
        assert count == 0

    def test_source_set_to_google(self, tmp_db):
        cid = _create_contact("Source", "source@example.com")
        _store_contact_labels(cid, ["MyGroup"], customer_id=CUST_ID)

        with get_connection() as conn:
            tag = conn.execute("SELECT source FROM tags").fetchone()
            ct = conn.execute("SELECT source FROM contact_tags").fetchone()
        assert tag["source"] == "google_contacts"
        assert ct["source"] == "google_contacts"


# ===========================================================================
# TestMigrationV14
# ===========================================================================

class TestMigrationV14:
    """Migration script v13→v14."""

    def test_creates_table_and_bumps_version(self, tmp_path):
        from poc.migrate_to_v14 import migrate

        # Create a v13 database
        db_file = tmp_path / "test_migrate.db"
        init_db(db_file)

        conn = sqlite3.connect(str(db_file))
        conn.execute("PRAGMA user_version = 13")
        conn.commit()
        conn.close()

        migrate(db_file, dry_run=False)

        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 14

        # Verify contact_tags table exists
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "contact_tags" in tables

        # Verify indexes exist
        indexes = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_contact_tags_contact" in indexes
        assert "idx_contact_tags_tag" in indexes

        conn.close()

    def test_dry_run_preserves_original(self, tmp_path):
        from poc.migrate_to_v14 import migrate

        db_file = tmp_path / "test_dryrun.db"
        init_db(db_file)

        conn = sqlite3.connect(str(db_file))
        conn.execute("PRAGMA user_version = 13")
        conn.commit()
        conn.close()

        migrate(db_file, dry_run=True)

        # Original should still be v13
        conn = sqlite3.connect(str(db_file))
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 13
        conn.close()


# ===========================================================================
# TestSyncContactsIntegration
# ===========================================================================

class TestSyncContactsIntegration:
    """End-to-end integration: all fields in a single sync."""

    def test_full_sync_with_all_fields(self, tmp_db):
        # Create company for domain resolution
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO companies (id, name, domain, status, customer_id, created_at, updated_at) "
                "VALUES ('co-integ', 'Integ Corp', 'integ.com', 'active', ?, ?, ?)",
                (CUST_ID, _NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO company_identifiers (id, company_id, type, value, is_primary, created_at, updated_at) "
                "VALUES (?, 'co-integ', 'domain', 'integ.com', 1, ?, ?)",
                (_uid(), _NOW, _NOW),
            )

        kc = KnownContact(
            email="full@integ.com",
            name="Full Contact",
            company="Integ Corp",
            title="Director",
            phones=[
                {"number": "+15550001", "type": "mobile"},
                {"number": "+15550002", "type": "work"},
            ],
            addresses=[
                {"type": "work", "street": "1 Corp Way", "city": "Denver",
                 "state": "CO", "postal_code": "80202", "country": "US"},
            ],
            biography="A seasoned professional.",
            labels=["Team Lead", "Remote"],
        )

        with patch("poc.sync.fetch_contact_groups", return_value={}), \
             patch("poc.sync.fetch_contacts", return_value=[kc]):
            count = sync_contacts(MagicMock(), customer_id=CUST_ID, user_id=USER_ID)

        assert count == 1

        with get_connection() as conn:
            # Contact created
            contact = conn.execute(
                "SELECT * FROM contacts WHERE name = 'Full Contact'"
            ).fetchone()
            assert contact is not None

            contact_id = contact["id"]

            # Affiliation with title
            cc = conn.execute(
                "SELECT title FROM contact_companies WHERE contact_id = ? AND company_id = 'co-integ'",
                (contact_id,),
            ).fetchone()
            assert cc["title"] == "Director"

            # Phones
            phones = conn.execute(
                "SELECT number FROM phone_numbers WHERE entity_id = ? ORDER BY number",
                (contact_id,),
            ).fetchall()
            numbers = [p["number"] for p in phones]
            assert "+15550001" in numbers
            assert "+15550002" in numbers

            # Address
            addrs = conn.execute(
                "SELECT * FROM addresses WHERE entity_id = ?",
                (contact_id,),
            ).fetchall()
            assert len(addrs) == 1
            assert addrs[0]["city"] == "Denver"

            # Biography note
            notes = conn.execute("SELECT * FROM notes").fetchall()
            assert len(notes) == 1

            # Labels
            ct = conn.execute(
                "SELECT * FROM contact_tags WHERE contact_id = ?",
                (contact_id,),
            ).fetchall()
            assert len(ct) == 2
            tags = conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
            tag_names = [t["name"] for t in tags]
            assert "remote" in tag_names
            assert "team lead" in tag_names
