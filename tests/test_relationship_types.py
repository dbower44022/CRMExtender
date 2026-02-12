"""Tests for relationship type CRUD operations."""

from __future__ import annotations

import pytest

from poc.database import get_connection, init_db
from poc.relationship_types import (
    create_relationship_type,
    delete_relationship_type,
    get_relationship_type,
    get_relationship_type_by_name,
    list_relationship_types,
    update_relationship_type,
)


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database and point config at it."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)
    return db_file


# ---------------------------------------------------------------------------
# Seed types
# ---------------------------------------------------------------------------

class TestSeedTypes:
    def test_seed_types_created(self, tmp_db):
        """init_db should seed the default relationship types."""
        types = list_relationship_types()
        names = {t["name"] for t in types}
        assert "KNOWS" in names
        assert "REPORTS_TO" in names
        assert "WORKS_WITH" in names
        assert "PARTNER" in names
        assert "VENDOR" in names

    def test_knows_is_system(self, tmp_db):
        rt = get_relationship_type_by_name("KNOWS")
        assert rt is not None
        assert rt["is_system"] == 1

    def test_vendor_entity_types(self, tmp_db):
        rt = get_relationship_type_by_name("VENDOR")
        assert rt is not None
        assert rt["from_entity_type"] == "company"
        assert rt["to_entity_type"] == "company"
        assert rt["forward_label"] == "Is a vendor of"
        assert rt["reverse_label"] == "Is a client of"

    def test_partner_is_company_to_company(self, tmp_db):
        rt = get_relationship_type_by_name("PARTNER")
        assert rt is not None
        assert rt["from_entity_type"] == "company"
        assert rt["to_entity_type"] == "company"

    def test_seed_is_idempotent(self, tmp_db):
        """Running init_db twice should not duplicate seed types."""
        init_db(tmp_db)
        types = list_relationship_types()
        names = [t["name"] for t in types]
        assert names.count("KNOWS") == 1

    def test_bidirectional_seed_types(self, tmp_db):
        """KNOWS, WORKS_WITH, and PARTNER should be bidirectional."""
        for name in ("KNOWS", "WORKS_WITH", "PARTNER"):
            rt = get_relationship_type_by_name(name)
            assert rt is not None
            assert rt["is_bidirectional"] == 1, f"{name} should be bidirectional"

        for name in ("REPORTS_TO", "VENDOR"):
            rt = get_relationship_type_by_name(name)
            assert rt is not None
            assert rt["is_bidirectional"] == 0, f"{name} should be unidirectional"


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

class TestCreate:
    def test_create_basic(self, tmp_db):
        row = create_relationship_type(
            "MENTOR",
            from_entity_type="contact",
            to_entity_type="contact",
            forward_label="Mentors",
            reverse_label="Mentored by",
            description="Mentorship",
        )
        assert row["name"] == "MENTOR"
        assert row["forward_label"] == "Mentors"
        assert row["is_system"] == 0

    def test_create_duplicate_raises(self, tmp_db):
        create_relationship_type("UNIQUE_TYPE", forward_label="A", reverse_label="B")
        with pytest.raises(ValueError, match="already exists"):
            create_relationship_type("UNIQUE_TYPE", forward_label="C", reverse_label="D")

    def test_create_invalid_entity_type(self, tmp_db):
        with pytest.raises(ValueError, match="Invalid from_entity_type"):
            create_relationship_type("BAD", from_entity_type="project",
                                     forward_label="A", reverse_label="B")

    def test_create_company_to_company(self, tmp_db):
        row = create_relationship_type(
            "SUBSIDIARY",
            from_entity_type="company",
            to_entity_type="company",
            forward_label="Parent of",
            reverse_label="Subsidiary of",
        )
        assert row["from_entity_type"] == "company"
        assert row["to_entity_type"] == "company"

    def test_create_bidirectional_type(self, tmp_db):
        row = create_relationship_type(
            "COLLABORATES",
            forward_label="Collaborates with",
            reverse_label="Collaborates with",
            is_bidirectional=True,
        )
        assert row["is_bidirectional"] == 1

        rt = get_relationship_type_by_name("COLLABORATES")
        assert rt is not None
        assert rt["is_bidirectional"] == 1


