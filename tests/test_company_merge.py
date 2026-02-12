"""Tests for company duplicate detection and merging."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from poc.company_merge import (
    detect_all_duplicates,
    find_duplicates_for_domain,
    get_merge_preview,
    merge_companies,
    normalize_domain,
)
from poc.database import get_connection, init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc).isoformat()


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
    init_db(db_file)

    # Seed customer + user for auth bypass mode
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, slug, is_active, created_at, updated_at) "
            "VALUES ('cust-test', 'Test Org', 'test', 1, ?, ?)",
            (_NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO users "
            "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
            "VALUES ('user-test', 'cust-test', 'test@example.com', 'Test User', "
            "'admin', 1, ?, ?)",
            (_NOW, _NOW),
        )

    return db_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_company(conn, company_id, name="Acme Corp", domain="acme.com",
                    customer_id="cust-test"):
    conn.execute(
        "INSERT OR IGNORE INTO companies "
        "(id, name, domain, status, customer_id, created_at, updated_at) "
        "VALUES (?, ?, ?, 'active', ?, ?, ?)",
        (company_id, name, domain, customer_id, _NOW, _NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO user_companies "
        "(id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
        "VALUES (?, 'user-test', ?, 'public', 1, ?, ?)",
        (f"uco-{company_id}", company_id, _NOW, _NOW),
    )


def _insert_identifier(conn, company_id, value, type_="domain", id_=None):
    import uuid
    conn.execute(
        "INSERT OR IGNORE INTO company_identifiers "
        "(id, company_id, type, value, is_primary, source, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 0, 'test', ?, ?)",
        (id_ or str(uuid.uuid4()), company_id, type_, value, _NOW, _NOW),
    )


def _insert_contact(conn, contact_id, name="Alice", email="alice@acme.com"):
    conn.execute(
        "INSERT OR IGNORE INTO contacts "
        "(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (contact_id, name, _NOW, _NOW),
    )
    conn.execute(
        "INSERT OR IGNORE INTO contact_identifiers "
        "(id, contact_id, type, value, created_at, updated_at) "
        "VALUES (?, ?, 'email', ?, ?, ?)",
        (f"ci-{contact_id}", contact_id, email, _NOW, _NOW),
    )


def _link_contact(conn, contact_id, company_id):
    """Create a contact_companies affiliation row."""
    import uuid as _uuid
    conn.execute(
        "INSERT OR IGNORE INTO contact_companies "
        "(id, contact_id, company_id, is_primary, is_current, source, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, 1, 1, 'test', ?, ?)",
        (str(_uuid.uuid4()), contact_id, company_id, _NOW, _NOW),
    )


def _insert_relationship(conn, rel_id, from_type, from_id, to_type, to_id,
                          type_id="rt-knows", source="manual", paired_id=None):
    conn.execute(
        "INSERT OR IGNORE INTO relationships "
        "(id, relationship_type_id, from_entity_type, from_entity_id, "
        "to_entity_type, to_entity_id, paired_relationship_id, source, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (rel_id, type_id, from_type, from_id, to_type, to_id,
         paired_id, source, _NOW, _NOW),
    )


def _insert_event(conn, event_id, title="Meeting"):
    conn.execute(
        "INSERT OR IGNORE INTO events "
        "(id, title, event_type, status, source, created_at, updated_at) "
        "VALUES (?, ?, 'meeting', 'confirmed', 'manual', ?, ?)",
        (event_id, title, _NOW, _NOW),
    )


def _insert_event_participant(conn, event_id, entity_type, entity_id):
    conn.execute(
        "INSERT OR IGNORE INTO event_participants "
        "(event_id, entity_type, entity_id) VALUES (?, ?, ?)",
        (event_id, entity_type, entity_id),
    )


def _insert_hierarchy(conn, hierarchy_id, parent_id, child_id,
                       hierarchy_type="subsidiary"):
    conn.execute(
        "INSERT OR IGNORE INTO company_hierarchy "
        "(id, parent_company_id, child_company_id, hierarchy_type, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (hierarchy_id, parent_id, child_id, hierarchy_type, _NOW, _NOW),
    )


def _insert_phone(conn, phone_id, entity_type, entity_id, number="555-1234"):
    conn.execute(
        "INSERT OR IGNORE INTO phone_numbers "
        "(id, entity_type, entity_id, phone_type, number, is_primary, "
        "source, created_at, updated_at) "
        "VALUES (?, ?, ?, 'main', ?, 0, '', ?, ?)",
        (phone_id, entity_type, entity_id, number, _NOW, _NOW),
    )


def _insert_address(conn, addr_id, entity_type, entity_id):
    conn.execute(
        "INSERT OR IGNORE INTO addresses "
        "(id, entity_type, entity_id, address_type, city, is_primary, "
        "source, created_at, updated_at) "
        "VALUES (?, ?, ?, 'work', 'Test City', 0, '', ?, ?)",
        (addr_id, entity_type, entity_id, _NOW, _NOW),
    )


def _insert_email_address(conn, email_id, entity_type, entity_id,
                            address="info@acme.com"):
    conn.execute(
        "INSERT OR IGNORE INTO email_addresses "
        "(id, entity_type, entity_id, email_type, address, is_primary, "
        "source, created_at, updated_at) "
        "VALUES (?, ?, ?, 'general', ?, 0, '', ?, ?)",
        (email_id, entity_type, entity_id, address, _NOW, _NOW),
    )


def _insert_social_profile(conn, profile_id, company_id, platform="twitter",
                             url="https://twitter.com/acme"):
    conn.execute(
        "INSERT OR IGNORE INTO company_social_profiles "
        "(id, company_id, platform, profile_url, username, source, "
        "created_at, updated_at) "
        "VALUES (?, ?, ?, ?, '', 'test', ?, ?)",
        (profile_id, company_id, platform, url, _NOW, _NOW),
    )


# ===================================================================
# TestNormalizeDomain
# ===================================================================

class TestNormalizeDomain:
    def test_lowercase(self):
        assert normalize_domain("ACME.COM") == "acme.com"

    def test_strip_www(self):
        assert normalize_domain("www.acme.com") == "acme.com"

    def test_subdomain(self):
        assert normalize_domain("mail.acme.com") == "acme.com"

    def test_strip_protocol(self):
        assert normalize_domain("https://acme.com/about") == "acme.com"

    def test_strip_protocol_with_www(self):
        assert normalize_domain("https://www.acme.com/about?q=1") == "acme.com"

    def test_empty(self):
        assert normalize_domain("") == ""

    def test_none(self):
        assert normalize_domain(None) == ""

    def test_country_tld_co_uk(self):
        assert normalize_domain("acme.co.uk") == "acme.co.uk"

    def test_country_tld_com_au(self):
        assert normalize_domain("www.acme.com.au") == "acme.com.au"

    def test_country_tld_subdomain(self):
        assert normalize_domain("mail.acme.co.uk") == "acme.co.uk"

    def test_simple_two_parts(self):
        assert normalize_domain("acme.com") == "acme.com"

    def test_http_prefix(self):
        assert normalize_domain("http://acme.com") == "acme.com"

    def test_path_without_protocol(self):
        assert normalize_domain("acme.com/about") == "acme.com"

    def test_whitespace(self):
        assert normalize_domain("  acme.com  ") == "acme.com"


# ===================================================================
# TestFindDuplicates
# ===================================================================

class TestFindDuplicates:
    def test_finds_by_company_domain(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme Corp", "acme.com")
        result = find_duplicates_for_domain("acme.com")
        assert len(result) == 1
        assert result[0]["id"] == "c1"

    def test_finds_by_identifier(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme Corp", "")
            _insert_identifier(conn, "c1", "acme.com")
        result = find_duplicates_for_domain("acme.com")
        assert len(result) == 1
        assert result[0]["id"] == "c1"

    def test_skips_public_domains(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Gmail Inc", "gmail.com")
        result = find_duplicates_for_domain("gmail.com")
        assert result == []

    def test_no_matches_returns_empty(self, tmp_db):
        result = find_duplicates_for_domain("nonexistent.com")
        assert result == []

    def test_normalises_input(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme Corp", "acme.com")
        result = find_duplicates_for_domain("https://www.acme.com/about")
        assert len(result) == 1


# ===================================================================
# TestDetectAllDuplicates
# ===================================================================

class TestDetectAllDuplicates:
    def test_groups_by_domain(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme Corp", "acme.com")
            _insert_company(conn, "c2", "Acme Corporation", "acme.com")
        groups = detect_all_duplicates()
        assert len(groups) == 1
        assert groups[0]["domain"] == "acme.com"
        ids = {c["id"] for c in groups[0]["companies"]}
        assert ids == {"c1", "c2"}

    def test_no_duplicates(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme Corp", "acme.com")
            _insert_company(conn, "c2", "Beta Inc", "beta.com")
        groups = detect_all_duplicates()
        assert groups == []

    def test_groups_via_identifier(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme Corp", "acme.com")
            _insert_company(conn, "c2", "Acme Old", "")
            _insert_identifier(conn, "c2", "acme.com")
        groups = detect_all_duplicates()
        assert len(groups) == 1

    def test_skips_public_domains(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Gmail 1", "gmail.com")
            _insert_company(conn, "c2", "Gmail 2", "gmail.com")
        groups = detect_all_duplicates()
        assert groups == []


# ===================================================================
# TestMergePreview
# ===================================================================

class TestMergePreview:
    def test_counts_contacts(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            _insert_contact(conn, "ct1")
            _link_contact(conn, "ct1", "abs")
            _insert_contact(conn, "ct2", name="Bob", email="bob@acme.com")
            _link_contact(conn, "ct2", "abs")
        preview = get_merge_preview("surv", "abs")
        assert preview["contacts"] == 2

    def test_counts_relationships(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            _insert_relationship(conn, "r1", "company", "abs",
                                  "company", "surv")
        preview = get_merge_preview("surv", "abs")
        assert preview["relationships"] == 1

    def test_counts_events(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            _insert_event(conn, "ev1")
            _insert_event_participant(conn, "ev1", "company", "abs")
        preview = get_merge_preview("surv", "abs")
        assert preview["events"] == 1

    def test_identifies_duplicate_relationships(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            _insert_company(conn, "third", "Third Co", "third.com")
            # Both companies have a KNOWS rel to the same third company
            _insert_relationship(conn, "r1", "company", "surv",
                                  "company", "third", type_id="rt-partner")
            _insert_relationship(conn, "r2", "company", "abs",
                                  "company", "third", type_id="rt-partner")
        preview = get_merge_preview("surv", "abs")
        assert preview["duplicate_relationships"] == 1

    def test_nonexistent_raises(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
        with pytest.raises(ValueError):
            get_merge_preview("surv", "nonexistent")


# ===================================================================
# TestMergeExecution
# ===================================================================

class TestMergeExecution:
    def test_reassigns_contacts(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            _insert_contact(conn, "ct1")
            _link_contact(conn, "ct1", "abs")

        result = merge_companies("surv", "abs")
        assert result["contacts_reassigned"] == 1

        with get_connection() as conn:
            ct = conn.execute(
                "SELECT company_id FROM contact_companies WHERE contact_id = 'ct1'"
            ).fetchone()
            assert ct["company_id"] == "surv"

    def test_reassigns_relationships(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            _insert_company(conn, "other", "Other", "other.com")
            _insert_relationship(conn, "r1", "company", "abs",
                                  "company", "other", type_id="rt-partner")

        result = merge_companies("surv", "abs")
        assert result["relationships_reassigned"] >= 1

        with get_connection() as conn:
            r = conn.execute(
                "SELECT from_entity_id FROM relationships WHERE id = 'r1'"
            ).fetchone()
            assert r["from_entity_id"] == "surv"

    def test_reassigns_event_participants(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            _insert_event(conn, "ev1")
            _insert_event_participant(conn, "ev1", "company", "abs")

        result = merge_companies("surv", "abs")
        assert result["events_reassigned"] == 1

        with get_connection() as conn:
            ep = conn.execute(
                "SELECT entity_id FROM event_participants WHERE event_id = 'ev1'"
            ).fetchone()
            assert ep["entity_id"] == "surv"

    def test_transfers_identifiers(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "")
            _insert_identifier(conn, "abs", "acme2.com")

        merge_companies("surv", "abs")

        with get_connection() as conn:
            ids = conn.execute(
                "SELECT value FROM company_identifiers WHERE company_id = 'surv' AND type = 'domain'"
            ).fetchall()
            values = {r["value"] for r in ids}
            assert "acme2.com" in values

    def test_transfers_hierarchy(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            _insert_company(conn, "child", "Child Co", "child.com")
            _insert_hierarchy(conn, "h1", "abs", "child")

        merge_companies("surv", "abs")

        with get_connection() as conn:
            h = conn.execute(
                "SELECT parent_company_id FROM company_hierarchy WHERE id = 'h1'"
            ).fetchone()
            assert h["parent_company_id"] == "surv"

    def test_transfers_sub_entities(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            _insert_phone(conn, "p1", "company", "abs")
            _insert_address(conn, "a1", "company", "abs")
            _insert_email_address(conn, "e1", "company", "abs")

        merge_companies("surv", "abs")

        with get_connection() as conn:
            phone = conn.execute(
                "SELECT entity_id FROM phone_numbers WHERE id = 'p1'"
            ).fetchone()
            assert phone["entity_id"] == "surv"
            addr = conn.execute(
                "SELECT entity_id FROM addresses WHERE id = 'a1'"
            ).fetchone()
            assert addr["entity_id"] == "surv"
            email = conn.execute(
                "SELECT entity_id FROM email_addresses WHERE id = 'e1'"
            ).fetchone()
            assert email["entity_id"] == "surv"

    def test_deduplicates_relationships(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            _insert_company(conn, "third", "Third Co", "third.com")
            # Both have partner rel to third
            _insert_relationship(conn, "r1", "company", "surv",
                                  "company", "third", type_id="rt-partner")
            _insert_relationship(conn, "r2", "company", "abs",
                                  "company", "third", type_id="rt-partner")

        result = merge_companies("surv", "abs")
        # The duplicate absorbed relationship should have been removed
        # before reassignment, so only the surviving one remains
        with get_connection() as conn:
            count = conn.execute(
                """SELECT COUNT(*) AS cnt FROM relationships
                   WHERE from_entity_id = 'surv'
                     AND to_entity_id = 'third'
                     AND relationship_type_id = 'rt-partner'"""
            ).fetchone()["cnt"]
            assert count == 1

    def test_backfills_empty_fields(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "")
            conn.execute(
                "UPDATE companies SET industry = '', description = '' WHERE id = 'surv'"
            )
            _insert_company(conn, "abs", "Absorbed", "acme.com")
            conn.execute(
                "UPDATE companies SET industry = 'Tech', description = 'Great co' WHERE id = 'abs'"
            )

        merge_companies("surv", "abs")

        with get_connection() as conn:
            c = conn.execute(
                "SELECT domain, industry, description FROM companies WHERE id = 'surv'"
            ).fetchone()
            assert c["domain"] == "acme.com"
            assert c["industry"] == "Tech"
            assert c["description"] == "Great co"

    def test_surviving_fields_not_overwritten(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "surviving.com")
            conn.execute(
                "UPDATE companies SET industry = 'Finance' WHERE id = 'surv'"
            )
            _insert_company(conn, "abs", "Absorbed", "absorbed.com")
            conn.execute(
                "UPDATE companies SET industry = 'Tech' WHERE id = 'abs'"
            )

        merge_companies("surv", "abs")

        with get_connection() as conn:
            c = conn.execute(
                "SELECT industry FROM companies WHERE id = 'surv'"
            ).fetchone()
            assert c["industry"] == "Finance"

    def test_deletes_absorbed_company(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")

        merge_companies("surv", "abs")

        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM companies WHERE id = 'abs'"
            ).fetchone()
            assert row is None

    def test_creates_audit_log(self, tmp_db):
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO customers (id, name, slug, is_active, created_at, updated_at) "
                "VALUES ('cust-test', 'Test', 'test', 1, ?, ?)",
                (_NOW, _NOW),
            )
            conn.execute(
                "INSERT INTO users (id, customer_id, email, name, created_at, updated_at) "
                "VALUES ('user-1', 'cust-test', 'user@test.com', 'Test User', ?, ?)",
                (_NOW, _NOW),
            )
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")

        result = merge_companies("surv", "abs", merged_by="user-1")

        with get_connection() as conn:
            log = conn.execute(
                "SELECT * FROM company_merges WHERE id = ?",
                (result["merge_id"],),
            ).fetchone()
            assert log is not None
            assert log["surviving_company_id"] == "surv"
            assert log["absorbed_company_id"] == "abs"
            assert log["merged_by"] == "user-1"

    def test_snapshot_contains_full_data(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            _insert_identifier(conn, "abs", "acme2.com")
            _insert_phone(conn, "p1", "company", "abs", "555-0001")

        result = merge_companies("surv", "abs")

        with get_connection() as conn:
            log = conn.execute(
                "SELECT absorbed_company_snapshot FROM company_merges WHERE id = ?",
                (result["merge_id"],),
            ).fetchone()
            snapshot = json.loads(log["absorbed_company_snapshot"])
            assert snapshot["name"] == "Absorbed"
            assert len(snapshot["identifiers"]) >= 1
            assert len(snapshot["phones"]) == 1

    def test_validation_same_company(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme", "acme.com")
        with pytest.raises(ValueError, match="itself"):
            merge_companies("c1", "c1")

    def test_validation_nonexistent(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme", "acme.com")
        with pytest.raises(ValueError):
            merge_companies("c1", "nonexistent")

    def test_transfers_social_profiles(self, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            _insert_social_profile(conn, "sp1", "abs", "linkedin",
                                    "https://linkedin.com/company/abs")

        merge_companies("surv", "abs")

        with get_connection() as conn:
            profiles = conn.execute(
                "SELECT * FROM company_social_profiles WHERE company_id = 'surv'"
            ).fetchall()
            assert len(profiles) >= 1
            urls = {p["profile_url"] for p in profiles}
            assert "https://linkedin.com/company/abs" in urls

    def test_repoints_prior_merge_audit_records(self, tmp_db):
        """If the absorbed company was surviving in a prior merge, the
        company_merges FK must be re-pointed so DELETE doesn't violate FK."""
        with get_connection() as conn:
            _insert_company(conn, "old", "Old Co", "old.com")
            _insert_company(conn, "mid", "Mid Co", "mid.com")
            _insert_company(conn, "final", "Final Co", "final.com")

        # First merge: mid absorbs old
        merge_companies("mid", "old")

        # Second merge: final absorbs mid — this must not raise FK error
        merge_companies("final", "mid")

        with get_connection() as conn:
            # Both merge audit rows should now point to "final"
            rows = conn.execute(
                "SELECT surviving_company_id FROM company_merges ORDER BY merged_at"
            ).fetchall()
            assert all(r["surviving_company_id"] == "final" for r in rows)

    def test_transfers_user_company_visibility(self, tmp_db):
        """Users with visibility to the absorbed company should gain visibility
        to the surviving company."""
        with get_connection() as conn:
            # Create a second user
            conn.execute(
                "INSERT INTO users "
                "(id, customer_id, email, name, role, is_active, created_at, updated_at) "
                "VALUES ('user-2', 'cust-test', 'user2@example.com', 'User 2', "
                "'user', 1, ?, ?)",
                (_NOW, _NOW),
            )
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            # user-2 has visibility to absorbed but NOT surviving
            conn.execute(
                "INSERT INTO user_companies "
                "(id, user_id, company_id, visibility, is_owner, created_at, updated_at) "
                "VALUES ('uco-u2-abs', 'user-2', 'abs', 'public', 0, ?, ?)",
                (_NOW, _NOW),
            )

        merge_companies("surv", "abs")

        with get_connection() as conn:
            # user-2 should now have visibility to surviving
            row = conn.execute(
                "SELECT * FROM user_companies WHERE user_id = 'user-2' AND company_id = 'surv'"
            ).fetchone()
            assert row is not None

    def test_user_company_visibility_no_duplicate(self, tmp_db):
        """If user already has visibility to surviving company, no duplicate
        row should be created."""
        with get_connection() as conn:
            _insert_company(conn, "surv", "Surviving", "acme.com")
            _insert_company(conn, "abs", "Absorbed", "acme2.com")
            # user-test already has visibility to both (via _insert_company)

        merge_companies("surv", "abs")

        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM user_companies "
                "WHERE user_id = 'user-test' AND company_id = 'surv'"
            ).fetchone()[0]
            assert count == 1


