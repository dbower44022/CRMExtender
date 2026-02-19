"""Jinja2 template filters for date/time display."""

from __future__ import annotations

from markupsafe import Markup


def datetime_filter(value):
    """Emit a <time> element for datetime values (date + time).

    Returns empty string for falsy values.  The fallback text inside the
    element is a readable ``YYYY-MM-DD HH:MM`` string so the page is usable
    without JavaScript.
    """
    if not value:
        return ""
    iso = str(value)
    fallback = iso[:16].replace("T", " ")
    return Markup(
        '<time datetime="{iso}" data-format="datetime">{fallback}</time>'
        .format(iso=Markup.escape(iso), fallback=Markup.escape(fallback))
    )


def dateonly_filter(value):
    """Emit a <time> element for date-only values.

    Returns empty string for falsy values.
    """
    if not value:
        return ""
    iso = str(value)
    return Markup(
        '<time datetime="{iso}" data-format="date">{fallback}</time>'
        .format(iso=Markup.escape(iso), fallback=Markup.escape(iso))
    )


# -- SVG icons for event sources (16×16, stroke="currentColor") -----------

_SVG_GOOGLE_CALENDAR = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" '
    'fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="2" y="3" width="12" height="11" rx="1.5"/>'
    '<line x1="2" y1="6.5" x2="14" y2="6.5"/>'
    '<line x1="5.5" y1="1.5" x2="5.5" y2="4.5"/>'
    '<line x1="10.5" y1="1.5" x2="10.5" y2="4.5"/>'
    '<text x="8" y="12" text-anchor="middle" font-size="5" font-weight="bold" '
    'fill="currentColor" stroke="none" font-family="sans-serif">G</text>'
    '</svg>'
)

_SVG_MANUAL = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" '
    'fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M11.5 2.5l2 2-8 8H3.5v-2z"/>'
    '<line x1="9.5" y1="4.5" x2="11.5" y2="6.5"/>'
    '</svg>'
)

_SVG_CALENDAR_FALLBACK = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" '
    'fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="2" y="3" width="12" height="11" rx="1.5"/>'
    '<line x1="2" y1="6.5" x2="14" y2="6.5"/>'
    '<line x1="5.5" y1="1.5" x2="5.5" y2="4.5"/>'
    '<line x1="10.5" y1="1.5" x2="10.5" y2="4.5"/>'
    '</svg>'
)

_SOURCE_LABELS = {
    "google_calendar": "Google Calendar",
    "manual": "Manually created",
}


def source_icon_filter(source, account_name=None, calendar_id=None):
    """Return an inline SVG icon wrapped in a <span> with a tooltip title."""
    source = source or "manual"

    if source == "google_calendar":
        svg = _SVG_GOOGLE_CALENDAR
    elif source == "manual":
        svg = _SVG_MANUAL
    else:
        svg = _SVG_CALENDAR_FALLBACK

    # Build tooltip parts: label — account — calendar
    parts = [_SOURCE_LABELS.get(source, source)]
    if account_name:
        parts.append(str(account_name))
    if calendar_id and calendar_id != "primary":
        parts.append(str(calendar_id))
    tooltip = Markup.escape(" \u2014 ".join(parts))

    return Markup(
        '<span class="source-icon" title="{title}">{svg}</span>'.format(
            title=tooltip, svg=svg,
        )
    )


def resolve_link_filter(template, row):
    """Substitute {key} placeholders in a link template from row values."""
    try:
        url = template
        for key, val in (row.items() if hasattr(row, 'items') else []):
            placeholder = '{' + key + '}'
            if placeholder in url and val:
                url = url.replace(placeholder, str(val))
        # Return None if any unresolved placeholders remain
        if '{' in url:
            return None
        return url
    except Exception:
        return None


def register_filters(templates):
    """Register date/time filters on a Jinja2Templates instance."""
    templates.env.filters["datetime"] = datetime_filter
    templates.env.filters["dateonly"] = dateonly_filter
    templates.env.filters["source_icon"] = source_icon_filter
    templates.env.filters["resolve_link"] = resolve_link_filter

    from ..phone_utils import format_phone
    templates.env.filters["format_phone"] = format_phone
