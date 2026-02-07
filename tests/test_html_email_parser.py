"""Tests for HTML-aware email quote and signature stripping."""

import pytest

from poc.html_email_parser import strip_html_quotes
from poc.email_parser import strip_quotes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wrap_html(body_html: str) -> str:
    """Wrap an HTML fragment in a minimal document structure."""
    return f"<html><body>{body_html}</body></html>"


# ---------------------------------------------------------------------------
# Gmail quote stripping
# ---------------------------------------------------------------------------

class TestGmailQuoteStripping:
    """Test removal of Gmail quoted content via structural HTML cues."""

    def test_gmail_quote_div(self):
        html = _wrap_html(
            '<div>My reply to you.</div>'
            '<div class="gmail_quote">'
            '<div class="gmail_attr">On Mon, Jan 1 wrote:</div>'
            '<blockquote>Original message content</blockquote>'
            '</div>'
        )
        result = strip_html_quotes(html)
        assert "My reply to you." in result
        assert "Original message content" not in result

    def test_gmail_quote_container(self):
        html = _wrap_html(
            '<div>Thanks for the update.</div>'
            '<div class="gmail_quote_container">'
            '<div>On Tue wrote:</div>'
            '<div>Some quoted text here</div>'
            '</div>'
        )
        result = strip_html_quotes(html)
        assert "Thanks for the update." in result
        assert "Some quoted text here" not in result

    def test_gmail_extra(self):
        html = _wrap_html(
            '<div>Sounds good!</div>'
            '<div class="gmail_extra">'
            '<div>Previous conversation</div>'
            '</div>'
        )
        result = strip_html_quotes(html)
        assert "Sounds good!" in result
        assert "Previous conversation" not in result

    def test_blockquote_gmail_quote(self):
        html = _wrap_html(
            '<div>I agree with your point.</div>'
            '<blockquote class="gmail_quote">'
            'The original email text goes here.'
            '</blockquote>'
        )
        result = strip_html_quotes(html)
        assert "I agree with your point." in result
        assert "original email text" not in result


# ---------------------------------------------------------------------------
# Gmail signature stripping
# ---------------------------------------------------------------------------

class TestGmailSignatureStripping:
    """Test removal of Gmail signature blocks."""

    def test_gmail_signature_div(self):
        html = _wrap_html(
            '<div>Please see attached.</div>'
            '<div class="gmail_signature">'
            '<div>John Smith</div>'
            '<div>VP of Engineering</div>'
            '<div>Tel: +1 555-123-4567</div>'
            '</div>'
        )
        result = strip_html_quotes(html)
        assert "Please see attached." in result
        assert "VP of Engineering" not in result
        assert "555-123-4567" not in result

    def test_gmail_smartmail_signature(self):
        html = _wrap_html(
            '<div>Let me know your thoughts.</div>'
            '<div data-smartmail="gmail_signature">'
            '<div>Jane Doe</div>'
            '<div>jane@example.com</div>'
            '</div>'
        )
        result = strip_html_quotes(html)
        assert "Let me know your thoughts." in result
        assert "jane@example.com" not in result


# ---------------------------------------------------------------------------
# Outlook quote stripping
# ---------------------------------------------------------------------------

class TestOutlookQuoteStripping:
    """Test removal of Outlook quoted content and separators."""

    def test_appendonsend(self):
        html = _wrap_html(
            '<div>Here is my response.</div>'
            '<div id="appendonsend"></div>'
            '<hr>'
            '<div><b>From:</b> sender@example.com</div>'
            '<div><b>Sent:</b> Monday, January 1, 2024</div>'
            '<div>Original message content</div>'
        )
        result = strip_html_quotes(html)
        assert "Here is my response." in result
        assert "Original message content" not in result

    def test_divRplyFwdMsg(self):
        html = _wrap_html(
            '<div>Thanks for the info.</div>'
            '<div id="divRplyFwdMsg">'
            '<div><b>From:</b> someone@example.com</div>'
            '<div>Forwarded content here</div>'
            '</div>'
        )
        result = strip_html_quotes(html)
        assert "Thanks for the info." in result
        assert "Forwarded content here" not in result

    def test_outlook_border_separator(self):
        html = _wrap_html(
            '<div>My reply above the line.</div>'
            '<div style="border-top:solid #E1E1E1 1.0pt; padding:3.0pt 0in 0in 0in">'
            '<p><b>From:</b> original@sender.com</p>'
            '<p>Original email body</p>'
            '</div>'
        )
        result = strip_html_quotes(html)
        assert "My reply above the line." in result
        assert "Original email body" not in result


