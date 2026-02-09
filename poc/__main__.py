"""CLI entry point — pipeline orchestration with multi-account support.

Usage:
    python -m poc                            # default: run all accounts
    python -m poc run                        # explicit: run all accounts
    python -m poc serve                      # launch web UI
    python -m poc add-account                # add a new Gmail account
    python -m poc list-accounts              # list registered accounts
    python -m poc remove-account EMAIL       # remove an account
    python -m poc infer-relationships        # infer contact relationships
    python -m poc show-relationships         # display inferred relationships
    python -m poc auto-assign PROJECT        # bulk assign conversations to topics
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
from .database import get_connection, init_db
from .display import (
    display_auto_assign_report,
    display_hierarchy,
    display_project_detail,
    display_relationships,
    display_results,
    display_triage_stats,
)

console = Console()


# ---------------------------------------------------------------------------
# Subcommand: run (default)
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> None:
    """Run sync + process for all registered accounts."""
    from .auth import get_credentials_for_account
    from .gmail_client import get_user_email
    from .rate_limiter import RateLimiter
    from .sync import (
        get_all_accounts,
        incremental_sync,
        initial_sync,
        load_conversations_for_display,
        process_conversations,
        sync_contacts,
    )

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
    from .auth import add_account_interactive
    from .rate_limiter import RateLimiter
    from .sync import initial_sync, register_account, sync_contacts

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
            "SELECT id FROM provider_accounts WHERE email_address = ?", (email,)
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
    from .sync import get_all_accounts

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
        # Count conversations for this account (via communications join)
        with get_connection() as conn:
            count = conn.execute(
                """SELECT COUNT(DISTINCT cc.conversation_id) as cnt
                   FROM conversation_communications cc
                   JOIN communications comm ON comm.id = cc.communication_id
                   WHERE comm.account_id = ?""",
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
            "SELECT id, auth_token_path FROM provider_accounts WHERE email_address = ?",
            (email,),
        ).fetchone()

    if not row:
        console.print(f"\n[red]Account not found:[/red] {email}")
        sys.exit(1)

    account_id = row["id"]
    token_file = row["auth_token_path"]

    # SET NULL on communications preserves them; CASCADE removes sync_log
    with get_connection() as conn:
        conn.execute("DELETE FROM provider_accounts WHERE id = ?", (account_id,))

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
    """Display relationships."""
    from .relationship_inference import load_relationships

    init_db()

    # Resolve --contact email to a contact_id via contact_identifiers
    contact_id = None
    if args.contact:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT contact_id FROM contact_identifiers WHERE type = 'email' AND value = ?",
                (args.contact.lower(),),
            ).fetchone()
        if not row:
            console.print(f"\n[red]Contact not found:[/red] {args.contact}")
            sys.exit(1)
        contact_id = row["contact_id"]

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
    type_names: dict[str, str] = {}
    with get_connection() as conn:
        if contact_ids:
            placeholders = ",".join("?" for _ in contact_ids)
            rows = conn.execute(
                f"""SELECT c.id, c.name, ci.value AS email
                    FROM contacts c
                    LEFT JOIN contact_identifiers ci ON ci.contact_id = c.id AND ci.type = 'email'
                    WHERE c.id IN ({placeholders})""",
                list(contact_ids),
            ).fetchall()
            for row in rows:
                contact_names[row["id"]] = row["name"] or row["email"] or row["id"][:8]

        # Build type name lookup
        for row in conn.execute("SELECT id, name FROM relationship_types").fetchall():
            type_names[row["id"]] = row["name"]

    display_relationships(relationships, contact_names, type_names=type_names)


# ---------------------------------------------------------------------------
# Subcommand: bootstrap-user
# ---------------------------------------------------------------------------

def cmd_bootstrap_user(args: argparse.Namespace) -> None:
    """Auto-create a user from the first provider account."""
    from .hierarchy import bootstrap_user

    init_db()
    try:
        result = bootstrap_user()
    except ValueError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        sys.exit(1)

    if result["created"]:
        console.print(f"\n[bold green]User created:[/bold green] {result['email']}")
    else:
        console.print(f"\n[yellow]User already exists:[/yellow] {result['email']}")


# ---------------------------------------------------------------------------
# Subcommand: create-company
# ---------------------------------------------------------------------------

def cmd_create_company(args: argparse.Namespace) -> None:
    """Create a new company."""
    from .hierarchy import create_company

    init_db()
    try:
        row = create_company(
            args.name,
            domain=args.domain or "",
            industry=args.industry or "",
            description=args.description or "",
        )
    except ValueError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        sys.exit(1)

    console.print(f"\n[bold green]Company created:[/bold green] {row['name']}")
    if row.get("domain"):
        console.print(f"  Domain: {row['domain']}")


# ---------------------------------------------------------------------------
# Subcommand: list-companies
# ---------------------------------------------------------------------------

def cmd_list_companies(args: argparse.Namespace) -> None:
    """List all companies."""
    from .hierarchy import list_companies

    init_db()
    companies = list_companies()

    if not companies:
        console.print("\n[yellow]No companies found.[/yellow]")
        return

    table = Table(title="Companies")
    table.add_column("Name", style="bold")
    table.add_column("Domain")
    table.add_column("Industry")
    table.add_column("Status")

    for c in companies:
        table.add_row(
            c["name"],
            c.get("domain") or "",
            c.get("industry") or "",
            c.get("status") or "active",
        )

    console.print()
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Subcommand: delete-company
# ---------------------------------------------------------------------------

def cmd_delete_company(args: argparse.Namespace) -> None:
    """Delete a company."""
    from .hierarchy import delete_company, find_company_by_name

    init_db()
    company = find_company_by_name(args.name)
    if not company:
        console.print(f"\n[red]Company not found:[/red] {args.name}")
        sys.exit(1)

    impact = delete_company(company["id"])
    console.print(f"\n[bold green]Deleted company:[/bold green] {args.name}")
    console.print(f"  Contacts unlinked: {impact['contacts_unlinked']}")


# ---------------------------------------------------------------------------
# Subcommand: create-project
# ---------------------------------------------------------------------------

def cmd_create_project(args: argparse.Namespace) -> None:
    """Create a new project."""
    from .hierarchy import create_project, get_current_user

    init_db()
    user = get_current_user()
    owner_id = user["id"] if user else None

    try:
        row = create_project(
            name=args.name,
            description=args.description or "",
            parent_name=args.parent,
            owner_id=owner_id,
        )
    except ValueError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        sys.exit(1)

    console.print(f"\n[bold green]Project created:[/bold green] {row['name']}")
    if row["parent_id"]:
        console.print(f"  Parent: {args.parent}")


# ---------------------------------------------------------------------------
# Subcommand: list-projects
# ---------------------------------------------------------------------------

def cmd_list_projects(args: argparse.Namespace) -> None:
    """List all projects as a tree."""
    from .hierarchy import get_hierarchy_stats, get_topic_stats

    init_db()
    stats = get_hierarchy_stats()
    display_hierarchy(stats, get_topic_stats)


# ---------------------------------------------------------------------------
# Subcommand: show-project
# ---------------------------------------------------------------------------

def cmd_show_project(args: argparse.Namespace) -> None:
    """Show a project's topics and stats."""
    from .hierarchy import find_project_by_name, get_topic_stats

    init_db()
    project = find_project_by_name(args.name)
    if not project:
        console.print(f"\n[red]Project not found:[/red] {args.name}")
        sys.exit(1)

    topic_stats = get_topic_stats(project["id"])
    display_project_detail(project, topic_stats)


