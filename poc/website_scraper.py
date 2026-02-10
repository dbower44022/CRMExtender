"""Website scraper enrichment provider — extracts company info from web pages."""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .enrichment_provider import (
    EnrichmentProvider,
    FieldValue,
    SourceTier,
    register_provider,
)
from .rate_limiter import RateLimiter

log = logging.getLogger(__name__)

_USER_AGENT = "CRMExtender/0.1 (enrichment bot; +https://example.com/bot)"
_TIMEOUT = 10
_MAX_CONTENT_BYTES = 2 * 1024 * 1024  # 2 MB

# Pages to crawl (in order of preference for about/contact)
_ABOUT_PATHS = ["/about", "/about-us", "/about_us"]
_CONTACT_PATHS = ["/contact", "/contact-us", "/contact_us"]

# Social media URL patterns
_SOCIAL_PATTERNS = {
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/(?:company|in)/[\w\-]+", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[\w]+", re.I),
    "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/[\w.\-]+", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[\w.\-]+", re.I),
    "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/(?:@|channel/|c/)[\w\-]+", re.I),
    "github": re.compile(r"https?://(?:www\.)?github\.com/[\w\-]+", re.I),
}

# Phone number regex (US-centric but reasonable)
_PHONE_RE = re.compile(
    r"(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
)

# Email regex
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# Domains to skip for email extraction (common tracking / no-reply)
_SKIP_EMAIL_DOMAINS = {
    "example.com", "sentry.io", "wixpress.com", "googleapis.com",
}


def _normalize_url(domain: str) -> str:
    """Ensure domain becomes a full URL."""
    if not domain:
        return ""
    if not domain.startswith(("http://", "https://")):
        return f"https://{domain}"
    return domain


def _fetch_robots_txt(session: requests.Session, base_url: str) -> str | None:
    """Fetch robots.txt for a domain. Returns content or None."""
    try:
        resp = session.get(
            urljoin(base_url, "/robots.txt"),
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.text
    except requests.RequestException:
        pass
    return None


def _is_allowed_by_robots(robots_txt: str | None, path: str) -> bool:
    """Basic robots.txt check — look for Disallow matching our path."""
    if not robots_txt:
        return True
    for line in robots_txt.splitlines():
        line = line.strip()
        if line.lower().startswith("disallow:"):
            disallowed = line.split(":", 1)[1].strip()
            if disallowed and path.startswith(disallowed):
                return False
    return True


def _fetch_page(
    session: requests.Session,
    url: str,
    rate_limiter: RateLimiter | None = None,
) -> BeautifulSoup | None:
    """Fetch a URL and return parsed BeautifulSoup, or None on failure."""
    if rate_limiter:
        rate_limiter.acquire()
    try:
        resp = session.get(
            url, timeout=_TIMEOUT,
            headers={"Accept": "text/html"},
            stream=True,
        )
        if resp.status_code != 200:
            return None
        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) > _MAX_CONTENT_BYTES:
            return None
        # Read limited content
        content = resp.content[:_MAX_CONTENT_BYTES]
        return BeautifulSoup(content, "lxml")
    except requests.RequestException as exc:
        log.debug("Failed to fetch %s: %s", url, exc)
        return None


def _extract_meta(soup: BeautifulSoup) -> list[FieldValue]:
    """Extract meta tags: description, og:title, og:description."""
    results = []
    # Meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        results.append(FieldValue(
            field_name="description",
            field_value=meta_desc["content"].strip(),
            confidence=0.7,
        ))
    # Open Graph
    og_desc = soup.find("meta", attrs={"property": "og:description"})
    if og_desc and og_desc.get("content"):
        # Only use if we didn't already get a meta description
        if not any(fv.field_name == "description" for fv in results):
            results.append(FieldValue(
                field_name="description",
                field_value=og_desc["content"].strip(),
                confidence=0.6,
            ))
    return results


