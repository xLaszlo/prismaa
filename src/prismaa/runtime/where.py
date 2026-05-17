from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Table, and_, not_, or_, select
from sqlalchemy import exists as sa_exists
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

if TYPE_CHECKING:
    from .metadata import ModelMetadata, RelationMeta


# ---------------------------------------------------------------------------
# Statement-level entry point (use this in find_many / find_first)
# ---------------------------------------------------------------------------


def apply_where(
    stmt: Select,
    table: Table,
    where: dict[str, Any],
    field_column_map: dict[str, str] | None = None,
    relations: "list[RelationMeta] | None" = None,
    all_metadata: "dict[str, ModelMetadata] | None" = None,
) -> Select:
    """Apply WHERE + JOIN to a SELECT statement.

    Relation filters are handled as JOINs (FK-side) or correlated EXISTS
    (back-reference), avoiding large IN lists. Scalar filters go through
    build_where. Compound AND/OR/NOT fall back to build_where for the whole
    clause — they are uncommon with relation keys and hard to split cleanly.
    """
    fcm = field_column_map or {}
    rel_by_name = {r.name: r for r in (relations or [])}
    scalar_filters: dict[str, Any] = {}

    for key, value in where.items():
        if key in ("AND", "OR", "NOT"):
            # Compound operators — pass straight through to build_where.
            # Relation keys nested inside AND/OR/NOT are handled with EXISTS there.
            scalar_filters[key] = value
        elif key in rel_by_name and all_metadata is not None:
            rel = rel_by_name[key]
            related_meta = all_metadata.get(rel.model)
            if related_meta is None:
                continue
            stmt = _apply_relation_to_stmt(stmt, table, rel, related_meta, value, all_metadata)
        else:
            scalar_filters[key] = value

    if scalar_filters:
        stmt = stmt.where(build_where(table, scalar_filters, fcm, relations, all_metadata))

    return stmt


def _apply_relation_to_stmt(
    stmt: Select,
    table: Table,
    rel: "RelationMeta",
    related_meta: "ModelMetadata",
    value: Any,
    all_metadata: "dict[str, ModelMetadata]",
) -> Select:
    related_table = related_meta.table
    related_fcm = related_meta.field_column_map
    related_rels = related_meta.relations

    if rel.fk_fields:
        # FK is on this table (many-to-one / 1-1 owning side).
        # JOIN: no duplicates, single query plan.
        join_cond = table.c[rel.fk_fields[0]] == related_table.c[rel.references[0]]
        stmt = stmt.join(related_table, join_cond)
        # Recursively apply the relation's filter dict onto the now-joined table.
        stmt = apply_where(stmt, related_table, value, related_fcm, related_rels, all_metadata)
    else:
        # FK is on the other table (one-to-many / 1-1 non-owning side).
        # Correlated EXISTS: short-circuits on first match, no DISTINCT, no large IN.
        back_fk_col, our_pk_col = _back_reference_cols(related_table, table)
        if back_fk_col is None:
            return stmt

        if isinstance(value, dict) and set(value.keys()) <= {"some", "none", "every"}:
            sub_where = value.get("some") or value.get("every") or value.get("none")
            negate = "none" in value
        else:
            sub_where = value
            negate = False

        subq = (
            select(related_table.c[back_fk_col])
            .where(related_table.c[back_fk_col] == table.c[our_pk_col])
            .where(build_where(related_table, sub_where, related_fcm, related_rels, all_metadata))
        )
        clause = sa_exists(subq)
        stmt = stmt.where(not_(clause) if negate else clause)

    return stmt


# ---------------------------------------------------------------------------
# Clause-level builder (use this inside subqueries and include sub-filters)
# ---------------------------------------------------------------------------


