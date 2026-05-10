from __future__ import annotations

from typing import Any

from sqlalchemy import Table, and_, not_, or_
from sqlalchemy.sql.elements import ColumnElement


def build_where(
    table: Table,
    where: dict[str, Any],
    field_column_map: dict[str, str] | None = None,
) -> ColumnElement:
    """Convert a WhereInput dict to a SQLAlchemy WHERE clause.

    field_column_map translates Prisma field names (camelCase) to DB column names.
    """
    fcm = field_column_map or {}
    clauses = []
    for key, value in where.items():
        if key == "AND":
            clauses.append(and_(*[build_where(table, w, fcm) for w in value]))
        elif key == "OR":
            clauses.append(or_(*[build_where(table, w, fcm) for w in value]))
        elif key == "NOT":
            clauses.append(not_(build_where(table, value, fcm)))
        else:
            col_name = fcm.get(key, key)
            col = table.c[col_name]
            if isinstance(value, dict):
                clauses.append(_apply_filter(col, value))
            else:
                clauses.append(col == value)
    return and_(*clauses) if clauses else and_(True)


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
