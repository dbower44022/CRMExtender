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
from .database import init_db
from .display import display_results, display_triage_stats
from .gmail_client import get_user_email
from .rate_limiter import RateLimiter
from .sync import (
    get_account,
    incremental_sync,
    initial_sync,
    load_conversations_for_display,
    process_conversations,
    register_account,
    sync_contacts,
)

console = Console()


def main() -> None:
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )
    log = logging.getLogger(__name__)

    # Step 0: Initialize database
    console.print("\n[bold]Step 0:[/bold] Initializing database...")
    init_db()
    console.print(f"[green]  Database ready at {config.DB_PATH}[/green]")

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

    # Step 2: Register account and sync contacts
    console.print("\n[bold]Step 2:[/bold] Registering account and syncing contacts...")
    account_id = register_account(creds)
    account = get_account(account_id)

    try:
        contact_count = sync_contacts(creds, rate_limiter=gmail_limiter)
        console.print(f"[green]  Synced {contact_count} contacts.[/green]")
    except Exception as exc:
        log.warning("Failed to sync contacts: %s", exc)
        console.print(f"[yellow]  Contact sync failed ({exc}), continuing without contacts.[/yellow]")

    # Step 3: Sync emails (initial or incremental)
    if account and account["initial_sync_done"]:
        console.print("\n[bold]Step 3:[/bold] Running incremental sync...")
        try:
            result = incremental_sync(account_id, creds, rate_limiter=gmail_limiter)
            console.print(
                f"[green]  Incremental sync: {result['messages_fetched']} fetched, "
                f"{result['messages_stored']} stored, "
                f"{result['conversations_created']} new conversations, "
                f"{result['conversations_updated']} updated.[/green]"
            )
        except Exception as exc:
            log.warning("Incremental sync failed: %s", exc)
            console.print(f"[yellow]  Incremental sync failed ({exc}).[/yellow]")
    else:
        console.print(
            f"\n[bold]Step 3:[/bold] Running initial sync "
            f"(query: [cyan]{account['backfill_query'] if account else config.GMAIL_QUERY}[/cyan])..."
        )
        try:
            result = initial_sync(account_id, creds, rate_limiter=gmail_limiter)
            console.print(
                f"[green]  Initial sync: {result['messages_fetched']} fetched, "
                f"{result['messages_stored']} stored, "
                f"{result['conversations_created']} conversations created.[/green]"
            )
        except Exception as exc:
            console.print(f"\n[red]Initial sync failed:[/red] {exc}")
            sys.exit(1)

    # Step 4: Process conversations (triage + summarize)
    if config.ANTHROPIC_API_KEY:
        console.print(
            f"\n[bold]Step 4:[/bold] Processing conversations "
            f"(model: [cyan]{config.CLAUDE_MODEL}[/cyan])..."
        )
    else:
        console.print(
            "\n[bold]Step 4:[/bold] Processing conversations "
            "(triage only — ANTHROPIC_API_KEY not set)..."
        )

    triaged, summarized, topics = process_conversations(
        account_id, creds, user_email,
        rate_limiter=gmail_limiter,
        claude_limiter=claude_limiter,
    )
    console.print(
        f"[green]  {triaged} triaged out, "
        f"{summarized} summarized, "
        f"{topics} topics extracted.[/green]"
    )

    # Step 5: Display results
    conversations, summaries, triage_filtered = load_conversations_for_display(account_id)

    if not conversations:
        console.print("[yellow]  No conversations remaining after triage.[/yellow]")
        display_triage_stats(triage_filtered)
        sys.exit(0)

    display_triage_stats(triage_filtered)
    display_results(conversations, summaries)


if __name__ == "__main__":
    main()