def build_where(
    table: Table,
    where: dict[str, Any],
    field_column_map: dict[str, str] | None = None,
    relations: "list[RelationMeta] | None" = None,
    all_metadata: "dict[str, ModelMetadata] | None" = None,
) -> ColumnElement:
    """Return a WHERE ColumnElement — no JOINs.

    Relation keys are handled with EXISTS subqueries so this stays a pure
    predicate usable inside subqueries and include sub-filters.
    """
    fcm = field_column_map or {}
    rel_by_name = {r.name: r for r in (relations or [])}
    clauses = []

    for key, value in where.items():
        if key == "AND":
            clauses.append(and_(*[build_where(table, w, fcm, relations, all_metadata) for w in value]))
        elif key == "OR":
            clauses.append(or_(*[build_where(table, w, fcm, relations, all_metadata) for w in value]))
        elif key == "NOT":
            clauses.append(not_(build_where(table, value, fcm, relations, all_metadata)))
        elif key in rel_by_name and all_metadata is not None:
            rel = rel_by_name[key]
            related_meta = all_metadata.get(rel.model)
            if related_meta is None:
                continue
            clauses.append(_relation_clause(table, rel, related_meta, value, all_metadata))
        else:
            col_name = fcm.get(key, key)
            col = table.c[col_name]
            clauses.append(_apply_filter(col, value) if isinstance(value, dict) else col == value)

    return and_(*clauses) if clauses else and_(True)


def _relation_clause(
    table: Table,
    rel: "RelationMeta",
    related_meta: "ModelMetadata",
    value: Any,
    all_metadata: "dict[str, ModelMetadata]",
) -> ColumnElement:
    """EXISTS-based relation predicate for use inside build_where (subquery contexts)."""
    related_table = related_meta.table
    related_fcm = related_meta.field_column_map
    related_rels = related_meta.relations

    if rel.fk_fields:
        # Many-to-one: WHERE fk IN (SELECT ref FROM related WHERE ...)
        # The subquery is over the PK of the related table — small, index-driven.
        subq = select(related_table.c[rel.references[0]]).where(
            build_where(related_table, value, related_fcm, related_rels, all_metadata)
        )
        return table.c[rel.fk_fields[0]].in_(subq)

    # One-to-many: correlated EXISTS
    back_fk_col, our_pk_col = _back_reference_cols(related_table, table)
    if back_fk_col is None:
        return and_(True)

    if isinstance(value, dict) and set(value.keys()) <= {"some", "none", "every"}:
        sub_where = value.get("some") or value.get("every") or value.get("none")
        negate = "none" in value
    else:
        sub_where = value
        negate = False

    subq = (
        select(related_table.c[back_fk_col])
        .where(related_table.c[back_fk_col] == table.c[our_pk_col])
        .where(build_where(related_table, sub_where, related_fcm, related_rels, all_metadata))
    )
    clause = sa_exists(subq)
    return not_(clause) if negate else clause


def _back_reference_cols(related_table: Table, our_table: Table) -> tuple[str | None, str | None]:
    for col in related_table.columns:
        for fk in col.foreign_keys:
            if fk.column.table.name == our_table.name:
                return col.name, fk.column.name
    return None, None


def _apply_filter(col: Any, f: dict[str, Any]) -> ColumnElement:
    parts = []
    for op, val in f.items():
        if op == "equals":
            parts.append(col == val)
        elif op == "not_":
            parts.append(col != val)
        elif op == "in_":
            parts.append(col.in_(val))
        elif op == "not_in":
            parts.append(col.notin_(val))
        elif op == "lt":
            parts.append(col < val)
        elif op == "lte":
            parts.append(col <= val)
        elif op == "gt":
            parts.append(col > val)
        elif op == "gte":
            parts.append(col >= val)
        elif op == "contains":
            parts.append(col.ilike(f"%{val}%"))
        elif op == "startswith":
            parts.append(col.ilike(f"{val}%"))
        elif op == "endswith":
            parts.append(col.ilike(f"%{val}"))
    return and_(*parts) if parts else and_(True)