# ---------------------------------------------------------------------------
# Subcommand: delete-project
# ---------------------------------------------------------------------------

def cmd_delete_project(args: argparse.Namespace) -> None:
    """Delete a project and its topics."""
    from .hierarchy import delete_project, find_project_by_name

    init_db()
    project = find_project_by_name(args.name)
    if not project:
        console.print(f"\n[red]Project not found:[/red] {args.name}")
        sys.exit(1)

    impact = delete_project(project["id"])
    console.print(f"\n[bold green]Deleted project:[/bold green] {args.name}")
    console.print(f"  Topics removed: {impact['topics_removed']}")
    console.print(f"  Conversations unassigned: {impact['conversations_unassigned']}")


# ---------------------------------------------------------------------------
# Subcommand: create-topic
# ---------------------------------------------------------------------------

def cmd_create_topic(args: argparse.Namespace) -> None:
    """Create a topic within a project."""
    from .hierarchy import create_topic, find_project_by_name

    init_db()
    project = find_project_by_name(args.project)
    if not project:
        console.print(f"\n[red]Project not found:[/red] {args.project}")
        sys.exit(1)

    try:
        row = create_topic(
            project_id=project["id"],
            name=args.name,
            description=args.description or "",
        )
    except ValueError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        sys.exit(1)

    console.print(
        f"\n[bold green]Topic created:[/bold green] {row['name']} "
        f"(in {args.project})"
    )


