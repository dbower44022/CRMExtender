"""Unit tests for Jinja2 date/time filters."""

from __future__ import annotations

import pytest
from markupsafe import Markup

from poc.web.filters import datetime_filter, dateonly_filter, register_filters


class TestDatetimeFilter:
    def test_returns_empty_for_none(self):
        assert datetime_filter(None) == ""

    def test_returns_empty_for_empty_string(self):
        assert datetime_filter("") == ""

    def test_returns_markup(self):
        result = datetime_filter("2026-02-10T14:23:00")
        assert isinstance(result, Markup)

    def test_contains_time_element(self):
        result = datetime_filter("2026-02-10T14:23:00")
        assert "<time " in result
        assert "</time>" in result

    def test_datetime_attribute(self):
        result = datetime_filter("2026-02-10T14:23:00")
        assert 'datetime="2026-02-10T14:23:00"' in result

    def test_data_format_datetime(self):
        result = datetime_filter("2026-02-10T14:23:00")
        assert 'data-format="datetime"' in result

    def test_fallback_text_readable(self):
        result = datetime_filter("2026-02-10T14:23:00")
        assert ">2026-02-10 14:23<" in result

    def test_fallback_replaces_T(self):
        result = datetime_filter("2026-02-10T09:00:00")
        assert "T" not in result.split(">")[1].split("<")[0]

    def test_truncates_to_16_chars(self):
        result = datetime_filter("2026-02-10T14:23:45.123456+00:00")
        fallback = result.split(">")[1].split("<")[0]
        assert fallback == "2026-02-10 14:23"

    def test_escapes_html_in_value(self):
        result = datetime_filter('<script>alert("xss")</script>')
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


class TestDateonlyFilter:
    def test_returns_empty_for_none(self):
        assert dateonly_filter(None) == ""

    def test_returns_empty_for_empty_string(self):
        assert dateonly_filter("") == ""

    def test_returns_markup(self):
        result = dateonly_filter("2026-02-10")
        assert isinstance(result, Markup)

    def test_contains_time_element(self):
        result = dateonly_filter("2026-02-10")
        assert "<time " in result
        assert "</time>" in result

    def test_datetime_attribute(self):
        result = dateonly_filter("2026-02-10")
        assert 'datetime="2026-02-10"' in result

    def test_data_format_date(self):
        result = dateonly_filter("2026-02-10")
        assert 'data-format="date"' in result

    def test_fallback_text_is_raw_value(self):
        result = dateonly_filter("2026-02-10")
        assert ">2026-02-10<" in result


class TestRegisterFilters:
    def test_registers_both_filters(self):
        class FakeEnv:
            filters = {}

        class FakeTemplates:
            env = FakeEnv()

        register_filters(FakeTemplates())
        assert "datetime" in FakeEnv.filters
        assert "dateonly" in FakeEnv.filters
        assert FakeEnv.filters["datetime"] is datetime_filter
        assert FakeEnv.filters["dateonly"] is dateonly_filter
