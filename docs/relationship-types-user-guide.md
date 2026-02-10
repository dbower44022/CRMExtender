# Relationship Types User Guide

This guide covers the relationship types system introduced in v4 and
updated in v5 (bidirectional support): migrating your database,
understanding types, managing relationships through the web UI, and
using the CLI commands.

---

## Migrating from v3 to v4

If you have an existing v3 database, run the migration to add
relationship type support.

### Preview with dry run

```bash
python3 -m poc migrate-to-v4 --dry-run
```

This creates a backup copy and applies the migration to the backup only.
Your production database is not modified.  Review the output to confirm:
- The `relationship_types` table was created with 6 seed types.
- All existing relationships were migrated (row count matches).
- No foreign key violations were found.

### Run for real

```bash
python3 -m poc migrate-to-v4
```

A timestamped backup is created automatically at
`{database}.v3-backup-{timestamp}.db` before any changes are made.

### What the migration does

1. Creates the `relationship_types` table.
2. Seeds six default relationship types (KNOWS, EMPLOYEE, REPORTS_TO,
   WORKS_WITH, PARTNER, VENDOR).
3. Rebuilds the `relationships` table to use a foreign key to
   `relationship_types` instead of free-text type strings.
4. Maps all existing relationships to the KNOWS type with
   `source='inferred'`.
5. Creates indexes and validates data integrity.

If the migration detects the table already has the v4 schema, it skips
the rebuild step safely.

### Specifying a custom database path

```bash
python3 -m poc migrate-to-v4 --db /path/to/your/database.db --dry-run
```

---

## Migrating from v4 to v5

If you have a v4 database, run the migration to add bidirectional
relationship support.

### Preview with dry run

```bash
python3 -m poc migrate-to-v5 --dry-run
```

This creates a backup copy and applies the migration to the backup only.
Review the output to confirm:
- The `is_bidirectional` column was added to `relationship_types`.
- KNOWS, WORKS_WITH, and PARTNER were marked bidirectional.
- The `paired_relationship_id` column was added to `relationships`.
- Reverse rows were created for existing bidirectional relationships.

### Run for real

```bash
python3 -m poc migrate-to-v5
```

A timestamped backup is created automatically at
`{database}.v4-backup-{timestamp}.db` before any changes are made.

### What the migration does

1. Adds `is_bidirectional` column to `relationship_types`.
2. Sets `is_bidirectional=1` for KNOWS, WORKS_WITH, and PARTNER.
3. Adds `paired_relationship_id` column to `relationships`.
4. Creates reverse rows (B→A) for each existing bidirectional
   relationship (A→B) and links them via `paired_relationship_id`.
5. Validates no orphaned references or unpaired bidirectional rows.

---

## Understanding Relationship Types

Every relationship in the system has a **type** that defines what it
means, who it connects, and how it reads in each direction.

### Seed types

The system ships with six built-in types:

| Type | From → To | Forward Label | Reverse Label | Bidirectional | Example |
|---|---|---|---|---|---|
| **KNOWS** | contact → contact | Knows | Knows | Yes | Alice *knows* Bob |
| **EMPLOYEE** | company → contact | Employs | Works at | No | Acme *employs* Bob / Bob *works at* Acme |
| **REPORTS_TO** | contact → contact | Has direct report | Reports to | No | Alice *has direct report* Bob / Bob *reports to* Alice |
| **WORKS_WITH** | contact → contact | Works with | Works with | Yes | Alice *works with* Bob |
| **PARTNER** | company → company | Partners with | Partners with | Yes | Acme *partners with* Globex |
| **VENDOR** | company → company | Is a vendor of | Is a client of | No | Acme *is a vendor of* Globex / Globex *is a client of* Acme |

### Directional labels

Each type has two labels:
- **Forward label** — describes the relationship from the "from" entity's
  perspective (e.g., "Employs").
- **Reverse label** — describes it from the "to" entity's perspective
  (e.g., "Works at").

The web UI uses these labels to display relationships naturally
regardless of which side you are viewing from.

### System vs. custom types

- **System types** are marked with `is_system=1`.  Currently only KNOWS
  is a system type.  System types cannot be deleted because the
  inference engine depends on them.