# ---------------------------------------------------------------------------
# Outlook signature stripping
# ---------------------------------------------------------------------------

class TestOutlookSignatureStripping:
    """Test removal of Outlook signature blocks."""

    def test_outlook_signature_div(self):
        html = _wrap_html(
            '<div>Meeting confirmed for Tuesday.</div>'
            '<div id="Signature">'
            '<div>Bob Wilson</div>'
            '<div>Director of Sales</div>'
            '<div>Phone: 555-999-8888</div>'
            '</div>'
        )
        result = strip_html_quotes(html)
        assert "Meeting confirmed for Tuesday." in result
        assert "Director of Sales" not in result
        assert "555-999-8888" not in result


# ---------------------------------------------------------------------------
# Apple Mail / Yahoo quote stripping
# ---------------------------------------------------------------------------

class TestAppleMailQuoteStripping:
    """Test removal of Apple Mail quoted content (blockquote[type=cite])."""

    def test_blockquote_type_cite(self):
        html = _wrap_html(
            '<div>Great idea, let\'s proceed.</div>'
            '<blockquote type="cite">'
            '<div>On Jan 1, 2024, at 10:00 AM, John wrote:</div>'
            '<div>What do you think about the proposal?</div>'
            '</blockquote>'
        )
        result = strip_html_quotes(html)
        assert "let's proceed" in result
        assert "What do you think about the proposal?" not in result


class TestYahooQuoteStripping:
    """Test removal of Yahoo Mail quoted content."""

    def test_yahoo_quoted_div(self):
        html = _wrap_html(
            '<div>Received, thank you.</div>'
            '<div class="yahoo_quoted">'
            '<div>--- Original Message ---</div>'
            '<div>Previous email content</div>'
            '</div>'
        )
        result = strip_html_quotes(html)
        assert "Received, thank you." in result
        assert "Previous email content" not in result


# ---------------------------------------------------------------------------
# Fallback behavior
# ---------------------------------------------------------------------------

class TestHTMLFallback:
    """Test that empty/malformed HTML falls back to plain-text pipeline."""

    def test_empty_html_uses_plaintext(self):
        body = "Plain text reply.\n\nSent from my iPhone"
        result = strip_quotes(body, body_html="")
        assert "Plain text reply." in result
        assert "Sent from my iPhone" not in result

    def test_none_html_uses_plaintext(self):
        body = "Plain text reply.\n\nSent from my iPhone"
        result = strip_quotes(body, body_html=None)
        assert "Plain text reply." in result
        assert "Sent from my iPhone" not in result

    def test_whitespace_only_html_uses_plaintext(self):
        body = "Quick reply.\n\nSent from my iPhone"
        result = strip_quotes(body, body_html="   \n  ")
        assert "Quick reply." in result
        assert "Sent from my iPhone" not in result

    def test_html_producing_empty_text_uses_plaintext(self):
        """If HTML stripping removes everything, fall back to plain text."""
        body = "Actual content here."
        # HTML that is entirely a quote - stripping yields empty
        html = _wrap_html(
            '<div class="gmail_quote">'
            '<div>Everything is quoted</div>'
            '</div>'
        )
        result = strip_quotes(body, body_html=html)
        assert "Actual content here." in result


# ---------------------------------------------------------------------------
# HTML track with text cleanup
# ---------------------------------------------------------------------------

class TestHTMLWithTextCleanup:
    """Test that lightweight text cleanup still runs on HTML-extracted text."""

    def test_mobile_sig_in_html_body(self):
        html = _wrap_html(
            '<div>Quick reply from phone.</div>'
            '<div>Sent from my iPhone</div>'
        )
        result = strip_quotes("fallback", body_html=html)
        assert "Quick reply from phone." in result
        assert "Sent from my iPhone" not in result

    def test_confidentiality_notice_in_html_body(self):
        html = _wrap_html(
            '<div>See attached document.</div>'
            '<div>This email may contain confidential information.</div>'
        )
        result = strip_quotes("fallback", body_html=html)
        assert "See attached document." in result
        assert "confidential" not in result

    def test_environmental_message_in_html_body(self):
        html = _wrap_html(
            '<div>Report is ready.</div>'
            '<div>Please consider the environment before printing this email.</div>'
        )
        result = strip_quotes("fallback", body_html=html)
        assert "Report is ready." in result
        assert "environment" not in result


