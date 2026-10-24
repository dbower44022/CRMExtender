"""Claude API: summarize conversations and determine open/closed status.

The request is built once (:func:`build_summary_params`) and parsed once
(:func:`parse_summary_text`) so the live call and the Message Batch path
(``poc/summary_batches.py``, MAIL-49) send the same prompt and read the
answer the same way. Every live call records its token usage in
``ai_usage`` (TDD D-48)."""

from __future__ import annotations

import json
import logging
from datetime import date

import anthropic

from . import config
from .models import Conversation, ConversationStatus, ConversationSummary
from .rate_limiter import RateLimiter

log = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """\
You are an email conversation analyst working on behalf of {user_email}.
Today's date is {today}.

Given an email thread, you must:

1. Write a concise summary (2-4 sentences) of the conversation.
2. Determine the conversation status from {user_email}'s perspective:
   - OPEN: The conversation is still active. Use OPEN if ANY of these apply:
     * Someone asked a question that hasn't been answered yet.
     * There is a pending request, task, or action item that hasn't been completed.
     * A follow-up or future plan was mentioned (e.g. a visit, a meeting, sending something).
     * The last message introduces new information, shares something for review, or \
continues a discussion — even without an explicit question.
     * The conversation is between people who regularly communicate and the thread \
could naturally continue.
     Bias toward OPEN for multi-message threads between known contacts. Casual sign-offs \
like "sounds good", "talk soon", or mentioning upcoming plans are NOT closers — they \
indicate the relationship and conversation are ongoing.
   - CLOSED: The conversation is definitively finished. Use CLOSED ONLY if:
     * A specific question was asked AND fully answered with no follow-up expected.
     * Both parties explicitly said goodbye with no outstanding items.
     * It's a one-way notification with no expected reply (e.g. receipts, alerts).
   - UNCERTAIN: Not enough context to determine status confidently.
3. List any action items (things someone needs to do).
4. List key topics discussed (2-5 short phrases).

Respond ONLY with valid JSON in this exact format:
{{
  "status": "OPEN" | "CLOSED" | "UNCERTAIN",
  "summary": "...",
  "action_items": ["...", "..."],
  "key_topics": ["...", "..."]
}}"""


def _format_thread_for_prompt(conv: Conversation) -> str:
    """Format a conversation's emails into a prompt string.

    For long threads (>MAX_CONVERSATION_CHARS), include the first 2 and
    last 3 messages to preserve context and recency.
    """
    emails = conv.emails

    def format_email(em) -> str:
        date_str = em.date.strftime("%Y-%m-%d %H:%M") if em.date else "unknown date"
        body = em.body_plain or em.snippet or "(no content)"
        return f"From: {em.sender}\nDate: {date_str}\n\n{body}"

    # Try formatting all emails first
    all_formatted = [format_email(em) for em in emails]
    full_text = f"Subject: {conv.subject}\n\n" + "\n\n---\n\n".join(all_formatted)

    if len(full_text) <= config.MAX_CONVERSATION_CHARS:
        return full_text

    # Truncate: first 2 + last 3 messages
    if len(emails) <= 5:
        # If 5 or fewer, just truncate the bodies
        truncated = []
        remaining = config.MAX_CONVERSATION_CHARS
        for em in emails:
            entry = format_email(em)
            if len(entry) > remaining // len(emails):
                entry = entry[: remaining // len(emails)] + "..."
            truncated.append(entry)
        return f"Subject: {conv.subject}\n\n" + "\n\n---\n\n".join(truncated)

    first = [format_email(em) for em in emails[:2]]
    last = [format_email(em) for em in emails[-3:]]
    omitted = len(emails) - 5
    middle = f"\n[... {omitted} messages omitted for brevity ...]\n"

    text = (
        f"Subject: {conv.subject}\n\n"
        + "\n\n---\n\n".join(first)
        + middle
        + "\n\n---\n\n".join(last)
    )

    # Final safety truncation
    if len(text) > config.MAX_CONVERSATION_CHARS:
        text = text[: config.MAX_CONVERSATION_CHARS] + "\n[truncated]"

    return text

def build_summary_params(conv: Conversation, user_email: str) -> dict:
    """The Messages API parameters for one conversation summary.

    Shared by the live call and the batch request so both send the same
    prompt. Current-generation models think before answering and the
    thinking tokens count against ``max_tokens``, so the cap is well above
    the ~300-token JSON answer. Effort is low: this is routine
    summarization.
    """
    thread_text = _format_thread_for_prompt(conv)
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        user_email=user_email,
        today=date.today().isoformat(),
    )
    return {
        "model": config.CLAUDE_MODEL,
        "max_tokens": 2048,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": f"Analyze this email conversation:\n\n{thread_text}",
            }
        ],
        "output_config": {"effort": "low"},
    }


