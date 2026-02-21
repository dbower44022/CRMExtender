"""Query engine — builds and executes SQL from a view configuration.

The engine is entity-agnostic: it reads the field registry for the
entity type, applies visibility scoping from ``poc.access``, and
renders dynamic SELECT / WHERE / ORDER BY clauses.
"""

from __future__ import annotations

import json
import sqlite3

from ..access import (
    my_companies_query,
    my_contacts_query,
    visible_communications_query,
    visible_companies_query,
    visible_contacts_query,
    visible_conversations_query,
    visible_notes_query,
    visible_projects_query,
    visible_relationships_query,
)
from .registry import ENTITY_TYPES, EntityDef, FieldDef

# Map: operator name → (SQL template, needs_value)
_FILTER_OPS: dict[str, tuple[str, bool]] = {
    "equals":       ("{field} = ?", True),
    "not_equals":   ("{field} != ?", True),
    "contains":     ("{field} LIKE '%' || ? || '%'", True),
    "not_contains": ("{field} NOT LIKE '%' || ? || '%'", True),
    "starts_with":  ("{field} LIKE ? || '%'", True),
    "gt":           ("{field} > ?", True),
    "lt":           ("{field} < ?", True),
    "gte":          ("{field} >= ?", True),
    "lte":          ("{field} <= ?", True),
    "is_empty":     ("({field} IS NULL OR {field} = '')", False),
    "is_not_empty": ("({field} IS NOT NULL AND {field} != '')", False),
    "is_before":    ("{field} < ?", True),
    "is_after":     ("{field} > ?", True),
}

# Visibility function per entity type
_VISIBILITY_FN = {
    "contact": visible_contacts_query,
    "company": visible_companies_query,
    "conversation": visible_conversations_query,
    "communication": visible_communications_query,
    "project": visible_projects_query,
    "relationship": visible_relationships_query,
    "note": visible_notes_query,
}


