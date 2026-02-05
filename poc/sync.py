"""Sync orchestration: initial and incremental sync to SQLite."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials

from . import config
from .contact_matcher import build_contact_index, match_contacts
from .contacts_client import fetch_contacts
from .conversation_builder import build_conversations
from .database import get_connection
from .email_parser import strip_quotes
from .gmail_client import (
    fetch_history,
    fetch_messages,
    fetch_threads,
    get_history_id,
    get_user_email,
)
from .models import (
    Conversation,
    ConversationSummary,
    FilterReason,
    KnownContact,
    ParsedEmail,
    TriageResult,
    _now_iso,
    filter_reason_from_db,
    filter_reason_to_db,
)
from .rate_limiter import RateLimiter
from .summarizer import summarize_conversation
from .triage import triage_conversations

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Account registration
# ---------------------------------------------------------------------------

def register_account(
    creds: Credentials,
    provider: str = "gmail",
    backfill_query: str | None = None,
    token_path: str | None = None,
) -> str:
    """Register an email account or return its existing ID.

    Returns the account_id (UUID).
    """
    user_email = get_user_email(creds)
    token_path = token_path or str(config.TOKEN_PATH)
    now = _now_iso()

    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM email_accounts WHERE provider = ? AND email_address = ?",
            (provider, user_email),
        ).fetchone()

        if row:
            log.info("Account already registered: %s (%s)", user_email, row["id"])
            return row["id"]

        account_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO email_accounts
               (id, provider, email_address, display_name, auth_token_path,
                backfill_query, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                account_id, provider, user_email, None, token_path,
                backfill_query or config.GMAIL_QUERY, now, now,
            ),
        )
        log.info("Registered account %s: %s", account_id, user_email)
        return account_id


def get_account(account_id: str) -> dict | None:
    """Load an account row as a dict."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM email_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        return dict(row) if row else None


def get_all_accounts() -> list[dict]:
    """Return all registered email accounts."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM email_accounts ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Contact sync
# ---------------------------------------------------------------------------

def sync_contacts(
    creds: Credentials,
    rate_limiter: RateLimiter | None = None,
) -> int:
    """Fetch contacts from Google People API and UPSERT into contacts table.

    Returns the number of contacts stored.
    """
    contacts = fetch_contacts(creds, rate_limiter=rate_limiter)
    now = _now_iso()
    count = 0

    with get_connection() as conn:
        for kc in contacts:
            conn.execute(
                """INSERT INTO contacts (id, email, name, source, source_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(email) DO UPDATE SET
                       name = excluded.name,
                       source_id = excluded.source_id,
                       updated_at = excluded.updated_at""",
                (
                    str(uuid.uuid4()), kc.email.lower(), kc.name,
                    "google_contacts", kc.resource_name, now, now,
                ),
            )
            count += 1

    log.info("Synced %d contacts to database", count)
    return count


def load_contact_index() -> dict[str, KnownContact]:
    """Load contacts from DB and return a contact_index (email -> KnownContact)."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM contacts").fetchall()

    index: dict[str, KnownContact] = {}
    for row in rows:
        kc = KnownContact.from_row(row)
        index[kc.email.lower()] = kc
    return index


# ---------------------------------------------------------------------------
# Conversation + email persistence
# ---------------------------------------------------------------------------