- **Custom types** can be created by users and deleted when they are no
  longer in use (i.e., no relationships reference them).

### Bidirectional vs. unidirectional

**Bidirectional types** (KNOWS, WORKS_WITH, PARTNER) represent symmetric
relationships.  When you create "Alice works with Bob", the system
automatically creates the reverse "Bob works with Alice".  Both entities
see the relationship on their detail pages.  Deleting either side
removes both.

**Unidirectional types** (EMPLOYEE, REPORTS_TO, VENDOR) represent
directional relationships.  "Alice reports to Bob" does *not*
automatically create "Bob reports to Alice" — the reverse reads as
"Bob has direct report Alice" (using the reverse_label).

### Entity types

Each relationship type specifies what kinds of entities it connects:
- `contact → contact` (KNOWS, REPORTS_TO, WORKS_WITH)
- `company → contact` (EMPLOYEE)
- `company → company` (PARTNER, VENDOR)

When creating a relationship, the system enforces that the "from" and
"to" entities match the type's expected entity types.

---

## Inferred vs. Manual Relationships

### Inferred relationships

The inference engine automatically discovers KNOWS relationships by
analyzing which contacts appear together in email conversations.  These
relationships:

- Have `source='inferred'`.
- Carry a **strength** score (0.0 - 1.0) based on:
  - 40% — number of shared conversations (log-scaled)
  - 30% — total shared messages (log-scaled)
  - 30% — recency of last interaction (1.0 at 30 days, decaying to 0.1
    at 365+ days)
- Are always of type KNOWS.
- Are **rebuilt on every inference run** — the engine deletes all
  `source='inferred'` rows and re-inserts from scratch.
- Cannot be deleted individually through the web UI.

### Manual relationships

Users can create relationships of any type through the web UI.  These
relationships:

- Have `source='manual'`.
- Are **never touched by the inference engine** — re-running inference
  preserves all manual relationships.
- Can be deleted individually through the web UI.
- Do not carry strength scores or co-occurrence metrics.

---

## Web UI Walkthrough

### Browsing relationships

Navigate to `/relationships` in the web UI.  The page shows:

- **Filter controls** at the top:
  - **Type** dropdown — select a specific relationship type or show all.
  - **Source** dropdown — filter by `inferred`, `manual`, or all.
  - **Min strength** — filter out weak inferred relationships.
  - **Contact ID** — focus on one contact's relationships.

- **Results table** showing:
  - From entity name
  - Relationship label (directional)
  - To entity name
  - Type name
  - Source (inferred / manual)
  - Strength (for inferred)
  - Shared conversations / messages (for inferred)

Filters update the table via HTMX without a full page reload.

### Creating a manual relationship

On the `/relationships` page:

1. Fill in the **Create Relationship** form at the bottom.
2. Select the **relationship type** from the dropdown.
3. Enter the **from entity ID** and **to entity ID**.
4. Submit.  The page redirects back to the relationship list.

The relationship is created with `source='manual'` and will persist
across inference runs.

### Deleting a manual relationship

Each manual relationship row shows a **delete** button.  Clicking it
removes the relationship immediately.  Inferred relationships do not
show a delete button.

### Running inference from the web UI

Click the **Infer Relationships** button on the `/relationships` page.
This triggers the inference engine and displays the count of
relationships upserted.  The results table refreshes to show the
updated data.

### Managing relationship types

Navigate to `/relationships/types` to see the type admin page.

**Viewing types** — the page lists all types with their name, entity
types, labels, system flag, and description.

**Creating a custom type:**

1. Fill in the form: name, from entity type (contact or company), to
   entity type, forward label, reverse label, and optional description.
2. Submit.  The page refreshes with the new type listed.

**Deleting a custom type:**

- Click the **delete** button next to a non-system type.
- If the type is still referenced by existing relationships, the delete
  will fail with an error message.  Remove all relationships of that
  type first.
- System types (KNOWS) cannot be deleted.

---

## CLI Reference

### `list-relationship-types`

```bash
python3 -m poc list-relationship-types
```

Displays a table of all relationship types:

