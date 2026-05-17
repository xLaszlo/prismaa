from __future__ import annotations

from typing import Any

from sqlalchemy import Table, select

from .connection import AsyncConnectionManager
from .metadata import ModelMetadata, RelationMeta
from .where import build_where


async def load_relations(
    rows: list[dict[str, Any]],
    include: dict[str, Any],
    relations: list[RelationMeta],
    all_metadata: dict[str, ModelMetadata],
    conn: AsyncConnectionManager,
    our_table: Table | None = None,
) -> None:
    """Attach related records onto each row dict in-place, supporting nested includes."""
    if not rows or not include:
        return

    for rel in relations:
        include_val = include.get(rel.name)
        if not include_val:
            continue

        nested_include: dict[str, Any] | None = None
        sub_where: dict[str, Any] | None = None
        sub_take: int | None = None
        sub_skip: int | None = None
        sub_order: dict[str, str] | list[dict[str, str]] | None = None

        if isinstance(include_val, dict):
            nested_include = include_val.get("include")
            sub_where = include_val.get("where")
            sub_take = include_val.get("take")
            sub_skip = include_val.get("skip")
            sub_order = include_val.get("orderBy")

        related_meta = all_metadata.get(rel.model)
        if related_meta is None:
            continue

        related_table = related_meta.table
        related_model_cls = related_meta.model_cls
        related_fcm = related_meta.field_column_map
        rel_col_to_field = {v: k for k, v in related_fcm.items()}

        def _make_related(
            rd: dict[str, Any],
            _fcm: dict[str, str] = rel_col_to_field,
            _cls: Any = related_model_cls,
        ) -> Any:
            mapped = {_fcm.get(k, k): v for k, v in rd.items()}
            return _cls(**mapped)

        if rel.fk_fields:
            # This side holds the FK — at most one related record per row.
            fk_col = rel.references[0]
            local_col = rel.fk_fields[0]
            local_values = [r[local_col] for r in rows if r.get(local_col) is not None]
            if not local_values:
                for row in rows:
                    row[rel.name] = None
                continue

            stmt = select(related_table).where(related_table.c[fk_col].in_(local_values))
            related_dicts = {r[fk_col]: dict(r) for r in await conn.execute(stmt)}

            if nested_include:
                await load_relations(
                    list(related_dicts.values()),
                    nested_include,
                    related_meta.relations,
                    all_metadata,
                    conn,
                    our_table=related_table,
                )

            for row in rows:
                rd = related_dicts.get(row.get(local_col))
                row[rel.name] = _make_related(rd) if rd is not None else None
        else:
            # The other side holds the FK pointing back at us.
            back_cols = _find_back_reference(related_table, our_table)
            if not back_cols:
                for row in rows:
                    row[rel.name] = [] if rel.is_list else None
                continue

            our_col, their_col = back_cols
            our_values = list({r[our_col] for r in rows if r.get(our_col) is not None})
            if not our_values:
                for row in rows:
                    row[rel.name] = [] if rel.is_list else None
                continue

            stmt = select(related_table).where(related_table.c[their_col].in_(our_values))
            if sub_where:
                stmt = stmt.where(build_where(related_table, sub_where, related_fcm))
            if sub_order:
                orders: list[dict[str, str]] = [sub_order] if isinstance(sub_order, dict) else sub_order
                for o in orders:
                    for field_name, direction in o.items():
                        col_name = related_fcm.get(field_name, field_name)
                        col = related_table.c[col_name]
                        stmt = stmt.order_by(col.asc() if direction == "asc" else col.desc())

            if rel.is_list:
                index_list: dict[Any, list[dict[str, Any]]] = {v: [] for v in our_values}
                for r in await conn.execute(stmt):
                    rd = dict(r)
                    key = rd[their_col]
                    if key in index_list:
                        index_list[key].append(rd)

                # take/skip apply per-parent at the Python level
                if sub_skip is not None or sub_take is not None:
                    for k in index_list:
                        lst = index_list[k]
                        if sub_skip:
                            lst = lst[sub_skip:]
                        if sub_take is not None:
                            lst = lst[:sub_take]
                        index_list[k] = lst

                if nested_include:
                    all_related_dicts = [d for lst in index_list.values() for d in lst]
                    await load_relations(
                        all_related_dicts,
                        nested_include,
                        related_meta.relations,
                        all_metadata,
                        conn,
                        our_table=related_table,
                    )

                for row in rows:
                    row[rel.name] = [_make_related(d) for d in index_list.get(row[our_col], [])]
            else:
                all_related_dicts = [dict(r) for r in await conn.execute(stmt)]
                index_one = {d[their_col]: d for d in all_related_dicts}

                if nested_include:
                    await load_relations(
                        all_related_dicts,
                        nested_include,
                        related_meta.relations,
                        all_metadata,
                        conn,
                        our_table=related_table,
                    )

                for row in rows:
                    rd = index_one.get(row[our_col])
                    row[rel.name] = _make_related(rd) if rd is not None else None


def _find_back_reference(related_table: Table, our_table: Table | None) -> tuple[str, str] | None:
    """Return (our_col, their_col) by finding the FK on related_table that points to our_table."""
    for col in related_table.columns:
        for fk in col.foreign_keys:
            if our_table is None or fk.column.table.name == our_table.name:
                return (fk.column.name, col.name)
    return None