def _store_thread(
    conn,
    account_id: str,
    account_email: str,
    thread_emails: list[ParsedEmail],
    contact_index: dict[str, KnownContact],
) -> tuple[bool, bool]:
    """Store a single thread's conversation and emails.

    Returns (conversation_created, conversation_updated).
    """
    if not thread_emails:
        return False, False

    thread_id = thread_emails[0].thread_id
    subject = thread_emails[0].subject or "(no subject)"

    # Strip quotes from bodies
    for em in thread_emails:
        em.body_plain = strip_quotes(em.body_plain)

    # Check if conversation already exists
    existing = conn.execute(
        "SELECT id, message_count FROM conversations WHERE account_id = ? AND provider_thread_id = ?",
        (account_id, thread_id),
    ).fetchone()

    # Compute date range
    dates = [e.date for e in thread_emails if e.date]
    first_dt = min(dates).isoformat() if dates else None
    last_dt = max(dates).isoformat() if dates else None
    now = _now_iso()

    if existing:
        conv_id = existing["id"]
        conversation_created = False
    else:
        conv_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO conversations
               (id, account_id, provider_thread_id, subject, status,
                message_count, first_message_at, last_message_at,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)""",
            (conv_id, account_id, thread_id, subject,
             len(thread_emails), first_dt, last_dt, now, now),
        )
        conversation_created = True

    # Insert emails (skip duplicates)
    new_email_count = 0
    for em in thread_emails:
        email_id = str(uuid.uuid4())
        row = em.to_row(
            account_id=account_id,
            conversation_id=conv_id,
            email_id=email_id,
            account_email=account_email,
        )
        try:
            conn.execute(
                """INSERT OR IGNORE INTO emails
                   (id, account_id, conversation_id, provider_message_id, subject,
                    sender_address, sender_name, date, body_text, body_html, snippet,
                    header_message_id, header_references, header_in_reply_to,
                    direction, is_read, has_attachments, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["id"], row["account_id"], row["conversation_id"],
                    row["provider_message_id"], row["subject"],
                    row["sender_address"], row["sender_name"], row["date"],
                    row["body_text"], row["body_html"], row["snippet"],
                    row["header_message_id"], row["header_references"],
                    row["header_in_reply_to"], row["direction"],
                    row["is_read"], row["has_attachments"], row["created_at"],
                ),
            )
        except Exception:
            # Duplicate — already stored
            continue

        # Check if this was actually inserted (not ignored due to UNIQUE)
        if conn.execute(
            "SELECT 1 FROM emails WHERE id = ?", (email_id,)
        ).fetchone():
            new_email_count += 1
            # Insert recipients
            for rec_row in em.recipient_rows(email_id):
                conn.execute(
                    """INSERT OR IGNORE INTO email_recipients
                       (email_id, address, name, role)
                       VALUES (?, ?, ?, ?)""",
                    (rec_row["email_id"], rec_row["address"],
                     rec_row["name"], rec_row["role"]),
                )

    conversation_updated = False
    if existing and new_email_count > 0:
        # Update conversation counts and timestamps
        actual_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM emails WHERE conversation_id = ?",
            (conv_id,),
        ).fetchone()["cnt"]

        # Recalculate date range from stored emails
        date_row = conn.execute(
            "SELECT MIN(date) as first_dt, MAX(date) as last_dt FROM emails WHERE conversation_id = ?",
            (conv_id,),
        ).fetchone()

        conn.execute(
            """UPDATE conversations
               SET message_count = ?, first_message_at = ?, last_message_at = ?,
                   ai_summarized_at = NULL, updated_at = ?
               WHERE id = ?""",
            (actual_count, date_row["first_dt"], date_row["last_dt"], now, conv_id),
        )
        conversation_updated = True

    # Upsert conversation participants
    all_participants: dict[str, None] = {}
    for em in thread_emails:
        for p in em.all_participants:
            all_participants[p] = None

    for addr in all_participants:
        # Look up contact_id
        contact_row = conn.execute(
            "SELECT id FROM contacts WHERE email = ?",
            (addr.lower(),),
        ).fetchone()
        contact_id = contact_row["id"] if contact_row else None

        # Count messages from this participant in the conversation
        msg_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM emails WHERE conversation_id = ? AND sender_address = ?",
            (conv_id, addr),
        ).fetchone()["cnt"]

        # Get first/last seen dates
        date_row = conn.execute(
            "SELECT MIN(date) as first_dt, MAX(date) as last_dt FROM emails WHERE conversation_id = ? AND sender_address = ?",
            (conv_id, addr),
        ).fetchone()

        conn.execute(
            """INSERT INTO conversation_participants
               (conversation_id, email_address, contact_id, message_count, first_seen_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(conversation_id, email_address) DO UPDATE SET
                   contact_id = excluded.contact_id,
                   message_count = excluded.message_count,
                   first_seen_at = excluded.first_seen_at,
                   last_seen_at = excluded.last_seen_at""",
            (conv_id, addr, contact_id, msg_count,
             date_row["first_dt"], date_row["last_dt"]),
        )

    return conversation_created, conversation_updated


