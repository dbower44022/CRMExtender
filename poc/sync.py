"""Sync orchestration: initial and incremental sync to SQLite."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials

from . import config
from .contacts_client import fetch_contacts
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
    KnownContact,
    ParsedEmail,
    TriageResult,
    _now_iso,
    filter_reason_from_db,
)
from .domain_resolver import (
    ensure_domain_identifier,
    extract_domain,
    is_public_domain,
    resolve_company_by_domain,
)
from .rate_limiter import RateLimiter
from .summarizer import summarize_conversation
from .triage import AUTOMATED_SENDER_PATTERNS

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
            "SELECT id FROM provider_accounts WHERE provider = ? AND email_address = ?",
            (provider, user_email),
        ).fetchone()

        if row:
            log.info("Account already registered: %s (%s)", user_email, row["id"])
            return row["id"]

        account_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO provider_accounts
               (id, provider, account_type, email_address, display_name,
                auth_token_path, backfill_query, created_at, updated_at)
               VALUES (?, ?, 'email', ?, ?, ?, ?, ?, ?)""",
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
            "SELECT * FROM provider_accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        return dict(row) if row else None


def get_all_accounts() -> list[dict]:
    """Return all registered provider accounts."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM provider_accounts ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Contact sync
# ---------------------------------------------------------------------------

def _resolve_company_id(
    conn, email: str, now: str,
    *, customer_id: str | None = None, user_id: str | None = None,
) -> str | None:
    """Look up or auto-create a company by email domain. Returns company_id or None.

    Uses the email domain as the sole source of truth for company identity.
    Public-domain emails (gmail.com, etc.) return None — no company affiliation.

    Resolution:
    1. Extract domain; return None for public/no domain
    2. Domain match via ``resolve_company_by_domain`` — return if found
    3. Auto-create company named after the domain
    """
    domain = extract_domain(email) if email else None
    if not domain or is_public_domain(domain):
        return None

    # Step 1: look up existing company by domain
    company = resolve_company_by_domain(conn, domain)
    if company:
        return company["id"]

    # Step 2: auto-create company named after the domain
    company_id = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO companies (id, name, domain, status, customer_id, created_at, updated_at)
           VALUES (?, ?, ?, 'active', ?, ?, ?)""",
        (company_id, domain, domain, customer_id, now, now),
    )

    # Create user_companies linkage
    if user_id:
        conn.execute(
            """INSERT OR IGNORE INTO user_companies
               (id, user_id, company_id, visibility, is_owner, created_at, updated_at)
               VALUES (?, ?, ?, 'public', 1, ?, ?)""",
            (str(uuid.uuid4()), user_id, company_id, now, now),
        )

    # Register email domain identifier
    ensure_domain_identifier(conn, company_id, domain)

    return company_id