# ---------------------------------------------------------------------------
# Integration: strip_quotes with body_html parameter
# ---------------------------------------------------------------------------

class TestStripQuotesHTMLIntegration:
    """Test the full strip_quotes() function with HTML bodies."""

    def test_html_track_preferred_over_plaintext(self):
        """When HTML is available, use it instead of plain text."""
        plain = (
            "My reply\n\n"
            "On Mon, Jan 1 wrote:\n"
            "> quoted text that plain-text track would catch\n"
        )
        html = _wrap_html(
            '<div>My reply</div>'
            '<div class="gmail_quote">'
            '<div>On Mon, Jan 1 wrote:</div>'
            '<blockquote>quoted text</blockquote>'
            '</div>'
        )
        result = strip_quotes(plain, body_html=html)
        assert "My reply" in result
        assert "quoted text" not in result

    def test_gmail_full_email_html(self):
        """Realistic Gmail email with quote, signature, and boilerplate."""
        html = _wrap_html(
            '<div dir="ltr">'
            '<div>Hi Team,</div>'
            '<div><br></div>'
            '<div>The meeting is confirmed for 3pm.</div>'
            '</div>'
            '<div class="gmail_signature">'
            '<div>Jennifer Wilson</div>'
            '<div>COO, Acme Corp</div>'
            '<div>Tel: 555-999-8888</div>'
            '</div>'
            '<div class="gmail_quote">'
            '<div class="gmail_attr">On Mon wrote:</div>'
            '<blockquote>Can we meet this week?</blockquote>'
            '</div>'
        )
        result = strip_quotes("fallback plain text", body_html=html)
        assert "meeting is confirmed for 3pm" in result
        assert "Acme Corp" not in result
        assert "Can we meet this week?" not in result

    def test_backward_compatibility_no_html(self):
        """Existing callers passing only body still work."""
        body = "Hello, simple message.\n\nSent from my iPhone"
        result = strip_quotes(body)
        assert "Hello, simple message." in result
        assert "Sent from my iPhone" not in result


# ---------------------------------------------------------------------------
# HTML-level unsubscribe footer stripping
# ---------------------------------------------------------------------------

class TestHTMLUnsubscribeFooter:
    """Test removal of newsletter/unsubscribe footers in HTML."""

    def test_footer_unsubscribe_id(self):
        html = _wrap_html(
            '<div>Great article content here.</div>'
            '<div id="footerUnsubscribe">'
            '<a href="#">Unsubscribe</a>'
            '</div>'
            '<div>Company address footer</div>'
        )
        result = strip_html_quotes(html)
        assert "Great article content here." in result
        assert "Unsubscribe" not in result
        assert "Company address" not in result

    def test_unsubscribe_text_in_div(self):
        html = _wrap_html(
            '<div>Newsletter body text.</div>'
            '<div><a href="#">Click here to unsubscribe</a></div>'
            '<div>Footer content</div>'
        )
        result = strip_html_quotes(html)
        assert "Newsletter body text." in result
        assert "unsubscribe" not in result
        assert "Footer content" not in result

    def test_unsubscribe_in_table_cell(self):
        html = _wrap_html(
            '<div>Product announcement.</div>'
            '<table><tr><td>You can <a href="#">unsubscribe</a> at any time.</td></tr></table>'
            '<div>More footer stuff</div>'
        )
        result = strip_html_quotes(html)
        assert "Product announcement." in result
        assert "unsubscribe" not in result

    def test_unsubscribe_in_paragraph(self):
        html = _wrap_html(
            '<div>Meeting notes from today.</div>'
            '<p>To unsubscribe from these emails, click here.</p>'
            '<p>Copyright 2024</p>'
        )
        result = strip_html_quotes(html)
        assert "Meeting notes from today." in result
        assert "unsubscribe" not in result
        assert "Copyright" not in result


# ---------------------------------------------------------------------------
# HTML track with signature detection (no CSS markup)
# ---------------------------------------------------------------------------

