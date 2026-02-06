"""Tests for email quote stripping functionality."""

import pytest

from poc.email_parser import strip_quotes


class TestExistingFunctionality:
    """Regression tests for existing quote stripping behavior."""

    def test_empty_body(self):
        assert strip_quotes("") == ""
        assert strip_quotes("   ") == ""
        assert strip_quotes(None) == ""

    def test_plain_text_unchanged(self):
        body = "Hello, this is a simple message.\n\nBest regards."
        # Note: "Best regards" is a valediction but with no signature after it
        result = strip_quotes(body)
        assert "Hello, this is a simple message." in result

    def test_forwarded_message_stripped(self):
        body = """Here's the info you requested.

-- Forwarded message --
From: someone@example.com
Subject: Original message

This was the original content."""
        result = strip_quotes(body)
        assert "Here's the info you requested." in result
        assert "Forwarded message" not in result
        assert "Original message" not in result

    def test_mobile_signature_stripped(self):
        body = "Quick reply to your question.\n\nSent from my iPhone"
        result = strip_quotes(body)
        assert "Quick reply to your question." in result
        assert "Sent from my iPhone" not in result

    def test_outlook_signature_stripped(self):
        body = "Thanks for the update.\n\nGet Outlook for iOS"
        result = strip_quotes(body)
        assert "Thanks for the update." in result
        assert "Get Outlook" not in result

    def test_excessive_whitespace_cleaned(self):
        body = "First paragraph.\n\n\n\n\nSecond paragraph."
        result = strip_quotes(body)
        assert "\n\n\n" not in result
        assert "First paragraph." in result
        assert "Second paragraph." in result


class TestConfidentialityNotices:
    """Tests for confidentiality/legal disclaimer stripping."""

    def test_confidential_notice(self):
        body = """Hi John,

Please review the attached document.

Best,
Jane

Confidential Notice: This email and any attachments are confidential."""
        result = strip_quotes(body)
        assert "Please review the attached document." in result
        assert "Confidential Notice" not in result

    def test_intended_recipient(self):
        body = """Meeting confirmed for 3pm.

Thanks,
Bob

This message is intended only for the individual to whom it is addressed."""
        result = strip_quotes(body)
        assert "Meeting confirmed for 3pm." in result
        assert "intended only for" not in result

    def test_if_not_intended_recipient(self):
        body = """The report is ready.

If you are not the intended recipient, please delete this email immediately."""
        result = strip_quotes(body)
        assert "The report is ready." in result
        assert "not the intended recipient" not in result

    def test_notify_sender(self):
        body = """I'll send the files tomorrow.

Please notify the sender immediately if you received this in error."""
        result = strip_quotes(body)
        assert "I'll send the files tomorrow." in result
        assert "notify the sender" not in result

    def test_delete_this_email(self):
        body = """Thanks for the update!

If you received this by mistake, please delete this email."""
        result = strip_quotes(body)
        assert "Thanks for the update!" in result
        assert "delete this email" not in result

    def test_disclosure_prohibited(self):
        body = """See you at the meeting.

Unauthorized disclosure is strictly prohibited."""
        result = strip_quotes(body)
        assert "See you at the meeting." in result
        assert "disclosure" not in result

    def test_unauthorized_use(self):
        body = """Here's the data you requested.

Unauthorized use of this information is prohibited."""
        result = strip_quotes(body)
        assert "Here's the data you requested." in result
        assert "Unauthorized use" not in result

    def test_may_contain_confidential(self):
        body = """Project update attached.

This email may contain confidential information."""
        result = strip_quotes(body)
        assert "Project update attached." in result
        assert "may contain confidential" not in result

    def test_email_is_confidential(self):
        body = """Sending the contract now.

This e-mail and any files transmitted with it are confidential."""
        result = strip_quotes(body)
        assert "Sending the contract now." in result
        assert "are confidential" not in result

    def test_long_legal_disclaimer(self):
        body = """Quick update on the project status.

CONFIDENTIAL AND PRIVILEGED

This email message is intended only for the use of the individual or entity
to which it is addressed and may contain information that is privileged,
confidential and exempt from disclosure. If you are not the intended recipient,
please notify the sender immediately by return email. Any unauthorized review,
use, disclosure, distribution is prohibited. If you received this in error,
please delete this message and destroy any copies."""
        result = strip_quotes(body)
        assert "Quick update on the project status." in result
        assert "CONFIDENTIAL AND PRIVILEGED" not in result
        assert "intended only for the use" not in result


