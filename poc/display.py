"""Rich terminal output for conversation summaries."""

from __future__ import annotations

from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .auto_assign import AutoAssignReport
from .models import (
    Conversation,
    ConversationStatus,
    ConversationSummary,
    FilterReason,
    KnownContact,
    ParsedEmail,
    Relationship,
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


def display_relationships(
    relationships: list[Relationship],
    contact_names: dict[str, str],
    *,
    type_names: dict[str, str] | None = None,
) -> None:
    """Display relationships in a Rich table.

    :param relationships: sorted list of Relationship objects
    :param contact_names: mapping of contact_id -> display name
    :param type_names: mapping of relationship_type_id -> type name
    """
    if not relationships:
        console.print("\n[yellow]No relationships found.[/yellow]")
        return

    console.print()
    console.rule("[bold]Relationships[/bold]")
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("From")
    table.add_column("To")
    table.add_column("Type")
    table.add_column("Source")
    table.add_column("Strength", justify="right")
    table.add_column("Shared Convos", justify="right")
    table.add_column("Shared Msgs", justify="right")
    table.add_column("Last Interaction")

    type_names = type_names or {}

    for rel in relationships:
        name_a = contact_names.get(rel.from_contact_id, rel.from_contact_id[:8])
        name_b = contact_names.get(rel.to_contact_id, rel.to_contact_id[:8])

        # Color strength: green >= 0.6, yellow >= 0.3, dim otherwise
        s = rel.strength
        if s >= 0.6:
            strength_str = f"[green]{s:.2f}[/green]"
        elif s >= 0.3:
            strength_str = f"[yellow]{s:.2f}[/yellow]"
        else:
            strength_str = f"[dim]{s:.2f}[/dim]"

        last = rel.last_interaction or ""
        if last:
            last = last[:10]  # date portion only

        type_name = type_names.get(rel.relationship_type_id, rel.relationship_type_id)
        source_str = (
            f"[cyan]{rel.source}[/cyan]" if rel.source == "inferred"
            else f"[green]{rel.source}[/green]"
        )

        table.add_row(
            name_a,
            name_b,
            type_name,
            source_str,
            strength_str,
            str(rel.shared_conversations),
            str(rel.shared_messages),
            last,
        )

    console.print(table)
    console.print(f"\n[dim]{len(relationships)} relationship(s) displayed.[/dim]")
    console.print()


def display_hierarchy(
    project_stats: list[dict],
    topic_stats_fn: Callable[[str], list[dict]],
) -> None:
    """Display the full project/topic hierarchy as a Rich Tree.

    :param project_stats: list from get_hierarchy_stats()
    :param topic_stats_fn: callable(project_id) -> list of topic stat dicts
    """
    if not project_stats:
        console.print("\n[yellow]No projects found.[/yellow]")
        console.print("Run [bold]python -m poc create-project NAME[/bold] to create one.")
        return

    # Build parent→children map for nested display
    children: dict[str | None, list[dict]] = {}
    by_id: dict[str, dict] = {}
    for p in project_stats:
        by_id[p["id"]] = p
        parent = p["parent_id"]
        children.setdefault(parent, []).append(p)

    console.print()
    console.rule("[bold]Project Hierarchy[/bold]")
    console.print()

    tree = Tree("[bold]Projects[/bold]")

    def _add_project(parent_node, proj: dict) -> None:
        label = f"[bold]{proj['name']}[/bold]"
        if proj.get("description"):
            label += f"  [dim]{proj['description']}[/dim]"
        label += (
            f"  [cyan]{proj['topic_count']} topic(s)[/cyan]"
            f", [green]{proj['conversation_count']} conversation(s)[/green]"
        )
        node = parent_node.add(label)

        # Add topics under this project
        topics = topic_stats_fn(proj["id"])
        for t in topics:
            t_label = f"{t['name']}"
            if t.get("description"):
                t_label += f"  [dim]{t['description']}[/dim]"
            t_label += f"  [green]{t['conversation_count']} conversation(s)[/green]"
            node.add(t_label)

        # Add child projects
        for child in children.get(proj["id"], []):
            _add_project(node, child)

    # Start from root projects (parent_id IS NULL)
    for proj in children.get(None, []):
        _add_project(tree, proj)

    console.print(tree)
    console.print()


def display_project_detail(project: dict, topic_stats: list[dict]) -> None:
    """Display a single project's topics in a Rich Table.

    :param project: project row dict
    :param topic_stats: list from get_topic_stats()
    """
    console.print()
    title = f"Project: {project['name']}"
    if project.get("description"):
        title += f"  —  {project['description']}"
    console.rule(f"[bold]{title}[/bold]")
    console.print()

    if not topic_stats:
        console.print("[yellow]No topics in this project.[/yellow]")
        console.print(
            f"Run [bold]python -m poc create-topic \"{project['name']}\" NAME[/bold] "
            "to create one."
        )
        console.print()
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Topic")
    table.add_column("Description")
    table.add_column("Conversations", justify="right")

    for t in topic_stats:
        table.add_row(
            t["name"],
            t.get("description") or "",
            str(t["conversation_count"]),
        )

    console.print(table)
    total = sum(t["conversation_count"] for t in topic_stats)
    console.print(
        f"\n[dim]{len(topic_stats)} topic(s), {total} conversation(s) assigned.[/dim]"
    )
    console.print()


def display_auto_assign_report(report: AutoAssignReport, *, dry_run: bool = False) -> None:
    """Display the results of an auto-assign run.

    :param report: AutoAssignReport from find_matching_topics()
    :param dry_run: if True, labels output as a preview
    """
    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]APPLIED[/green]"

    console.print()
    console.rule(f"[bold]Auto-Assign: {report.project_name}[/bold]  ({mode})")
    console.print()

    # Summary stats
    stats = Table(show_header=False, box=None, padding=(0, 2))
    stats.add_column(style="bold")
    stats.add_column(justify="right")
    stats.add_row("Candidates:", str(report.total_candidates))
    stats.add_row("Matched:", f"[green]{report.matched}[/green]")
    stats.add_row("Unmatched:", f"[dim]{report.unmatched}[/dim]")
    console.print(stats)
    console.print()

    if not report.assignments:
        console.print("[yellow]No matches found.[/yellow]")
        console.print()
        return

    # Assignments table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Topic")
    table.add_column("Conversation", max_width=50, no_wrap=True)
    table.add_column("Score", justify="right")
    table.add_column("Matched Tags")
    table.add_column("Title", justify="center")

    for m in sorted(report.assignments, key=lambda x: (-x.score, x.topic_name)):
        title_str = "[green]Y[/green]" if m.title_matched else "[dim]-[/dim]"
        tags_str = ", ".join(m.matched_tags) if m.matched_tags else "[dim]-[/dim]"
        conv_display = m.conversation_title[:50] if m.conversation_title else "[dim](no title)[/dim]"
        table.add_row(
            m.topic_name,
            conv_display,
            str(m.score),
            tags_str,
            title_str,
        )

    console.print(table)
    console.print(
        f"\n[dim]{report.matched} conversation(s) "
        f"{'would be assigned' if dry_run else 'assigned'}.[/dim]"
    )
    console.print()
