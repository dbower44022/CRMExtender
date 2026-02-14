"""Tests for vCard import feature.

Covers:
- File finding (single file, directory, recursive, errors)
- vCard parsing (single, multi-vCard, invalid files)
- Data extraction (name, emails, phones, addresses, org, title)
- Type mapping (phone, address, email)
- Import logic (create contacts, skip duplicates, skip no-name, company resolution)
- Web routes (GET/POST /contacts/import, list button)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import vobject
from fastapi.testclient import TestClient

from poc.database import get_connection, init_db
from poc.vcard_import import (
    ImportResult,
    _map_address_type,
    _map_email_label,
    _map_phone_type,
    extract_contact_data,
    find_vcf_files,
    import_vcards,
    parse_vcard_file,
)


_NOW = datetime.now(timezone.utc).isoformat()

CUST_ID = "cust-test"
USER_ID = "user-admin"

_SYSTEM_ROLES = [
    ("ccr-employee", "Employee", 0),
    ("ccr-contractor", "Contractor", 1),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    monkeypatch.setattr("poc.config.CRM_AUTH_ENABLED", False)
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
            "VALUES (?, ?, 'admin@test.com', 'Admin User', 'admin', 1, ?, ?)",
            (USER_ID, CUST_ID, _NOW, _NOW),
        )
        for role_id, role_name, sort_order in _SYSTEM_ROLES:
            full_id = f"{role_id}-{CUST_ID}"
            conn.execute(
                "INSERT OR IGNORE INTO contact_company_roles "
                "(id, customer_id, name, sort_order, is_system, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 1, ?, ?)",
                (full_id, CUST_ID, role_name, sort_order, _NOW, _NOW),
            )

    return db_file


@pytest.fixture()
def client(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "poc.hierarchy.get_current_user",
        lambda: {"id": USER_ID, "email": "admin@test.com", "name": "Admin User",
                 "role": "admin", "customer_id": CUST_ID},
    )
    from poc.web.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def _make_vcf(path: Path, content: str) -> Path:
    """Write a .vcf file with given content."""
    path.write_text(content, encoding="utf-8")
    return path


SAMPLE_VCF = """\
BEGIN:VCARD
VERSION:3.0
FN:John Smith
N:Smith;John;;;
ORG:Acme Corp
TITLE:Engineer
TEL;TYPE=WORK:+1-555-123-4567
TEL;TYPE=CELL:+1-555-987-6543
EMAIL;TYPE=INTERNET;TYPE=WORK:john@acme.com
EMAIL;TYPE=INTERNET;TYPE=HOME:john@gmail.com
ADR;TYPE=WORK:;;123 Main St;Springfield;IL;62701;USA
END:VCARD
"""

SAMPLE_NO_NAME = """\
BEGIN:VCARD
VERSION:3.0
EMAIL;TYPE=INTERNET:nobody@test.com
END:VCARD
"""

SAMPLE_MULTI_VCF = """\
BEGIN:VCARD
VERSION:3.0
FN:Alice Wonder
EMAIL;TYPE=INTERNET;TYPE=WORK:alice@wonder.com
END:VCARD
BEGIN:VCARD
VERSION:3.0
FN:Bob Builder
EMAIL;TYPE=INTERNET;TYPE=WORK:bob@builder.com
ORG:Builder Inc
END:VCARD
"""


# ---------------------------------------------------------------------------
# Unit tests: find_vcf_files
# ---------------------------------------------------------------------------

class TestFindVcfFiles:

    def test_single_file(self, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", SAMPLE_VCF)
        files = find_vcf_files(vcf)
        assert files == [vcf]

    def test_non_vcf_file_raises(self, tmp_path):
        txt = tmp_path / "test.txt"
        txt.write_text("not a vcard")
        with pytest.raises(ValueError, match="Not a .vcf file"):
            find_vcf_files(txt)

    def test_directory_finds_vcf_files(self, tmp_path):
        _make_vcf(tmp_path / "a.vcf", SAMPLE_VCF)
        _make_vcf(tmp_path / "b.vcf", SAMPLE_VCF)
        (tmp_path / "c.txt").write_text("not a vcard")
        files = find_vcf_files(tmp_path)
        assert len(files) == 2
        assert all(f.suffix == ".vcf" for f in files)

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(ValueError, match="No .vcf files found"):
            find_vcf_files(tmp_path)

    def test_nonexistent_path_raises(self):
        with pytest.raises(FileNotFoundError):
            find_vcf_files("/nonexistent/path")

    def test_recursive_finds_subdirectories(self, tmp_path):
        _make_vcf(tmp_path / "root.vcf", SAMPLE_VCF)
        sub = tmp_path / "subdir"
        sub.mkdir()
        _make_vcf(sub / "nested.vcf", SAMPLE_VCF)

        # Non-recursive: only root
        files = find_vcf_files(tmp_path, recursive=False)
        assert len(files) == 1

        # Recursive: root + nested
        files = find_vcf_files(tmp_path, recursive=True)
        assert len(files) == 2

    def test_directory_non_recursive_skips_subdir(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        _make_vcf(sub / "nested.vcf", SAMPLE_VCF)
        with pytest.raises(ValueError, match="No .vcf files found"):
            find_vcf_files(tmp_path, recursive=False)


# ---------------------------------------------------------------------------
# Unit tests: parse_vcard_file
# ---------------------------------------------------------------------------

class TestParseVcardFile:

    def test_single_vcard(self, tmp_path):
        vcf = _make_vcf(tmp_path / "single.vcf", SAMPLE_VCF)
        cards = parse_vcard_file(vcf)
        assert len(cards) == 1

    def test_multi_vcard_file(self, tmp_path):
        vcf = _make_vcf(tmp_path / "multi.vcf", SAMPLE_MULTI_VCF)
        cards = parse_vcard_file(vcf)
        assert len(cards) == 2

    def test_invalid_file_returns_empty(self, tmp_path):
        bad = _make_vcf(tmp_path / "bad.vcf", "not a vcard at all")
        cards = parse_vcard_file(bad)
        assert cards == []

    def test_empty_file_returns_empty(self, tmp_path):
        empty = _make_vcf(tmp_path / "empty.vcf", "")
        cards = parse_vcard_file(empty)
        assert cards == []


# ---------------------------------------------------------------------------
# Unit tests: extract_contact_data
# ---------------------------------------------------------------------------

class TestExtractContactData:

    def _parse_one(self, text):
        return list(vobject.readComponents(text))[0]

    def test_full_extraction(self):
        card = self._parse_one(SAMPLE_VCF)
        data = extract_contact_data(card)
        assert data is not None
        assert data["name"] == "John Smith"
        assert len(data["emails"]) == 2
        assert data["emails"][0]["value"] == "john@acme.com"
        assert data["emails"][0]["label"] == "work"
        assert data["emails"][1]["value"] == "john@gmail.com"
        assert data["emails"][1]["label"] == "home"
        assert len(data["phones"]) == 2
        assert len(data["addresses"]) == 1
        assert data["addresses"][0]["city"] == "Springfield"
        assert data["org"] == "Acme Corp"
        assert data["title"] == "Engineer"

    def test_no_name_returns_none(self):
        card = self._parse_one(SAMPLE_NO_NAME)
        data = extract_contact_data(card)
        assert data is None

    def test_fn_preferred_over_n(self):
        text = """\
