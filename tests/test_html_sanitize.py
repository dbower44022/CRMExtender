"""Unit tests for server-side email HTML sanitization."""

from __future__ import annotations

from poc.html_sanitize import sanitize_email_html


class TestSanitizeEmailHtml:
    def test_keeps_formatting_markup(self):
        out = sanitize_email_html("<p>Hi <strong>there</strong></p>")
        assert out == "<p>Hi <strong>there</strong></p>"

    def test_removes_script_and_style_with_content(self):
        out = sanitize_email_html(
            "<style>.a{color:red}</style><p>ok</p><script>alert(1)</script>"
        )
        assert out == "<p>ok</p>"

    def test_removes_head_block_and_comments(self):
        out = sanitize_email_html(
            "<html><head><title>Nextdoor</title></head>"
            "<body><!-- preheader --><div>body text</div></body></html>"
        )
        assert "Nextdoor" not in out
        assert "preheader" not in out
        assert "<div>body text</div>" in out

    def test_strips_event_handlers_and_js_urls(self):
        out = sanitize_email_html(
            '<a href="javascript:alert(1)" onclick="x()">link</a>'
        )
        assert "javascript:" not in out
        assert "onclick" not in out
        assert "link" in out

    def test_keeps_safe_links_and_images(self):
        out = sanitize_email_html(
            '<a href="https://example.com">site</a>'
            '<img src="https://example.com/logo.png" alt="logo">'
        )
        assert 'href="https://example.com"' in out
        assert 'src="https://example.com/logo.png"' in out

    def test_empty_and_none_return_none(self):
        assert sanitize_email_html(None) is None
        assert sanitize_email_html("") is None
        assert sanitize_email_html("<style>.a{}</style>") is None
