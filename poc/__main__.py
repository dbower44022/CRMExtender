"""CLI entry point — pipeline orchestration with multi-account support.

Usage:
    python -m poc                            # default: run all accounts
    python -m poc run                        # explicit: run all accounts
    python -m poc add-account                # add a new Gmail account
    python -m poc list-accounts              # list registered accounts
    python -m poc remove-account EMAIL       # remove an account
    python -m poc infer-relationships        # infer contact relationships
    python -m poc show-relationships         # display inferred relationships
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from . import config
from .auth import add_account_interactive, get_credentials_for_account
from .database import get_connection, init_db
from .display import display_relationships, display_results, display_triage_stats
from .gmail_client import get_user_email
from .rate_limiter import RateLimiter
from .sync import (
    get_account,
    get_all_accounts,
    incremental_sync,
    initial_sync,
    load_conversations_for_display,
    process_conversations,
    register_account,
    sync_contacts,
)

console = Console()


# ---------------------------------------------------------------------------
# Subcommand: run (default)
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> None:
    """Run sync + process for all registered accounts."""
    log = logging.getLogger(__name__)

    # Init DB
    console.print("\n[bold]Initializing database...[/bold]")
    init_db()
    console.print(f"[green]  Database ready at {config.DB_PATH}[/green]")

    # Load all accounts
    accounts = get_all_accounts()
    if not accounts:
        console.print(
            "\n[yellow]No accounts registered.[/yellow] "
            "Run [bold]python -m poc add-account[/bold] to add a Gmail account."
        )
        sys.exit(0)

    console.print(f"\n[bold]Found {len(accounts)} account(s).[/bold]")

    gmail_limiter = RateLimiter(rate=config.GMAIL_RATE_LIMIT)
    claude_limiter = RateLimiter(rate=config.CLAUDE_RATE_LIMIT)
    all_account_ids: list[str] = []

    for account in accounts:
        account_id = account["id"]
        email_addr = account["email_address"]
        all_account_ids.append(account_id)

        console.print(f"\n[bold]--- {email_addr} ---[/bold]")

        # Authenticate
        token_path = Path(account["auth_token_path"])
        try:
            creds = get_credentials_for_account(token_path)
        except Exception as exc:
            log.warning("Auth failed for %s: %s", email_addr, exc)
            console.print(f"[yellow]  Authentication failed ({exc}), skipping.[/yellow]")
            continue

        user_email = get_user_email(creds)

        # Sync contacts
        try:
            contact_count = sync_contacts(creds, rate_limiter=gmail_limiter)
            console.print(f"[green]  Synced {contact_count} contacts.[/green]")
        except Exception as exc:
            log.warning("Contact sync failed for %s: %s", email_addr, exc)
            console.print(f"[yellow]  Contact sync failed ({exc}), continuing.[/yellow]")

        # Sync emails (initial or incremental)
        if account["initial_sync_done"]:
            try:
                result = incremental_sync(account_id, creds, rate_limiter=gmail_limiter)
                console.print(
                    f"[green]  Incremental sync: {result['messages_fetched']} fetched, "
                    f"{result['messages_stored']} stored, "
                    f"{result['conversations_created']} new, "
                    f"{result['conversations_updated']} updated.[/green]"
                )
            except Exception as exc:
                log.warning("Incremental sync failed for %s: %s", email_addr, exc)
                console.print(f"[yellow]  Incremental sync failed ({exc}).[/yellow]")
        else:
            query = account["backfill_query"] or config.GMAIL_QUERY
            console.print(f"  Running initial sync (query: [cyan]{query}[/cyan])...")
            try:
                result = initial_sync(account_id, creds, rate_limiter=gmail_limiter)
                console.print(
                    f"[green]  Initial sync: {result['messages_fetched']} fetched, "
                    f"{result['messages_stored']} stored, "
                    f"{result['conversations_created']} conversations.[/green]"
                )
            except Exception as exc:
                log.warning("Initial sync failed for %s: %s", email_addr, exc)
                console.print(f"[red]  Initial sync failed ({exc}).[/red]")
                continue

        # Process conversations (triage + summarize)
        if config.ANTHROPIC_API_KEY:
            console.print(
                f"  Processing conversations (model: [cyan]{config.CLAUDE_MODEL}[/cyan])..."
            )
        else:
            console.print("  Processing conversations (triage only)...")

        try:
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
        except Exception as exc:
            log.warning("Processing failed for %s: %s", email_addr, exc)
            console.print(f"[yellow]  Processing failed ({exc}).[/yellow]")

    # Display merged results
    multi_account = len(all_account_ids) > 1
    conversations, summaries, triage_filtered = load_conversations_for_display(
        account_ids=all_account_ids,
    )

    if not conversations:
        console.print("\n[yellow]No conversations remaining after triage.[/yellow]")
        display_triage_stats(triage_filtered)
        sys.exit(0)

    display_triage_stats(triage_filtered)
    display_results(conversations, summaries, multi_account=multi_account)


# ---------------------------------------------------------------------------
# Subcommand: add-account
# ---------------------------------------------------------------------------

def cmd_add_account(args: argparse.Namespace) -> None:
    """Add a new Gmail account interactively."""
    log = logging.getLogger(__name__)

    console.print("\n[bold]Initializing database...[/bold]")
    init_db()

    console.print("[bold]Starting OAuth flow for new account...[/bold]")
    try:
        creds, email, token_path = add_account_interactive()
    except FileNotFoundError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        sys.exit(1)
    except Exception as exc:
        console.print(f"\n[red]Authentication failed:[/red] {exc}")
        sys.exit(1)

    console.print(f"[green]  Authenticated as {email}.[/green]")

    # Check if already registered
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM email_accounts WHERE email_address = ?", (email,)
        ).fetchone()

    if existing:
        console.print(f"[yellow]  Account {email} is already registered.[/yellow]")
        sys.exit(0)

    # Register
    gmail_limiter = RateLimiter(rate=config.GMAIL_RATE_LIMIT)
    account_id = register_account(creds, token_path=str(token_path))
    console.print(f"[green]  Account registered: {email}[/green]")

    # Sync contacts
    try:
        contact_count = sync_contacts(creds, rate_limiter=gmail_limiter)
        console.print(f"[green]  Synced {contact_count} contacts.[/green]")
    except Exception as exc:
        log.warning("Contact sync failed: %s", exc)
        console.print(f"[yellow]  Contact sync failed ({exc}), continuing.[/yellow]")

    # Run initial sync
    console.print("  Running initial sync...")
    try:
        result = initial_sync(account_id, creds, rate_limiter=gmail_limiter)
        console.print(
            f"[green]  Initial sync complete: {result['conversations_created']} "
            f"conversations, {result['messages_stored']} messages.[/green]"
        )
    except Exception as exc:
        console.print(f"[red]  Initial sync failed ({exc}).[/red]")
        sys.exit(1)

    console.print(f"\n[bold green]Account {email} added successfully.[/bold green]")


# ---------------------------------------------------------------------------
# Subcommand: list-accounts
# ---------------------------------------------------------------------------

def cmd_list_accounts(args: argparse.Namespace) -> None:
    """List all registered accounts."""
    init_db()
    accounts = get_all_accounts()

    if not accounts:
        console.print("\n[yellow]No accounts registered.[/yellow]")
        console.print("Run [bold]python -m poc add-account[/bold] to add one.")
        return

    table = Table(title="Registered Accounts")
    table.add_column("Email", style="bold")
    table.add_column("Provider")
    table.add_column("Last Synced")
    table.add_column("Initial Sync", justify="center")
    table.add_column("Conversations", justify="right")

    for account in accounts:
        # Count conversations for this account
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM conversations WHERE account_id = ?",
                (account["id"],),
            ).fetchone()["cnt"]

        last_synced = account["last_synced_at"] or "Never"
        if last_synced != "Never":
            # Truncate to just the date/time portion
            last_synced = last_synced[:19].replace("T", " ")

        table.add_row(
            account["email_address"],
            account["provider"],
            last_synced,
            "[green]Yes[/green]" if account["initial_sync_done"] else "[yellow]No[/yellow]",
            str(count),
        )

    console.print()
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Subcommand: remove-account
# ---------------------------------------------------------------------------

def cmd_remove_account(args: argparse.Namespace) -> None:
    """Remove an account and all its data."""
    init_db()
    email = args.email

    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, auth_token_path FROM email_accounts WHERE email_address = ?",
            (email,),
        ).fetchone()

    if not row:
        console.print(f"\n[red]Account not found:[/red] {email}")
        sys.exit(1)

    account_id = row["id"]
    token_file = row["auth_token_path"]

    # CASCADE delete removes conversations, emails, participants, topics, sync_log
    with get_connection() as conn:
        conn.execute("DELETE FROM email_accounts WHERE id = ?", (account_id,))

    # Delete token file from disk
    if token_file:
        token_path = Path(token_file)
        if token_path.exists():
            token_path.unlink()
            console.print(f"  Deleted token file: {token_path}")

    console.print(f"\n[bold green]Account {email} removed.[/bold green]")


# ---------------------------------------------------------------------------
# Subcommand: infer-relationships
# ---------------------------------------------------------------------------

def cmd_infer_relationships(args: argparse.Namespace) -> None:
    """Run the relationship inference pipeline."""
    from .relationship_inference import infer_relationships

    console.print("\n[bold]Initializing database...[/bold]")
    init_db()

    console.print("[bold]Inferring relationships from conversation co-occurrence...[/bold]")
    count = infer_relationships()
    console.print(f"\n[bold green]{count} relationship(s) upserted.[/bold green]")


# ---------------------------------------------------------------------------
# Subcommand: show-relationships
# ---------------------------------------------------------------------------

def cmd_show_relationships(args: argparse.Namespace) -> None:
    """Display inferred relationships."""
    from .relationship_inference import load_relationships

    init_db()

    # Resolve --contact email to a contact_id
    contact_id = None
    if args.contact:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM contacts WHERE email = ?",
                (args.contact.lower(),),
            ).fetchone()
        if not row:
            console.print(f"\n[red]Contact not found:[/red] {args.contact}")
            sys.exit(1)
        contact_id = row["id"]

    relationships = load_relationships(
        contact_id=contact_id,
        min_strength=args.min_strength,
    )

    # Build contact name lookup for display
    contact_ids = set()
    for rel in relationships:
        contact_ids.add(rel.from_contact_id)
        contact_ids.add(rel.to_contact_id)

    contact_names: dict[str, str] = {}
    if contact_ids:
        placeholders = ",".join("?" for _ in contact_ids)
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT id, name, email FROM contacts WHERE id IN ({placeholders})",
                list(contact_ids),
            ).fetchall()
        for row in rows:
            contact_names[row["id"]] = row["name"] or row["email"]

    display_relationships(relationships, contact_names)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m poc",
        description="Gmail Conversation Aggregation PoC",
    )
    sub = parser.add_subparsers(dest="command")

    # run (also the default when no subcommand given)
    sub.add_parser("run", help="Sync and display all accounts (default)")

    # add-account
    sub.add_parser("add-account", help="Add a new Gmail account")

    # list-accounts
    sub.add_parser("list-accounts", help="List registered accounts")

    # remove-account
    rm = sub.add_parser("remove-account", help="Remove an account")
    rm.add_argument("email", help="Email address of the account to remove")

    # infer-relationships
    sub.add_parser("infer-relationships", help="Infer contact relationships from conversations")

    # show-relationships
    sr = sub.add_parser("show-relationships", help="Display inferred relationships")
    sr.add_argument("--contact", help="Filter by contact email address")
    sr.add_argument(
        "--min-strength", type=float, default=0.0,
        help="Minimum strength threshold (0.0–1.0)",
    )

    return parser


def main() -> None:
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )

    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "run": cmd_run,
        "add-account": cmd_add_account,
        "list-accounts": cmd_list_accounts,
        "remove-account": cmd_remove_account,
        "infer-relationships": cmd_infer_relationships,
        "show-relationships": cmd_show_relationships,
    }

    # Default to "run" when no subcommand given
    command = args.command or "run"
    commands[command](args)


if __name__ == "__main__":
    main()
