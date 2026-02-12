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


def register_filters(templates):
    """Register date/time filters on a Jinja2Templates instance."""
    templates.env.filters["datetime"] = datetime_filter
    templates.env.filters["dateonly"] = dateonly_filter

    from ..phone_utils import format_phone
    templates.env.filters["format_phone"] = format_phone
