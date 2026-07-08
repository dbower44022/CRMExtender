"""Contact identity resolution engine (Identity Resolution Sub-PRD §5–§7).

Signal-based matching with weighted confidence combination:

    confidence = 1 - ((1 - s1) * (1 - s2) * ... * (1 - sN))

Thresholds are tenant-configurable via system settings
(idr_threshold_auto, idr_threshold_flag, idr_threshold_review);
defaults follow the PRD (0.90 / 0.70 / 0.40).

This module scores candidate pairs and manages match_candidates rows.
The batch scan covers KP-6's queue population for existing data; the
silent auto-merge path (KP-1) is intentionally not wired into email
sync yet — auto-merges only happen through explicit review.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher

from .database import get_connection

log = logging.getLogger(__name__)

# Signal weights (PRD §6.1)
WEIGHTS = {
    "email_exact": 1.0,
    "linkedin_url": 1.0,
    "phone_e164": 0.95,
    "name_exact": 0.30,
    "name_fuzzy": 0.20,
    "company_exact": 0.25,
    "company_fuzzy": 0.15,
    "title_match": 0.15,
    "email_domain": 0.20,
}

DEFAULT_THRESHOLDS = {"auto": 0.90, "flag": 0.70, "review": 0.40}

_PUBLIC_DOMAINS = frozenset({
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "me.com", "msn.com", "live.com", "comcast.net",
    "txt.voice.google.com",
})


@dataclass
class Signal:
    name: str
    weight: float
    value_a: str
    value_b: str


@dataclass
class MatchResult:
    contact_a: str
    contact_b: str
    confidence: float
    signals: list[Signal] = field(default_factory=list)

    def signals_json(self) -> str:
        return json.dumps([
            {"name": s.name, "weight": s.weight,
             "value_a": s.value_a, "value_b": s.value_b}
            for s in self.signals
        ])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def combine(signal_weights: list[float]) -> float:
    """Probabilistic independence combination (PRD §6.1)."""
    result = 1.0
    for w in signal_weights:
        result *= (1.0 - w)
    return round(1.0 - result, 4)


def get_thresholds(customer_id: str | None) -> dict:
    """Tenant thresholds with PRD defaults (IDENT-09)."""
    from .settings import get_setting

    out = dict(DEFAULT_THRESHOLDS)
    if customer_id:
        for key in out:
            val = get_setting(customer_id, f"idr_threshold_{key}")
            if val:
                try:
                    out[key] = float(val)
                except ValueError:
                    pass
    return out


def _fuzzy(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


@dataclass
class ContactProfile:
    """Everything the scorer needs about one contact."""
    id: str
    name: str
    emails: frozenset[str]
    domains: frozenset[str]
    phones: frozenset[str]
    linkedin: frozenset[str]
    companies: frozenset[str]
    titles: frozenset[str]


def load_profiles(customer_id: str | None) -> list[ContactProfile]:
    """Load matchable profiles for all active/incomplete contacts."""
    with get_connection() as conn:
        contacts = conn.execute(
            "SELECT id, name FROM contacts "
            "WHERE status IN ('active', 'incomplete') "
            "AND (customer_id IS NULL OR customer_id = ?)",
            (customer_id,),
        ).fetchall()

        emails: dict[str, set] = {}
        for r in conn.execute(
            "SELECT contact_id, LOWER(value) AS v FROM contact_identifiers "
            "WHERE type = 'email'"
        ):
            emails.setdefault(r["contact_id"], set()).add(r["v"])

        phones: dict[str, set] = {}
        for r in conn.execute(
            "SELECT entity_id, number FROM phone_numbers "
            "WHERE entity_type = 'contact' AND is_current = 1"
        ):
            phones.setdefault(r["entity_id"], set()).add(r["number"])

        linkedin: dict[str, set] = {}
        for r in conn.execute(
            "SELECT contact_id, LOWER(profile_url) AS v "
            "FROM contact_social_profiles WHERE platform = 'linkedin'"
        ):
            linkedin.setdefault(r["contact_id"], set()).add(
                r["v"].rstrip("/"))

        companies: dict[str, set] = {}
        titles: dict[str, set] = {}
        for r in conn.execute(
            "SELECT cc.contact_id, LOWER(co.name) AS co_name, "
            "       LOWER(COALESCE(cc.title, '')) AS title "
            "FROM contact_companies cc "
            "JOIN companies co ON co.id = cc.company_id "
            "WHERE cc.is_current = 1"
        ):
            companies.setdefault(r["contact_id"], set()).add(r["co_name"])
            if r["title"]:
                titles.setdefault(r["contact_id"], set()).add(r["title"])

    return [
        ContactProfile(
            id=c["id"],
            name=(c["name"] or "").strip(),
            emails=frozenset(emails.get(c["id"], ())),
            domains=frozenset(
                e.split("@", 1)[1] for e in emails.get(c["id"], ())
                if "@" in e and e.split("@", 1)[1] not in _PUBLIC_DOMAINS
            ),
            phones=frozenset(phones.get(c["id"], ())),
            linkedin=frozenset(linkedin.get(c["id"], ())),
            companies=frozenset(companies.get(c["id"], ())),
            titles=frozenset(titles.get(c["id"], ())),
        )
        for c in contacts
    ]


def load_profile(conn, contact_id: str) -> ContactProfile | None:
    """Load one contact's matchable profile (targeted queries)."""
    c = conn.execute(
        "SELECT id, name FROM contacts WHERE id = ?", (contact_id,)
    ).fetchone()
    if not c:
        return None
    emails = {
        r["v"] for r in conn.execute(
            "SELECT LOWER(value) AS v FROM contact_identifiers "
            "WHERE contact_id = ? AND type = 'email'", (contact_id,))
    }
    phones = {
        r["number"] for r in conn.execute(
            "SELECT number FROM phone_numbers WHERE entity_type = 'contact' "
            "AND entity_id = ? AND is_current = 1", (contact_id,))
    }
    linkedin = {
        r["v"].rstrip("/") for r in conn.execute(
            "SELECT LOWER(profile_url) AS v FROM contact_social_profiles "
            "WHERE contact_id = ? AND platform = 'linkedin'", (contact_id,))
    }
    companies, titles = set(), set()
    for r in conn.execute(
        "SELECT LOWER(co.name) AS co_name, LOWER(COALESCE(cc.title,'')) AS title "
        "FROM contact_companies cc JOIN companies co ON co.id = cc.company_id "
        "WHERE cc.contact_id = ? AND cc.is_current = 1", (contact_id,)
    ):
        companies.add(r["co_name"])
        if r["title"]:
            titles.add(r["title"])
    return ContactProfile(
        id=c["id"], name=(c["name"] or "").strip(),
        emails=frozenset(emails),
        domains=frozenset(
            e.split("@", 1)[1] for e in emails
            if "@" in e and e.split("@", 1)[1] not in _PUBLIC_DOMAINS),
        phones=frozenset(phones), linkedin=frozenset(linkedin),
        companies=frozenset(companies), titles=frozenset(titles),
    )