# ---------------------------------------------------------------------------
# Subcommand: list-topics
# ---------------------------------------------------------------------------

def cmd_list_topics(args: argparse.Namespace) -> None:
    """List topics in a project."""
    from .hierarchy import find_project_by_name, get_topic_stats

    init_db()
    project = find_project_by_name(args.project)
    if not project:
        console.print(f"\n[red]Project not found:[/red] {args.project}")
        sys.exit(1)

    topic_stats = get_topic_stats(project["id"])
    display_project_detail(project, topic_stats)


# ---------------------------------------------------------------------------
# Subcommand: delete-topic
# ---------------------------------------------------------------------------

def cmd_delete_topic(args: argparse.Namespace) -> None:
    """Delete a topic from a project."""
    from .hierarchy import delete_topic, find_project_by_name, find_topic_by_name

    init_db()
    project = find_project_by_name(args.project)
    if not project:
        console.print(f"\n[red]Project not found:[/red] {args.project}")
        sys.exit(1)

    topic = find_topic_by_name(project["id"], args.topic)
    if not topic:
        console.print(f"\n[red]Topic not found:[/red] {args.topic} (in {args.project})")
        sys.exit(1)

    impact = delete_topic(topic["id"])
    console.print(f"\n[bold green]Deleted topic:[/bold green] {args.topic}")
    console.print(f"  Conversations unassigned: {impact['conversations_unassigned']}")


# ---------------------------------------------------------------------------
# Subcommand: assign-topic
# ---------------------------------------------------------------------------

def cmd_assign_topic(args: argparse.Namespace) -> None:
    """Assign a conversation to a topic."""
    from .hierarchy import (
        assign_conversation_to_topic,
        find_project_by_name,
        find_topic_by_name,
        resolve_conversation_by_prefix,
    )

    init_db()
    try:
        conv_id = resolve_conversation_by_prefix(args.conversation)
    except ValueError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        sys.exit(1)

    project = find_project_by_name(args.project)
    if not project:
        console.print(f"\n[red]Project not found:[/red] {args.project}")
        sys.exit(1)

    topic = find_topic_by_name(project["id"], args.topic)
    if not topic:
        console.print(f"\n[red]Topic not found:[/red] {args.topic} (in {args.project})")
        sys.exit(1)

    try:
        assign_conversation_to_topic(conv_id, topic["id"])
    except ValueError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        sys.exit(1)

    console.print(
        f"\n[bold green]Assigned[/bold green] conversation {conv_id[:8]}... "
        f"to {args.topic} (in {args.project})"
    )


# ---------------------------------------------------------------------------
# Subcommand: unassign-topic
# ---------------------------------------------------------------------------