def parse_summary_text(raw_text: str, thread_id: str) -> ConversationSummary:
    """Turn the model's JSON answer into a :class:`ConversationSummary`.

    Markdown code fences are tolerated. A parse failure returns an
    UNCERTAIN summary carrying ``error`` so the caller can skip the store.
    """
    json_text = raw_text.strip()
    if json_text.startswith("```"):
        lines = json_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        json_text = "\n".join(lines)
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        log.warning("Failed to parse Claude response for thread %s: %s", thread_id, exc)
        return ConversationSummary(
            thread_id=thread_id,
            status=ConversationStatus.UNCERTAIN,
            summary="",
            error=f"JSON parse error: {exc}",
        )

    status_str = str(data.get("status", "UNCERTAIN")).upper()
    try:
        status = ConversationStatus(status_str)
    except ValueError:
        status = ConversationStatus.UNCERTAIN

    return ConversationSummary(
        thread_id=thread_id,
        status=status,
        summary=data.get("summary", ""),
        action_items=data.get("action_items", []) or [],
        key_topics=data.get("key_topics", []) or [],
    )


def response_text(content) -> str:
    """The first text block of a response; a thinking block may come first."""
    return next(
        (b.text for b in content if getattr(b, "type", "") == "text"), ""
    ).strip()


def _record_live_usage(response, conv_id: str) -> None:
    """Store the call's token usage; never lets accounting break summarization."""
    try:
        from .ai_usage import MODE_LIVE, record_usage
        from .database import get_connection

        with get_connection() as conn:
            row = conn.execute("SELECT customer_id FROM conversations WHERE id = ?", (conv_id,)).fetchone()
            customer_id = row["customer_id"] if row else None
            record_usage(
                conn, purpose="summary", mode=MODE_LIVE,
                model=getattr(response, "model", None) or config.CLAUDE_MODEL,
                usage=getattr(response, "usage", None),
                conversation_id=conv_id,
                request_id=getattr(response, "_request_id", None),
                customer_id=customer_id,
            )
    except Exception as exc:  # pragma: no cover - accounting must not block the summary
        log.warning("Could not record AI usage for thread %s: %s", conv_id, exc)


def summarize_conversation(
    conv: Conversation,
    client: anthropic.Anthropic,
    user_email: str,
    rate_limiter: RateLimiter | None = None,
) -> ConversationSummary:
    """Summarize a single conversation using Claude (live call)."""
    params = build_summary_params(conv, user_email)

    try:
        if rate_limiter:
            rate_limiter.acquire()

        # extra_body keeps output_config valid on the installed SDK.
        output_config = params.pop("output_config")
        response = client.messages.create(**params, extra_body={"output_config": output_config})
        _record_live_usage(response, conv.thread_id)
        return parse_summary_text(response_text(response.content), conv.thread_id)

    except Exception as exc:
        log.warning("Claude API error for thread %s: %s", conv.thread_id, exc)
        return ConversationSummary(
            thread_id=conv.thread_id,
            status=ConversationStatus.UNCERTAIN,
            summary="",
            error=str(exc),
        )


def summarize_all(
    conversations: list[Conversation],
    user_email: str = "",
    rate_limiter: RateLimiter | None = None,
) -> list[ConversationSummary]:
    """Summarize all conversations, skipping failures gracefully."""
    if not config.ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY not set — skipping summarization")
        return [
            ConversationSummary(
                thread_id=c.thread_id,
                status=ConversationStatus.UNCERTAIN,
                summary="(Summarization skipped — no API key)",
                error="ANTHROPIC_API_KEY not configured",
            )
            for c in conversations
        ]

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    summaries: list[ConversationSummary] = []

    for conv in conversations:
        summary = summarize_conversation(conv, client, user_email, rate_limiter)
        summaries.append(summary)

    succeeded = sum(1 for s in summaries if not s.error)
    log.info("Summarized %d/%d conversations successfully",
             succeeded, len(conversations))
    return summaries