def _extract_json_ld(soup: BeautifulSoup) -> list[FieldValue]:
    """Extract schema.org JSON-LD Organization/LocalBusiness data."""
    results = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle @graph arrays
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "@graph" in data:
                items = data["@graph"]
            else:
                items = [data]

        for item in items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type", "")
            if isinstance(item_type, list):
                item_type = item_type[0] if item_type else ""
            if item_type not in ("Organization", "LocalBusiness", "Corporation"):
                continue

            if item.get("description"):
                results.append(FieldValue(
                    field_name="description",
                    field_value=str(item["description"]).strip(),
                    confidence=0.8,
                ))
            if item.get("foundingDate"):
                try:
                    year = str(item["foundingDate"])[:4]
                    results.append(FieldValue(
                        field_name="founded_year",
                        field_value=year,
                        confidence=0.9,
                    ))
                except (ValueError, IndexError):
                    pass
            if item.get("numberOfEmployees"):
                emp = item["numberOfEmployees"]
                if isinstance(emp, dict):
                    val = emp.get("value", "")
                else:
                    val = str(emp)
                if val:
                    results.append(FieldValue(
                        field_name="employee_count",
                        field_value=str(val),
                        confidence=0.8,
                    ))

            # Address from JSON-LD
            addr = item.get("address")
            if isinstance(addr, dict):
                parts = []
                for key in ("streetAddress", "addressLocality", "addressRegion", "postalCode"):
                    if addr.get(key):
                        parts.append(str(addr[key]))
                if parts:
                    results.append(FieldValue(
                        field_name="address",
                        field_value=", ".join(parts),
                        confidence=0.8,
                    ))

            # Social links from JSON-LD
            same_as = item.get("sameAs", [])
            if isinstance(same_as, str):
                same_as = [same_as]
            for url in same_as:
                if isinstance(url, str):
                    for platform, pattern in _SOCIAL_PATTERNS.items():
                        if pattern.match(url):
                            results.append(FieldValue(
                                field_name=f"social_{platform}",
                                field_value=url,
                                confidence=0.9,
                            ))
                            break

    return results


def _extract_social_links(soup: BeautifulSoup, base_domain: str) -> list[FieldValue]:
    """Extract social media links from <a> tags."""
    results = []
    seen = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        for platform, pattern in _SOCIAL_PATTERNS.items():
            match = pattern.match(href)
            if match:
                url = match.group(0)
                key = (platform, url)
                if key not in seen:
                    seen.add(key)
                    results.append(FieldValue(
                        field_name=f"social_{platform}",
                        field_value=url,
                        confidence=0.8,
                    ))
                break
    return results


def _extract_contact_info(soup: BeautifulSoup, base_domain: str) -> list[FieldValue]:
    """Extract phone numbers and email addresses from page text."""
    results = []
    text = soup.get_text(" ", strip=True)

    # Phone numbers
    seen_phones = set()
    for match in _PHONE_RE.finditer(text):
        phone = match.group(0).strip()
        # Normalize: remove non-digit except leading +
        digits = re.sub(r"[^\d+]", "", phone)
        if len(digits) >= 10 and digits not in seen_phones:
            seen_phones.add(digits)
            results.append(FieldValue(
                field_name="phone",
                field_value=phone,
                confidence=0.7,
            ))

    # Email addresses
    seen_emails = set()
    for match in _EMAIL_RE.finditer(text):
        email = match.group(0).lower()
        domain = email.split("@", 1)[1]
        if domain not in _SKIP_EMAIL_DOMAINS and email not in seen_emails:
            seen_emails.add(email)
            results.append(FieldValue(
                field_name="email",
                field_value=email,
                confidence=0.7,
            ))

    # Also look for mailto: links
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.startswith("mailto:"):
            email = href[7:].split("?")[0].lower()
            domain = email.split("@", 1)[1] if "@" in email else ""
            if domain and domain not in _SKIP_EMAIL_DOMAINS and email not in seen_emails:
                seen_emails.add(email)
                results.append(FieldValue(
                    field_name="email",
                    field_value=email,
                    confidence=0.8,
                ))

    return results