# ===================================================================
# Web route tests
# ===================================================================

@pytest.fixture()
def client(tmp_db):
    from poc.web.app import create_app
    app = create_app()
    from fastapi.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


class TestMergeWebRoutes:
    def test_merge_page_loads(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme Corp", "acme.com")
        resp = client.get("/companies/c1/merge")
        assert resp.status_code == 200
        assert "Acme Corp" in resp.text

    def test_merge_preview_shows_impact(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme Corp", "acme.com")
            _insert_company(conn, "c2", "Acme Inc", "acme.com")
            _insert_contact(conn, "ct1")
            _link_contact(conn, "ct1", "c2")
        resp = client.post("/companies/c1/merge", data={"target_id": "c2"})
        assert resp.status_code == 200
        assert "contact" in resp.text.lower()

    def test_merge_execute_redirects(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme Corp", "acme.com")
            _insert_company(conn, "c2", "Acme Inc", "acme2.com")
        resp = client.post(
            "/companies/c1/merge/confirm",
            data={
                "surviving_id": "c1",
                "company_a": "c1",
                "company_b": "c2",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "/companies/c1" in resp.headers["location"]

    def test_duplicates_scan_page(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme Corp", "acme.com")
            _insert_company(conn, "c2", "Acme Inc", "acme.com")
        resp = client.get("/companies/duplicates")
        assert resp.status_code == 200
        assert "acme.com" in resp.text

    def test_create_shows_duplicate_warning(self, client, tmp_db):
        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme Corp", "acme.com")
            _insert_identifier(conn, "c1", "acme.com")
        resp = client.post(
            "/companies",
            data={"name": "Acme New", "domain": "acme.com"},
        )
        assert resp.status_code == 200
        # Should show a warning about existing company
        assert "Acme Corp" in resp.text or "already" in resp.text.lower() or "existing" in resp.text.lower()


# ---------------------------------------------------------------------------
# Sync duplicate detection (domain-aware _resolve_company_id)
# ---------------------------------------------------------------------------

class TestSyncDuplicateDetection:
    """Verify that _resolve_company_id uses domain matching to prevent duplicates."""

    def test_domain_match_prevents_duplicate(self, tmp_db):
        """Company exists with domain acme.com — contact with different org name
        but same email domain should resolve to existing company, not create a new one."""
        from poc.sync import _resolve_company_id

        with get_connection() as conn:
            _insert_company(conn, "c1", "Acme Corp", "acme.com")
            _insert_identifier(conn, "c1", "acme.com")

            result = _resolve_company_id(conn, "Acme Inc", "bob@acme.com", _NOW)

        assert result == "c1"
        # No new company should have been created
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        assert count == 1

    def test_auto_create_adds_domain_identifier(self, tmp_db):
        """When a new company is auto-created, its email domain should be
        registered in company_identifiers for future lookups."""
        from poc.sync import _resolve_company_id

        with get_connection() as conn:
            company_id = _resolve_company_id(conn, "NewCo", "alice@newco.io", _NOW)

        assert company_id is not None
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM company_identifiers WHERE company_id = ? AND type = 'domain'",
                (company_id,),
            ).fetchone()
        assert row is not None
        assert row["value"] == "newco.io"

    def test_public_domain_no_identifier(self, tmp_db):
        """Contact with a public domain email (gmail.com) should NOT get a
        domain identifier added to the newly created company."""
        from poc.sync import _resolve_company_id

        with get_connection() as conn:
            company_id = _resolve_company_id(conn, "SomeCo", "user@gmail.com", _NOW)

        assert company_id is not None
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM company_identifiers WHERE company_id = ?",
                (company_id,),
            ).fetchone()
        assert row is None

    def test_exact_name_match_still_preferred(self, tmp_db):
        """When the company name matches exactly, that company is returned even
        if the domain could match a different company."""
        from poc.sync import _resolve_company_id

        with get_connection() as conn:
            _insert_company(conn, "c1", "Alpha LLC", "alpha.com")
            _insert_identifier(conn, "c1", "alpha.com")
            _insert_company(conn, "c2", "Beta Inc", "beta.com")

            # Name matches c2 exactly, even though email domain matches c1
            result = _resolve_company_id(conn, "Beta Inc", "info@alpha.com", _NOW)

        assert result == "c2"

    def test_empty_company_name_returns_none(self, tmp_db):
        """Empty company name should return None (existing behaviour)."""
        from poc.sync import _resolve_company_id

        with get_connection() as conn:
            result = _resolve_company_id(conn, "", "user@example.com", _NOW)

        assert result is None
