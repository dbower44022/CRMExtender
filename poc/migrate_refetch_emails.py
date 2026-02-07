#!/usr/bin/env python3
"""Migration to re-fetch email bodies from Gmail and reprocess with updated parser.

This is needed when the email_parser logic changes and we need to reprocess
existing emails with the new logic.
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from poc import config
from poc.auth import get_credentials
from poc.database import get_connection
from poc.email_parser import strip_quotes
from poc.gmail_client import fetch_messages
from poc.rate_limiter import RateLimiter


def migrate():
    """Re-fetch all email bodies from Gmail and reprocess."""
    # Load credentials
    try:
        creds = get_credentials()
    except Exception as e:
        print(f"Error: Failed to load credentials: {e}")
        print("Run the app first to authenticate with Gmail.")
        return

    rate_limiter = RateLimiter(rate=config.GMAIL_RATE_LIMIT)

    with get_connection() as conn:
        cursor = conn.cursor()

        # Get all emails with their Gmail message IDs
        cursor.execute("""
            SELECT id, provider_message_id, subject
            FROM emails
            WHERE provider_message_id IS NOT NULL
        """)
        emails = cursor.fetchall()

        print(f"Re-fetching {len(emails)} emails from Gmail...")

        updated = 0
        failed = 0
        batch_size = 50

        # Process in batches
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            message_ids = [row[1] for row in batch]

            # Fetch from Gmail
            try:
                parsed_emails = fetch_messages(creds, message_ids, rate_limiter)
            except Exception as e:
                print(f"  Error fetching batch: {e}")
                failed += len(batch)
                continue

            # Create lookup by message ID
            parsed_by_id = {e.message_id: e for e in parsed_emails}

            # Update each email
            for db_id, msg_id, subject in batch:
                if msg_id not in parsed_by_id:
                    failed += 1
                    continue

                parsed = parsed_by_id[msg_id]
                new_body = strip_quotes(
                    parsed.body_plain or "",
                    parsed.body_html or None,
                )

                cursor.execute(
                    "UPDATE emails SET body_text = ? WHERE id = ?",
                    (new_body, db_id)
                )
                updated += 1

            print(f"  Processed {min(i + batch_size, len(emails))}/{len(emails)} emails...")

        conn.commit()

    print(f"\nDone! Updated {updated} emails, {failed} failed.")


if __name__ == "__main__":
    migrate()