class TestHTMLTrackSignatureDetection:
    """Test that the HTML track now catches signatures lacking CSS markup."""

    def test_valediction_signature_in_html(self):
        html = _wrap_html(
            '<div>Please review the attached.</div>'
            '<div>Best regards,</div>'
            '<div>John Smith</div>'
            '<div>VP of Engineering</div>'
            '<div>Tel: +1 555-123-4567</div>'
        )
        result = strip_quotes("fallback", body_html=html)
        assert "Please review the attached." in result
        assert "VP of Engineering" not in result
        assert "555-123-4567" not in result

    def test_standalone_name_signature_in_html(self):
        html = _wrap_html(
            '<div>The report is ready for review.</div>'
            '<div>ROBIN BAUM, CPA</div>'
            '<div>Director of Finance</div>'
            '<div>Phone: 555-000-1111</div>'
        )
        result = strip_quotes("fallback", body_html=html)
        assert "report is ready for review" in result
        assert "ROBIN BAUM" not in result

    def test_promotional_content_in_html(self):
        html = _wrap_html(
            '<div>See you at the conference.</div>'
            '<div>Follow us on LinkedIn <http://linkedin.com></div>'
            '<div>Twitter <http://twitter.com></div>'
        )
        result = strip_quotes("fallback", body_html=html)
        assert "See you at the conference." in result
        assert "LinkedIn" not in result

    def test_dash_dash_signature_in_html(self):
        html = _wrap_html(
            '<div>Quick update on the project.</div>'
            '<div>--</div>'
            '<div>Jane Doe</div>'
            '<div>jane@example.com</div>'
        )
        result = strip_quotes("fallback", body_html=html)
        assert "Quick update on the project." in result
        assert "Jane Doe" not in result

    def test_unsubscribe_footer_in_html_via_strip_quotes(self):
        html = _wrap_html(
            '<div>Important product update.</div>'
            '<div><a href="#">Unsubscribe</a> from this mailing list.</div>'
        )
        result = strip_quotes("fallback", body_html=html)
        assert "Important product update." in result
        assert "Unsubscribe" not in result

    def test_underscore_signature_in_html(self):
        html = _wrap_html(
            '<div>Please update the reports.</div>'
            '<div>____</div>'
            '<div>Sharon Rose</div>'
            '<div>SCORE Cleveland Co-Chair</div>'
            '<div>Email:sharon@example.org</div>'
        )
        result = strip_quotes("fallback", body_html=html)
        assert "Please update the reports." in result
        assert "Sharon Rose" not in result
        assert "Co-Chair" not in result


# ---------------------------------------------------------------------------
# HTML track resilience: body inside signature div
# ---------------------------------------------------------------------------

class TestHTMLBodyInsideSignature:
    """Test that body content inside a gmail_signature div is preserved."""

    def test_body_inside_gmail_signature(self):
        """When entire body is inside gmail_signature, don't strip it."""
        html = _wrap_html(
            '<div dir="ltr">'
            '<div class="gmail_signature" data-smartmail="gmail_signature">'
            '<div>Hi Everyone,</div>'
            '<div>The meeting is on Wednesday at 10:00</div>'
            '<div>Looking forward to seeing you then,</div>'
            '<div>Sharon</div>'
            '<div>____</div>'
            '<div>Sharon Rose</div>'
            '<div>SCORE Cleveland Co-Chair</div>'
            '<div>Email:sharon@example.org</div>'
            '</div>'
            '</div>'
        )
        result = strip_quotes("fallback", body_html=html)
        assert "meeting is on Wednesday" in result
        assert "Co-Chair" not in result

    def test_normal_signature_still_removed(self):
        """Normal case: body is NOT inside signature div — still stripped."""
        html = _wrap_html(
            '<div>Please see the attached report.</div>'
            '<div class="gmail_signature">'
            '<div>John Smith</div>'
            '<div>VP of Engineering</div>'
            '<div>Tel: 555-123-4567</div>'
            '</div>'
        )
        result = strip_html_quotes(html)
        assert "Please see the attached report." in result
        assert "VP of Engineering" not in result

    def test_body_inside_smartmail_signature(self):
        """data-smartmail=gmail_signature wrapping body content."""
        html = _wrap_html(
            '<div data-smartmail="gmail_signature">'
            '<div>Quick update on the project status.</div>'
            '<div>____</div>'
            '<div>Jane Doe</div>'
            '<div>Director</div>'
            '<div>jane@example.com</div>'
            '</div>'
        )
        result = strip_quotes("fallback", body_html=html)
        assert "Quick update on the project status." in result
        assert "Director" not in result