def _blocking_candidate_ids(conn, profile: ContactProfile,
                            customer_id: str | None) -> set[str]:
    """Existing active/incomplete contacts that share a blocking key with
    the given profile — the only ones worth scoring against it."""
    ids: set[str] = set()

    def _add(rows):
        for r in rows:
            ids.add(r[0])

    # Shared email domain
    for domain in profile.domains:
        _add(conn.execute(
            "SELECT DISTINCT ci.contact_id FROM contact_identifiers ci "
            "JOIN contacts c ON c.id = ci.contact_id "
            "WHERE ci.type = 'email' AND LOWER(ci.value) LIKE ? "
            "AND c.status IN ('active','incomplete') "
            "AND (c.customer_id IS NULL OR c.customer_id = ?)",
            (f"%@{domain}", customer_id)))
    # Shared phone
    for phone in profile.phones:
        _add(conn.execute(
            "SELECT DISTINCT pn.entity_id FROM phone_numbers pn "
            "JOIN contacts c ON c.id = pn.entity_id "
            "WHERE pn.entity_type = 'contact' AND pn.number = ? "
            "AND c.status IN ('active','incomplete') "
            "AND (c.customer_id IS NULL OR c.customer_id = ?)",
            (phone, customer_id)))
    # Shared company
    for company in profile.companies:
        _add(conn.execute(
            "SELECT DISTINCT cc.contact_id FROM contact_companies cc "
            "JOIN companies co ON co.id = cc.company_id "
            "JOIN contacts c ON c.id = cc.contact_id "
            "WHERE LOWER(co.name) = ? AND cc.is_current = 1 "
            "AND c.status IN ('active','incomplete') "
            "AND (c.customer_id IS NULL OR c.customer_id = ?)",
            (company, customer_id)))
    # Name-token overlap (each significant token)
    for token in profile.name.lower().split():
        if len(token) > 2:
            _add(conn.execute(
                "SELECT id FROM contacts "
                "WHERE LOWER(name) LIKE ? AND status IN ('active','incomplete') "
                "AND (customer_id IS NULL OR customer_id = ?)",
                (f"%{token}%", customer_id)))

    ids.discard(profile.id)
    return ids


