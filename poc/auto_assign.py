"""Bulk auto-assign conversations to topics based on tag and title matching."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .database import get_connection


@dataclass
class MatchResult:
    """A single conversation-to-topic match."""

    conversation_id: str
    conversation_title: str
    topic_id: str
    topic_name: str
    score: int
    matched_tags: list[str]
    title_matched: bool


@dataclass
class AutoAssignReport:
    """Summary of an auto-assign run."""

    project_name: str
    total_candidates: int
    matched: int
    unmatched: int
    assignments: list[MatchResult]


def _score_conversation(
    title: str | None,
    tags: list[str],
    topic_name: str,
) -> tuple[int, list[str], bool]:
    """Score a conversation against a single topic.

    Returns (score, matched_tags, title_matched).
    Tag match: 2 points per tag whose name contains the topic name (case-insensitive).
    Title match: 1 point if the conversation title contains the topic name.
    """
    topic_lower = topic_name.lower()
    matched_tags = [t for t in tags if topic_lower in t.lower()]
    title_matched = bool(title and topic_lower in title.lower())
    score = 2 * len(matched_tags) + (1 if title_matched else 0)
    return score, matched_tags, title_matched


def find_matching_topics(
    project_id: str,
    *,
    include_triaged: bool = False,
) -> AutoAssignReport:
    """Find the best topic match for each unassigned conversation.

    Loads all topics for the project and all candidate conversations,
    scores every pair, and picks the highest-scoring topic per conversation.
    Ties broken alphabetically by topic name.

    Raises ValueError if the project has no topics.
    """
    with get_connection() as conn:
        # Load project info
        proj = conn.execute(
            "SELECT name FROM projects WHERE id = ? AND status = 'active'",
            (project_id,),
        ).fetchone()
        if not proj:
            raise ValueError(f"Project not found (id={project_id}).")
        project_name = proj["name"]

        # Load topics for this project
        topic_rows = conn.execute(
            "SELECT id, name FROM topics WHERE project_id = ? ORDER BY name COLLATE NOCASE",
            (project_id,),
        ).fetchall()
        if not topic_rows:
            raise ValueError(f"Project '{project_name}' has no topics.")
        topics = [(r["id"], r["name"]) for r in topic_rows]

        # Load candidate conversations (unassigned, optionally excluding triaged)
        rows = conn.execute(
            """SELECT c.id, c.title, GROUP_CONCAT(t.name, '||') AS tag_names
               FROM conversations c
               LEFT JOIN conversation_tags ct ON ct.conversation_id = c.id
               LEFT JOIN tags t ON t.id = ct.tag_id
               WHERE c.topic_id IS NULL
                 AND (c.triage_result IS NULL OR :include_triaged)
               GROUP BY c.id""",
            {"include_triaged": 1 if include_triaged else 0},
        ).fetchall()

    # Score each conversation against each topic
    assignments: list[MatchResult] = []
    for row in rows:
        conv_id = row["id"]
        conv_title = row["title"] or ""
        tag_names = row["tag_names"].split("||") if row["tag_names"] else []

        best: MatchResult | None = None
        for topic_id, topic_name in topics:
            score, matched_tags, title_matched = _score_conversation(
                conv_title, tag_names, topic_name,
            )
            if score < 1:
                continue
            candidate = MatchResult(
                conversation_id=conv_id,
                conversation_title=conv_title,
                topic_id=topic_id,
                topic_name=topic_name,
                score=score,
                matched_tags=matched_tags,
                title_matched=title_matched,
            )
            if best is None or score > best.score or (
                score == best.score and topic_name < best.topic_name
            ):
                best = candidate

        if best is not None:
            assignments.append(best)

    total = len(rows)
    matched = len(assignments)
    return AutoAssignReport(
        project_name=project_name,
        total_candidates=total,
        matched=matched,
        unmatched=total - matched,
        assignments=assignments,
    )


def apply_assignments(assignments: list[MatchResult]) -> int:
    """Batch-update conversations with their assigned topic_id.

    Returns the number of rows updated.
    """
    if not assignments:
        return 0

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        for match in assignments:
            conn.execute(
                "UPDATE conversations SET topic_id = ?, updated_at = ? WHERE id = ?",
                (match.topic_id, now, match.conversation_id),
            )
    return len(assignments)