def cmd_unassign_topic(args: argparse.Namespace) -> None:
    """Clear topic assignment from a conversation."""
    from .hierarchy import resolve_conversation_by_prefix, unassign_conversation

    init_db()
    try:
        conv_id = resolve_conversation_by_prefix(args.conversation)
    except ValueError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        sys.exit(1)

    try:
        unassign_conversation(conv_id)
    except ValueError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        sys.exit(1)

    console.print(
        f"\n[bold green]Unassigned[/bold green] conversation {conv_id[:8]}... from its topic."
    )


# ---------------------------------------------------------------------------
# Subcommand: auto-assign
# ---------------------------------------------------------------------------

def cmd_auto_assign(args: argparse.Namespace) -> None:
    """Bulk auto-assign conversations to topics by tag/title matching."""
    from .auto_assign import apply_assignments, find_matching_topics
    from .hierarchy import find_project_by_name

    init_db()
    project = find_project_by_name(args.project)
    if not project:
        console.print(f"\n[red]Project not found:[/red] {args.project}")
        sys.exit(1)

    try:
        report = find_matching_topics(
            project["id"],
            include_triaged=args.include_triaged,
        )
    except ValueError as exc:
        console.print(f"\n[red]Error:[/red] {exc}")
        sys.exit(1)

    display_auto_assign_report(report, dry_run=args.dry_run)

    if not args.dry_run and report.assignments:
        count = apply_assignments(report.assignments)
        console.print(f"[bold green]{count} conversation(s) assigned.[/bold green]")


# ---------------------------------------------------------------------------
# Subcommand: serve
# ---------------------------------------------------------------------------

def cmd_list_relationship_types(args: argparse.Namespace) -> None:
    """List all relationship types."""
    from .relationship_types import list_relationship_types

    init_db()
    types = list_relationship_types()

    if not types:
        console.print("\n[yellow]No relationship types found.[/yellow]")
        return

    table = Table(title="Relationship Types")
    table.add_column("Name", style="bold")
    table.add_column("From")
    table.add_column("To")
    table.add_column("Forward Label")
    table.add_column("Reverse Label")
    table.add_column("System", justify="center")

    for t in types:
        table.add_row(
            t["name"],
            t["from_entity_type"],
            t["to_entity_type"],
            t["forward_label"],
            t["reverse_label"],
            "[green]Yes[/green]" if t["is_system"] else "[dim]No[/dim]",
        )

    console.print()
    console.print(table)
    console.print()


def cmd_migrate_to_v4(args: argparse.Namespace) -> None:
    """Run the v3 -> v4 migration."""
    from .migrate_to_v4 import migrate

    db_path = args.db
    if not db_path:
        db_path = config.DB_PATH

    migrate(db_path, dry_run=args.dry_run)


def cmd_serve(args: argparse.Namespace) -> None:
    """Launch the web UI."""
    import uvicorn

    from .web.app import create_app

    app = create_app()
    console.print(f"\n[bold]Starting web UI at http://{args.host}:{args.port}[/bold]")
    uvicorn.run(app, host=args.host, port=args.port)


# ---------------------------------------------------------------------------
# Subcommand: show-hierarchy
# ---------------------------------------------------------------------------

