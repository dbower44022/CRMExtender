"""Rich terminal output for conversation summaries."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import (
    Conversation,
    ConversationStatus,
    ConversationSummary,
    FilterReason,
    KnownContact,
    ParsedEmail,
    TriageResult,
)

console = Console()

_STATUS_COLORS = {
    ConversationStatus.OPEN: "red",
    ConversationStatus.CLOSED: "green",
    ConversationStatus.UNCERTAIN: "yellow",
}

_STATUS_EMOJI = {
    ConversationStatus.OPEN: "[red]OPEN[/red]",
    ConversationStatus.CLOSED: "[green]CLOSED[/green]",
    ConversationStatus.UNCERTAIN: "[yellow]UNCERTAIN[/yellow]",
}


def _format_sender_name(email: ParsedEmail, contacts: dict[str, KnownContact]) -> str:
    """Resolve display name: prefer matched contact, fall back to sender field."""
    contact = contacts.get(email.sender_email.lower())
    if contact and contact.name:
        return contact.name
    # sender field is like "Paul Charles McMillian <paul@...>" — use the name part
    if email.sender and "<" in email.sender:
        return email.sender.split("<")[0].strip()
    return email.sender or email.sender_email


def _format_participant(email: str, contacts: dict[str, KnownContact]) -> str:
    """Format a participant, showing contact name if matched."""
    contact = contacts.get(email.lower())
    if contact and contact.name:
        return f"{contact.name} ({email})"
    return email


def display_triage_stats(filtered: list[TriageResult]) -> None:
    """Display a summary table of triage-filtered threads."""
    if not filtered:
        return

    counts: dict[FilterReason, int] = {}
    for result in filtered:
        counts[result.reason] = counts.get(result.reason, 0) + 1

    console.print()
    console.rule("[bold]Triage Filter Results[/bold]")
    console.print()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold")
    table.add_column(justify="right")

    table.add_row("Filtered:", f"[dim]{len(filtered)} threads[/dim]")
    for reason in FilterReason:
        count = counts.get(reason, 0)
        if count:
            table.add_row(f"  {reason.value}:", str(count))

    console.print(table)
    console.print()


def display_results(
    conversations: list[Conversation],
    summaries: list[ConversationSummary],
    *,
    multi_account: bool = False,
) -> None:
    """Display conversation summaries grouped by status using Rich."""
    # Build lookup from thread_id to summary and conversation
    summary_map = {s.thread_id: s for s in summaries}
    conv_map = {c.thread_id: c for c in conversations}

    # Group by status
    grouped: dict[ConversationStatus, list[tuple[Conversation, ConversationSummary]]] = {
        ConversationStatus.OPEN: [],
        ConversationStatus.CLOSED: [],
        ConversationStatus.UNCERTAIN: [],
    }

    for conv in conversations:
        summary = summary_map.get(conv.thread_id)
        if summary:
            grouped[summary.status].append((conv, summary))

    # Display header
    console.print()
    console.rule("[bold]Gmail Conversation Summary[/bold]")
    console.print()

    # Statistics
    stats = Table(show_header=False, box=None, padding=(0, 2))
    stats.add_column(style="bold")
    stats.add_column()
    if multi_account:
        distinct_emails = sorted({c.account_email for c in conversations if c.account_email})
        if distinct_emails:
            stats.add_row("Accounts:", ", ".join(distinct_emails))
    stats.add_row("Total conversations:", str(len(conversations)))
    stats.add_row("Open:", f"[red]{len(grouped[ConversationStatus.OPEN])}[/red]")
    stats.add_row("Closed:", f"[green]{len(grouped[ConversationStatus.CLOSED])}[/green]")
    stats.add_row("Uncertain:", f"[yellow]{len(grouped[ConversationStatus.UNCERTAIN])}[/yellow]")
    errors = sum(1 for s in summaries if s.error)
    if errors:
        stats.add_row("Errors:", f"[red]{errors}[/red]")
    console.print(stats)
    console.print()

    # Display each status group
    for status in (ConversationStatus.OPEN, ConversationStatus.CLOSED, ConversationStatus.UNCERTAIN):
        items = grouped[status]
        if not items:
            continue

        color = _STATUS_COLORS[status]
        console.rule(f"[bold {color}]{status.value} Conversations ({len(items)})[/bold {color}]")
        console.print()

        for conv, summary in items:
            _display_conversation(conv, summary, color, multi_account=multi_account)


def _display_conversation(
    conv: Conversation,
    summary: ConversationSummary,
    color: str,
    *,
    multi_account: bool = False,
) -> None:
    """Display a single conversation panel."""
    first_date, last_date = conv.date_range
    date_range = ""
    if first_date and last_date:
        if first_date.date() == last_date.date():
            date_range = first_date.strftime("%Y-%m-%d")
        else:
            date_range = f"{first_date.strftime('%Y-%m-%d')} to {last_date.strftime('%Y-%m-%d')}"

    # Build content
    lines: list[str] = []

    if summary.summary:
        lines.append(f"[bold]Summary:[/bold] {summary.summary}")
        lines.append("")

    # Participants
    participant_strs = [
        _format_participant(p, conv.matched_contacts)
        for p in conv.participants
    ]
    if participant_strs:
        lines.append(f"[bold]Participants:[/bold] {', '.join(participant_strs)}")

    lines.append(f"[bold]Messages:[/bold] {conv.message_count}")

    if date_range:
        lines.append(f"[bold]Date range:[/bold] {date_range}")

    # Action items
    if summary.action_items:
        lines.append("")
        lines.append("[bold]Action items:[/bold]")
        for item in summary.action_items:
            lines.append(f"  - {item}")

    # Key topics
    if summary.key_topics:
        lines.append("")
        lines.append(f"[bold]Topics:[/bold] {', '.join(summary.key_topics)}")

    # Error note
    if summary.error:
        lines.append("")
        lines.append(f"[dim red]Error: {summary.error}[/dim red]")

    # Conversation details — full email text
    if conv.emails:
        lines.append("")
        lines.append("[dim]────────── [/dim][bold]Conversation[/bold][dim] ──────────[/dim]")
        for email in conv.emails:
            lines.append("")
            date_str = email.date.strftime("%b %d %H:%M") if email.date else "Unknown"
            sender_name = _format_sender_name(email, conv.matched_contacts)
            lines.append(f"[dim]{date_str}  {sender_name}[/dim]")
            if email.body_plain:
                for body_line in email.body_plain.splitlines():
                    lines.append(f"  {body_line}")

    title = f"[{color}]{_STATUS_EMOJI[summary.status]}[/{color}]  {conv.subject}"
    if multi_account and conv.account_email:
        title += f"  [dim]({conv.account_email})[/dim]"
    panel = Panel(
        "\n".join(lines),
        title=title,
        title_align="left",
        border_style=color,
        padding=(1, 2),
    )
    console.print(panel)
    console.print()