BEGIN:VCARD
VERSION:3.0
FN:Display Name
N:Last;First;;;
END:VCARD
"""
        card = self._parse_one(text)
        data = extract_contact_data(card)
        assert data["name"] == "Display Name"

    def test_n_fallback_when_no_fn(self):
        text = """\
BEGIN:VCARD
VERSION:3.0
N:Smith;John;;;
END:VCARD
"""
        card = self._parse_one(text)
        data = extract_contact_data(card)
        assert data is not None
        assert "John" in data["name"]
        assert "Smith" in data["name"]

    def test_no_org_returns_none_org(self):
        text = """\
BEGIN:VCARD
VERSION:3.0
FN:Simple Person
END:VCARD
"""
        card = self._parse_one(text)
        data = extract_contact_data(card)
        assert data["org"] is None
        assert data["title"] is None

    def test_empty_org_returns_none(self):
        text = """\
BEGIN:VCARD
VERSION:3.0
FN:Simple Person
ORG:;
END:VCARD
"""
        card = self._parse_one(text)
        data = extract_contact_data(card)
        assert data["org"] is None

    def test_address_extraction(self):
        text = """\
BEGIN:VCARD
VERSION:3.0
FN:Test Person
ADR;TYPE=HOME:;;456 Oak Ave;Portland;OR;97201;US
ADR;TYPE=WORK:;;789 Elm St;Seattle;WA;98101;US
END:VCARD
"""
        card = self._parse_one(text)
        data = extract_contact_data(card)
        assert len(data["addresses"]) == 2
        assert data["addresses"][0]["type"] == "home"
        assert data["addresses"][1]["type"] == "work"


# ---------------------------------------------------------------------------
# Unit tests: type mappers
# ---------------------------------------------------------------------------

class TestTypeMappers:

    def test_phone_type_cell(self):
        assert _map_phone_type(["CELL", "VOICE"]) == "mobile"

    def test_phone_type_work(self):
        assert _map_phone_type(["WORK"]) == "work"

    def test_phone_type_home(self):
        assert _map_phone_type(["HOME"]) == "home"

    def test_phone_type_fax(self):
        assert _map_phone_type(["FAX"]) == "fax"

    def test_phone_type_unknown(self):
        assert _map_phone_type(["PAGER"]) == "other"

    def test_phone_type_empty(self):
        assert _map_phone_type([]) == "other"

    def test_address_type_work(self):
        assert _map_address_type(["WORK"]) == "work"

    def test_address_type_home(self):
        assert _map_address_type(["HOME"]) == "home"

    def test_address_type_unknown(self):
        assert _map_address_type(["OTHER"]) == "other"

    def test_email_label_work(self):
        assert _map_email_label(["INTERNET", "WORK"]) == "work"

    def test_email_label_home(self):
        assert _map_email_label(["INTERNET", "HOME"]) == "home"

    def test_email_label_default(self):
        assert _map_email_label(["INTERNET"]) == "general"


# ---------------------------------------------------------------------------
# Integration tests: import_vcards
# ---------------------------------------------------------------------------

class TestImportVcards:

    def test_import_creates_contact(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", SAMPLE_VCF)
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)

        assert result.contacts_created == 1
        assert result.files_processed == 1
        assert result.vcards_parsed == 1
        assert len(result.imported_contacts) == 1
        assert result.imported_contacts[0]["name"] == "John Smith"

    def test_import_creates_identifiers(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", SAMPLE_VCF)
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)

        # John has 2 emails: john@acme.com (work), john@gmail.com (public)
        assert result.emails_added == 2

        # Verify in DB
        contact_id = result.imported_contacts[0]["id"]
        with get_connection() as conn:
            idents = conn.execute(
                "SELECT * FROM contact_identifiers WHERE contact_id = ? ORDER BY is_primary DESC",
                (contact_id,),
            ).fetchall()
        assert len(idents) == 2
        assert idents[0]["value"] == "john@acme.com"
        assert idents[0]["is_primary"] == 1

    def test_import_creates_phones(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", SAMPLE_VCF)
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)

        assert result.phones_added >= 1  # At least some phones parse

    def test_import_creates_addresses(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", SAMPLE_VCF)
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)

        assert result.addresses_added == 1

        contact_id = result.imported_contacts[0]["id"]
        with get_connection() as conn:
            addrs = conn.execute(
                "SELECT * FROM addresses WHERE entity_type = 'contact' AND entity_id = ?",
                (contact_id,),
            ).fetchall()
        assert len(addrs) == 1
        assert addrs[0]["city"] == "Springfield"

    def test_import_skips_duplicate(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", SAMPLE_VCF)

        # First import
        result1 = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)
        assert result1.contacts_created == 1

        # Second import — same email, should skip
        result2 = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)
        assert result2.contacts_created == 0
        assert result2.contacts_skipped_duplicate == 1

    def test_import_skips_no_name(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", SAMPLE_NO_NAME)
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)

        assert result.contacts_created == 0
        assert result.contacts_skipped_no_name == 1

    def test_import_multi_vcard_file(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "multi.vcf", SAMPLE_MULTI_VCF)
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)

        assert result.files_processed == 1
        assert result.vcards_parsed == 2
        assert result.contacts_created == 2

    def test_import_directory(self, tmp_db, tmp_path):
        _make_vcf(tmp_path / "a.vcf", SAMPLE_VCF)
        _make_vcf(tmp_path / "b.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Jane Doe
EMAIL;TYPE=INTERNET:jane@doe.com
END:VCARD
""")
        result = import_vcards(tmp_path, customer_id=CUST_ID, user_id=USER_ID)

        assert result.files_processed == 2
        assert result.contacts_created == 2

    def test_import_recursive(self, tmp_db, tmp_path):
        _make_vcf(tmp_path / "root.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Root Contact
EMAIL;TYPE=INTERNET:root@test.com
END:VCARD
""")
        sub = tmp_path / "subdir"
        sub.mkdir()
        _make_vcf(sub / "nested.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Nested Contact
EMAIL;TYPE=INTERNET:nested@test.com
END:VCARD
""")

        # Non-recursive
        result = import_vcards(tmp_path, recursive=False,
                               customer_id=CUST_ID, user_id=USER_ID)
        assert result.contacts_created == 1

    def test_import_recursive_finds_nested(self, tmp_db, tmp_path):
        _make_vcf(tmp_path / "root.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Root Contact
EMAIL;TYPE=INTERNET:root2@test.com
END:VCARD
""")
        sub = tmp_path / "subdir"
        sub.mkdir()
        _make_vcf(sub / "nested.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Nested Contact
EMAIL;TYPE=INTERNET:nested2@test.com
END:VCARD
""")

        result = import_vcards(tmp_path, recursive=True,
                               customer_id=CUST_ID, user_id=USER_ID)
        assert result.contacts_created == 2

    def test_import_invalid_file_recorded(self, tmp_db, tmp_path):
        _make_vcf(tmp_path / "bad.vcf", "not a vcard")
        result = import_vcards(tmp_path, customer_id=CUST_ID, user_id=USER_ID)

        assert result.files_processed == 1
        assert result.contacts_created == 0
        assert len(result.invalid_files) == 1

    def test_import_creates_user_contact_visibility(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Visible Person
EMAIL;TYPE=INTERNET:visible@test.com
END:VCARD
""")
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)
        contact_id = result.imported_contacts[0]["id"]

        with get_connection() as conn:
            uc = conn.execute(
                "SELECT * FROM user_contacts WHERE contact_id = ?",
                (contact_id,),
            ).fetchone()
        assert uc is not None
        assert uc["user_id"] == USER_ID

    def test_import_contact_source_is_vcard(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Sourced Person
EMAIL;TYPE=INTERNET:sourced@test.com
END:VCARD
""")
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)
        contact_id = result.imported_contacts[0]["id"]

        with get_connection() as conn:
            contact = conn.execute(
                "SELECT source FROM contacts WHERE id = ?",
                (contact_id,),
            ).fetchone()
        assert contact["source"] == "vcard_import"

    def test_import_company_from_domain(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Domain Person
EMAIL;TYPE=INTERNET:user@specialcorp.com
END:VCARD
""")
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)

        assert result.companies_created == 1
        assert result.affiliations_created == 1

        # Verify company was created with domain name
        with get_connection() as conn:
            co = conn.execute(
                "SELECT * FROM companies WHERE domain = 'specialcorp.com'"
            ).fetchone()
        assert co is not None

    def test_import_company_from_org_when_public_email(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Gmail Person
ORG:Some Company
EMAIL;TYPE=INTERNET:person@gmail.com
END:VCARD
""")
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)

        # gmail.com is public, so domain resolution returns None
        # But ORG is present, so company should be created by name
        assert result.companies_created == 1
        assert result.affiliations_created == 1

        with get_connection() as conn:
            co = conn.execute(
                "SELECT * FROM companies WHERE name = 'Some Company'"
            ).fetchone()
        assert co is not None

    def test_import_existing_company_by_org_name(self, tmp_db, tmp_path):
        # Pre-create company
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO companies "
                "(id, customer_id, name, status, created_at, updated_at) "
                "VALUES ('co-existing', ?, 'Existing Corp', 'active', ?, ?)",
                (CUST_ID, _NOW, _NOW),
            )

        vcf = _make_vcf(tmp_path / "test.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Org Match Person
ORG:Existing Corp
EMAIL;TYPE=INTERNET:person2@gmail.com
END:VCARD
""")
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)

        assert result.companies_created == 0
        assert result.affiliations_created == 1

    def test_import_no_email_contact(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:No Email Person
TEL;TYPE=CELL:+1-555-000-0000
END:VCARD
""")
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)

        assert result.contacts_created == 1
        assert result.emails_added == 0

    def test_import_affiliation_has_title(self, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "test.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Titled Person
ORG:Title Corp
TITLE:VP of Engineering
EMAIL;TYPE=INTERNET:titled@gmail.com
END:VCARD
""")
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)

        contact_id = result.imported_contacts[0]["id"]
        with get_connection() as conn:
            aff = conn.execute(
                "SELECT title FROM contact_companies WHERE contact_id = ?",
                (contact_id,),
            ).fetchone()
        assert aff is not None
        assert aff["title"] == "VP of Engineering"


# ---------------------------------------------------------------------------
# Web route tests
# ---------------------------------------------------------------------------

class TestWebRoutes:

    def test_import_form_renders(self, client, tmp_db):
        resp = client.get("/contacts/import")
        assert resp.status_code == 200
        assert "Import vCards" in resp.text
        assert 'name="path"' in resp.text

    def test_import_button_on_list_page(self, client, tmp_db):
        resp = client.get("/contacts")
        assert resp.status_code == 200
        assert "Import vCards" in resp.text
        assert '/contacts/import' in resp.text

    def test_import_post_empty_path(self, client, tmp_db):
        resp = client.post("/contacts/import", data={"path": ""})
        assert resp.status_code == 200
        assert "Please enter" in resp.text

    def test_import_post_nonexistent_path(self, client, tmp_db):
        resp = client.post("/contacts/import", data={"path": "/nonexistent/path"})
        assert resp.status_code == 200
        assert "not found" in resp.text.lower() or "Not found" in resp.text

    def test_import_post_success(self, client, tmp_db, tmp_path):
        vcf = _make_vcf(tmp_path / "web_test.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Web Test Contact
EMAIL;TYPE=INTERNET:webtest@example.com
END:VCARD
""")
        resp = client.post("/contacts/import", data={"path": str(vcf)})
        assert resp.status_code == 200
        assert "Web Test Contact" in resp.text
        assert "Contacts created" in resp.text

    def test_import_post_with_recursive(self, client, tmp_db, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        _make_vcf(sub / "nested.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Recursive Contact
EMAIL;TYPE=INTERNET:recursive@example.com
END:VCARD
""")
        resp = client.post("/contacts/import", data={
            "path": str(tmp_path),
            "recursive": "1",
        })
        assert resp.status_code == 200
        assert "Recursive Contact" in resp.text

    def test_import_post_no_vcf_files(self, client, tmp_db, tmp_path):
        (tmp_path / "readme.txt").write_text("not a vcard")
        resp = client.post("/contacts/import", data={"path": str(tmp_path)})
        assert resp.status_code == 200
        assert "No .vcf files" in resp.text

    def test_import_results_show_summary(self, client, tmp_db, tmp_path):
        _make_vcf(tmp_path / "summary.vcf", SAMPLE_VCF)
        resp = client.post("/contacts/import", data={"path": str(tmp_path)})
        assert resp.status_code == 200
        assert "Files processed" in resp.text
        assert "vCards parsed" in resp.text

    def test_import_results_link_to_contact(self, client, tmp_db, tmp_path):
        _make_vcf(tmp_path / "link.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Link Test
EMAIL;TYPE=INTERNET:linktest@example.com
END:VCARD
""")
        resp = client.post("/contacts/import", data={"path": str(tmp_path)})
        assert resp.status_code == 200
        assert "/contacts/" in resp.text
        assert "Link Test" in resp.text


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_import_contact_with_only_name(self, tmp_db, tmp_path):
        """Contact with name but no email, phone, or address."""
        vcf = _make_vcf(tmp_path / "test.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Bare Minimum
END:VCARD
""")
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)
        assert result.contacts_created == 1
        assert result.emails_added == 0
        assert result.phones_added == 0
        assert result.addresses_added == 0

    def test_import_handles_encoding(self, tmp_db, tmp_path):
        """Contact with special characters in name."""
        vcf = _make_vcf(tmp_path / "test.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:Jean-Pierre Dupont
EMAIL;TYPE=INTERNET:jp@example.com
END:VCARD
""")
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=USER_ID)
        assert result.contacts_created == 1
        assert result.imported_contacts[0]["name"] == "Jean-Pierre Dupont"

    def test_import_no_user_id(self, tmp_db, tmp_path):
        """Import without user_id — no visibility rows created."""
        vcf = _make_vcf(tmp_path / "test.vcf", """\
BEGIN:VCARD
VERSION:3.0
FN:No User Contact
EMAIL;TYPE=INTERNET:nouser@example.com
END:VCARD
""")
        result = import_vcards(vcf, customer_id=CUST_ID, user_id=None)
        assert result.contacts_created == 1

        contact_id = result.imported_contacts[0]["id"]
        with get_connection() as conn:
            uc = conn.execute(
                "SELECT * FROM user_contacts WHERE contact_id = ?",
                (contact_id,),
            ).fetchone()
        assert uc is None

    def test_import_result_dataclass_defaults(self):
        result = ImportResult()
        assert result.files_processed == 0
        assert result.contacts_created == 0
        assert result.errors == []
        assert result.imported_contacts == []