# ---------------------------------------------------------------------------
# Initial sync
# ---------------------------------------------------------------------------

def initial_sync(
    account_id: str,
    creds: Credentials,
    rate_limiter: RateLimiter | None = None,
) -> dict:
    """Run the initial full sync for an account.

    Returns a summary dict with counts.
    """
    account = get_account(account_id)
    if not account:
        raise ValueError(f"Account {account_id} not found")

    account_email = account["email_address"]
    query = account["backfill_query"] or config.GMAIL_QUERY

    # Start sync log
    sync_id = str(uuid.uuid4())
    now = _now_iso()

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO sync_log
               (id, account_id, sync_type, started_at, status)
               VALUES (?, ?, 'initial', ?, 'running')""",
            (sync_id, account_id, now),
        )

    contact_index = load_contact_index()

    # Fetch all threads
    messages_fetched = 0
    messages_stored = 0
    conversations_created = 0
    conversations_updated = 0
    page_token: str | None = None

    while True:
        threads, page_token = fetch_threads(
            creds,
            query=query,
            max_threads=config.GMAIL_MAX_THREADS,
            rate_limiter=rate_limiter,
            page_token=page_token,
        )

        if not threads:
            break

        with get_connection() as conn:
            for thread_emails in threads:
                messages_fetched += len(thread_emails)
                created, updated = _store_thread(
                    conn, account_id, account_email, thread_emails, contact_index,
                )
                if created:
                    conversations_created += 1
                if updated:
                    conversations_updated += 1
                # Count net new emails stored
                for em in thread_emails:
                    row = conn.execute(
                        "SELECT 1 FROM emails WHERE account_id = ? AND provider_message_id = ?",
                        (account_id, em.message_id),
                    ).fetchone()
                    if row:
                        messages_stored += 1

        if not page_token:
            break

    # Record sync cursor (current historyId)
    history_id = get_history_id(creds)
    now = _now_iso()

    with get_connection() as conn:
        conn.execute(
            """UPDATE email_accounts
               SET sync_cursor = ?, initial_sync_done = 1,
                   last_synced_at = ?, updated_at = ?
               WHERE id = ?""",
            (history_id, now, now, account_id),
        )
        conn.execute(
            """UPDATE sync_log
               SET status = 'completed', completed_at = ?,
                   messages_fetched = ?, messages_stored = ?,
                   conversations_created = ?, conversations_updated = ?,
                   cursor_after = ?
               WHERE id = ?""",
            (now, messages_fetched, messages_stored,
             conversations_created, conversations_updated,
             history_id, sync_id),
        )

    result = {
        "sync_id": sync_id,
        "messages_fetched": messages_fetched,
        "messages_stored": messages_stored,
        "conversations_created": conversations_created,
        "conversations_updated": conversations_updated,
        "history_id": history_id,
    }
    log.info("Initial sync complete: %s", result)
    return result


# ---------------------------------------------------------------------------
# Incremental sync
# ---------------------------------------------------------------------------

def incremental_sync(
    account_id: str,
    creds: Credentials,
    rate_limiter: RateLimiter | None = None,
) -> dict:
    """Run an incremental sync using Gmail historyId.

    Returns a summary dict with counts.
    """
    account = get_account(account_id)
    if not account:
        raise ValueError(f"Account {account_id} not found")

    account_email = account["email_address"]
    cursor_before = account["sync_cursor"]

    if not cursor_before:
        raise ValueError(f"Account {account_id} has no sync_cursor; run initial_sync first")

    # Start sync log
    sync_id = str(uuid.uuid4())
    now = _now_iso()

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO sync_log
               (id, account_id, sync_type, started_at, cursor_before, status)
               VALUES (?, ?, 'incremental', ?, ?, 'running')""",
            (sync_id, account_id, now, cursor_before),
        )

    contact_index = load_contact_index()

    # Fetch history changes
    added_ids, deleted_ids = fetch_history(
        creds, cursor_before, rate_limiter=rate_limiter,
    )

    messages_fetched = len(added_ids)
    messages_stored = 0
    conversations_created = 0
    conversations_updated = 0

    # Process additions: fetch full messages and store
    if added_ids:
        new_emails = fetch_messages(creds, added_ids, rate_limiter=rate_limiter)

        # Group by thread_id
        threads_map: dict[str, list[ParsedEmail]] = {}
        for em in new_emails:
            threads_map.setdefault(em.thread_id, []).append(em)

        with get_connection() as conn:
            for thread_id, thread_emails in threads_map.items():
                # Sort by date
                thread_emails.sort(
                    key=lambda e: e.date or datetime.min.replace(tzinfo=timezone.utc)
                )
                created, updated = _store_thread(
                    conn, account_id, account_email, thread_emails, contact_index,
                )
                if created:
                    conversations_created += 1
                if updated:
                    conversations_updated += 1
                messages_stored += len(thread_emails)

    # Process deletions
    if deleted_ids:
        with get_connection() as conn:
            for mid in deleted_ids:
                # Find the email and its conversation
                email_row = conn.execute(
                    "SELECT id, conversation_id FROM emails WHERE account_id = ? AND provider_message_id = ?",
                    (account_id, mid),
                ).fetchone()
                if email_row:
                    conv_id = email_row["conversation_id"]
                    conn.execute(
                        "DELETE FROM emails WHERE id = ?",
                        (email_row["id"],),
                    )
                    # Update conversation message count
                    if conv_id:
                        actual_count = conn.execute(
                            "SELECT COUNT(*) as cnt FROM emails WHERE conversation_id = ?",
                            (conv_id,),
                        ).fetchone()["cnt"]
                        conn.execute(
                            "UPDATE conversations SET message_count = ?, updated_at = ? WHERE id = ?",
                            (actual_count, _now_iso(), conv_id),
                        )

    # Update sync cursor
    history_id = get_history_id(creds)
    now = _now_iso()

    with get_connection() as conn:
        conn.execute(
            """UPDATE email_accounts
               SET sync_cursor = ?, last_synced_at = ?, updated_at = ?
               WHERE id = ?""",
            (history_id, now, now, account_id),
        )
        conn.execute(
            """UPDATE sync_log
               SET status = 'completed', completed_at = ?,
                   messages_fetched = ?, messages_stored = ?,
                   conversations_created = ?, conversations_updated = ?,
                   cursor_after = ?
               WHERE id = ?""",
            (now, messages_fetched, messages_stored,
             conversations_created, conversations_updated,
             history_id, sync_id),
        )

    result = {
        "sync_id": sync_id,
        "messages_fetched": messages_fetched,
        "messages_stored": messages_stored,
        "conversations_created": conversations_created,
        "conversations_updated": conversations_updated,
        "cursor_before": cursor_before,
        "history_id": history_id,
    }
    log.info("Incremental sync complete: %s", result)
    return result