class TestList:
    def test_list_all(self, tmp_db):
        types = list_relationship_types()
        assert len(types) >= 5  # seed types

    def test_filter_by_from_entity_type(self, tmp_db):
        types = list_relationship_types(from_entity_type="company")
        for t in types:
            assert t["from_entity_type"] == "company"

    def test_filter_by_to_entity_type(self, tmp_db):
        types = list_relationship_types(to_entity_type="company")
        for t in types:
            assert t["to_entity_type"] == "company"

    def test_filter_combined(self, tmp_db):
        types = list_relationship_types(
            from_entity_type="company", to_entity_type="contact"
        )
        assert all(t["from_entity_type"] == "company" for t in types)
        assert all(t["to_entity_type"] == "contact" for t in types)


class TestGet:
    def test_get_by_id(self, tmp_db):
        rt = get_relationship_type("rt-knows")
        assert rt is not None
        assert rt["name"] == "KNOWS"

    def test_get_by_name(self, tmp_db):
        rt = get_relationship_type_by_name("VENDOR")
        assert rt is not None
        assert rt["forward_label"] == "Is a vendor of"

    def test_get_nonexistent(self, tmp_db):
        assert get_relationship_type("nonexistent") is None
        assert get_relationship_type_by_name("NONEXISTENT") is None


class TestUpdate:
    def test_update_labels(self, tmp_db):
        row = create_relationship_type(
            "UPDATABLE", forward_label="Old", reverse_label="Old Rev"
        )
        updated = update_relationship_type(
            row["id"], forward_label="New", reverse_label="New Rev"
        )
        assert updated is not None
        assert updated["forward_label"] == "New"
        assert updated["reverse_label"] == "New Rev"

    def test_update_description(self, tmp_db):
        row = create_relationship_type(
            "DESC_TEST", forward_label="A", reverse_label="B"
        )
        updated = update_relationship_type(row["id"], description="Updated desc")
        assert updated["description"] == "Updated desc"

    def test_update_nonexistent(self, tmp_db):
        assert update_relationship_type("fake-id", forward_label="X") is None


class TestDelete:
    def test_delete_user_type(self, tmp_db):
        row = create_relationship_type(
            "DELETABLE", forward_label="A", reverse_label="B"
        )
        delete_relationship_type(row["id"])
        assert get_relationship_type(row["id"]) is None

    def test_delete_system_type_raises(self, tmp_db):
        with pytest.raises(ValueError, match="Cannot delete system"):
            delete_relationship_type("rt-knows")

    def test_delete_in_use_raises(self, tmp_db):
        """Cannot delete a type that has relationships referencing it."""
        from datetime import datetime, timezone
        row = create_relationship_type(
            "IN_USE", forward_label="A", reverse_label="B"
        )
        now = datetime.now(timezone.utc).isoformat()
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO contacts (id, name, created_at, updated_at) "
                "VALUES ('ct-1', 'Alice', ?, ?)", (now, now)
            )
            conn.execute(
                "INSERT INTO contacts (id, name, created_at, updated_at) "
                "VALUES ('ct-2', 'Bob', ?, ?)", (now, now)
            )
            conn.execute(
                """INSERT INTO relationships
                   (id, relationship_type_id, from_entity_type, from_entity_id,
                    to_entity_type, to_entity_id, source, created_at, updated_at)
                   VALUES ('r-1', ?, 'contact', 'ct-1', 'contact', 'ct-2',
                           'manual', ?, ?)""",
                (row["id"], now, now),
            )

        with pytest.raises(ValueError, match="still reference it"):
            delete_relationship_type(row["id"])

    def test_delete_nonexistent_raises(self, tmp_db):
        with pytest.raises(ValueError, match="not found"):
            delete_relationship_type("fake-id")