def execute_view(
    conn: sqlite3.Connection,
    *,
    entity_type: str,
    columns: list[dict],
    filters: list[dict],
    sort_field: str | None = None,
    sort_direction: str = "asc",
    search: str = "",
    page: int = 1,
    per_page: int = 50,
    customer_id: str = "",
    user_id: str = "",
    scope: str = "all",
    extra_where: list[tuple[str, list]] | None = None,
) -> tuple[list[dict], int]:
    """Execute a view query and return (rows, total_count).

    Parameters
    ----------
    columns : list of dicts with at least ``field_key``
    filters : list of dicts with ``field_key``, ``operator``, ``value``
    scope : "all" (default) or "mine" — "mine" restricts to user-owned rows
    extra_where : additional WHERE clauses as (sql_fragment, params_list) tuples
    """
    entity_def = ENTITY_TYPES.get(entity_type)
    if not entity_def:
        raise ValueError(f"Unknown entity type: {entity_type}")

    select_exprs, select_keys = _build_select(entity_def, columns)
    from_clause = f"{entity_def.table} {entity_def.alias}"
    join_parts = list(entity_def.base_joins)

    where_parts: list[str] = []
    params: list = []

    # Visibility scoping (with "mine" support for contacts/companies)
    if scope == "mine" and entity_type == "contact" and customer_id and user_id:
        join_parts.append("JOIN user_contacts uc ON uc.contact_id = c.id")
        vis_where, vis_params = my_contacts_query(customer_id, user_id)
        where_parts.append(vis_where)
        params.extend(vis_params)
    elif scope == "mine" and entity_type == "company" and customer_id and user_id:
        join_parts.append("JOIN user_companies uco ON uco.company_id = co.id")
        vis_where, vis_params = my_companies_query(customer_id, user_id)
        where_parts.append(vis_where)
        params.extend(vis_params)
    else:
        vis_fn = _VISIBILITY_FN.get(entity_type)
        if vis_fn and customer_id and user_id:
            vis_where, vis_params = vis_fn(customer_id, user_id)
            where_parts.append(vis_where)
            params.extend(vis_params)

    if entity_type == "event" and customer_id:
        where_parts.append(
            "(e.account_id IS NULL OR e.account_id IN "
            "(SELECT id FROM provider_accounts WHERE customer_id = ?))"
        )
        params.append(customer_id)

    # Communication-specific: only current, non-archived
    if entity_type == "communication":
        where_parts.append("comm.is_current = 1")
        where_parts.append("comm.is_archived = 0")

    # Extra WHERE clauses from the caller (status tabs, topic filters, etc.)
    if extra_where:
        for sql_frag, ew_params in extra_where:
            where_parts.append(sql_frag)
            params.extend(ew_params)

    # User-defined filters
    for f in filters:
        fk = f.get("field_key", "")
        op = f.get("operator", "")
        val = f.get("value")
        field_def = entity_def.fields.get(fk)
        op_def = _FILTER_OPS.get(op)
        if not field_def or not op_def:
            continue
        sql_tpl, needs_val = op_def
        sql_frag = sql_tpl.replace("{field}", field_def.sql)
        where_parts.append(sql_frag)
        if needs_val:
            # value may be JSON-encoded in DB
            if isinstance(val, str):
                try:
                    decoded = json.loads(val)
                    if isinstance(decoded, str):
                        val = decoded
                except (json.JSONDecodeError, TypeError):
                    pass
            params.append(val)

    # Search
    if search:
        search_clauses = [f"{sf} LIKE ?" for sf in entity_def.search_fields]
        search_params = [f"%{search}%"] * len(entity_def.search_fields)
        if entity_def.search_subquery:
            search_clauses.append(f"{entity_def.search_subquery} IS NOT NULL")
            search_params.append(f"%{search}%")
        if search_clauses:
            where_parts.append(f"({' OR '.join(search_clauses)})")
            params.extend(search_params)

    where_sql = " AND ".join(where_parts) if where_parts else "1=1"
    join_clause = "\n".join(join_parts)

    # GROUP BY (prevents JOIN expansion for contacts)
    group_sql = f"GROUP BY {entity_def.group_by}" if entity_def.group_by else ""

    # ORDER BY
    order_sql = _build_order_by(entity_def, sort_field, sort_direction)

    # Count query
    count_sql = (
        f"SELECT COUNT(*) AS cnt FROM ("
        f"SELECT {entity_def.alias}.id FROM {from_clause}\n{join_clause}\n"
        f"WHERE {where_sql} {group_sql})"
    )
    total = conn.execute(count_sql, params).fetchone()["cnt"]

    # Data query
    offset = (page - 1) * per_page
    if select_exprs:
        select_str = f"{entity_def.alias}.id, " + ", ".join(select_exprs)
    else:
        select_str = f"{entity_def.alias}.id"
    data_sql = (
        f"SELECT {select_str}\n"
        f"FROM {from_clause}\n{join_clause}\n"
        f"WHERE {where_sql}\n"
        f"{group_sql}\n"
        f"{order_sql}\n"
        f"LIMIT ? OFFSET ?"
    )
    data_params = params + [per_page, offset]
    rows = conn.execute(data_sql, data_params).fetchall()

    result = []
    for row in rows:
        d = {"id": row["id"]}
        for key in select_keys:
            d[key] = row[key]
        result.append(d)

    return result, total


def _build_select(
    entity_def: EntityDef, columns: list[dict],
) -> tuple[list[str], list[str]]:
    """Build SELECT expressions from column config.

    Returns (sql_expressions, field_keys) — both aligned lists.
    """
    exprs: list[str] = []
    keys: list[str] = []
    seen: set[str] = set()

    for col in columns:
        fk = col.get("field_key", "")
        if fk in seen:
            continue
        field_def = entity_def.fields.get(fk)
        if not field_def:
            continue
        seen.add(fk)
        exprs.append(f"{field_def.sql} AS {fk}")
        keys.append(fk)

        # If a field has a link template that references another field,
        # ensure that field is included (e.g. company_id for company_name link)
        if field_def.link:
            for ref_key, ref_def in entity_def.fields.items():
                if ref_key in field_def.link and ref_key not in seen:
                    if ref_def.type == "hidden":
                        seen.add(ref_key)
                        exprs.append(f"{ref_def.sql} AS {ref_key}")
                        keys.append(ref_key)

    return exprs, keys


def _build_order_by(
    entity_def: EntityDef,
    sort_field: str | None,
    sort_direction: str,
) -> str:
    """Build ORDER BY clause with NULL-last handling."""
    if not sort_field:
        sort_field, sort_direction = entity_def.default_sort

    field_def = entity_def.fields.get(sort_field)
    if not field_def or not field_def.sortable:
        sort_field, sort_direction = entity_def.default_sort
        field_def = entity_def.fields[sort_field]

    direction = "DESC" if sort_direction == "desc" else "ASC"
    sql_expr = field_def.sql

    # Case-insensitive sort for text fields; NULLs sort last
    collate = " COLLATE NOCASE" if field_def.type == "text" else ""
    return f"ORDER BY ({sql_expr}) IS NULL, {sql_expr}{collate} {direction}"
