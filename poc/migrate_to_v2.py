#!/usr/bin/env python3
"""Migrate the CRMExtender database from v1 (8-table email-only) to v2 (21-table multi-channel).

This script performs an in-place migration of the production SQLite database.
It backs up the file first, then applies schema changes using ALTER TABLE,
CREATE TABLE, and data transforms.

Usage:
    python3 -m poc.migrate_to_v2 [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path for imports when run as script
sys.path.insert(0, str(Path(__file__).parent.parent))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def migrate(db_path: Path, *, dry_run: bool = False) -> None:
    """Run the full v1 → v2 migration."""
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    # 1. Backup
    backup_path = db_path.with_suffix(f".v1-backup-{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    print(f"Backing up to {backup_path}...")
    shutil.copy2(str(db_path), str(backup_path))
    print(f"  Backup created ({backup_path.stat().st_size:,} bytes)")

    if dry_run:
        # Work on the backup for dry run
        db_path = backup_path

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        _run_migration(conn)
        conn.commit()
        print("\nMigration committed successfully.")
    except Exception:
        conn.rollback()
        print("\nMigration FAILED — rolled back.")
        raise
    finally:
        conn.close()

    if dry_run:
        print(f"\nDry run complete. Changes applied to backup: {backup_path}")
        print("Production database was NOT modified.")
    else:
        print(f"\nProduction database migrated. Backup at: {backup_path}")


def _run_migration(conn: sqlite3.Connection) -> None:
    """Execute all migration steps in order."""
    now = _now_iso()

    # -----------------------------------------------------------------------
    # Pre-migration counts for validation
    # -----------------------------------------------------------------------
    pre = {}
    pre["accounts"] = conn.execute("SELECT COUNT(*) FROM email_accounts").fetchone()[0]
    pre["conversations"] = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    pre["emails"] = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
    pre["contacts"] = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    pre["participants"] = conn.execute("SELECT COUNT(*) FROM conversation_participants").fetchone()[0]
    pre["recipients"] = conn.execute("SELECT COUNT(*) FROM email_recipients").fetchone()[0]
    pre["topics"] = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
    pre["conv_topics"] = conn.execute("SELECT COUNT(*) FROM conversation_topics").fetchone()[0]

    print(f"\nPre-migration counts:")
    for k, v in pre.items():
        print(f"  {k}: {v}")

    # -----------------------------------------------------------------------
    # Step 1: Create new empty tables
    # -----------------------------------------------------------------------
    print("\nStep 1: Creating new tables...")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT,
            role TEXT DEFAULT 'member', is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, parent_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL, description TEXT, status TEXT DEFAULT 'active',
            owner_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS contact_identifiers (
            id TEXT PRIMARY KEY,
            contact_id TEXT NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
            type TEXT NOT NULL, value TEXT NOT NULL, label TEXT,
            is_primary INTEGER DEFAULT 0, status TEXT DEFAULT 'active',
            source TEXT, verified INTEGER DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(type, value)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_communications (
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            communication_id TEXT NOT NULL,
            display_content TEXT, is_primary INTEGER DEFAULT 1,
            assignment_source TEXT NOT NULL DEFAULT 'sync',
            confidence REAL DEFAULT 1.0, reviewed INTEGER DEFAULT 0,
            reviewed_at TEXT, created_at TEXT NOT NULL,
            PRIMARY KEY (conversation_id, communication_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS attachments (
            id TEXT PRIMARY KEY,
            communication_id TEXT NOT NULL,
            filename TEXT NOT NULL, mime_type TEXT, size_bytes INTEGER,
            storage_ref TEXT, source TEXT, created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS views (
            id TEXT PRIMARY KEY, owner_id TEXT, name TEXT NOT NULL,
            description TEXT, query_def TEXT NOT NULL,
            is_shared INTEGER DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY, view_id TEXT NOT NULL, owner_id TEXT,
            is_active INTEGER DEFAULT 1, frequency TEXT NOT NULL,
            aggregation TEXT DEFAULT 'batched', delivery_method TEXT NOT NULL,
            last_triggered TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS assignment_corrections (
            id TEXT PRIMARY KEY, communication_id TEXT NOT NULL,
            from_conversation_id TEXT, to_conversation_id TEXT,
            correction_type TEXT NOT NULL, original_source TEXT,
            original_confidence REAL, corrected_by TEXT, created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS triage_corrections (
            id TEXT PRIMARY KEY, communication_id TEXT NOT NULL,
            original_result TEXT, corrected_result TEXT,
            correction_type TEXT NOT NULL, sender_address TEXT,
            sender_domain TEXT, subject TEXT, corrected_by TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS triage_rules (
            id TEXT PRIMARY KEY, rule_type TEXT NOT NULL,
            match_type TEXT NOT NULL, match_value TEXT NOT NULL,
            source TEXT NOT NULL, confidence REAL DEFAULT 1.0,
            user_id TEXT, created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_corrections (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
            correction_type TEXT NOT NULL, reason TEXT, details TEXT,
            participant_addresses TEXT, subject TEXT,
            communication_count INTEGER, corrected_by TEXT,
            created_at TEXT NOT NULL
        )
    """)

    print("  Created 11 new tables.")

    # -----------------------------------------------------------------------
    # Step 2: Rename topics → tags, conversation_topics → conversation_tags
    # -----------------------------------------------------------------------
    print("\nStep 2: Renaming topics → tags, conversation_topics → conversation_tags...")

    conn.execute("ALTER TABLE conversation_topics RENAME TO conversation_tags")
    conn.execute("ALTER TABLE conversation_tags RENAME COLUMN topic_id TO tag_id")
    conn.execute("ALTER TABLE topics RENAME TO tags")
    # Add source column to tags
    conn.execute("ALTER TABLE tags ADD COLUMN source TEXT DEFAULT 'ai'")

    print(f"  Renamed. {pre['topics']} tags, {pre['conv_topics']} conversation_tags.")

    # Create new organizational topics table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name TEXT NOT NULL, description TEXT,
            source TEXT DEFAULT 'user',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)
    print("  Created new organizational topics table.")

    # -----------------------------------------------------------------------
    # Step 3: Transform emails → communications
    # -----------------------------------------------------------------------
    print("\nStep 3: Transforming emails → communications...")

    # Add new columns to emails table
    conn.execute("ALTER TABLE emails ADD COLUMN channel TEXT DEFAULT 'email'")
    conn.execute("ALTER TABLE emails ADD COLUMN timestamp TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN content TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN source TEXT DEFAULT 'auto_sync'")
    conn.execute("ALTER TABLE emails ADD COLUMN provider_thread_id TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN is_current INTEGER DEFAULT 1")
    conn.execute("ALTER TABLE emails ADD COLUMN updated_at TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN phone_number_from TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN phone_number_to TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN duration_seconds INTEGER")
    conn.execute("ALTER TABLE emails ADD COLUMN transcript_source TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN note_type TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN provider_metadata TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN user_metadata TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN previous_revision TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN next_revision TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN ai_summary TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN ai_summarized_at TEXT")
    conn.execute("ALTER TABLE emails ADD COLUMN triage_result TEXT")

    # Populate timestamp from date, content from body_text
    conn.execute("UPDATE emails SET timestamp = date WHERE date IS NOT NULL")
    conn.execute(f"UPDATE emails SET timestamp = '{now}' WHERE timestamp IS NULL")
    conn.execute("UPDATE emails SET content = body_text")
    conn.execute(f"UPDATE emails SET updated_at = '{now}'")

    # Populate provider_thread_id from conversations
    conn.execute("""
        UPDATE emails SET provider_thread_id = (
            SELECT c.provider_thread_id FROM conversations c
            WHERE c.id = emails.conversation_id
        )
        WHERE conversation_id IS NOT NULL
    """)

    # Populate conversation_communications from conversation_id FK
    print("  Populating conversation_communications join table...")
    conn.execute(f"""
        INSERT INTO conversation_communications
            (conversation_id, communication_id, assignment_source, confidence, reviewed, created_at)
        SELECT conversation_id, id, 'sync', 1.0, 1, '{now}'
        FROM emails
        WHERE conversation_id IS NOT NULL
    """)
    cc_count = conn.execute("SELECT COUNT(*) FROM conversation_communications").fetchone()[0]
    print(f"  Created {cc_count} conversation_communication rows.")

    # Rename emails → communications
    conn.execute("ALTER TABLE emails RENAME TO communications")

    print(f"  Transformed {pre['emails']} emails → communications.")

    # -----------------------------------------------------------------------
    # Step 4: Transform email_recipients → communication_participants
    # -----------------------------------------------------------------------
    print("\nStep 4: Transforming email_recipients → communication_participants...")

    # Add contact_id column before rename
    conn.execute("ALTER TABLE email_recipients ADD COLUMN contact_id TEXT")
    conn.execute("ALTER TABLE email_recipients RENAME COLUMN email_id TO communication_id")
    conn.execute("ALTER TABLE email_recipients RENAME TO communication_participants")

    print(f"  Transformed {pre['recipients']} recipients → communication_participants.")

    # -----------------------------------------------------------------------
    # Step 5: Transform contacts (add columns, populate contact_identifiers)
    # -----------------------------------------------------------------------
    print("\nStep 5: Transforming contacts...")

    conn.execute("ALTER TABLE contacts ADD COLUMN company TEXT")
    conn.execute("ALTER TABLE contacts ADD COLUMN status TEXT DEFAULT 'active'")

    # Populate contact_identifiers from contacts.email
    conn.execute(f"""
        INSERT INTO contact_identifiers
            (id, contact_id, type, value, is_primary, status, source, verified, created_at, updated_at)
        SELECT
            lower(hex(randomblob(16))),
            id, 'email', lower(email), 1, 'active', source, 1, '{now}', '{now}'
        FROM contacts
        WHERE email IS NOT NULL AND email != ''
    """)
    ci_count = conn.execute("SELECT COUNT(*) FROM contact_identifiers").fetchone()[0]
    print(f"  Created {ci_count} contact_identifiers from contacts.email.")

    # Note: We can't drop columns in SQLite without recreating the table.
    # The old email and source_id columns will remain but be unused.
    # This is acceptable for the PoC migration.

    # -----------------------------------------------------------------------
    # Step 6: Transform conversations
    # -----------------------------------------------------------------------
    print("\nStep 6: Transforming conversations...")

    conn.execute("ALTER TABLE conversations ADD COLUMN topic_id TEXT")
    conn.execute("ALTER TABLE conversations ADD COLUMN title TEXT")
    conn.execute("ALTER TABLE conversations ADD COLUMN dismissed INTEGER DEFAULT 0")
    conn.execute("ALTER TABLE conversations ADD COLUMN dismissed_reason TEXT")
    conn.execute("ALTER TABLE conversations ADD COLUMN dismissed_at TEXT")
    conn.execute("ALTER TABLE conversations ADD COLUMN dismissed_by TEXT")
    conn.execute("ALTER TABLE conversations ADD COLUMN participant_count INTEGER DEFAULT 0")
    conn.execute("ALTER TABLE conversations ADD COLUMN communication_count INTEGER DEFAULT 0")
    conn.execute("ALTER TABLE conversations ADD COLUMN first_activity_at TEXT")
    conn.execute("ALTER TABLE conversations ADD COLUMN last_activity_at TEXT")

    # Populate new columns from old
    conn.execute("UPDATE conversations SET title = subject")
    conn.execute("UPDATE conversations SET communication_count = message_count")
    conn.execute("UPDATE conversations SET first_activity_at = first_message_at")
    conn.execute("UPDATE conversations SET last_activity_at = last_message_at")

    # Compute participant_count
    conn.execute("""
        UPDATE conversations SET participant_count = (
            SELECT COUNT(*) FROM conversation_participants cp
            WHERE cp.conversation_id = conversations.id
        )
    """)

    print(f"  Transformed {pre['conversations']} conversations.")

    # -----------------------------------------------------------------------
    # Step 7: Transform conversation_participants
    # -----------------------------------------------------------------------
    print("\nStep 7: Transforming conversation_participants...")

    conn.execute("ALTER TABLE conversation_participants ADD COLUMN address TEXT")
    conn.execute("ALTER TABLE conversation_participants ADD COLUMN communication_count INTEGER DEFAULT 0")
    conn.execute("ALTER TABLE conversation_participants ADD COLUMN name TEXT")

    # Populate address from email_address, communication_count from message_count
    conn.execute("UPDATE conversation_participants SET address = email_address")
    conn.execute("UPDATE conversation_participants SET communication_count = message_count")

    # Populate name from contacts where available
    conn.execute("""
        UPDATE conversation_participants SET name = (
            SELECT c.name FROM contacts c WHERE c.id = conversation_participants.contact_id
        )
        WHERE contact_id IS NOT NULL
    """)

    print(f"  Transformed {pre['participants']} participants.")

    # -----------------------------------------------------------------------
    # Step 8: Rename email_accounts → provider_accounts
    # -----------------------------------------------------------------------
    print("\nStep 8: Renaming email_accounts → provider_accounts...")

    conn.execute("ALTER TABLE email_accounts ADD COLUMN account_type TEXT DEFAULT 'email'")
    conn.execute("ALTER TABLE email_accounts ADD COLUMN phone_number TEXT")
    conn.execute("ALTER TABLE email_accounts RENAME TO provider_accounts")

    print(f"  Renamed. {pre['accounts']} provider_accounts.")

    # -----------------------------------------------------------------------
    # Step 9: Drop old indexes and create new ones
    # -----------------------------------------------------------------------
    print("\nStep 9: Recreating indexes...")

    # Drop old indexes
    old_indexes = [
        "idx_emails_account", "idx_emails_conversation", "idx_emails_date",
        "idx_emails_sender", "idx_emails_message_id_hdr",
        "idx_conversations_account", "idx_conversations_status",
        "idx_conversations_last_msg",
        "idx_recipients_address",
        "idx_participants_contact", "idx_participants_email",
        "idx_sync_log_account",
        "idx_relationships_from", "idx_relationships_to",
    ]
    for idx in old_indexes:
        conn.execute(f"DROP INDEX IF EXISTS {idx}")

    # Create new indexes
    new_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_comm_account ON communications(account_id)",
        "CREATE INDEX IF NOT EXISTS idx_comm_channel ON communications(channel)",
        "CREATE INDEX IF NOT EXISTS idx_comm_timestamp ON communications(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_comm_sender ON communications(sender_address)",
        "CREATE INDEX IF NOT EXISTS idx_comm_thread ON communications(provider_thread_id)",
        "CREATE INDEX IF NOT EXISTS idx_comm_header_msg_id ON communications(header_message_id)",
        "CREATE INDEX IF NOT EXISTS idx_comm_current ON communications(is_current)",
        "CREATE INDEX IF NOT EXISTS idx_conv_topic ON conversations(topic_id)",
        "CREATE INDEX IF NOT EXISTS idx_conv_status ON conversations(status)",
        "CREATE INDEX IF NOT EXISTS idx_conv_last_activity ON conversations(last_activity_at)",
        "CREATE INDEX IF NOT EXISTS idx_conv_ai_status ON conversations(ai_status)",
        "CREATE INDEX IF NOT EXISTS idx_conv_triage ON conversations(triage_result)",
        "CREATE INDEX IF NOT EXISTS idx_conv_needs_processing ON conversations(triage_result, ai_summarized_at)",
        "CREATE INDEX IF NOT EXISTS idx_conv_dismissed ON conversations(dismissed)",
        "CREATE INDEX IF NOT EXISTS idx_cc_communication ON conversation_communications(communication_id)",
        "CREATE INDEX IF NOT EXISTS idx_cc_review ON conversation_communications(assignment_source, reviewed)",
        "CREATE INDEX IF NOT EXISTS idx_cp_contact ON conversation_participants(contact_id)",
        "CREATE INDEX IF NOT EXISTS idx_cp_address ON conversation_participants(address)",
        "CREATE INDEX IF NOT EXISTS idx_commpart_address ON communication_participants(address)",
        "CREATE INDEX IF NOT EXISTS idx_commpart_contact ON communication_participants(contact_id)",
        "CREATE INDEX IF NOT EXISTS idx_ci_contact ON contact_identifiers(contact_id)",
        "CREATE INDEX IF NOT EXISTS idx_ci_status ON contact_identifiers(status)",
        "CREATE INDEX IF NOT EXISTS idx_projects_parent ON projects(parent_id)",
        "CREATE INDEX IF NOT EXISTS idx_topics_project ON topics(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_attachments_comm ON attachments(communication_id)",
        "CREATE INDEX IF NOT EXISTS idx_sync_log_account ON sync_log(account_id)",
        "CREATE INDEX IF NOT EXISTS idx_views_owner ON views(owner_id)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_view ON alerts(view_id)",
        "CREATE INDEX IF NOT EXISTS idx_triage_rules_match ON triage_rules(match_type, match_value)",
        "CREATE INDEX IF NOT EXISTS idx_ac_communication ON assignment_corrections(communication_id)",
        "CREATE INDEX IF NOT EXISTS idx_tc_communication ON triage_corrections(communication_id)",
        "CREATE INDEX IF NOT EXISTS idx_tc_sender_domain ON triage_corrections(sender_domain)",
        "CREATE INDEX IF NOT EXISTS idx_cc_conversation ON conversation_corrections(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_entity_id)",
        "CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_entity_id)",
    ]
    for sql in new_indexes:
        conn.execute(sql)

    print(f"  Created {len(new_indexes)} indexes.")

    # -----------------------------------------------------------------------
    # Step 10: Validation
    # -----------------------------------------------------------------------
    print("\nStep 10: Validation...")

    post = {}
    post["provider_accounts"] = conn.execute("SELECT COUNT(*) FROM provider_accounts").fetchone()[0]
    post["conversations"] = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    post["communications"] = conn.execute("SELECT COUNT(*) FROM communications").fetchone()[0]
    post["contacts"] = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    post["contact_identifiers"] = conn.execute("SELECT COUNT(*) FROM contact_identifiers").fetchone()[0]
    post["conversation_communications"] = conn.execute("SELECT COUNT(*) FROM conversation_communications").fetchone()[0]
    post["conversation_participants"] = conn.execute("SELECT COUNT(*) FROM conversation_participants").fetchone()[0]
    post["communication_participants"] = conn.execute("SELECT COUNT(*) FROM communication_participants").fetchone()[0]
    post["tags"] = conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    post["conversation_tags"] = conn.execute("SELECT COUNT(*) FROM conversation_tags").fetchone()[0]

    print(f"\nPost-migration counts:")
    for k, v in post.items():
        print(f"  {k}: {v}")

    # Assertions
    errors = []
    if post["provider_accounts"] != pre["accounts"]:
        errors.append(f"Account count mismatch: {post['provider_accounts']} != {pre['accounts']}")
    if post["conversations"] != pre["conversations"]:
        errors.append(f"Conversation count mismatch: {post['conversations']} != {pre['conversations']}")
    if post["communications"] != pre["emails"]:
        errors.append(f"Communication count mismatch: {post['communications']} != {pre['emails']}")
    if post["contacts"] != pre["contacts"]:
        errors.append(f"Contact count mismatch: {post['contacts']} != {pre['contacts']}")
    if post["contact_identifiers"] != pre["contacts"]:
        errors.append(f"Contact identifiers count mismatch: {post['contact_identifiers']} != {pre['contacts']}")
    if post["tags"] != pre["topics"]:
        errors.append(f"Tags count mismatch: {post['tags']} != {pre['topics']}")
    if post["conversation_tags"] != pre["conv_topics"]:
        errors.append(f"Conversation tags mismatch: {post['conversation_tags']} != {pre['conv_topics']}")

    # Verify all communications have channel='email' and is_current=1
    non_email = conn.execute(
        "SELECT COUNT(*) FROM communications WHERE channel != 'email'"
    ).fetchone()[0]
    if non_email > 0:
        errors.append(f"{non_email} communications without channel='email'")

    non_current = conn.execute(
        "SELECT COUNT(*) FROM communications WHERE is_current != 1"
    ).fetchone()[0]
    if non_current > 0:
        errors.append(f"{non_current} communications without is_current=1")

    # Verify all communications have timestamps
    null_ts = conn.execute(
        "SELECT COUNT(*) FROM communications WHERE timestamp IS NULL"
    ).fetchone()[0]
    if null_ts > 0:
        errors.append(f"{null_ts} communications with NULL timestamp")

    # Verify conversation_communications count matches emails with conversation_id
    emails_with_conv = conn.execute(
        "SELECT COUNT(*) FROM communications WHERE conversation_id IS NOT NULL"
    ).fetchone()[0]
    if post["conversation_communications"] != emails_with_conv:
        errors.append(
            f"conversation_communications ({post['conversation_communications']}) "
            f"!= emails with conversation_id ({emails_with_conv})"
        )

    # FK integrity check
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        errors.append(f"{len(fk_violations)} FK violations found")
        for v in fk_violations[:5]:
            errors.append(f"  FK violation: {dict(v) if hasattr(v, 'keys') else v}")

    if errors:
        print("\nVALIDATION ERRORS:")
        for e in errors:
            print(f"  ERROR: {e}")
        raise RuntimeError(f"Migration validation failed with {len(errors)} error(s)")
    else:
        print("\nAll validations passed!")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate CRMExtender database from v1 to v2 schema"
    )
    parser.add_argument(
        "--db", type=Path,
        help="Path to the SQLite database file",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Apply migration to a backup copy instead of the real database",
    )
    args = parser.parse_args()

    if args.db:
        db_path = args.db
    else:
        # Import config to get default path
        from poc import config
        db_path = config.DB_PATH

    migrate(db_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
