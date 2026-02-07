#!/usr/bin/env python3
"""Audit tool: compare text-only vs HTML-aware email parsing pipelines.

Processes all stored emails through both the old (text-only) and new
(HTML-aware) pipelines and reports differences so you can validate
results before running a migration.

Usage:
    python -m poc.audit_parser [--limit N] [--show-diffs N]
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from poc.database import get_connection
from poc.email_parser import strip_quotes


def audit(*, limit: int | None = None, show_diffs: int = 10) -> None:
    """Run the audit comparison."""
    with get_connection() as conn:
        query = "SELECT id, subject, body_text, body_html FROM emails WHERE body_text IS NOT NULL"
        if limit:
            query += f" LIMIT {limit}"
        rows = conn.execute(query).fetchall()

    total = len(rows)
    changed = 0
    empty_new = 0
    total_old_chars = 0
    total_new_chars = 0
    diffs: list[tuple[str, str, str, str, int]] = []  # (id, subject, old, new, delta)

    print(f"Auditing {total} emails...\n")

    for row in rows:
        email_id = row["id"]
        subject = row["subject"] or "(no subject)"
        body = row["body_text"] or ""
        body_html = row["body_html"] or ""

        # Old pipeline: text-only
        old_result = strip_quotes(body)

        # New pipeline: HTML-aware (falls back to text if no HTML)
        new_result = strip_quotes(body, body_html or None)

        total_old_chars += len(old_result)
        total_new_chars += len(new_result)

        if old_result != new_result:
            changed += 1
            delta = len(old_result) - len(new_result)
            diffs.append((email_id, subject, old_result, new_result, delta))

        if not new_result.strip():
            empty_new += 1

    # Sort diffs by absolute character change (most changed first)
    diffs.sort(key=lambda d: abs(d[4]), reverse=True)

    # Report summary
    print("=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)
    print(f"Total emails processed:    {total}")
    print(f"Results changed:           {changed} ({changed/total*100:.1f}%)" if total else "")
    print(f"Empty results (new):       {empty_new}")
    print(f"Total chars (old):         {total_old_chars:,}")
    print(f"Total chars (new):         {total_new_chars:,}")
    if total_old_chars > 0:
        reduction = (total_old_chars - total_new_chars) / total_old_chars * 100
        print(f"Average char reduction:    {reduction:.1f}%")
    print()

    # Show top diffs
    if diffs and show_diffs > 0:
        print(f"Top {min(show_diffs, len(diffs))} most-changed emails:")
        print("-" * 70)
        for email_id, subject, old, new, delta in diffs[:show_diffs]:
            print(f"\n  ID:      {email_id[:12]}...")
            print(f"  Subject: {subject[:60]}")
            print(f"  Delta:   {delta:+d} chars")

            # Show unified diff (limited lines)
            old_lines = old.splitlines(keepends=True)
            new_lines = new.splitlines(keepends=True)
            diff_lines = list(difflib.unified_diff(
                old_lines, new_lines,
                fromfile="text-only", tofile="html-aware",
                lineterm="",
            ))
            for line in diff_lines[:20]:
                print(f"    {line.rstrip()}")
            if len(diff_lines) > 20:
                print(f"    ... ({len(diff_lines) - 20} more diff lines)")
            print()

    # Warn about empty results
    if empty_new > 0:
        print("WARNING: Some emails have empty results with the new pipeline.")
        print("Review these before running the migration.\n")
        for email_id, subject, old, new, delta in diffs:
            if not new.strip():
                print(f"  EMPTY: {email_id[:12]}... - {subject[:50]}")


def main():
    parser = argparse.ArgumentParser(description="Audit email parser pipelines")
    parser.add_argument("--limit", type=int, default=None, help="Max emails to process")
    parser.add_argument("--show-diffs", type=int, default=10, help="Number of diffs to display")
    args = parser.parse_args()
    audit(limit=args.limit, show_diffs=args.show_diffs)


if __name__ == "__main__":
    main()
