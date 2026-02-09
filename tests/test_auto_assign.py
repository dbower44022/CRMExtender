"""Tests for bulk auto-assign conversations to topics."""

from datetime import datetime, timezone

import pytest

from poc.auto_assign import (
    AutoAssignReport,
    MatchResult,
    _score_conversation,
    apply_assignments,
    find_matching_topics,
)
from poc.database import get_connection, init_db
from poc.hierarchy import create_project, create_topic


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary database and point config at it."""
    db_file = tmp_path / "test.db"
    monkeypatch.setattr("poc.config.DB_PATH", db_file)
    init_db(db_file)
    return db_file


def _insert_conversation(conn, conv_id, title="Test subject", topic_id=None,
                          triage_result=None):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO conversations "
        "(id, topic_id, title, triage_result, dismissed, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 0, ?, ?)",
        (conv_id, topic_id, title, triage_result, now, now),
    )


def _insert_tag(conn, tag_name):
    """Insert a tag and return its id."""
    now = datetime.now(timezone.utc).isoformat()
    import uuid
    tag_id = str(uuid.uuid4())
    conn.execute(
        "INSERT OR IGNORE INTO tags (id, name, source, created_at) VALUES (?, ?, 'ai', ?)",
        (tag_id, tag_name, now),
    )
    # Fetch back in case of IGNORE (duplicate name)
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
    return row["id"]


def _link_tag(conn, conv_id, tag_id):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO conversation_tags "
        "(conversation_id, tag_id, confidence, source, created_at) "
        "VALUES (?, ?, 1.0, 'ai', ?)",
        (conv_id, tag_id, now),
    )


# ---------------------------------------------------------------------------
# Unit tests: _score_conversation
# ---------------------------------------------------------------------------

class TestScoreConversation:

    def test_tag_match(self):
        score, matched, title_hit = _score_conversation(
            "Unrelated title", ["tax strategy", "tax filing"], "Tax",
        )
        assert score == 4
        assert matched == ["tax strategy", "tax filing"]
        assert title_hit is False

    def test_title_match(self):
        score, matched, title_hit = _score_conversation(
            "Tax planning discussion", [], "Tax",
        )
        assert score == 1
        assert matched == []
        assert title_hit is True

    def test_combined_tag_and_title(self):
        score, matched, title_hit = _score_conversation(
            "Tax planning", ["tax strategy", "tax filing"], "Tax",
        )
        assert score == 5
        assert len(matched) == 2
        assert title_hit is True

    def test_no_match(self):
        score, matched, title_hit = _score_conversation(
            "Meeting notes", ["budget", "hiring"], "Tax",
        )
        assert score == 0
        assert matched == []
        assert title_hit is False

    def test_case_insensitive(self):
        score, matched, title_hit = _score_conversation(
            "TAX PLANNING", ["Tax Strategy"], "tax",
        )
        assert score == 3
        assert matched == ["Tax Strategy"]
        assert title_hit is True

    def test_empty_inputs(self):
        score, matched, title_hit = _score_conversation(None, [], "Tax")
        assert score == 0
        assert matched == []
        assert title_hit is False

    def test_substring_matching(self):
        score, matched, title_hit = _score_conversation(
            "Taxation overview", ["pre-tax deductions"], "tax",
        )
        assert score == 3
        assert matched == ["pre-tax deductions"]
        assert title_hit is True


# ---------------------------------------------------------------------------
# Integration tests: find_matching_topics
# ---------------------------------------------------------------------------

class TestFindMatchingTopics:

    def test_basic_matching(self, tmp_db):
        proj = create_project("TestProj")
        create_topic(proj["id"], "Tax")

        with get_connection() as conn:
            _insert_conversation(conn, "c1", title="Tax planning")
            tag_id = _insert_tag(conn, "tax strategy")
            _link_tag(conn, "c1", tag_id)

        report = find_matching_topics(proj["id"])
        assert report.project_name == "TestProj"
        assert report.matched == 1
        assert report.assignments[0].topic_name == "Tax"
        assert report.assignments[0].score == 3  # 1 tag (2) + title (1)

    def test_highest_score_wins(self, tmp_db):
        proj = create_project("TestProj")
        create_topic(proj["id"], "Tax")
        create_topic(proj["id"], "Budget")

        with get_connection() as conn:
            _insert_conversation(conn, "c1", title="Budget review")
            tag_id = _insert_tag(conn, "tax planning")
            _link_tag(conn, "c1", tag_id)
            budget_tag = _insert_tag(conn, "budget forecast")
            _link_tag(conn, "c1", budget_tag)
            budget_tag2 = _insert_tag(conn, "budget analysis")
            _link_tag(conn, "c1", budget_tag2)

        report = find_matching_topics(proj["id"])
        assert report.matched == 1
        # Budget: 2 tags (4) + title (1) = 5; Tax: 1 tag (2) = 2
        assert report.assignments[0].topic_name == "Budget"
        assert report.assignments[0].score == 5

    def test_skips_already_assigned(self, tmp_db):
        proj = create_project("TestProj")
        topic = create_topic(proj["id"], "Tax")

        with get_connection() as conn:
            _insert_conversation(conn, "c1", title="Tax planning",
                                  topic_id=topic["id"])

        report = find_matching_topics(proj["id"])
        assert report.total_candidates == 0
        assert report.matched == 0

    def test_no_topics_raises(self, tmp_db):
        proj = create_project("EmptyProj")
        with pytest.raises(ValueError, match="has no topics"):
            find_matching_topics(proj["id"])

    def test_no_matches(self, tmp_db):
        proj = create_project("TestProj")
        create_topic(proj["id"], "Tax")

        with get_connection() as conn:
            _insert_conversation(conn, "c1", title="Meeting notes")

        report = find_matching_topics(proj["id"])
        assert report.total_candidates == 1
        assert report.matched == 0
        assert report.unmatched == 1

    def test_triaged_excluded_by_default(self, tmp_db):
        proj = create_project("TestProj")
        create_topic(proj["id"], "Tax")

        with get_connection() as conn:
            _insert_conversation(conn, "c1", title="Tax planning",
                                  triage_result="marketing")

        report = find_matching_topics(proj["id"])
        assert report.total_candidates == 0

    def test_triaged_included_with_flag(self, tmp_db):
        proj = create_project("TestProj")
        create_topic(proj["id"], "Tax")

        with get_connection() as conn:
            _insert_conversation(conn, "c1", title="Tax planning",
                                  triage_result="marketing")

        report = find_matching_topics(proj["id"], include_triaged=True)
        assert report.total_candidates == 1
        assert report.matched == 1

    def test_title_only_match(self, tmp_db):
        proj = create_project("TestProj")
        create_topic(proj["id"], "Tax")

        with get_connection() as conn:
            _insert_conversation(conn, "c1", title="Tax discussion")

        report = find_matching_topics(proj["id"])
        assert report.matched == 1
        assert report.assignments[0].score == 1
        assert report.assignments[0].title_matched is True
        assert report.assignments[0].matched_tags == []

    def test_alphabetical_tiebreak(self, tmp_db):
        proj = create_project("TestProj")
        create_topic(proj["id"], "Beta")
        create_topic(proj["id"], "Alpha")

        with get_connection() as conn:
            # Title matches both "Alpha" and "Beta"?  No — use tags that match both.
            _insert_conversation(conn, "c1", title="Unrelated")
            a_tag = _insert_tag(conn, "alpha work")
            _link_tag(conn, "c1", a_tag)
            b_tag = _insert_tag(conn, "beta work")
            _link_tag(conn, "c1", b_tag)

        report = find_matching_topics(proj["id"])
        assert report.matched == 1
        # Both score 2 (one tag each). Alpha wins alphabetically.
        assert report.assignments[0].topic_name == "Alpha"


# ---------------------------------------------------------------------------
# Integration tests: apply_assignments
# ---------------------------------------------------------------------------

class TestApplyAssignments:

    def test_applies_topic_id(self, tmp_db):
        proj = create_project("TestProj")
        topic = create_topic(proj["id"], "Tax")

        with get_connection() as conn:
            _insert_conversation(conn, "c1", title="Tax planning")

        assignments = [
            MatchResult(
                conversation_id="c1",
                conversation_title="Tax planning",
                topic_id=topic["id"],
                topic_name="Tax",
                score=1,
                matched_tags=[],
                title_matched=True,
            ),
        ]
        count = apply_assignments(assignments)
        assert count == 1

        with get_connection() as conn:
            row = conn.execute(
                "SELECT topic_id FROM conversations WHERE id = 'c1'"
            ).fetchone()
        assert row["topic_id"] == topic["id"]

    def test_empty_list(self, tmp_db):
        count = apply_assignments([])
        assert count == 0

    def test_idempotent(self, tmp_db):
        proj = create_project("TestProj")
        topic = create_topic(proj["id"], "Tax")

        with get_connection() as conn:
            _insert_conversation(conn, "c1", title="Tax planning")

        assignments = [
            MatchResult(
                conversation_id="c1",
                conversation_title="Tax planning",
                topic_id=topic["id"],
                topic_name="Tax",
                score=1,
                matched_tags=[],
                title_matched=True,
            ),
        ]
        apply_assignments(assignments)
        apply_assignments(assignments)  # second call should not fail

        with get_connection() as conn:
            row = conn.execute(
                "SELECT topic_id FROM conversations WHERE id = 'c1'"
            ).fetchone()
        assert row["topic_id"] == topic["id"]