# ---------------------------------------------------------------------------
# Conversation processing (triage + summarize)
# ---------------------------------------------------------------------------

def process_conversations(
    account_id: str,
    creds: Credentials,
    user_email: str,
    rate_limiter: RateLimiter | None = None,
    claude_limiter: RateLimiter | None = None,
) -> tuple[int, int, int]:
    """Triage and summarize conversations that need processing.

    Returns (triaged_count, summarized_count, topic_count).
    """
    contact_index = load_contact_index()
    import anthropic

    # Find conversations needing processing
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM conversations
               WHERE account_id = ?
                 AND triage_result IS NULL
                 AND ai_summarized_at IS NULL
               ORDER BY last_message_at DESC""",
            (account_id,),
        ).fetchall()

    if not rows:
        log.info("No conversations need processing")
        return 0, 0, 0

    triaged_count = 0
    summarized_count = 0
    topic_count = 0

    for conv_row in rows:
        conv_id = conv_row["id"]

        # Load emails for this conversation
        with get_connection() as conn:
            email_rows = conn.execute(
                "SELECT * FROM emails WHERE conversation_id = ? ORDER BY date",
                (conv_id,),
            ).fetchall()

        emails = []
        for er in email_rows:
            rec_rows = None
            with get_connection() as conn:
                rec_rows = conn.execute(
                    "SELECT * FROM email_recipients WHERE email_id = ?",
                    (er["id"],),
                ).fetchall()
            emails.append(ParsedEmail.from_row(er, recipients=rec_rows))

        # Reconstruct Conversation object for triage/summarization
        conv = Conversation(
            thread_id=conv_row["provider_thread_id"] or conv_id,
            subject=conv_row["subject"] or "",
            emails=emails,
            participants=[],
        )

        # Collect participants and match contacts
        all_participants: dict[str, None] = {}
        for em in conv.emails:
            for p in em.all_participants:
                all_participants[p] = None
        conv.participants = list(all_participants.keys())

        # Match contacts
        for p in conv.participants:
            if p in contact_index:
                conv.matched_contacts[p] = contact_index[p]

        # Triage
        kept, filtered = triage_conversations([conv], user_email)

        if filtered:
            reason = filtered[0].reason
            with get_connection() as conn:
                conn.execute(
                    "UPDATE conversations SET triage_result = ?, updated_at = ? WHERE id = ?",
                    (filter_reason_to_db(reason), _now_iso(), conv_id),
                )
            triaged_count += 1
            continue

        # Summarize (only if API key is set)
        if not config.ANTHROPIC_API_KEY:
            continue

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        summary = summarize_conversation(conv, client, user_email, claude_limiter)

        if not summary.error:
            update = summary.to_update_dict()
            with get_connection() as conn:
                conn.execute(
                    """UPDATE conversations
                       SET ai_summary = ?, ai_status = ?, ai_action_items = ?,
                           ai_topics = ?, ai_summarized_at = ?, updated_at = ?
                       WHERE id = ?""",
                    (
                        update["ai_summary"], update["ai_status"],
                        update["ai_action_items"], update["ai_topics"],
                        update["ai_summarized_at"], _now_iso(), conv_id,
                    ),
                )
            summarized_count += 1

            # Extract and normalize topics
            if summary.key_topics:
                topic_count += _store_topics(conv_id, summary.key_topics)

    log.info(
        "Processing complete: %d triaged, %d summarized, %d topics",
        triaged_count, summarized_count, topic_count,
    )
    return triaged_count, summarized_count, topic_count


def _store_topics(conversation_id: str, topics: list[str]) -> int:
    """Normalize and store topics for a conversation. Returns count stored."""
    now = _now_iso()
    count = 0

    with get_connection() as conn:
        for raw_topic in topics:
            name = raw_topic.strip().lower()
            if not name:
                continue

            # Upsert topic
            topic_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO topics (id, name, created_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(name) DO NOTHING""",
                (topic_id, name, now),
            )

            # Get the actual topic ID (may already exist)
            topic_row = conn.execute(
                "SELECT id FROM topics WHERE name = ?",
                (name,),
            ).fetchone()
            actual_id = topic_row["id"]

            # Link to conversation
            conn.execute(
                """INSERT OR IGNORE INTO conversation_topics
                   (conversation_id, topic_id, confidence, source, created_at)
                   VALUES (?, ?, 1.0, 'ai', ?)""",
                (conversation_id, actual_id, now),
            )
            count += 1

    return count