class TestEnvironmentalMessages:
    """Tests for environmental message stripping."""

    def test_please_consider_environment(self):
        body = """The documents are attached.

Please consider the environment before printing this email."""
        result = strip_quotes(body)
        assert "The documents are attached." in result
        assert "consider the environment" not in result

    def test_think_before_print(self):
        body = """Here's the report.

Think before you print."""
        result = strip_quotes(body)
        assert "Here's the report." in result
        assert "Think before" not in result

    def test_save_a_tree(self):
        body = """Attached is the spreadsheet.

Save a tree - don't print this email."""
        result = strip_quotes(body)
        assert "Attached is the spreadsheet." in result
        assert "Save a tree" not in result

    def test_go_green(self):
        body = """See the notes below.

Go green - avoid printing."""
        result = strip_quotes(body)
        assert "See the notes below." in result
        assert "Go green" not in result


class TestSignatureBlocks:
    """Tests for signature block stripping after valedictions."""

    def test_simple_signature_with_phone(self):
        body = """Let me know if you have questions.

Thanks,
John Smith
Tel: +1 (555) 123-4567"""
        result = strip_quotes(body)
        assert "Let me know if you have questions." in result
        assert "Tel:" not in result
        assert "John Smith" not in result

    def test_signature_with_email(self):
        body = """I'll review and get back to you.

Best regards,
Jane Doe
jane.doe@example.com"""
        result = strip_quotes(body)
        assert "I'll review and get back to you." in result
        assert "jane.doe@example.com" not in result

    def test_signature_with_title(self):
        body = """The proposal looks good.

Cheers,
Bob Wilson
Senior Engineer
Acme Corp."""
        result = strip_quotes(body)
        assert "The proposal looks good." in result
        assert "Senior Engineer" not in result
        assert "Acme Corp." not in result

    def test_signature_with_url(self):
        body = """Please review the attached.

Kind regards,
Alice Brown
www.example.com"""
        result = strip_quotes(body)
        assert "Please review the attached." in result
        assert "www.example.com" not in result

    def test_sincerely_signature(self):
        body = """Thank you for your consideration.

Sincerely,
Michael Johnson
Director of Operations
Phone: 555-987-6543"""
        result = strip_quotes(body)
        assert "Thank you for your consideration." in result
        assert "Director of Operations" not in result
        assert "Phone:" not in result

    def test_thank_you_signature(self):
        body = """I appreciate your help.

Thank you,
Sarah Lee
Manager
Mobile: +1-555-000-1234"""
        result = strip_quotes(body)
        assert "I appreciate your help." in result
        assert "Manager" not in result
        assert "Mobile:" not in result


