"""Server-side sanitization of stored email HTML for browser rendering.

The React frontend sanitizes client-side (frontend/src/lib/sanitizeHtml.ts);
this is the equivalent for server-rendered Jinja templates, which would
otherwise autoescape stored HTML into visible markup.
"""

from __future__ import annotations

import re

import bleach

# Elements whose content must go too — bleach strips tags but keeps
# their inner text, which for these would leak CSS/JS as visible text.
_CONTAINER_NOISE = re.compile(
    r"<(script|style|head|title)\b[^>]*>.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)

_ALLOWED_TAGS = [
    "a", "abbr", "b", "blockquote", "br", "caption", "center", "code",
    "dd", "div", "dl", "dt", "em", "font", "h1", "h2", "h3", "h4", "h5",
    "h6", "hr", "i", "img", "li", "ol", "p", "pre", "s", "small", "span",
    "strike", "strong", "sub", "sup", "table", "tbody", "td", "tfoot",
    "th", "thead", "tr", "u", "ul",
]

_ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "img": ["src", "alt", "width", "height"],
    "td": ["colspan", "rowspan", "align", "valign"],
    "th": ["colspan", "rowspan", "align", "valign"],
    "font": ["color"],
    "*": ["align"],
}

_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def sanitize_email_html(html: str | None) -> str | None:
    """Return email HTML reduced to safe formatting markup, or None if
    nothing renderable remains."""
    if not html:
        return None
    cleaned = _CONTAINER_NOISE.sub("", html)
    cleaned = _COMMENTS.sub("", cleaned)
    cleaned = bleach.clean(
        cleaned,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )
    return cleaned if cleaned.strip() else None


_NOTE_TAGS = [
    "p", "br", "strong", "em", "u", "s", "code", "pre", "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "span", "div", "hr", "sub", "sup", "mark",
]

_NOTE_ATTRS = {
    "a": ["href", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "span": ["class", "data-type", "data-id", "data-mention-type"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}


def sanitize_note_html(html: str | None) -> str | None:
    """Sanitize note editor HTML on save (Tiptap output incl. mention spans).

    Distinct allowlist from sanitize_email_html: notes keep editing markup
    (mark, sub/sup, mention data attributes) and never contain full email
    documents.
    """
    if not html:
        return html
    return bleach.clean(html, tags=_NOTE_TAGS, attributes=_NOTE_ATTRS, strip=True)
