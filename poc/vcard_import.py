"""Import contacts from vCard (.vcf) files."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import vobject

from .database import get_connection
from .domain_resolver import extract_domain, is_public_domain
from .hierarchy import (
    add_address,
    add_contact_identifier,
    add_phone_number,
    find_company_by_name,
    create_company,
)
from .sync import _resolve_company_id

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_vcf_files(path: str | Path, *, recursive: bool = False) -> list[Path]:
    """Resolve *path* to a list of .vcf files.

    - If *path* is a file, return it (must end in .vcf).
    - If *path* is a directory, glob for *.vcf (optionally recursive).

    Raises FileNotFoundError if path doesn't exist,
    ValueError if a file doesn't have .vcf extension or no .vcf files found.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Path not found: {p}")

    if p.is_file():
        if p.suffix.lower() != ".vcf":
            raise ValueError(f"Not a .vcf file: {p}")
        return [p]

    if p.is_dir():
        pattern = "**/*.vcf" if recursive else "*.vcf"
        files = sorted(p.glob(pattern))
        if not files:
            raise ValueError(f"No .vcf files found in {p}")
        return files

    raise ValueError(f"Path is not a file or directory: {p}")


# ---------------------------------------------------------------------------
# vCard parsing
# ---------------------------------------------------------------------------