```
      Relationship Types
┌─────────────┬─────────┬─────────┬──────────────────┬──────────────────┬────────┐
│ Name        │ From    │ To      │ Forward Label    │ Reverse Label    │ System │
├─────────────┼─────────┼─────────┼──────────────────┼──────────────────┼────────┤
│ EMPLOYEE    │ company │ contact │ Employs          │ Works at         │  No    │
│ KNOWS       │ contact │ contact │ Knows            │ Knows            │  Yes   │
│ PARTNER     │ company │ company │ Partners with    │ Partners with    │  No    │
│ REPORTS_TO  │ contact │ contact │ Has direct report│ Reports to       │  No    │
│ VENDOR      │ company │ company │ Is a vendor of   │ Is a client of   │  No    │
│ WORKS_WITH  │ contact │ contact │ Works with       │ Works with       │  No    │
└─────────────┴─────────┴─────────┴──────────────────┴──────────────────┴────────┘
```

### `infer-relationships`

```bash
python3 -m poc infer-relationships
```

Runs the full inference pipeline:
1. Deletes all existing `source='inferred'` relationships.
2. Queries conversation co-occurrence data.
3. Deduplicates contacts by name (canonical mapping).
4. Scores each pair and upserts KNOWS relationships.

Output:

```
Initializing database...
Inferring relationships from conversation co-occurrence...

90 relationship(s) upserted.
```

Manual relationships are never affected.

### `show-relationships`

```bash
# Show all relationships
python3 -m poc show-relationships

# Filter by contact email
python3 -m poc show-relationships --contact alice@example.com

# Only strong relationships
python3 -m poc show-relationships --min-strength 0.5

# Combine filters
python3 -m poc show-relationships --contact alice@example.com --min-strength 0.3
```

Options:
- `--contact EMAIL` — show only relationships involving this contact.
  The email is resolved to a contact ID via the `contact_identifiers`
  table.
- `--min-strength FLOAT` — minimum strength threshold (0.0 - 1.0).
  Default is 0.0 (show all).

### `migrate-to-v4`

```bash
# Dry run (preview on backup)
python3 -m poc migrate-to-v4 --dry-run

# Apply to production
python3 -m poc migrate-to-v4

# Custom database path
python3 -m poc migrate-to-v4 --db /path/to/database.db
```

Options:
- `--db PATH` — path to the SQLite database.  Defaults to
  `data/crm_extender.db`.
- `--dry-run` — apply the migration to an auto-created backup copy
  instead of the production database.

### `migrate-to-v5`

```bash
# Dry run (preview on backup)
python3 -m poc migrate-to-v5 --dry-run

# Apply to production
python3 -m poc migrate-to-v5

# Custom database path
python3 -m poc migrate-to-v5 --db /path/to/database.db
```

Options:
- `--db PATH` — path to the SQLite database.  Defaults to
  `data/crm_extender.db`.
- `--dry-run` — apply the migration to an auto-created backup copy
  instead of the production database.

---

## Creating Custom Relationship Types

### Via the web UI

1. Navigate to `/relationships/types`.
2. Fill in the create form:
   - **Name** — a unique identifier (e.g., `MENTOR`).
   - **From entity type** — `contact` or `company`.
   - **To entity type** — `contact` or `company`.
   - **Forward label** — how the relationship reads from the "from"
     entity (e.g., "Mentors").
   - **Reverse label** — how it reads from the "to" entity (e.g.,
     "Mentored by").
   - **Description** — optional explanation.
3. Submit.

The new type immediately appears in the type dropdown on the
`/relationships` page and can be used when creating manual
relationships.

### Via the API (`poc/relationship_types.py`)

```python
from poc.relationship_types import create_relationship_type

create_relationship_type(
    "MENTOR",
    from_entity_type="contact",
    to_entity_type="contact",
    forward_label="Mentors",
    reverse_label="Mentored by",
    description="Mentorship relationship",
)
```

### Deleting a custom type

Custom types can only be deleted when no relationships reference them.
To delete a type that is in use:

1. Delete or reassign all relationships of that type.
2. Then delete the type via the web UI or API.

System types (KNOWS) can never be deleted.