def cmd_show_hierarchy(args: argparse.Namespace) -> None:
    """Show the full project/topic/conversation hierarchy."""
    from .hierarchy import get_hierarchy_stats, get_topic_stats

    init_db()
    stats = get_hierarchy_stats()
    display_hierarchy(stats, get_topic_stats)


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

    # serve
    sv = sub.add_parser("serve", help="Launch web UI")
    sv.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    sv.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")

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

    # bootstrap-user
    sub.add_parser("bootstrap-user", help="Auto-create user from provider account")

    # create-company
    cc = sub.add_parser("create-company", help="Create a new company")
    cc.add_argument("name", help="Company name")
    cc.add_argument("--domain", help="Company domain (e.g. acme.com)")
    cc.add_argument("--industry", help="Industry")
    cc.add_argument("--description", help="Company description")

    # list-companies
    sub.add_parser("list-companies", help="List all companies")

    # delete-company
    dc = sub.add_parser("delete-company", help="Delete a company")
    dc.add_argument("name", help="Company name")

    # create-project
    cp = sub.add_parser("create-project", help="Create a new project")
    cp.add_argument("name", help="Project name")
    cp.add_argument("--parent", help="Parent project name (for nesting)")
    cp.add_argument("--description", help="Project description")

    # list-projects
    sub.add_parser("list-projects", help="List all projects as a tree")

    # show-project
    sp = sub.add_parser("show-project", help="Show project detail with topics")
    sp.add_argument("name", help="Project name")

    # delete-project
    dp = sub.add_parser("delete-project", help="Delete a project")
    dp.add_argument("name", help="Project name")

    # create-topic
    ct = sub.add_parser("create-topic", help="Create a topic in a project")
    ct.add_argument("project", help="Project name")
    ct.add_argument("name", help="Topic name")
    ct.add_argument("--description", help="Topic description")

    # list-topics
    lt = sub.add_parser("list-topics", help="List topics in a project")
    lt.add_argument("project", help="Project name")

    # delete-topic
    dt = sub.add_parser("delete-topic", help="Delete a topic from a project")
    dt.add_argument("project", help="Project name")
    dt.add_argument("topic", help="Topic name")

    # assign-topic
    at = sub.add_parser("assign-topic", help="Assign a conversation to a topic")
    at.add_argument("conversation", help="Conversation ID or prefix")
    at.add_argument("project", help="Project name")
    at.add_argument("topic", help="Topic name")

    # unassign-topic
    ut = sub.add_parser("unassign-topic", help="Clear topic from a conversation")
    ut.add_argument("conversation", help="Conversation ID or prefix")

    # auto-assign
    aa = sub.add_parser("auto-assign", help="Bulk auto-assign conversations to topics")
    aa.add_argument("project", help="Project name")
    aa.add_argument("--dry-run", action="store_true", help="Preview without applying")
    aa.add_argument(
        "--include-triaged", action="store_true",
        help="Also consider triaged-out conversations",
    )

    # show-hierarchy
    sub.add_parser("show-hierarchy", help="Show full project/topic hierarchy")

    # list-relationship-types
    sub.add_parser("list-relationship-types", help="List all relationship types")

    # migrate-to-v4
    m4 = sub.add_parser("migrate-to-v4", help="Migrate database from v3 to v4")
    m4.add_argument("--db", type=Path, help="Path to the SQLite database file")
    m4.add_argument("--dry-run", action="store_true",
                    help="Apply migration to a backup copy instead of the real database")

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
        "serve": cmd_serve,
        "add-account": cmd_add_account,
        "list-accounts": cmd_list_accounts,
        "remove-account": cmd_remove_account,
        "infer-relationships": cmd_infer_relationships,
        "show-relationships": cmd_show_relationships,
        "bootstrap-user": cmd_bootstrap_user,
        "create-company": cmd_create_company,
        "list-companies": cmd_list_companies,
        "delete-company": cmd_delete_company,
        "create-project": cmd_create_project,
        "list-projects": cmd_list_projects,
        "show-project": cmd_show_project,
        "delete-project": cmd_delete_project,
        "create-topic": cmd_create_topic,
        "list-topics": cmd_list_topics,
        "delete-topic": cmd_delete_topic,
        "assign-topic": cmd_assign_topic,
        "unassign-topic": cmd_unassign_topic,
        "auto-assign": cmd_auto_assign,
        "show-hierarchy": cmd_show_hierarchy,
        "list-relationship-types": cmd_list_relationship_types,
        "migrate-to-v4": cmd_migrate_to_v4,
    }

    # Default to "run" when no subcommand given
    command = args.command or "run"
    commands[command](args)


if __name__ == "__main__":
    main()
