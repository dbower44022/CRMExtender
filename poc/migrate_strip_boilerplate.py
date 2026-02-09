#!/usr/bin/env python3
"""One-time migration to re-strip boilerplate from existing email bodies."""

import sqlite3
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from poc.email_parser import strip_quotes
from poc.database import get_connection


def migrate():
    """Re-process all email bodies through strip_quotes."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Get all communications with body text (include body_html for HTML-aware parsing)
        cursor.execute("SELECT id, content, body_html FROM communications WHERE content IS NOT NULL")
        communications = cursor.fetchall()

        print(f"Processing {len(communications)} communications...")

        updated = 0
        for email_id, body, body_html in communications:
            if not body:
                continue

            stripped = strip_quotes(body, body_html or None)

            # Only update if content changed
            if stripped != body:
                cursor.execute(
                    "UPDATE communications SET content = ? WHERE id = ?",
                    (stripped, email_id)
                )
                updated += 1

                # Show progress for changed communications
                reduction = len(body) - len(stripped)
                print(f"  Updated {email_id[:8]}... (removed {reduction} chars)")

        conn.commit()

    print(f"\nDone! Updated {updated} of {len(communications)} communications.")


if __name__ == "__main__":
    migrate()
