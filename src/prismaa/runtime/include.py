from __future__ import annotations

from typing import Any

from sqlalchemy import Table, select

from .connection import AsyncConnectionManager


async def load_relations(
    rows: list[dict[str, Any]],
    include: dict[str, bool],
    relations: list[dict[str, Any]],
    all_tables: dict[str, Table],
    all_models: dict[str, Any],
    conn: AsyncConnectionManager,
    all_field_column_maps: dict[str, dict[str, str]] | None = None,
    our_table: Table | None = None,
) -> None:
    """Attach related records onto each row dict in-place."""
    if not rows or not include:
        return

    fcmaps = all_field_column_maps or {}

    for rel in relations:
        name = rel["name"]
        if not include.get(name):
            continue

        related_model_name = rel["model"]
        related_table = all_tables.get(related_model_name)
        related_model_cls = all_models.get(related_model_name)
        if related_table is None or related_model_cls is None:
            continue

        rel_col_to_field = {v: k for k, v in fcmaps.get(related_model_name, {}).items()}

        def _make_related(
            rd: dict[str, Any],
            _fcm: dict[str, str] = rel_col_to_field,
            _cls: Any = related_model_cls,
        ) -> Any:
            mapped = {_fcm.get(k, k): v for k, v in rd.items()}
            return _cls(**mapped)

        fk_fields: list[str] = rel["fk_fields"]
        references: list[str] = rel["references"]
        is_list: bool = rel["is_list"]

        if fk_fields:
            # This side holds the FK: fk_fields/references are already column names
            fk_col = references[0]
            local_col = fk_fields[0]
            local_values = [r[local_col] for r in rows if r.get(local_col) is not None]
            if not local_values:
                for row in rows:
                    row[name] = None
                continue

            ref_col = related_table.c[fk_col]
            stmt = select(related_table).where(ref_col.in_(local_values))
            related_rows = await conn.execute(stmt)
            index = {r[fk_col]: dict(r) for r in related_rows}
            for row in rows:
                val = row.get(local_col)
                related_data = index.get(val)
                row[name] = _make_related(related_data) if related_data else None
        else:
            # The other side holds the FK pointing back at us.
            back_cols = _find_back_reference(related_table, our_table)
            if not back_cols:
                for row in rows:
                    row[name] = [] if is_list else None
                continue

            our_col, their_col = back_cols
            our_values = list({r[our_col] for r in rows if r.get(our_col) is not None})
            if not our_values:
                for row in rows:
                    row[name] = [] if is_list else None
                continue

            stmt = select(related_table).where(related_table.c[their_col].in_(our_values))
            related_rows = await conn.execute(stmt)

            if is_list:
                index_list: dict[Any, list[Any]] = {v: [] for v in our_values}
                for r in related_rows:
                    rd = dict(r)
                    key = rd[their_col]
                    if key in index_list:
                        index_list[key].append(_make_related(rd))
                for row in rows:
                    row[name] = index_list.get(row[our_col], [])
            else:
                index_one = {dict(r)[their_col]: _make_related(dict(r)) for r in related_rows}
                for row in rows:
                    row[name] = index_one.get(row[our_col])


def _find_back_reference(related_table: Table, our_table: Table | None) -> tuple[str, str] | None:
    """Return (our_col, their_col) by finding the FK on related_table that points to our_table."""
    for col in related_table.columns:
        for fk in col.foreign_keys:
            if our_table is None or fk.column.table.name == our_table.name:
                return (fk.column.name, col.name)
    return None
