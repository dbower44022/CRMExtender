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

    # Step 3: Fetch, build, and triage in batches until target met
    target = config.TARGET_CONVERSATIONS
    console.print(
        f"\n[bold]Step 3:[/bold] Searching for {target} conversations "
        f"(query: [cyan]{config.GMAIL_QUERY}[/cyan], "
        f"batch size: {config.GMAIL_MAX_THREADS})..."
    )

    conversations = []
    triage_filtered = []
    page_token = None
    total_threads = 0
    batch_num = 0

    while len(conversations) < target:
        batch_num += 1
        try:
            threads, page_token = fetch_threads(
                creds,
                query=config.GMAIL_QUERY,
                max_threads=config.GMAIL_MAX_THREADS,
                rate_limiter=gmail_limiter,
                page_token=page_token,
            )
        except Exception as exc:
            console.print(f"\n[red]Failed to fetch emails:[/red] {exc}")
            sys.exit(1)

        if not threads:
            if batch_num == 1:
                console.print("[yellow]  No threads found matching the query.[/yellow]")
                sys.exit(0)
            break

        total_threads += len(threads)
        batch_msgs = sum(len(t) for t in threads)
        console.print(
            f"  Batch {batch_num}: {len(threads)} threads "
            f"({batch_msgs} messages)..."
        )

        batch_convs = build_conversations(threads)
        match_contacts(batch_convs, contact_index)
        kept, filtered = triage_conversations(batch_convs, user_email)
        conversations.extend(kept)
        triage_filtered.extend(filtered)

        console.print(
            f"  [green]{len(kept)} kept[/green], "
            f"{len(filtered)} filtered — "
            f"[bold]{len(conversations)}[/bold]/{target} conversations so far"
        )

        if not page_token:
            break

    # Trim to target if we overshot
    conversations = conversations[:target]

    console.print(
        f"\n[green]  Located {len(conversations)} conversations "
        f"from {total_threads} threads searched.[/green]"
    )

    if not conversations:
        console.print("[yellow]  No conversations remaining after triage.[/yellow]")
        display_triage_stats(triage_filtered)
        sys.exit(0)

    # Step 4: Summarize with Claude
    if config.ANTHROPIC_API_KEY:
        console.print(
            f"\n[bold]Step 4:[/bold] Summarizing conversations with Claude "
            f"(model: [cyan]{config.CLAUDE_MODEL}[/cyan])..."
        )
        summaries = summarize_all(conversations, user_email=user_email, rate_limiter=claude_limiter)
        succeeded = sum(1 for s in summaries if not s.error)
        console.print(
            f"[green]  Summarized {succeeded}/{len(conversations)} conversations.[/green]"
        )
    else:
        console.print(
            "\n[yellow]Step 4:[/yellow] ANTHROPIC_API_KEY not set — "
            "skipping summarization."
        )
        summaries = summarize_all(conversations, user_email=user_email)

    # Step 5: Display results
    display_triage_stats(triage_filtered)
    display_results(conversations, summaries)


if __name__ == "__main__":
    main()