def _resolve_page_url(base_url: str, paths: list[str], session: requests.Session,
                      robots_txt: str | None,
                      rate_limiter: RateLimiter | None = None) -> str | None:
    """Try multiple path variants, return first that succeeds."""
    for path in paths:
        if not _is_allowed_by_robots(robots_txt, path):
            continue
        url = urljoin(base_url, path)
        if rate_limiter:
            rate_limiter.acquire()
        try:
            resp = session.head(url, timeout=_TIMEOUT, allow_redirects=True)
            if resp.status_code == 200:
                return url
        except requests.RequestException:
            continue
    return None


class WebsiteScraperProvider(EnrichmentProvider):
    """Scrape a company's website for basic info."""

    @property
    def name(self) -> str:
        return "website_scraper"

    @property
    def tier(self) -> SourceTier:
        return SourceTier.WEBSITE_SCRAPE

    @property
    def entity_types(self) -> list[str]:
        return ["company"]

    @property
    def rate_limit(self) -> float:
        return 2.0

    @property
    def cost_per_lookup(self) -> float:
        return 0.0

    @property
    def refresh_cadence_days(self) -> int:
        return 90

    def __init__(self) -> None:
        self._rate_limiter = RateLimiter(rate=2.0, burst=2)

    def enrich(self, entity: dict) -> list[FieldValue]:
        """Scrape up to 3 pages from the entity's domain/website."""
        domain = entity.get("website") or entity.get("domain") or ""
        if not domain:
            return []

        base_url = _normalize_url(domain)
        parsed = urlparse(base_url)
        base_domain = parsed.netloc or parsed.path

        session = requests.Session()
        session.headers["User-Agent"] = _USER_AGENT

        # Check robots.txt
        robots_txt = _fetch_robots_txt(session, base_url)

        all_results: list[FieldValue] = []

        # 1. Homepage
        if _is_allowed_by_robots(robots_txt, "/"):
            soup = _fetch_page(session, base_url, self._rate_limiter)
            if soup:
                all_results.extend(_extract_meta(soup))
                all_results.extend(_extract_json_ld(soup))
                all_results.extend(_extract_social_links(soup, base_domain))
                all_results.extend(_extract_contact_info(soup, base_domain))

        # 2. About page
        about_url = _resolve_page_url(
            base_url, _ABOUT_PATHS, session, robots_txt, self._rate_limiter
        )
        if about_url:
            soup = _fetch_page(session, about_url, self._rate_limiter)
            if soup:
                all_results.extend(_extract_meta(soup))
                all_results.extend(_extract_json_ld(soup))
                all_results.extend(_extract_social_links(soup, base_domain))

        # 3. Contact page
        contact_url = _resolve_page_url(
            base_url, _CONTACT_PATHS, session, robots_txt, self._rate_limiter
        )
        if contact_url:
            soup = _fetch_page(session, contact_url, self._rate_limiter)
            if soup:
                all_results.extend(_extract_contact_info(soup, base_domain))
                all_results.extend(_extract_social_links(soup, base_domain))

        # Deduplicate: keep highest confidence per (field_name, field_value)
        best: dict[tuple[str, str], FieldValue] = {}
        for fv in all_results:
            key = (fv.field_name, fv.field_value)
            if key not in best or fv.confidence > best[key].confidence:
                best[key] = fv

        # For direct fields, keep only the best value per field_name
        direct_best: dict[str, FieldValue] = {}
        multi_value_fields = {"phone", "email", "address"}
        final = []
        for fv in best.values():
            if fv.field_name.startswith("social_") or fv.field_name in multi_value_fields:
                final.append(fv)
            else:
                if fv.field_name not in direct_best or fv.confidence > direct_best[fv.field_name].confidence:
                    direct_best[fv.field_name] = fv
        final.extend(direct_best.values())

        return final


# Auto-register on import
_provider = WebsiteScraperProvider()
register_provider(_provider)
