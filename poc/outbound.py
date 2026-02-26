"""Outbound email business logic: compose, draft, send, and track."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from .database import get_connection
from .models import _now_iso

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Draft CRUD
# ---------------------------------------------------------------------------

def create_draft(
    conn,
    *,
    customer_id: str,
    user_id: str,
    from_account_id: str,
    to_addresses: list[dict],
    cc_addresses: list[dict] | None = None,
    bcc_addresses: list[dict] | None = None,
    subject: str,
    body_json: str,
    body_html: str,
    body_text: str,
    source_type: str = "manual",
    reply_to_communication_id: str | None = None,
    forward_of_communication_id: str | None = None,
    conversation_id: str | None = None,
    signature_id: str | None = None,
) -> dict:
    """Insert an outbound_email_queue row with status='draft'. Return dict."""
    now = _now_iso()
    draft_id = str(uuid.uuid4())

    conn.execute(
        """INSERT INTO outbound_email_queue
           (id, customer_id, from_account_id,
            to_addresses, cc_addresses, bcc_addresses,
            subject, body_json, body_html, body_text,
            signature_id, source_type,
            reply_to_communication_id, forward_of_communication_id,
            conversation_id, status,
            created_at, updated_at, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)""",
        (
            draft_id, customer_id, from_account_id,
            json.dumps(to_addresses),
            json.dumps(cc_addresses) if cc_addresses else None,
            json.dumps(bcc_addresses) if bcc_addresses else None,
            subject, body_json, body_html, body_text,
            signature_id, source_type,
            reply_to_communication_id, forward_of_communication_id,
            conversation_id,
            now, now, user_id,
        ),
    )

    return get_queue_record(conn, queue_id=draft_id)


def update_draft(conn, *, draft_id: str, user_id: str, **fields) -> dict | None:
    """Update mutable fields on a draft. Return updated dict or None."""
    record = get_queue_record(conn, queue_id=draft_id)
    if not record:
        return None
    if record["status"] not in ("draft",):
        return None
    if record["created_by"] != user_id:
        return None

    now = _now_iso()
    allowed = {
        "to_addresses", "cc_addresses", "bcc_addresses",
        "subject", "body_json", "body_html", "body_text",
        "signature_id", "from_account_id",
    }

    sets = []
    params = []
    for key, val in fields.items():
        if key not in allowed:
            continue
        if key in ("to_addresses", "cc_addresses", "bcc_addresses"):
            val = json.dumps(val) if val is not None else None
        sets.append(f"{key} = ?")
        params.append(val)

    if not sets:
        return record

    sets.append("updated_at = ?")
    params.append(now)
    params.append(draft_id)

    conn.execute(
        f"UPDATE outbound_email_queue SET {', '.join(sets)} WHERE id = ?",
        params,
    )
    return get_queue_record(conn, queue_id=draft_id)


def get_queue_record(conn, *, queue_id: str) -> dict | None:
    """Fetch single outbound email queue record."""
    row = conn.execute(
        "SELECT * FROM outbound_email_queue WHERE id = ?",
        (queue_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    # Parse JSON address fields for consumer convenience
    for addr_field in ("to_addresses", "cc_addresses", "bcc_addresses"):
        val = d.get(addr_field)
        if val and isinstance(val, str):
            try:
                d[addr_field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def list_drafts(conn, *, user_id: str, customer_id: str) -> list[dict]:
    """List user's drafts ordered by updated_at desc."""
    rows = conn.execute(
        """SELECT * FROM outbound_email_queue
           WHERE created_by = ? AND customer_id = ? AND status = 'draft'
           ORDER BY updated_at DESC""",
        (user_id, customer_id),
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        for addr_field in ("to_addresses", "cc_addresses", "bcc_addresses"):
            val = d.get(addr_field)
            if val and isinstance(val, str):
                try:
                    d[addr_field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        result.append(d)
    return result


def cancel_draft(conn, *, queue_id: str, user_id: str) -> bool:
    """Set status='cancelled' on draft. Returns True if cancelled."""
    record = get_queue_record(conn, queue_id=queue_id)
    if not record:
        return False
    if record["status"] not in ("draft", "queued"):
        return False
    if record["created_by"] != user_id:
        return False

    now = _now_iso()
    conn.execute(
        "UPDATE outbound_email_queue SET status = 'cancelled', updated_at = ? WHERE id = ?",
        (now, queue_id),
    )
    return True


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def send_email(conn, *, queue_id: str, user_id: str) -> dict:
    """Send an outbound email.

    1. Load queue record, verify status is 'draft' or 'queued'
    2. Transition to 'sending'
    3. Load provider_account credentials
    4. Inject signature HTML into body if signature_id set
    5. Call gmail_client.send_message()
    6. Create Communication record + participants
    7. Update queue record: status='sent', communication_id, sent_at
    8. Auto-create contacts for unknown recipients
    9. Return result dict

    On failure: status='failed', failure_reason=str(error)
    """
    from .auth import get_credentials_for_account
    from .gmail_client import send_message

    record = get_queue_record(conn, queue_id=queue_id)
    if not record:
        raise ValueError("Queue record not found")
    if record["status"] not in ("draft", "queued"):
        raise ValueError(f"Cannot send email with status '{record['status']}'")
    if record["created_by"] != user_id:
        raise ValueError("Not authorized to send this email")

    now = _now_iso()

    # Transition to 'sending'
    conn.execute(
        "UPDATE outbound_email_queue SET status = 'sending', updated_at = ? WHERE id = ?",
        (now, queue_id),
    )

    # Load provider account
    acct = conn.execute(
        "SELECT * FROM provider_accounts WHERE id = ?",
        (record["from_account_id"],),
    ).fetchone()
    if not acct:
        _fail_send(conn, queue_id, "Provider account not found")
        raise ValueError("Provider account not found")

    acct = dict(acct)
    from_email = acct["email_address"]

    # Load credentials
    token_path = Path(acct["auth_token_path"])
    try:
        creds = get_credentials_for_account(token_path)
    except Exception as exc:
        _fail_send(conn, queue_id, f"Could not load credentials: {exc}")
        raise ValueError(f"Could not load credentials: {exc}") from exc

    # Resolve body with signature
    body_html = record["body_html"]
    body_text = record["body_text"]
    signature_html, signature_text = _resolve_signature(conn, record)
    if signature_html:
        body_html += signature_html
        body_text += signature_text

    # Append quoted content for replies/forwards
    quoted_html = _build_quoted_content(conn, record)
    if quoted_html:
        body_html += quoted_html

    # Extract plain email addresses from address objects
    to_emails = [a["email"] for a in record["to_addresses"]]
    cc_emails = [a["email"] for a in (record["cc_addresses"] or [])]
    bcc_emails = [a["email"] for a in (record["bcc_addresses"] or [])]

    # Get threading headers for replies
    in_reply_to = None
    references = None
    thread_id = None
    if record["reply_to_communication_id"]:
        parent = conn.execute(
            "SELECT header_message_id, header_references, provider_thread_id "
            "FROM communications WHERE id = ?",
            (record["reply_to_communication_id"],),
        ).fetchone()
        if parent:
            in_reply_to = parent["header_message_id"]
            refs = parent["header_references"] or ""
            if in_reply_to:
                references = f"{refs} {in_reply_to}".strip()
            thread_id = parent["provider_thread_id"]

    # Send via Gmail
    try:
        provider_msg_id, provider_thread_id = send_message(
            creds,
            from_email=from_email,
            to=to_emails,
            subject=record["subject"],
            body_html=body_html,
            body_text=body_text,
            cc=cc_emails or None,
            bcc=bcc_emails or None,
            in_reply_to=in_reply_to,
            references=references,
            thread_id=thread_id,
        )
    except Exception as exc:
        _fail_send(conn, queue_id, str(exc))
        return {
            "queue_id": queue_id,
            "status": "failed",
            "failure_reason": str(exc),
        }

    # Create communication record
    comm_id = _create_communication_record(
        conn,
        queue_record=record,
        provider_msg_id=provider_msg_id,
        provider_thread_id=provider_thread_id,
        customer_id=record["customer_id"],
        user_id=user_id,
        from_email=from_email,
        body_html=body_html,
        body_text=body_text,
    )

    # Update queue record
    now = _now_iso()
    conn.execute(
        """UPDATE outbound_email_queue
           SET status = 'sent', communication_id = ?, sent_at = ?, updated_at = ?
           WHERE id = ?""",
        (comm_id, now, now, queue_id),
    )

    # Auto-create contacts for unknown recipients
    _auto_create_contacts(
        conn,
        communication_id=comm_id,
        to_addresses=record["to_addresses"],
        cc_addresses=record["cc_addresses"] or [],
        customer_id=record["customer_id"],
        user_id=user_id,
    )

    return {
        "queue_id": queue_id,
        "communication_id": comm_id,
        "provider_message_id": provider_msg_id,
        "provider_thread_id": provider_thread_id,
        "status": "sent",
    }


def _fail_send(conn, queue_id: str, reason: str) -> None:
    """Mark a queue record as failed."""
    now = _now_iso()
    conn.execute(
        """UPDATE outbound_email_queue
           SET status = 'failed', failure_reason = ?,
               retry_count = retry_count + 1, updated_at = ?
           WHERE id = ?""",
        (reason, now, queue_id),
    )


def _resolve_signature(conn, record: dict) -> tuple[str, str]:
    """Return (html, text) for the signature, or ('', '') if none."""
    sig_id = record.get("signature_id")

    if sig_id:
        sig = conn.execute(
            "SELECT * FROM email_signatures WHERE id = ?",
            (sig_id,),
        ).fetchone()
        if sig:
            html = f'\n<div class="email-signature"><br>-- <br>{sig["body_html"]}</div>'
            # Strip tags for text version
            import re
            text = "\n\n-- \n" + re.sub(r"<[^>]+>", "", sig["body_html"]).strip()
            return html, text

    # Try default signature for the account
    sig = conn.execute(
        """SELECT * FROM email_signatures
           WHERE user_id = ? AND provider_account_id = ? AND is_default = 1
           LIMIT 1""",
        (record["created_by"], record["from_account_id"]),
    ).fetchone()

    if not sig:
        # Try user's overall default
        sig = conn.execute(
            """SELECT * FROM email_signatures
               WHERE user_id = ? AND is_default = 1 AND provider_account_id IS NULL
               LIMIT 1""",
            (record["created_by"],),
        ).fetchone()

    if sig:
        html = f'\n<div class="email-signature"><br>-- <br>{sig["body_html"]}</div>'
        import re
        text = "\n\n-- \n" + re.sub(r"<[^>]+>", "", sig["body_html"]).strip()
        return html, text

    return "", ""


def _build_quoted_content(conn, record: dict) -> str:
    """Build quoted content HTML for replies and forwards."""
    if record["source_type"] == "reply" and record["reply_to_communication_id"]:
        parent = conn.execute(
            "SELECT sender_name, sender_address, timestamp, cleaned_html, original_html "
            "FROM communications WHERE id = ?",
            (record["reply_to_communication_id"],),
        ).fetchone()
        if parent:
            sender = parent["sender_name"] or parent["sender_address"]
            content = parent["cleaned_html"] or parent["original_html"] or ""
            return (
                f'\n<div class="quoted-reply" style="border-left:2px solid #ccc;'
                f'padding-left:12px;color:#666;margin-top:16px;">'
                f'<p>On {parent["timestamp"]}, {sender} wrote:</p>'
                f'{content}</div>'
            )

    if record["source_type"] == "forward" and record["forward_of_communication_id"]:
        parent = conn.execute(
            "SELECT sender_name, sender_address, timestamp, subject, "
            "cleaned_html, original_html FROM communications WHERE id = ?",
            (record["forward_of_communication_id"],),
        ).fetchone()
        if parent:
            content = parent["cleaned_html"] or parent["original_html"] or ""
            # Get original recipients
            parts = conn.execute(
                "SELECT address, role FROM communication_participants "
                "WHERE communication_id = ? AND role = 'to'",
                (record["forward_of_communication_id"],),
            ).fetchall()
            to_addrs = ", ".join(p["address"] for p in parts)
            return (
                f'\n<div class="forward-header" style="margin-top:16px;">'
                f'---------- Forwarded message ----------<br>'
                f'From: {parent["sender_name"] or parent["sender_address"]}<br>'
                f'Date: {parent["timestamp"]}<br>'
                f'Subject: {parent["subject"]}<br>'
                f'To: {to_addrs}</div>\n{content}'
            )

    return ""


def _create_communication_record(
    conn,
    *,
    queue_record: dict,
    provider_msg_id: str,
    provider_thread_id: str,
    customer_id: str,
    user_id: str,
    from_email: str,
    body_html: str,
    body_text: str,
) -> str:
    """Create communications row + participants. Return communication_id."""
    now = _now_iso()
    comm_id = str(uuid.uuid4())

    conn.execute(
        """INSERT INTO communications
           (id, account_id, channel, timestamp,
            original_text, original_html, cleaned_html, search_text,
            direction, source,
            sender_address, sender_name, subject, snippet,
            provider_message_id, provider_thread_id,
            is_read, is_current, created_at, updated_at)
           VALUES (?, ?, 'email', ?, ?, ?, ?, ?, 'outbound', 'composed',
                   ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)""",
        (
            comm_id, queue_record["from_account_id"], now,
            body_text, body_html, body_html, body_text,
            from_email, None, queue_record["subject"],
            body_text[:200] if body_text else "",
            provider_msg_id, provider_thread_id,
            now, now,
        ),
    )

    # Insert participants
    for addr_obj in queue_record["to_addresses"]:
        email_addr = addr_obj["email"]
        conn.execute(
            """INSERT OR IGNORE INTO communication_participants
               (communication_id, address, name, contact_id, role)
               VALUES (?, ?, ?, ?, 'to')""",
            (comm_id, email_addr, addr_obj.get("name"), addr_obj.get("contact_id")),
        )

    for addr_obj in (queue_record["cc_addresses"] or []):
        email_addr = addr_obj["email"]
        conn.execute(
            """INSERT OR IGNORE INTO communication_participants
               (communication_id, address, name, contact_id, role)
               VALUES (?, ?, ?, ?, 'cc')""",
            (comm_id, email_addr, addr_obj.get("name"), addr_obj.get("contact_id")),
        )

    for addr_obj in (queue_record["bcc_addresses"] or []):
        email_addr = addr_obj["email"]
        conn.execute(
            """INSERT OR IGNORE INTO communication_participants
               (communication_id, address, name, contact_id, role)
               VALUES (?, ?, ?, ?, 'bcc')""",
            (comm_id, email_addr, addr_obj.get("name"), addr_obj.get("contact_id")),
        )

    # Link to conversation if one exists
    conv_id = queue_record.get("conversation_id")
    if conv_id:
        conn.execute(
            """INSERT OR IGNORE INTO conversation_communications
               (conversation_id, communication_id, assignment_source, confidence, reviewed, created_at)
               VALUES (?, ?, 'composed', 1.0, 1, ?)""",
            (conv_id, comm_id, now),
        )
        # Update conversation stats
        actual_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM conversation_communications WHERE conversation_id = ?",
            (conv_id,),
        ).fetchone()["cnt"]
        conn.execute(
            """UPDATE conversations
               SET communication_count = ?, last_activity_at = ?,
                   last_message_at = ?, updated_at = ?
               WHERE id = ?""",
            (actual_count, now, now, now, conv_id),
        )

    return comm_id


# ---------------------------------------------------------------------------
# Sending account resolution
# ---------------------------------------------------------------------------

def resolve_sending_account(
    conn,
    *,
    user_id: str,
    customer_id: str,
    reply_to_comm_id: str | None = None,
    to_email: str | None = None,
) -> str | None:
    """Smart default priority chain for sending account.

    1. Reply context → parent communication's account_id
    2. Historical pattern → most recent outbound to this contact's email
    3. User's default account (only active, or first active)
    """
    # Priority 1: Reply context
    if reply_to_comm_id:
        parent = conn.execute(
            "SELECT account_id FROM communications WHERE id = ?",
            (reply_to_comm_id,),
        ).fetchone()
        if parent and parent["account_id"]:
            # Verify account is still active and accessible
            acct = conn.execute(
                """SELECT pa.id FROM provider_accounts pa
                   JOIN user_provider_accounts upa ON upa.account_id = pa.id
                   WHERE pa.id = ? AND pa.is_active = 1 AND upa.user_id = ?""",
                (parent["account_id"], user_id),
            ).fetchone()
            if acct:
                return acct["id"]

    # Priority 2: Historical pattern (most recent outbound to same email)
    if to_email:
        recent = conn.execute(
            """SELECT c.account_id FROM communications c
               JOIN communication_participants cp ON cp.communication_id = c.id
               WHERE c.direction = 'outbound' AND cp.address = ?
               ORDER BY c.timestamp DESC LIMIT 1""",
            (to_email.lower(),),
        ).fetchone()
        if recent and recent["account_id"]:
            acct = conn.execute(
                """SELECT pa.id FROM provider_accounts pa
                   JOIN user_provider_accounts upa ON upa.account_id = pa.id
                   WHERE pa.id = ? AND pa.is_active = 1 AND upa.user_id = ?""",
                (recent["account_id"], user_id),
            ).fetchone()
            if acct:
                return acct["id"]

    # Priority 3: User's default (first active) account
    default = conn.execute(
        """SELECT pa.id FROM provider_accounts pa
           JOIN user_provider_accounts upa ON upa.account_id = pa.id
           WHERE upa.user_id = ? AND pa.is_active = 1 AND pa.provider = 'gmail'
           ORDER BY pa.created_at ASC LIMIT 1""",
        (user_id,),
    ).fetchone()
    return default["id"] if default else None


# ---------------------------------------------------------------------------
# Compose context (reply/forward pre-fill)
# ---------------------------------------------------------------------------

def get_compose_context(
    conn,
    *,
    communication_id: str,
    action: str,
    user_id: str,
    customer_id: str,
) -> dict:
    """Get pre-filled context for reply/reply_all/forward.

    Returns dict with to, cc, subject, quoted_html, sender_account_id,
    in_reply_to, references, conversation_id.
    """
    comm = conn.execute(
        "SELECT * FROM communications WHERE id = ?",
        (communication_id,),
    ).fetchone()
    if not comm:
        return {"error": "Communication not found"}

    comm = dict(comm)
    participants = conn.execute(
        "SELECT * FROM communication_participants WHERE communication_id = ?",
        (communication_id,),
    ).fetchall()

    # Get the sending account's email
    account_email = ""
    if comm["account_id"]:
        acct = conn.execute(
            "SELECT email_address FROM provider_accounts WHERE id = ?",
            (comm["account_id"],),
        ).fetchone()
        if acct:
            account_email = acct["email_address"]

    # Get conversation_id
    conv_row = conn.execute(
        "SELECT conversation_id FROM conversation_communications WHERE communication_id = ?",
        (communication_id,),
    ).fetchone()
    conversation_id = conv_row["conversation_id"] if conv_row else None

    sender_account_id = resolve_sending_account(
        conn,
        user_id=user_id,
        customer_id=customer_id,
        reply_to_comm_id=communication_id,
    )

    result = {
        "reply_to_communication_id": communication_id,
        "conversation_id": conversation_id,
        "from_account_id": sender_account_id,
        "in_reply_to": comm.get("header_message_id"),
        "references": comm.get("header_references"),
        "provider_thread_id": comm.get("provider_thread_id"),
    }

    sender_addr = (comm.get("sender_address") or "").lower()
    sender_name = comm.get("sender_name") or ""

    if action == "reply":
        # Reply to sender only
        if sender_addr and sender_addr != account_email:
            result["to_addresses"] = [{"email": sender_addr, "name": sender_name}]
        else:
            # Replying to own message — reply to first 'to' participant
            to_parts = [dict(p) for p in participants if p["role"] == "to"]
            if to_parts:
                result["to_addresses"] = [
                    {"email": to_parts[0]["address"], "name": to_parts[0]["name"] or ""}
                ]
            else:
                result["to_addresses"] = []
        result["cc_addresses"] = []
        result["subject"] = _prefix_subject("Re: ", comm.get("subject", ""))
        result["source_type"] = "reply"

    elif action == "reply_all":
        to_addrs = []
        cc_addrs = []

        # Sender goes to To (unless it's us)
        if sender_addr and sender_addr != account_email:
            to_addrs.append({"email": sender_addr, "name": sender_name})

        for p in participants:
            addr = (p["address"] or "").lower()
            if addr == account_email:
                continue
            entry = {"email": addr, "name": p["name"] or ""}
            if p["role"] == "to":
                # If sender was already added to To, put other To in CC
                if to_addrs:
                    cc_addrs.append(entry)
                else:
                    to_addrs.append(entry)
            elif p["role"] == "cc":
                cc_addrs.append(entry)

        result["to_addresses"] = to_addrs
        result["cc_addresses"] = cc_addrs
        result["subject"] = _prefix_subject("Re: ", comm.get("subject", ""))
        result["source_type"] = "reply"

    elif action == "forward":
        result["to_addresses"] = []
        result["cc_addresses"] = []
        result["subject"] = _prefix_subject("Fwd: ", comm.get("subject", ""))
        result["source_type"] = "forward"
        result["forward_of_communication_id"] = communication_id
        result["reply_to_communication_id"] = None

    # Build quoted content
    content = comm.get("cleaned_html") or comm.get("original_html") or ""
    if action in ("reply", "reply_all"):
        result["quoted_html"] = (
            f'<div class="quoted-reply" style="border-left:2px solid #ccc;'
            f'padding-left:12px;color:#666;margin-top:16px;">'
            f'<p>On {comm.get("timestamp", "")}, '
            f'{sender_name or sender_addr} wrote:</p>'
            f'{content}</div>'
        )
    elif action == "forward":
        to_parts = [p["address"] for p in participants if p["role"] == "to"]
        result["quoted_html"] = (
            f'<div class="forward-header" style="margin-top:16px;">'
            f'---------- Forwarded message ----------<br>'
            f'From: {sender_name or sender_addr}<br>'
            f'Date: {comm.get("timestamp", "")}<br>'
            f'Subject: {comm.get("subject", "")}<br>'
            f'To: {", ".join(to_parts)}</div>\n{content}'
        )

    return result


def _prefix_subject(prefix: str, subject: str) -> str:
    """Add Re:/Fwd: prefix if not already present."""
    if not subject:
        return prefix.strip()
    # Don't double-prefix
    if subject.lower().startswith(prefix.lower().strip().lower()):
        return subject
    return f"{prefix}{subject}"


# ---------------------------------------------------------------------------
# Contact auto-creation for unknown recipients
# ---------------------------------------------------------------------------

def _auto_create_contacts(
    conn,
    *,
    communication_id: str,
    to_addresses: list[dict],
    cc_addresses: list[dict],
    customer_id: str,
    user_id: str,
) -> None:
    """Create contacts for recipient addresses not linked to existing contacts."""
    now = _now_iso()
    all_addrs = to_addresses + cc_addresses

    for addr_obj in all_addrs:
        email_addr = addr_obj["email"].lower()
        contact_id = addr_obj.get("contact_id")
        if contact_id:
            continue  # Already linked

        # Check if identifier exists
        existing = conn.execute(
            "SELECT contact_id FROM contact_identifiers WHERE type = 'email' AND value = ?",
            (email_addr,),
        ).fetchone()
        if existing:
            # Update participant with contact_id
            conn.execute(
                """UPDATE communication_participants
                   SET contact_id = ?
                   WHERE communication_id = ? AND address = ?""",
                (existing["contact_id"], communication_id, email_addr),
            )
            continue

        # Create new contact
        new_contact_id = str(uuid.uuid4())
        name = addr_obj.get("name") or email_addr.split("@")[0]
        conn.execute(
            """INSERT INTO contacts
               (id, name, source, status, customer_id, created_by, created_at, updated_at)
               VALUES (?, ?, 'outbound_email', 'active', ?, ?, ?, ?)""",
            (new_contact_id, name, customer_id, user_id, now, now),
        )
        conn.execute(
            """INSERT INTO contact_identifiers
               (id, contact_id, type, value, is_primary, is_current,
                source, verified, created_at, updated_at)
               VALUES (?, ?, 'email', ?, 1, 1, 'outbound_email', 0, ?, ?)""",
            (str(uuid.uuid4()), new_contact_id, email_addr, now, now),
        )
        # Create user_contacts visibility row
        conn.execute(
            """INSERT OR IGNORE INTO user_contacts
               (id, user_id, contact_id, visibility, is_owner, created_at, updated_at)
               VALUES (?, ?, ?, 'public', 1, ?, ?)""",
            (str(uuid.uuid4()), user_id, new_contact_id, now, now),
        )
        # Update participant
        conn.execute(
            """UPDATE communication_participants
               SET contact_id = ?
               WHERE communication_id = ? AND address = ?""",
            (new_contact_id, communication_id, email_addr),
        )

        log.info("Auto-created contact %s for %s", new_contact_id, email_addr)


# ---------------------------------------------------------------------------
# Delivery status tracking
# ---------------------------------------------------------------------------

def update_delivery_status(
    conn,
    *,
    email_address: str,
    status: str,
) -> bool:
    """Update delivery_status on a contact_identifier. Returns True if updated."""
    now = _now_iso()
    result = conn.execute(
        """UPDATE contact_identifiers
           SET delivery_status = ?, delivery_status_updated_at = ?
           WHERE type = 'email' AND value = ?""",
        (status, now, email_address.lower()),
    )
    return result.rowcount > 0


def get_delivery_status(conn, *, email_address: str) -> str | None:
    """Get delivery_status for an email address."""
    row = conn.execute(
        "SELECT delivery_status FROM contact_identifiers WHERE type = 'email' AND value = ?",
        (email_address.lower(),),
    ).fetchone()
    return row["delivery_status"] if row else None


# ---------------------------------------------------------------------------
# Signature CRUD
# ---------------------------------------------------------------------------

def create_signature(
    conn,
    *,
    customer_id: str,
    user_id: str,
    name: str,
    body_json: str,
    body_html: str,
    provider_account_id: str | None = None,
    is_default: bool = False,
) -> dict:
    """Create a new email signature."""
    now = _now_iso()
    sig_id = str(uuid.uuid4())

    # If setting as default, clear other defaults for same scope
    if is_default:
        if provider_account_id:
            conn.execute(
                """UPDATE email_signatures SET is_default = 0
                   WHERE user_id = ? AND provider_account_id = ?""",
                (user_id, provider_account_id),
            )
        else:
            conn.execute(
                """UPDATE email_signatures SET is_default = 0
                   WHERE user_id = ? AND provider_account_id IS NULL""",
                (user_id,),
            )

    conn.execute(
        """INSERT INTO email_signatures
           (id, customer_id, user_id, name, body_json, body_html,
            provider_account_id, is_default, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sig_id, customer_id, user_id, name, body_json, body_html,
         provider_account_id, 1 if is_default else 0, now, now),
    )

    return get_signature(conn, signature_id=sig_id)


def get_signature(conn, *, signature_id: str) -> dict | None:
    """Get a signature by ID."""
    row = conn.execute(
        "SELECT * FROM email_signatures WHERE id = ?",
        (signature_id,),
    ).fetchone()
    return dict(row) if row else None


def list_signatures(conn, *, user_id: str) -> list[dict]:
    """List all signatures for a user."""
    rows = conn.execute(
        "SELECT * FROM email_signatures WHERE user_id = ? ORDER BY name COLLATE NOCASE",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_signature(conn, *, signature_id: str, user_id: str, **fields) -> dict | None:
    """Update a signature. Returns updated dict or None."""
    sig = get_signature(conn, signature_id=signature_id)
    if not sig or sig["user_id"] != user_id:
        return None

    now = _now_iso()
    allowed = {"name", "body_json", "body_html", "provider_account_id", "is_default"}

    # If setting as default, clear other defaults in same scope
    if fields.get("is_default"):
        pa_id = fields.get("provider_account_id", sig["provider_account_id"])
        if pa_id:
            conn.execute(
                """UPDATE email_signatures SET is_default = 0
                   WHERE user_id = ? AND provider_account_id = ? AND id != ?""",
                (user_id, pa_id, signature_id),
            )
        else:
            conn.execute(
                """UPDATE email_signatures SET is_default = 0
                   WHERE user_id = ? AND provider_account_id IS NULL AND id != ?""",
                (user_id, signature_id),
            )

    sets = []
    params = []
    for key, val in fields.items():
        if key not in allowed:
            continue
        if key == "is_default":
            val = 1 if val else 0
        sets.append(f"{key} = ?")
        params.append(val)

    if not sets:
        return sig

    sets.append("updated_at = ?")
    params.append(now)
    params.append(signature_id)

    conn.execute(
        f"UPDATE email_signatures SET {', '.join(sets)} WHERE id = ?",
        params,
    )
    return get_signature(conn, signature_id=signature_id)


def delete_signature(conn, *, signature_id: str, user_id: str) -> bool:
    """Delete a signature. Returns True if deleted."""
    sig = get_signature(conn, signature_id=signature_id)
    if not sig or sig["user_id"] != user_id:
        return False

    conn.execute("DELETE FROM email_signatures WHERE id = ?", (signature_id,))
    return True