def parse_vcard_file(path: Path) -> list:
    """Parse a .vcf file, returning a list of vobject vCard components.

    Handles multi-vCard files (multiple BEGIN:VCARD blocks).
    Returns empty list if the file can't be parsed.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return list(vobject.readComponents(text))
    except Exception as exc:
        log.warning("Failed to parse %s: %s", path, exc)
        return []


# ---------------------------------------------------------------------------
# Type mappers
# ---------------------------------------------------------------------------

def _map_phone_type(vcard_types: list[str]) -> str:
    """Map vCard TEL TYPE params to CRM phone_type."""
    types = {t.upper() for t in vcard_types}
    if "CELL" in types:
        return "mobile"
    if "WORK" in types:
        return "work"
    if "HOME" in types:
        return "home"
    if "FAX" in types:
        return "fax"
    return "other"


def _map_address_type(vcard_types: list[str]) -> str:
    """Map vCard ADR TYPE params to CRM address_type."""
    types = {t.upper() for t in vcard_types}
    if "WORK" in types:
        return "work"
    if "HOME" in types:
        return "home"
    return "other"


def _map_email_label(vcard_types: list[str]) -> str:
    """Map vCard EMAIL TYPE params to CRM label."""
    types = {t.upper() for t in vcard_types}
    if "WORK" in types:
        return "work"
    if "HOME" in types:
        return "home"
    return "general"


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def extract_contact_data(vcard) -> dict | None:
    """Extract structured contact data from a parsed vCard component.

    Returns dict with keys: name, emails, phones, addresses, org, title.
    Returns None if no usable name can be extracted.
    """
    # Name: prefer FN, fallback to N
    name = None
    if hasattr(vcard, "fn"):
        name = vcard.fn.value.strip()
    if not name and hasattr(vcard, "n"):
        n = vcard.n.value
        parts = [p for p in [n.prefix, n.given, n.additional, n.family, n.suffix] if p]
        name = " ".join(parts).strip()
    if not name:
        return None

    # Emails
    emails = []
    for child in vcard.getChildren():
        if child.name.upper() == "EMAIL":
            value = child.value.strip().lower()
            if value:
                types = child.params.get("TYPE", [])
                emails.append({"value": value, "label": _map_email_label(types)})

    # Phones
    phones = []
    for child in vcard.getChildren():
        if child.name.upper() == "TEL":
            value = child.value.strip()
            if value:
                types = child.params.get("TYPE", [])
                phones.append({"number": value, "type": _map_phone_type(types)})

    # Addresses
    addresses = []
    for child in vcard.getChildren():
        if child.name.upper() == "ADR":
            adr = child.value
            # vobject returns Address with box, extended, street, city, region, code, country
            street = adr.street or ""
            city = adr.city or ""
            state = adr.region or ""
            postal_code = adr.code or ""
            country = adr.country or ""
            if any([street, city, state, postal_code, country]):
                types = child.params.get("TYPE", [])
                addresses.append({
                    "type": _map_address_type(types),
                    "street": street,
                    "city": city,
                    "state": state,
                    "postal_code": postal_code,
                    "country": country,
                })

    # Organization and title
    org = None
    if hasattr(vcard, "org"):
        org_val = vcard.org.value
        if isinstance(org_val, list):
            first = org_val[0] if org_val else None
            # vobject may nest lists (e.g. [['Company']])
            while isinstance(first, list):
                first = first[0] if first else None
            org = first.strip() if isinstance(first, str) and first else None
        elif isinstance(org_val, str):
            org = org_val.strip()
        if org == "":
            org = None

    title = None
    if hasattr(vcard, "title"):
        title = vcard.title.value.strip() or None

    return {
        "name": name,
        "emails": emails,
        "phones": phones,
        "addresses": addresses,
        "org": org,
        "title": title,
    }


# ---------------------------------------------------------------------------
# Import result
# ---------------------------------------------------------------------------

@dataclass
class ImportResult:
    """Summary of a vCard import operation."""

    files_processed: int = 0
    vcards_parsed: int = 0
    invalid_files: list[str] = field(default_factory=list)
    contacts_created: int = 0
    contacts_skipped_duplicate: int = 0
    contacts_skipped_no_name: int = 0
    companies_created: int = 0
    affiliations_created: int = 0
    phones_added: int = 0
    addresses_added: int = 0
    emails_added: int = 0
    imported_contacts: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main import
# ---------------------------------------------------------------------------

def import_vcards(
    path: str | Path,
    *,
    recursive: bool = False,
    customer_id: str | None = None,
    user_id: str | None = None,
) -> ImportResult:
    """Import contacts from vCard file(s).

    1. Find .vcf files at *path*
    2. Parse each file, extract contact data
    3. Skip if no name; skip if any email already in contact_identifiers (duplicate)
    4. Create contact, email identifiers, user_contacts visibility
    5. Company resolution: email domain via _resolve_company_id();
       if no domain match and ORG present, look up by name / create company
    6. Create affiliation with Employee role + title from vCard
    7. Add phones and addresses
    """
    result = ImportResult()

    files = find_vcf_files(path, recursive=recursive)

    for vcf_path in files:
        result.files_processed += 1
        vcards = parse_vcard_file(vcf_path)

        if not vcards:
            result.invalid_files.append(str(vcf_path))
            continue

        for vcard in vcards:
            result.vcards_parsed += 1
            data = extract_contact_data(vcard)

            if data is None:
                result.contacts_skipped_no_name += 1
                continue

            try:
                _import_single_contact(data, result,
                                       customer_id=customer_id,
                                       user_id=user_id)
            except Exception as exc:
                result.errors.append(f"{data['name']}: {exc}")
                log.warning("Error importing %s: %s", data["name"], exc)

    return result


def _import_single_contact(
    data: dict,
    result: ImportResult,
    *,
    customer_id: str | None,
    user_id: str | None,
) -> None:
    """Import a single extracted contact into the database."""
    now = datetime.now(timezone.utc).isoformat()
    emails = data["emails"]

    # Check for duplicate: any email already exists in contact_identifiers
    with get_connection() as conn:
        for em in emails:
            existing = conn.execute(
                "SELECT contact_id FROM contact_identifiers "
                "WHERE type = 'email' AND value = ?",
                (em["value"],),
            ).fetchone()
            if existing:
                result.contacts_skipped_duplicate += 1
                return

    # Create the contact
    contact_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO contacts
               (id, name, source, status, customer_id, created_by, created_at, updated_at)
               VALUES (?, ?, 'vcard_import', 'active', ?, ?, ?, ?)""",
            (contact_id, data["name"], customer_id, user_id, now, now),
        )

        # User visibility
        if user_id:
            conn.execute(
                """INSERT OR IGNORE INTO user_contacts
                   (id, user_id, contact_id, visibility, is_owner, created_at, updated_at)
                   VALUES (?, ?, ?, 'public', 1, ?, ?)""",
                (str(uuid.uuid4()), user_id, contact_id, now, now),
            )

    # Add email identifiers
    for i, em in enumerate(emails):
        try:
            add_contact_identifier(
                contact_id, "email", em["value"],
                label=em["label"],
                is_primary=(i == 0),
                source="vcard_import",
            )
            result.emails_added += 1
        except Exception as exc:
            result.errors.append(f"Email {em['value']}: {exc}")

    # Company resolution
    company_id = None
    # 1. Try domain-based resolution from the first email
    if emails:
        with get_connection() as conn:
            company_id = _resolve_company_id(
                conn, emails[0]["value"], now,
                customer_id=customer_id, user_id=user_id,
            )
            if company_id:
                # Check if this was a newly created company (name == domain)
                co = conn.execute(
                    "SELECT name, domain FROM companies WHERE id = ?", (company_id,)
                ).fetchone()
                if co and co["name"] == co["domain"]:
                    result.companies_created += 1

    # 2. If no domain match and ORG is present, try name-based resolution
    if not company_id and data.get("org"):
        existing_company = find_company_by_name(data["org"])
        if existing_company:
            company_id = existing_company["id"]
        else:
            try:
                new_co = create_company(
                    data["org"],
                    customer_id=customer_id,
                    created_by=user_id,
                )
                company_id = new_co["id"]
                result.companies_created += 1
                # Create user_companies visibility
                if user_id:
                    with get_connection() as conn:
                        conn.execute(
                            """INSERT OR IGNORE INTO user_companies
                               (id, user_id, company_id, visibility, is_owner, created_at, updated_at)
                               VALUES (?, ?, ?, 'public', 1, ?, ?)""",
                            (str(uuid.uuid4()), user_id, company_id, now, now),
                        )
            except ValueError:
                # Company already exists (race condition or name mismatch)
                existing_company = find_company_by_name(data["org"])
                if existing_company:
                    company_id = existing_company["id"]

    # Create affiliation
    if company_id:
        with get_connection() as conn:
            # Get Employee role
            emp_role = conn.execute(
                "SELECT id FROM contact_company_roles "
                "WHERE name = 'Employee' AND customer_id = ?",
                (customer_id,),
            ).fetchone()
            emp_role_id = emp_role["id"] if emp_role else None

            conn.execute(
                """INSERT OR IGNORE INTO contact_companies
                   (id, contact_id, company_id, role_id, title, is_primary, is_current,
                    source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 1, 1, 'vcard_import', ?, ?)""",
                (str(uuid.uuid4()), contact_id, company_id, emp_role_id,
                 data.get("title"), now, now),
            )
            result.affiliations_created += 1

    # Add phones
    for phone in data["phones"]:
        phone_result = add_phone_number(
            "contact", contact_id, phone["number"],
            phone_type=phone["type"],
            customer_id=customer_id,
        )
        if phone_result:
            result.phones_added += 1

    # Add addresses
    for addr in data["addresses"]:
        add_address(
            "contact", contact_id,
            address_type=addr["type"],
            street=addr["street"],
            city=addr["city"],
            state=addr["state"],
            postal_code=addr["postal_code"],
            country=addr["country"],
        )
        result.addresses_added += 1

    result.contacts_created += 1
    result.imported_contacts.append({
        "id": contact_id,
        "name": data["name"],
        "emails": [em["value"] for em in emails],
        "company": data.get("org") or "",
    })
