"""CLI entry point — pipeline orchestration.

Usage:
    python -m poc
"""

from __future__ import annotations

import logging
import sys

from rich.console import Console
from rich.logging import RichHandler

from . import config
from .auth import get_credentials
from .contact_matcher import build_contact_index, match_contacts
from .contacts_client import fetch_contacts
from .conversation_builder import build_conversations
from .display import display_results, display_triage_stats
from .gmail_client import fetch_threads, get_user_email
from .rate_limiter import RateLimiter
from .summarizer import summarize_all
from .triage import triage_conversations

console = Console()


def main() -> None:
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )
    log = logging.getLogger(__name__)

    # Step 1: Authenticate
    console.print("\n[bold]Step 1:[/bold] Authenticating with Google...")
    try:
        creds = get_credentials()
    except FileNotFoundError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        sys.exit(1)
    except Exception as exc:
        console.print(f"\n[red]Authentication failed:[/red] {exc}")
        sys.exit(1)
    user_email = get_user_email(creds)
    console.print(f"[green]  Authenticated as {user_email}.[/green]")

    # Rate limiters
    gmail_limiter = RateLimiter(rate=config.GMAIL_RATE_LIMIT)
    claude_limiter = RateLimiter(rate=config.CLAUDE_RATE_LIMIT)

    # Step 2: Fetch contacts
    console.print("\n[bold]Step 2:[/bold] Fetching contacts from Google People API...")
    try:
        contacts = fetch_contacts(creds, rate_limiter=gmail_limiter)
        console.print(f"[green]  Loaded {len(contacts)} contacts.[/green]")
    except Exception as exc:
        log.warning("Failed to fetch contacts: %s", exc)
        console.print(f"[yellow]  Contact fetch failed ({exc}), continuing without contacts.[/yellow]")
        contacts = []

    contact_index = build_contact_index(contacts)

    # Step 3: Fetch Gmail threads
    console.print(
        f"\n[bold]Step 3:[/bold] Fetching Gmail threads "
        f"(query: [cyan]{config.GMAIL_QUERY}[/cyan], "
        f"max: {config.GMAIL_MAX_THREADS})..."
    )
    try:
        threads = fetch_threads(
            creds,
            query=config.GMAIL_QUERY,
            max_threads=config.GMAIL_MAX_THREADS,
            rate_limiter=gmail_limiter,
        )
    except Exception as exc:
        console.print(f"\n[red]Failed to fetch emails:[/red] {exc}")
        sys.exit(1)

    if not threads:
        console.print("[yellow]  No threads found matching the query.[/yellow]")
        sys.exit(0)

    console.print(
        f"[green]  Found {len(threads)} threads with "
        f"{sum(len(t) for t in threads)} total messages.[/green]"
    )

    # Step 4: Build conversations
    console.print("\n[bold]Step 4:[/bold] Processing conversations...")
    conversations = build_conversations(threads)

    # Step 5: Match contacts
    match_contacts(conversations, contact_index)
    matched_count = sum(len(c.matched_contacts) for c in conversations)
    console.print(
        f"[green]  Built {len(conversations)} conversations, "
        f"matched {matched_count} participants to contacts.[/green]"
    )

    # Step 6: Triage — filter junk / non-contact threads
    console.print("\n[bold]Step 6:[/bold] Triaging conversations...")
    conversations, triage_filtered = triage_conversations(conversations, user_email)
    console.print(
        f"[green]  Kept {len(conversations)} conversations, "
        f"filtered {len(triage_filtered)}.[/green]"
    )

    if not conversations:
        console.print("[yellow]  No conversations remaining after triage.[/yellow]")
        display_triage_stats(triage_filtered)
        sys.exit(0)

    # Step 7: Summarize with Claude
    if config.ANTHROPIC_API_KEY:
        console.print(
            f"\n[bold]Step 7:[/bold] Summarizing conversations with Claude "
            f"(model: [cyan]{config.CLAUDE_MODEL}[/cyan])..."
        )
        summaries = summarize_all(conversations, rate_limiter=claude_limiter)
        succeeded = sum(1 for s in summaries if not s.error)
        console.print(
            f"[green]  Summarized {succeeded}/{len(conversations)} conversations.[/green]"
        )
    else:
        console.print(
            "\n[yellow]Step 7:[/yellow] ANTHROPIC_API_KEY not set — "
            "skipping summarization."
        )
        summaries = summarize_all(conversations)

    # Step 8: Display results
    display_triage_stats(triage_filtered)
    display_results(conversations, summaries)


if __name__ == "__main__":
    main()