def resolve_new_contact(
    contact_id: str, *, customer_id: str | None, source: str,
) -> dict:
    """Score a newly created contact against existing ones and queue
    review candidates (Identity Resolution Sub-PRD §7, IDENT-14).

    Runs at import/create time. Queues (does not auto-merge) any pair at
    or above the review threshold — deletions/merges stay human-driven,
    matching the batch scan's safety stance. Idempotent per pair.
    """
    thresholds = get_thresholds(customer_id)
    created = 0
    with get_connection() as conn:
        profile = load_profile(conn, contact_id)
        if profile is None:
            return {"candidates_created": 0}
        candidate_ids = _blocking_candidate_ids(conn, profile, customer_id)
        if not candidate_ids:
            return {"candidates_created": 0}

        existing = {
            _pair_key(r["contact_a_id"], r["contact_b_id"])
            for r in conn.execute(
                "SELECT contact_a_id, contact_b_id FROM match_candidates "
                "WHERE contact_a_id = ? OR contact_b_id = ?",
                (contact_id, contact_id))
        }
        now = _now()
        for other_id in candidate_ids:
            key = _pair_key(profile.id, other_id)
            if key in existing:
                continue
            other = load_profile(conn, other_id)
            if other is None:
                continue
            result = score_pair(profile, other)
            if result.confidence < thresholds["review"]:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO match_candidates "
                "(id, customer_id, contact_a_id, contact_b_id, confidence, "
                " signals, status, source, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
                (str(uuid.uuid4()), customer_id, key[0], key[1],
                 result.confidence, result.signals_json(), source, now, now))
            existing.add(key)
            created += 1
    return {"candidates_created": created}