class TestSignatureBlockEdgeCases:
    """Edge cases for signature detection to avoid false positives."""

    def test_valediction_mid_email_with_content(self):
        """Should NOT truncate when substantive content follows valediction."""
        body = """Thanks, let me know if you have questions about this.

I'll be available tomorrow for a call."""
        result = strip_quotes(body)
        assert "Thanks, let me know" in result
        assert "I'll be available tomorrow" in result

    def test_thanks_followed_by_more_discussion(self):
        """Thanks followed by actual discussion should not truncate."""
        body = """Thanks,

That said, I wanted to follow up on the budget discussion from yesterday.
We need to finalize the numbers by Friday."""
        result = strip_quotes(body)
        assert "follow up on the budget discussion" in result
        assert "finalize the numbers" in result

    def test_regards_with_follow_up_question(self):
        """Regards followed by a question should not truncate."""
        body = """Best regards,

Actually, one more thing - can you send me the updated schedule?"""
        result = strip_quotes(body)
        # This has substantive content after, should not truncate
        assert "can you send me the updated schedule" in result

    def test_short_name_only_signature(self):
        """Just a name after valediction without signature markers."""
        body = """Let me know your thoughts.

Thanks,
John"""
        result = strip_quotes(body)
        # No signature markers (phone, email, title), so keep as-is
        assert "Let me know your thoughts." in result

    def test_long_content_after_valediction(self):
        """Long content after valediction should not be truncated."""
        body = """Regards,

Here is the full project summary that you requested. The project began in
January and we've made significant progress on all fronts. The development
team has completed the core functionality and we're now in the testing phase.
We expect to launch by the end of next month."""
        result = strip_quotes(body)
        assert "project summary" in result
        assert "testing phase" in result


class TestCombinedBoilerplate:
    """Tests for emails with multiple types of boilerplate."""

    def test_signature_and_confidentiality(self):
        body = """Project update attached.

Best regards,
John Smith
VP of Engineering
Tel: 555-123-4567

CONFIDENTIAL NOTICE: This email is intended only for the addressee."""
        result = strip_quotes(body)
        assert "Project update attached." in result
        assert "VP of Engineering" not in result
        assert "CONFIDENTIAL NOTICE" not in result

    def test_mobile_signature_and_disclaimer(self):
        body = """Quick reply.

Sent from my iPhone

This email may contain confidential information."""
        result = strip_quotes(body)
        assert "Quick reply." in result
        assert "Sent from my iPhone" not in result
        assert "confidential information" not in result

    def test_environmental_and_confidentiality(self):
        body = """See attached documents.

Please consider the environment before printing this email.

This message is confidential and intended only for the recipient."""
        result = strip_quotes(body)
        assert "See attached documents." in result
        assert "environment" not in result
        assert "confidential" not in result


class TestRealWorldExamples:
    """Tests using realistic email content."""

    def test_corporate_email_full_boilerplate(self):
        body = """Hi Team,

The quarterly review meeting is scheduled for next Tuesday at 2pm in Conference Room A.
Please bring your department updates.

Best regards,
Jennifer Wilson
Chief Operating Officer
Acme Corporation
Tel: +1 (555) 999-8888
Fax: +1 (555) 999-8889
jennifer.wilson@acmecorp.com
www.acmecorp.com

CONFIDENTIALITY NOTICE: This e-mail message, including any attachments, is for
the sole use of the intended recipient(s) and may contain confidential and
privileged information. Any unauthorized review, use, disclosure or distribution
is prohibited. If you are not the intended recipient, please contact the sender
by reply e-mail and destroy all copies of the original message.

Please consider the environment before printing this email."""
        result = strip_quotes(body)
        assert "quarterly review meeting" in result
        assert "next Tuesday at 2pm" in result
        assert "Chief Operating Officer" not in result
        assert "CONFIDENTIALITY NOTICE" not in result
        assert "environment" not in result
        assert "jennifer.wilson@acmecorp.com" not in result

    def test_simple_professional_email(self):
        body = """John,

I've reviewed the proposal and have a few suggestions. Let's discuss tomorrow.

Thanks,
Mike"""
        result = strip_quotes(body)
        assert "reviewed the proposal" in result
        assert "few suggestions" in result
        # Simple name-only signature without markers stays
        assert "Mike" in result or "Thanks" in result

    def test_forwarded_with_original_disclaimer(self):
        body = """FYI - see below.

-- Forwarded message --
From: legal@company.com
Subject: Contract Update

Please review the attached contract.

This email is confidential and privileged."""
        result = strip_quotes(body)
        assert "FYI - see below." in result
        assert "Forwarded message" not in result
        assert "Contract Update" not in result