# ---------------------------------------------------------------------------
# Query helpers (for display / __main__)
# ---------------------------------------------------------------------------

def load_conversations_for_display(
    account_id: str | None = None,
    *,
    account_ids: list[str] | None = None,
    include_triaged: bool = False,
    limit: int | None = None,
) -> tuple[list[Conversation], list[ConversationSummary], list]:
    """Load conversations with their summaries from DB.

    Pass a single account_id or a list of account_ids for multi-account.
    Returns (conversations, summaries, triage_filtered) ready for display.py.
    """
    # Resolve the list of IDs to query
    ids = account_ids or ([account_id] if account_id else [])
    if not ids:
        return [], [], []

    placeholders = ",".join("?" for _ in ids)

    # Build email-address lookup for account badges
    account_email_map: dict[str, str] = {}
    with get_connection() as conn:
        for aid in ids:
            row = conn.execute(
                "SELECT email_address FROM email_accounts WHERE id = ?", (aid,)
            ).fetchone()
            if row:
                account_email_map[aid] = row["email_address"]

    with get_connection() as conn:
        if include_triaged:
            query = f"""SELECT * FROM conversations
                       WHERE account_id IN ({placeholders})
                       ORDER BY last_message_at DESC"""
        else:
            query = f"""SELECT * FROM conversations
                       WHERE account_id IN ({placeholders}) AND triage_result IS NULL
                       ORDER BY last_message_at DESC"""

        if limit:
            query += f" LIMIT {limit}"

        conv_rows = conn.execute(query, ids).fetchall()

    conversations: list[Conversation] = []
    summaries: list[ConversationSummary] = []
    triage_filtered: list[TriageResult] = []

    for cr in conv_rows:
        conv_id = cr["id"]

        # Check if triaged out
        if cr["triage_result"]:
            triage_filtered.append(
                TriageResult(
                    thread_id=cr["provider_thread_id"] or conv_id,
                    subject=cr["subject"] or "",
                    reason=filter_reason_from_db(cr["triage_result"]),
                )
            )
            continue

        # Load emails
        with get_connection() as conn:
            email_rows = conn.execute(
                "SELECT * FROM emails WHERE conversation_id = ? ORDER BY date",
                (conv_id,),
            ).fetchall()

        emails = []
        for er in email_rows:
            with get_connection() as conn:
                rec_rows = conn.execute(
                    "SELECT * FROM email_recipients WHERE email_id = ?",
                    (er["id"],),
                ).fetchall()
            emails.append(ParsedEmail.from_row(er, recipients=rec_rows))

        # Build conversation
        conv = Conversation(
            thread_id=cr["provider_thread_id"] or conv_id,
            subject=cr["subject"] or "",
            emails=emails,
            participants=[],
            account_email=account_email_map.get(cr["account_id"], ""),
        )

        # Load participants and match contacts
        with get_connection() as conn:
            part_rows = conn.execute(
                "SELECT * FROM conversation_participants WHERE conversation_id = ?",
                (conv_id,),
            ).fetchall()

        for pr in part_rows:
            conv.participants.append(pr["email_address"])
            if pr["contact_id"]:
                with get_connection() as conn:
                    contact_row = conn.execute(
                        "SELECT * FROM contacts WHERE id = ?",
                        (pr["contact_id"],),
                    ).fetchone()
                if contact_row:
                    conv.matched_contacts[pr["email_address"]] = KnownContact.from_row(contact_row)

        conversations.append(conv)

        # Load summary
        summary = ConversationSummary.from_conversation_row(cr)
        if summary:
            summaries.append(summary)

    # Also load triage-only rows if not already included
    if not include_triaged:
        with get_connection() as conn:
            triaged_rows = conn.execute(
                f"""SELECT * FROM conversations
                   WHERE account_id IN ({placeholders}) AND triage_result IS NOT NULL
                   ORDER BY last_message_at DESC""",
                ids,
            ).fetchall()
        for tr in triaged_rows:
            triage_filtered.append(
                TriageResult(
                    thread_id=tr["provider_thread_id"] or tr["id"],
                    subject=tr["subject"] or "",
                    reason=filter_reason_from_db(tr["triage_result"]),
                )
            )

    return conversations, summaries, triage_filtered