def pending_candidate_contact_ids(customer_id: str | None) -> set[str]:
    """Contact IDs that appear in a pending match candidate (for the
    "Possible Duplicate" badge, IDENT-15)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT contact_a_id, contact_b_id FROM match_candidates "
            "WHERE status = 'pending' "
            "AND (customer_id IS NULL OR customer_id = ?)",
            (customer_id,)).fetchall()
    ids: set[str] = set()
    for r in rows:
        ids.add(r["contact_a_id"])
        ids.add(r["contact_b_id"])
    return ids


def score_pair(a: ContactProfile, b: ContactProfile) -> MatchResult:
    """Score two contacts against each other (PRD §5/§6)."""
    signals: list[Signal] = []

    def add(name: str, va: str, vb: str, weight: float | None = None):
        signals.append(Signal(name, weight or WEIGHTS[name], va, vb))

    shared_emails = a.emails & b.emails
    if shared_emails:
        v = next(iter(shared_emails))
        add("email_exact", v, v)

    shared_linkedin = a.linkedin & b.linkedin
    if shared_linkedin:
        v = next(iter(shared_linkedin))
        add("linkedin_url", v, v)

    shared_phones = a.phones & b.phones
    if shared_phones:
        v = next(iter(shared_phones))
        add("phone_e164", v, v)

    if a.name and b.name:
        if a.name.lower() == b.name.lower():
            add("name_exact", a.name, b.name)
        else:
            ratio = _fuzzy(a.name, b.name)
            if ratio > 0.90:
                add("name_fuzzy", a.name, b.name)

    shared_companies = a.companies & b.companies
    if shared_companies:
        v = next(iter(shared_companies))
        add("company_exact", v, v)
    elif a.companies and b.companies:
        best = max(
            ((ca, cb, _fuzzy(ca, cb)) for ca in a.companies for cb in b.companies),
            key=lambda t: t[2],
        )
        if best[2] > 0.85:
            add("company_fuzzy", best[0], best[1])

    shared_titles = a.titles & b.titles
    if shared_titles:
        v = next(iter(shared_titles))
        add("title_match", v, v)

    if not shared_emails:
        shared_domains = a.domains & b.domains
        if shared_domains:
            v = next(iter(shared_domains))
            add("email_domain", v, v)

    return MatchResult(
        contact_a=a.id, contact_b=b.id,
        confidence=combine([s.weight for s in signals]),
        signals=signals,
    )


def _pair_key(id_a: str, id_b: str) -> tuple[str, str]:
    return (id_a, id_b) if id_a < id_b else (id_b, id_a)


def scan_existing_contacts(
    *, customer_id: str | None, source: str = "scan",
) -> dict:
    """Scan existing contacts pairwise and queue review candidates.

    Idempotent (IDENT-13): existing candidates for a pair — in any
    status, including rejected — are never re-created. Only pairs whose
    combined confidence reaches the review threshold are stored; scores
    at/above the flag threshold are still stored as pending (no silent
    auto-merge in the batch scan — merging existing records is always a
    human decision here).
    """
    thresholds = get_thresholds(customer_id)
    profiles = load_profiles(customer_id)

    # Blocking: only compare pairs that share a name token, company, or
    # domain — avoids the full O(n^2) scoring
    buckets: dict[str, list[int]] = {}
    for idx, p in enumerate(profiles):
        keys = set()
        for token in p.name.lower().split():
            if len(token) > 2:
                keys.add(f"n:{token}")
        keys.update(f"c:{c}" for c in p.companies)
        keys.update(f"d:{d}" for d in p.domains)
        keys.update(f"p:{ph}" for ph in p.phones)
        for k in keys:
            buckets.setdefault(k, []).append(idx)

    candidate_pairs: set[tuple[int, int]] = set()
    for members in buckets.values():
        if len(members) < 2 or len(members) > 50:
            continue  # skip hyper-common tokens
        for i, x in enumerate(members):
            for y in members[i + 1:]:
                candidate_pairs.add((x, y) if x < y else (y, x))

    with get_connection() as conn:
        existing = {
            _pair_key(r["contact_a_id"], r["contact_b_id"])
            for r in conn.execute(
                "SELECT contact_a_id, contact_b_id FROM match_candidates"
            ).fetchall()
        }

    created = 0
    scored = 0
    now = _now()
    with get_connection() as conn:
        for x, y in candidate_pairs:
            a, b = profiles[x], profiles[y]
            key = _pair_key(a.id, b.id)
            if key in existing:
                continue
            result = score_pair(a, b)
            scored += 1
            if result.confidence < thresholds["review"]:
                continue
            conn.execute(
                "INSERT INTO match_candidates "
                "(id, customer_id, contact_a_id, contact_b_id, confidence, "
                " signals, status, source, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
                (str(uuid.uuid4()), customer_id, key[0], key[1],
                 result.confidence, result.signals_json(), source, now, now),
            )
            existing.add(key)
            created += 1

    return {"contacts": len(profiles), "pairs_scored": scored,
            "candidates_created": created}