def sync_contacts(
    creds: Credentials,
    rate_limiter: RateLimiter | None = None,
    *,
    customer_id: str | None = None,
    user_id: str | None = None,
) -> int:
    """Fetch contacts from Google People API and UPSERT into contacts + contact_identifiers.

    Returns the number of contacts stored.
    """
    contacts = fetch_contacts(creds, rate_limiter=rate_limiter)
    now = _now_iso()
    count = 0

    with get_connection() as conn:
        for kc in contacts:
            email_lower = kc.email.lower()
            company_id = _resolve_company_id(
                conn, kc.email, now,
                customer_id=customer_id, user_id=user_id,
            )

            # Check if identifier already exists
            existing = conn.execute(
                "SELECT ci.contact_id FROM contact_identifiers ci WHERE ci.type = 'email' AND ci.value = ?",
                (email_lower,),
            ).fetchone()

            if existing:
                # Update existing contact
                contact_id = existing["contact_id"]
                conn.execute(
                    "UPDATE contacts SET name = ?, updated_at = ? WHERE id = ?",
                    (kc.name, now, contact_id),
                )
            else:
                # Insert new contact + identifier
                contact_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO contacts (id, name, source, status,
                       customer_id, created_by, created_at, updated_at)
                       VALUES (?, ?, 'google_contacts', 'active', ?, ?, ?, ?)""",
                    (contact_id, kc.name,
                     customer_id, user_id, now, now),
                )
                conn.execute(
                    """INSERT INTO contact_identifiers
                       (id, contact_id, type, value, is_primary, status, source, verified, created_at, updated_at)
                       VALUES (?, ?, 'email', ?, 1, 'active', 'google_contacts', 1, ?, ?)""",
                    (str(uuid.uuid4()), contact_id, email_lower, now, now),
                )
                # Create user_contacts linkage
                if user_id:
                    conn.execute(
                        """INSERT OR IGNORE INTO user_contacts
                           (id, user_id, contact_id, visibility, is_owner, created_at, updated_at)
                           VALUES (?, ?, ?, 'public', 1, ?, ?)""",
                        (str(uuid.uuid4()), user_id, contact_id, now, now),
                    )

            # Create affiliation if company resolved
            if company_id:
                # Use default Employee role for the customer
                emp_role = conn.execute(
                    "SELECT id FROM contact_company_roles "
                    "WHERE name = 'Employee' AND customer_id = ?",
                    (customer_id,),
                ).fetchone()
                emp_role_id = emp_role["id"] if emp_role else None
                conn.execute(
                    """INSERT OR IGNORE INTO contact_companies
                       (id, contact_id, company_id, role_id, is_primary, is_current,
                        source, created_at, updated_at)
                       VALUES (?, ?, ?, ?, 1, 1, 'sync', ?, ?)""",
                    (str(uuid.uuid4()), contact_id, company_id, emp_role_id, now, now),
                )

            count += 1

    log.info("Synced %d contacts to database", count)
    return count


def load_contact_index() -> dict[str, KnownContact]:
    """Load contacts from DB and return a contact_index (email -> KnownContact)."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.*, ci.value AS email
               FROM contacts c
               JOIN contact_identifiers ci ON ci.contact_id = c.id
               WHERE ci.type = 'email'"""
        ).fetchall()

    index: dict[str, KnownContact] = {}
    for row in rows:
        r = dict(row)
        email = r["email"].lower()
        kc = KnownContact(
            email=email,
            name=r.get("name") or "",
            company=r.get("company") or "",
            status=r.get("status") or "active",
        )
        index[email] = kc
    return index


# ---------------------------------------------------------------------------
# Conversation creation rules
# ---------------------------------------------------------------------------

def _is_blocked_sender(addr: str) -> bool:
    """Return True if the address matches an automated/blocked sender pattern."""
    addr = addr.lower().strip()
    return any(pat.search(addr) for pat in AUTOMATED_SENDER_PATTERNS)


def _should_create_conversation(
    comm_rows: list[dict],
    account_email: str,
    contact_index: dict[str, KnownContact],
) -> bool:
    """Decide whether a conversation should be created for this thread.

    Implements three rules:
      Rule 1 — Single inbound from a known, non-blocked contact → Yes
      Rule 2 — Single outbound to a known contact → Yes (unknown recipient → No)
      Rule 3 — Multi-email thread where user sent at least one, OR at least one
               participant is a known, non-blocked contact → Yes
    """
    if not comm_rows:
        return False

    total = len(comm_rows)
    account_lower = account_email.lower()

    # Gather all participant addresses and directions
    user_sent = False
    has_known_nonblocked = False

    for row in comm_rows:
        sender = (row.get("sender_address") or "").lower()
        direction = row.get("direction") or ("outbound" if sender == account_lower else "inbound")

        if sender == account_lower:
            user_sent = True

        # Check sender (skip the user themselves)
        if sender and sender != account_lower:
            if not _is_blocked_sender(sender) and sender in contact_index:
                has_known_nonblocked = True

        # Check recipients from communication_participants
        participants = row.get("_participants", [])
        for p in participants:
            addr = (p.get("address") or "").lower()
            if addr and addr != account_lower:
                if not _is_blocked_sender(addr) and addr in contact_index:
                    has_known_nonblocked = True

    if total == 1:
        row = comm_rows[0]
        sender = (row.get("sender_address") or "").lower()
        if sender == account_lower:
            # Rule 2: outbound — need a known recipient
            return has_known_nonblocked
        else:
            # Rule 1: inbound — sender must be known AND not blocked
            return has_known_nonblocked
    else:
        # Rule 3: multi-email — user participated OR any known non-blocked contact
        return user_sent or has_known_nonblocked


# ---------------------------------------------------------------------------
# Conversation + communication persistence
# ---------------------------------------------------------------------------

def _store_thread(
    conn,
    account_id: str,
    account_email: str,
    thread_emails: list[ParsedEmail],
    contact_index: dict[str, KnownContact],
    *,
    customer_id: str | None = None,
    created_by: str | None = None,
) -> tuple[bool, bool]:
    """Store a single thread's communications and conditionally create a conversation.

    Communications are always stored. A conversation is only created when the
    thread satisfies the conversation-creation rules (known contacts, user
    participation, etc.).  When a previously-skipped thread later qualifies,
    the conversation is created retroactively and ALL existing communications
    for that thread are linked.

    Returns (conversation_created, conversation_updated).
    """
    if not thread_emails:
        return False, False

    thread_id = thread_emails[0].thread_id
    subject = thread_emails[0].subject or "(no subject)"
    now = _now_iso()

    # Strip quotes from bodies
    for em in thread_emails:
        em.body_plain = strip_quotes(em.body_plain, em.body_html or None)

    # ------------------------------------------------------------------
    # Step 1: Always store communications + participants first
    # ------------------------------------------------------------------
    new_comm_ids: list[str] = []
    for em in thread_emails:
        comm_id = str(uuid.uuid4())
        row = em.to_row(
            account_id=account_id,
            communication_id=comm_id,
            account_email=account_email,
        )
        try:
            conn.execute(
                """INSERT OR IGNORE INTO communications
                   (id, account_id, channel, timestamp, content, direction, source,
                    sender_address, sender_name, subject, body_html, snippet,
                    provider_message_id, provider_thread_id,
                    header_message_id, header_references, header_in_reply_to,
                    is_read, is_current, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["id"], row["account_id"], row["channel"],
                    row["timestamp"], row["content"], row["direction"],
                    row["source"], row["sender_address"], row["sender_name"],
                    row["subject"], row["body_html"], row["snippet"],
                    row["provider_message_id"], row["provider_thread_id"],
                    row["header_message_id"], row["header_references"],
                    row["header_in_reply_to"], row["is_read"],
                    row["is_current"], row["created_at"], row["updated_at"],
                ),
            )
        except Exception:
            continue

        # Check if this was actually inserted (not ignored due to UNIQUE)
        if conn.execute(
            "SELECT 1 FROM communications WHERE id = ?", (comm_id,)
        ).fetchone():
            new_comm_ids.append(comm_id)

            # Insert recipients into communication_participants
            for rec_row in em.recipient_rows(comm_id):
                conn.execute(
                    """INSERT OR IGNORE INTO communication_participants
                       (communication_id, address, name, role)
                       VALUES (?, ?, ?, ?)""",
                    (rec_row["communication_id"], rec_row["address"],
                     rec_row["name"], rec_row["role"]),
                )

    # ------------------------------------------------------------------
    # Step 2: Check for existing conversation
    # ------------------------------------------------------------------
    existing = conn.execute(
        """SELECT cc.conversation_id, conv.communication_count
           FROM communications c
           JOIN conversation_communications cc ON cc.communication_id = c.id
           JOIN conversations conv ON conv.id = cc.conversation_id
           WHERE c.provider_thread_id = ?
           LIMIT 1""",
        (thread_id,),
    ).fetchone()

    conversation_created = False
    conversation_updated = False

    if existing:
        # Conversation already exists — link new communications to it
        conv_id = existing["conversation_id"]
        for cid in new_comm_ids:
            conn.execute(
                """INSERT OR IGNORE INTO conversation_communications
                   (conversation_id, communication_id, assignment_source, confidence, reviewed, created_at)
                   VALUES (?, ?, 'sync', 1.0, 1, ?)""",
                (conv_id, cid, now),
            )

        if new_comm_ids:
            # Update conversation counts and timestamps
            actual_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM conversation_communications WHERE conversation_id = ?",
                (conv_id,),
            ).fetchone()["cnt"]

            date_row = conn.execute(
                """SELECT MIN(c.timestamp) as first_dt, MAX(c.timestamp) as last_dt
                   FROM communications c
                   JOIN conversation_communications cc ON cc.communication_id = c.id
                   WHERE cc.conversation_id = ?""",
                (conv_id,),
            ).fetchone()

            conn.execute(
                """UPDATE conversations
                   SET communication_count = ?, first_activity_at = ?, last_activity_at = ?,
                       ai_summarized_at = NULL, updated_at = ?
                   WHERE id = ?""",
                (actual_count, date_row["first_dt"], date_row["last_dt"], now, conv_id),
            )
            conversation_updated = True
    else:
        # ------------------------------------------------------------------
        # Step 3: No existing conversation — evaluate creation rules
        # ------------------------------------------------------------------
        # Load ALL communications for this thread (including previously stored ones)
        all_thread_comms = conn.execute(
            """SELECT c.id, c.sender_address, c.direction
               FROM communications c
               WHERE c.provider_thread_id = ?""",
            (thread_id,),
        ).fetchall()

        # Enrich with participant data for _should_create_conversation
        comm_dicts = []
        for cr in all_thread_comms:
            d = dict(cr)
            parts = conn.execute(
                "SELECT address, role FROM communication_participants WHERE communication_id = ?",
                (d["id"],),
            ).fetchall()
            d["_participants"] = [dict(p) for p in parts]
            comm_dicts.append(d)

        if _should_create_conversation(comm_dicts, account_email, contact_index):
            # Create conversation and link ALL thread communications (retroactive)
            conv_id = str(uuid.uuid4())
            all_comm_ids = [d["id"] for d in comm_dicts]
            total_count = len(all_comm_ids)

            # Calculate date range from all thread communications
            date_row = conn.execute(
                """SELECT MIN(c.timestamp) as first_dt, MAX(c.timestamp) as last_dt
                   FROM communications c
                   WHERE c.provider_thread_id = ?""",
                (thread_id,),
            ).fetchone()

            conn.execute(
                """INSERT INTO conversations
                   (id, account_id, title, subject, status,
                    communication_count, message_count, participant_count,
                    first_activity_at, last_activity_at, first_message_at, last_message_at,
                    dismissed, customer_id, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'active', ?, ?, 0, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
                (conv_id, account_id, subject, subject,
                 total_count, total_count,
                 date_row["first_dt"], date_row["last_dt"],
                 date_row["first_dt"], date_row["last_dt"],
                 customer_id, created_by, now, now),
            )
            conversation_created = True

            # Link ALL thread communications to the new conversation
            for cid in all_comm_ids:
                conn.execute(
                    """INSERT OR IGNORE INTO conversation_communications
                       (conversation_id, communication_id, assignment_source, confidence, reviewed, created_at)
                       VALUES (?, ?, 'sync', 1.0, 1, ?)""",
                    (conv_id, cid, now),
                )
        else:
            # Rules say no conversation — communications stored but unlinked
            return False, False

    # ------------------------------------------------------------------
    # Step 4: Upsert conversation participants
    # ------------------------------------------------------------------
    all_participants: dict[str, None] = {}
    # Gather from ALL communications linked to this conversation
    linked_comms = conn.execute(
        """SELECT c.sender_address FROM communications c
           JOIN conversation_communications cc ON cc.communication_id = c.id
           WHERE cc.conversation_id = ?""",
        (conv_id,),
    ).fetchall()
    for lc in linked_comms:
        if lc["sender_address"]:
            all_participants[lc["sender_address"].lower()] = None

    linked_parts = conn.execute(
        """SELECT cp.address FROM communication_participants cp
           JOIN conversation_communications cc ON cc.communication_id = cp.communication_id
           WHERE cc.conversation_id = ?""",
        (conv_id,),
    ).fetchall()
    for lp in linked_parts:
        if lp["address"]:
            all_participants[lp["address"].lower()] = None

    for addr in all_participants:
        contact_row = conn.execute(
            "SELECT contact_id FROM contact_identifiers WHERE type = 'email' AND value = ?",
            (addr.lower(),),
        ).fetchone()
        contact_id = contact_row["contact_id"] if contact_row else None

        msg_count = conn.execute(
            """SELECT COUNT(*) as cnt FROM communications c
               JOIN conversation_communications cc ON cc.communication_id = c.id
               WHERE cc.conversation_id = ? AND LOWER(c.sender_address) = ?""",
            (conv_id, addr),
        ).fetchone()["cnt"]

        date_row = conn.execute(
            """SELECT MIN(c.timestamp) as first_dt, MAX(c.timestamp) as last_dt
               FROM communications c
               JOIN conversation_communications cc ON cc.communication_id = c.id
               WHERE cc.conversation_id = ? AND LOWER(c.sender_address) = ?""",
            (conv_id, addr),
        ).fetchone()

        conn.execute(
            """INSERT INTO conversation_participants
               (conversation_id, email_address, address, contact_id,
                communication_count, first_seen_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(conversation_id, email_address) DO UPDATE SET
                   address = excluded.address,
                   contact_id = excluded.contact_id,
                   communication_count = excluded.communication_count,
                   first_seen_at = excluded.first_seen_at,
                   last_seen_at = excluded.last_seen_at""",
            (conv_id, addr, addr, contact_id, msg_count,
             date_row["first_dt"], date_row["last_dt"]),
        )

    # Update participant_count on conversation
    part_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM conversation_participants WHERE conversation_id = ?",
        (conv_id,),
    ).fetchone()["cnt"]
    conn.execute(
        "UPDATE conversations SET participant_count = ? WHERE id = ?",
        (part_count, conv_id),
    )

    return conversation_created, conversation_updated


# ---------------------------------------------------------------------------
# Initial sync
# ---------------------------------------------------------------------------

def initial_sync(
    account_id: str,
    creds: Credentials,
    rate_limiter: RateLimiter | None = None,
    *,
    customer_id: str | None = None,
    user_id: str | None = None,
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
                    customer_id=customer_id, created_by=user_id,
                )
                if created:
                    conversations_created += 1
                if updated:
                    conversations_updated += 1
                # Count net new communications stored
                for em in thread_emails:
                    row = conn.execute(
                        "SELECT 1 FROM communications WHERE account_id = ? AND provider_message_id = ?",
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
            """UPDATE provider_accounts
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
    *,
    customer_id: str | None = None,
    user_id: str | None = None,
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
                    customer_id=customer_id, created_by=user_id,
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
                # Find the communication and its conversation
                comm_row = conn.execute(
                    "SELECT id FROM communications WHERE account_id = ? AND provider_message_id = ?",
                    (account_id, mid),
                ).fetchone()
                if comm_row:
                    comm_id = comm_row["id"]
                    # Find conversation via join table
                    cc_row = conn.execute(
                        "SELECT conversation_id FROM conversation_communications WHERE communication_id = ?",
                        (comm_id,),
                    ).fetchone()
                    conv_id = cc_row["conversation_id"] if cc_row else None

                    # Delete the communication (CASCADE removes join rows)
                    conn.execute(
                        "DELETE FROM communications WHERE id = ?",
                        (comm_id,),
                    )
                    # Update conversation communication count
                    if conv_id:
                        actual_count = conn.execute(
                            "SELECT COUNT(*) as cnt FROM conversation_communications WHERE conversation_id = ?",
                            (conv_id,),
                        ).fetchone()["cnt"]
                        conn.execute(
                            "UPDATE conversations SET communication_count = ?, updated_at = ? WHERE id = ?",
                            (actual_count, _now_iso(), conv_id),
                        )

    # Update sync cursor
    history_id = get_history_id(creds)
    now = _now_iso()

    with get_connection() as conn:
        conn.execute(
            """UPDATE provider_accounts
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
# Conversation processing (summarize)
# ---------------------------------------------------------------------------

def process_conversations(
    account_id: str,
    creds: Credentials,
    user_email: str,
    rate_limiter: RateLimiter | None = None,
    claude_limiter: RateLimiter | None = None,
) -> tuple[int, int, int]:
    """Summarize conversations that need processing.

    Triage is no longer needed here — conversations are pre-filtered at
    creation time by ``_should_create_conversation()``.

    Returns (triaged_count, summarized_count, tag_count).
    triaged_count is always 0 (kept for backward-compatible return signature).
    """
    import anthropic

    # Find conversations needing summarization
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM conversations
               WHERE ai_summarized_at IS NULL
                 AND dismissed = 0
               ORDER BY last_activity_at DESC""",
        ).fetchall()

    if not rows:
        log.info("No conversations need processing")
        return 0, 0, 0

    summarized_count = 0
    tag_count = 0

    for conv_row in rows:
        conv_id = conv_row["id"]

        # Summarize (only if API key is set)
        if not config.ANTHROPIC_API_KEY:
            continue

        # Load communications for this conversation via join
        with get_connection() as conn:
            comm_rows = conn.execute(
                """SELECT c.* FROM communications c
                   JOIN conversation_communications cc ON cc.communication_id = c.id
                   WHERE cc.conversation_id = ?
                   ORDER BY c.timestamp""",
                (conv_id,),
            ).fetchall()

        emails = []
        for cr in comm_rows:
            with get_connection() as conn:
                rec_rows = conn.execute(
                    "SELECT * FROM communication_participants WHERE communication_id = ?",
                    (cr["id"],),
                ).fetchall()
            emails.append(ParsedEmail.from_row(cr, recipients=rec_rows))

        # Reconstruct Conversation object for summarization
        conv = Conversation(
            thread_id=conv_id,
            title=conv_row["title"] or "",
            emails=emails,
            participants=[],
        )

        # Collect participants
        all_participants: dict[str, None] = {}
        for em in conv.emails:
            for p in em.all_participants:
                all_participants[p] = None
        conv.participants = list(all_participants.keys())

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

            # Extract and normalize tags
            if summary.key_topics:
                tag_count += _store_tags(conv_id, summary.key_topics)

    log.info(
        "Processing complete: %d summarized, %d tags",
        summarized_count, tag_count,
    )
    return 0, summarized_count, tag_count


def _store_tags(conversation_id: str, tag_names: list[str]) -> int:
    """Normalize and store tags for a conversation. Returns count stored."""
    now = _now_iso()
    count = 0

    with get_connection() as conn:
        for raw_tag in tag_names:
            name = raw_tag.strip().lower()
            if not name:
                continue

            # Upsert tag
            tag_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO tags (id, name, source, created_at)
                   VALUES (?, ?, 'ai', ?)
                   ON CONFLICT(name) DO NOTHING""",
                (tag_id, name, now),
            )

            # Get the actual tag ID (may already exist)
            tag_row = conn.execute(
                "SELECT id FROM tags WHERE name = ?",
                (name,),
            ).fetchone()
            actual_id = tag_row["id"]

            # Link to conversation
            conn.execute(
                """INSERT OR IGNORE INTO conversation_tags
                   (conversation_id, tag_id, confidence, source, created_at)
                   VALUES (?, ?, 1.0, 'ai', ?)""",
                (conversation_id, actual_id, now),
            )
            count += 1

    return count


# Keep old name as alias for backward compatibility during transition
_store_topics = _store_tags


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

    Conversations are now account-independent. When account_ids are given,
    we filter to conversations that contain at least one communication from
    those accounts.
    Returns (conversations, summaries, triage_filtered) ready for display.py.
    """
    ids = account_ids or ([account_id] if account_id else [])

    # Build email-address lookup for account badges
    account_email_map: dict[str, str] = {}
    if ids:
        with get_connection() as conn:
            for aid in ids:
                row = conn.execute(
                    "SELECT email_address FROM provider_accounts WHERE id = ?", (aid,)
                ).fetchone()
                if row:
                    account_email_map[aid] = row["email_address"]

    with get_connection() as conn:
        if ids:
            placeholders = ",".join("?" for _ in ids)
            # Find conversations that have at least one communication from these accounts
            if include_triaged:
                query = f"""SELECT DISTINCT conv.* FROM conversations conv
                           JOIN conversation_communications cc ON cc.conversation_id = conv.id
                           JOIN communications comm ON comm.id = cc.communication_id
                           WHERE comm.account_id IN ({placeholders})
                           ORDER BY conv.last_activity_at DESC"""
            else:
                query = f"""SELECT DISTINCT conv.* FROM conversations conv
                           JOIN conversation_communications cc ON cc.conversation_id = conv.id
                           JOIN communications comm ON comm.id = cc.communication_id
                           WHERE comm.account_id IN ({placeholders}) AND conv.triage_result IS NULL
                           ORDER BY conv.last_activity_at DESC"""
            if limit:
                query += f" LIMIT {limit}"
            conv_rows = conn.execute(query, ids).fetchall()
        else:
            # No account filter — load all conversations
            if include_triaged:
                query = "SELECT * FROM conversations ORDER BY last_activity_at DESC"
            else:
                query = "SELECT * FROM conversations WHERE triage_result IS NULL ORDER BY last_activity_at DESC"
            if limit:
                query += f" LIMIT {limit}"
            conv_rows = conn.execute(query).fetchall()

    conversations: list[Conversation] = []
    summaries: list[ConversationSummary] = []
    triage_filtered: list[TriageResult] = []

    for cr in conv_rows:
        conv_id = cr["id"]

        # Check if triaged out
        if cr["triage_result"]:
            triage_filtered.append(
                TriageResult(
                    thread_id=conv_id,
                    subject=cr["title"] or "",
                    reason=filter_reason_from_db(cr["triage_result"]),
                )
            )
            continue

        # Load communications via join
        with get_connection() as conn:
            comm_rows = conn.execute(
                """SELECT c.* FROM communications c
                   JOIN conversation_communications cc ON cc.communication_id = c.id
                   WHERE cc.conversation_id = ?
                   ORDER BY c.timestamp""",
                (conv_id,),
            ).fetchall()

        emails = []
        for cr2 in comm_rows:
            with get_connection() as conn:
                rec_rows = conn.execute(
                    "SELECT * FROM communication_participants WHERE communication_id = ?",
                    (cr2["id"],),
                ).fetchall()
            emails.append(ParsedEmail.from_row(cr2, recipients=rec_rows))

        # Derive account_email from the first communication's account_id
        first_account_id = comm_rows[0]["account_id"] if comm_rows else None
        account_email = account_email_map.get(first_account_id, "") if first_account_id else ""

        # Build conversation
        conv = Conversation(
            thread_id=conv_id,
            title=cr["title"] or "",
            emails=emails,
            participants=[],
            account_email=account_email,
        )

        # Load participants and match contacts
        with get_connection() as conn:
            part_rows = conn.execute(
                "SELECT * FROM conversation_participants WHERE conversation_id = ?",
                (conv_id,),
            ).fetchall()

        for pr in part_rows:
            conv.participants.append(pr["address"])
            if pr["contact_id"]:
                with get_connection() as conn:
                    contact_row = conn.execute(
                        """SELECT c.*, ci.value AS email
                           FROM contacts c
                           LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
                           WHERE c.id = ?""",
                        (pr["contact_id"],),
                    ).fetchone()
                if contact_row:
                    conv.matched_contacts[pr["address"]] = KnownContact.from_row(contact_row)

        conversations.append(conv)

        # Load summary
        summary = ConversationSummary.from_conversation_row(cr)
        if summary:
            summaries.append(summary)

    # Also load triage-only rows if not already included
    if not include_triaged:
        with get_connection() as conn:
            if ids:
                placeholders = ",".join("?" for _ in ids)
                triaged_rows = conn.execute(
                    f"""SELECT DISTINCT conv.* FROM conversations conv
                       JOIN conversation_communications cc ON cc.conversation_id = conv.id
                       JOIN communications comm ON comm.id = cc.communication_id
                       WHERE comm.account_id IN ({placeholders}) AND conv.triage_result IS NOT NULL
                       ORDER BY conv.last_activity_at DESC""",
                    ids,
                ).fetchall()
            else:
                triaged_rows = conn.execute(
                    """SELECT * FROM conversations
                       WHERE triage_result IS NOT NULL
                       ORDER BY last_activity_at DESC""",
                ).fetchall()
        for tr in triaged_rows:
            triage_filtered.append(
                TriageResult(
                    thread_id=tr["id"],
                    subject=tr["title"] or "",
                    reason=filter_reason_from_db(tr["triage_result"]),
                )
            )

    return conversations, summaries, triage_filtered
