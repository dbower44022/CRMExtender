"""HTML-aware email quote and signature stripping.

Uses quotequail for HTML quote detection and BeautifulSoup for
structural removal of signatures, reply headers, and boilerplate
elements identified by CSS classes and IDs common to Gmail, Outlook,
Yahoo, and Apple Mail.
"""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup, Tag

log = logging.getLogger(__name__)

# CSS selectors for elements to remove, grouped by purpose.

# Quoted content containers
_QUOTE_SELECTORS = [
    "div.gmail_quote",
    "div.gmail_quote_container",
    "div.gmail_extra",
    "blockquote.gmail_quote",
    "div.yahoo_quoted",
    "blockquote[type=cite]",
]

# Signature containers
_SIGNATURE_SELECTORS = [
    "div.gmail_signature",
    "[data-smartmail=gmail_signature]",
    "div#Signature",
]

# Reply/forward separator markers — remove these AND all following siblings
_CUTOFF_SELECTORS = [
    "div#appendonsend",
    "div#divRplyFwdMsg",
]

# Combined list for elements where only the element itself is removed
_ALL_REMOVE_SELECTORS = _QUOTE_SELECTORS + _SIGNATURE_SELECTORS

# Outlook separator style pattern (border-top:solid #E1E1E1)
_OUTLOOK_BORDER_RE = re.compile(r"border-top\s*:\s*solid\s+#E1E1E1", re.IGNORECASE)


def _remove_unsubscribe_footers(soup: BeautifulSoup) -> None:
    """Remove newsletter/unsubscribe footer blocks from the HTML tree.

    Targets:
    1. Elements with IDs starting with ``footerUnsubscribe``.
    2. Elements containing the word "unsubscribe" in their text.

    In both cases the matched element and all following siblings are removed.
    """
    # 1. ID-based: footerUnsubscribe*
    for tag in soup.find_all(id=re.compile(r"^footerUnsubscribe", re.IGNORECASE)):
        if isinstance(tag, Tag):
            for sibling in list(tag.find_next_siblings()):
                sibling.decompose()
            tag.decompose()

    # 2. Text-based: any element whose *direct* text contains "unsubscribe"
    for tag in soup.find_all(string=re.compile(r"unsubscribe", re.IGNORECASE)):
        # Navigate up to a block-level container
        parent = tag.parent
        if parent and isinstance(parent, Tag):
            # Walk up to find a reasonable block container (div, td, p, tr, table)
            container = parent
            for _ in range(5):
                if container.name in ("div", "td", "p", "tr", "table", "body"):
                    break
                if container.parent and isinstance(container.parent, Tag):
                    container = container.parent
                else:
                    break
            if container.name != "body":
                for sibling in list(container.find_next_siblings()):
                    sibling.decompose()
                container.decompose()
                break  # only need first match


def _remove_outlook_separators(soup: BeautifulSoup) -> None:
    """Remove Outlook-style separators identified by inline border-top style."""
    for tag in soup.find_all(style=True):
        if isinstance(tag, Tag) and _OUTLOOK_BORDER_RE.search(tag.get("style", "")):
            # Remove this element and everything after it in the parent
            for sibling in list(tag.find_next_siblings()):
                sibling.decompose()
            tag.decompose()
            break  # only need the first separator


def strip_html_quotes(html: str) -> str:
    """Strip quoted replies, signatures, and boilerplate from an HTML email body.

    Returns cleaned plain text extracted from the HTML.
    """
    if not html or not html.strip():
        return ""

    # Step 1: Use quotequail to identify and remove quoted regions.
    # quotequail returns [(is_reply, html_chunk), ...] where is_reply=True
    # is the author's own content.
    try:
        import quotequail

        parts = quotequail.quote_html(html)
        if parts:
            # Keep only the reply portions (is_reply=True)
            reply_parts = [chunk for is_reply, chunk in parts if is_reply]
            if reply_parts:
                html = reply_parts[0]  # use the first (primary) reply block
    except Exception as exc:
        log.debug("quotequail failed, continuing with raw HTML: %s", exc)

    # Step 2: Parse with BeautifulSoup and remove structural elements
    soup = BeautifulSoup(html, "lxml")

    # Remove quoted content (always safe)
    for selector in _QUOTE_SELECTORS:
        for el in soup.select(selector):
            el.decompose()

    # Remove signature elements — but some clients (notably Gmail) wrap
    # the entire message body inside a signature div.  When that happens,
    # removing signatures empties the result.  Detect that and re-parse
    # without signature removal so that text-level cleanup can handle it.
    sig_elements = []
    for selector in _SIGNATURE_SELECTORS:
        sig_elements.extend(soup.select(selector))

    if sig_elements:
        for el in sig_elements:
            el.decompose()
        if not soup.get_text(strip=True):
            # Signature removal emptied the result — re-parse without it
            log.debug("Signature removal emptied result, re-parsing without it")
            soup = BeautifulSoup(html, "lxml")
            for selector in _QUOTE_SELECTORS:
                for el in soup.select(selector):
                    el.decompose()

    # Remove cutoff markers and everything after them (siblings)
    for selector in _CUTOFF_SELECTORS:
        for el in soup.select(selector):
            for sibling in list(el.find_next_siblings()):
                sibling.decompose()
            el.decompose()

    # Remove Outlook border-top separators
    _remove_outlook_separators(soup)

    # Remove newsletter / unsubscribe footers
    _remove_unsubscribe_footers(soup)

    # Step 3: Convert to plain text
    text = soup.get_text(separator="\n", strip=True)

    return text
