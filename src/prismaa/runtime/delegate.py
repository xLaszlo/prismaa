from __future__ import annotations

import datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import and_, delete, func, insert, or_, update
from sqlalchemy import select as select_sa

from .connection import AsyncConnectionManager
from .errors import ForeignKeyViolationError, RecordNotFoundError, UniqueViolationError
from .include import load_relations
from .metadata import ModelMetadata
from .where import apply_where, build_where

T = TypeVar("T")


class AsyncModelDelegate(Generic[T]):
    def __init__(
        self,
        *,
        model_name: str,
        all_metadata: dict[str, ModelMetadata],
        conn: AsyncConnectionManager,
    ) -> None:
        meta = all_metadata[model_name]
        self._table = meta.table
        self._model_cls = meta.model_cls
        self._field_column_map = meta.field_column_map
        self._col_to_field_map = {v: k for k, v in meta.field_column_map.items()}
        self._relations = meta.relations
        self._unique_fields = meta.unique_fields
        self._updated_at_fields = meta.updated_at_fields
        self._all_metadata = all_metadata
        self._conn = conn

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row_to_model(self, row_dict: dict[str, Any]) -> T:
        """Translate column names → field names then construct the model."""
        mapped = {self._col_to_field_map.get(k, k): v for k, v in row_dict.items()}
        return self._model_cls(**mapped)

    def _partial_row_to_model(self, row_dict: dict[str, Any], select: dict[str, bool]) -> T:
        """Build a model with only the selected fields populated (bypasses Pydantic validation)."""
        selected = {f for f, v in select.items() if v}
        col_names = {c.name for c in self._table.columns}
        mapped: dict[str, Any] = {}
        for k, v in row_dict.items():
            if k in col_names:
                field_name = self._col_to_field_map.get(k, k)
                if field_name in selected:
                    mapped[field_name] = v
            else:
                mapped[k] = v  # relation objects attached by _attach_includes
        return self._model_cls.model_construct(**mapped)

    def _validate_select(self, select: dict[str, bool]) -> None:
        known = set(self._field_column_map.keys())
        unknown = [f for f, v in select.items() if v and f not in known]
        if unknown:
            raise ValueError(f"Unknown field(s) in select: {unknown}")

    async def _attach_includes(self, rows: list[dict[str, Any]], include: dict[str, Any] | None) -> None:
        if include:
            await load_relations(
                rows,
                include,
                self._relations,
                self._all_metadata,
                self._conn,
                our_table=self._table,
            )

    def _build_unique_where(self, where: dict[str, Any]) -> Any:
        """Build a WHERE clause from a WhereUniqueInput dict, translating field→column names."""
        parts = []
        for key, value in where.items():
            col_name = self._field_column_map.get(key, key)
            parts.append(self._table.c[col_name] == value)
        return and_(*parts)

    def _inject_updated_at(self, data: dict[str, Any]) -> dict[str, Any]:
        """Set @updatedAt fields to current UTC time."""
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        result = dict(data)
        for field in self._updated_at_fields:
            result[field] = now
        return result

    def _strip_relation_keys(self, data: dict[str, Any]) -> dict[str, Any]:
        """Translate Prisma field names to column names, dropping relation/unknown keys."""
        col_names = {c.name for c in self._table.columns}
        result = {}
        for k, v in data.items():
            col_name = self._field_column_map.get(k, k)
            if col_name in col_names:
                result[col_name] = v
        return result

    _ATOMIC_OPS = {
        "increment": lambda col, val: col + val,
        "decrement": lambda col, val: col - val,
        "multiply": lambda col, val: col * val,
        "divide": lambda col, val: col / val,
    }

    def _build_update_values(self, data: dict[str, Any]) -> dict:
        """Translate update data, resolving atomic operator dicts to SQLAlchemy expressions."""
        col_names = {c.name for c in self._table.columns}
        result: dict = {}
        for k, v in data.items():
            col_name = self._field_column_map.get(k, k)
            if col_name not in col_names:
                continue
            col = self._table.c[col_name]
            if isinstance(v, dict):
                for op, operand in v.items():
                    if op in self._ATOMIC_OPS:
                        result[col] = self._ATOMIC_OPS[op](col, operand)
                        break
            else:
                result[col_name] = v
        return result

    async def _resolve_nested_writes(self, data: dict[str, Any]) -> dict[str, Any]:
        """Resolve connect / disconnect / connectOrCreate on FK-side relations to scalar FK values."""
        result = dict(data)
        for rel in self._relations:
            if rel.name not in result or not rel.fk_fields:
                continue
            val = result.pop(rel.name)
            if not isinstance(val, dict):
                continue
            if "connect" in val:
                connect_where = val["connect"]
                for fk_col, ref_field in zip(rel.fk_fields, rel.references, strict=True):
                    field_name = self._col_to_field_map.get(fk_col, fk_col)
                    result[field_name] = connect_where.get(ref_field)
            elif "disconnect" in val:
                for fk_col in rel.fk_fields:
                    result[self._col_to_field_map.get(fk_col, fk_col)] = None
            elif "connectOrCreate" in val:
                coc = val["connectOrCreate"]
                where_data: dict[str, Any] = coc["where"]
                create_data: dict[str, Any] = coc["create"]
                related_meta = self._all_metadata[rel.model]
                related_table = related_meta.table
                related_fcm = related_meta.field_column_map
                where_parts = [related_table.c[related_fcm.get(k, k)] == v for k, v in where_data.items()]
                existing = await self._conn.execute(select_sa(related_table).where(and_(*where_parts)))
                if existing:
                    row = dict(existing[0])
                else:
                    clean = {
                        related_fcm.get(k, k): v
                        for k, v in create_data.items()
                        if related_fcm.get(k, k) in {c.name for c in related_table.columns}
                    }
                    new_rows = await self._conn.execute_write(
                        insert(related_table).values(**clean).returning(related_table)
                    )
                    row = dict(new_rows[0])
                for fk_col, ref_field in zip(rel.fk_fields, rel.references, strict=True):
                    result[self._col_to_field_map.get(fk_col, fk_col)] = row.get(ref_field)
        return result

    @staticmethod
    def _wrap_integrity_error(exc: Exception) -> Exception:
        msg = str(exc).upper()
        if "FOREIGN KEY" in msg:
            return ForeignKeyViolationError(str(exc))
        if "UNIQUE" in msg:
            return UniqueViolationError(str(exc))
        return exc

    @staticmethod
    def _cursor_condition(sort_specs: list[tuple[Any, str, Any]]) -> Any:
        """OR-expanded keyset condition for cursor pagination.

        For each position i, require all prior columns to be equal and column i
        to be strictly after (or equal for the last column) the cursor value.
        This correctly handles mixed asc/desc sort directions.
        """
        clauses = []
        for i, (col, direction, val) in enumerate(sort_specs):
            eq_parts = [c == v for c, _, v in sort_specs[:i]]
            is_last = i == len(sort_specs) - 1
            cmp = (
                (col >= val if direction == "asc" else col <= val)
                if is_last
                else (col > val if direction == "asc" else col < val)
            )
            clauses.append(and_(*eq_parts, cmp) if eq_parts else cmp)
        return or_(*clauses) if len(clauses) > 1 else clauses[0]

    def _validate_unique_where(self, where: dict[str, Any]) -> None:
        if "__composite__" in self._unique_fields:
            return
        if not any(k in self._unique_fields for k in where):
            raise ValueError(
                f"find_unique requires at least one unique field "
                f"({', '.join(self._unique_fields)}); got {list(where.keys())}"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def find_unique(
        self,
        *,
        where: dict[str, Any],
        include: dict[str, Any] | None = None,
        select: dict[str, bool] | None = None,
    ) -> T | None:
        self._validate_unique_where(where)
        if select:
            self._validate_select(select)
        clause = self._build_unique_where(where)
        stmt = select_sa(self._table).where(clause)
        rows = await self._conn.execute(stmt)
        if not rows:
            return None
        row_dicts = [dict(r) for r in rows]
        await self._attach_includes(row_dicts, include)
        if select:
            return self._partial_row_to_model(row_dicts[0], select)
        return self._row_to_model(row_dicts[0])

    async def find_unique_or_raise(
        self,
        *,
        where: dict[str, Any],
        include: dict[str, Any] | None = None,
        select: dict[str, bool] | None = None,
    ) -> T:
        result = await self.find_unique(where=where, include=include, select=select)
        if result is None:
            raise RecordNotFoundError(f"No record found matching {where}")
        return result

    async def find_first(
        self,
        *,
        where: dict[str, Any] | None = None,
        include: dict[str, Any] | None = None,
        order: dict[str, str] | list[dict[str, str]] | None = None,
        skip: int | None = None,
        select: dict[str, bool] | None = None,
    ) -> T | None:
        results = await self.find_many(where=where, include=include, order=order, skip=skip, take=1, select=select)
        return results[0] if results else None

    async def find_first_or_raise(
        self,
        *,
        where: dict[str, Any] | None = None,
        include: dict[str, Any] | None = None,
        order: dict[str, str] | list[dict[str, str]] | None = None,
        skip: int | None = None,
        select: dict[str, bool] | None = None,
    ) -> T:
        result = await self.find_first(where=where, include=include, order=order, skip=skip, select=select)
        if result is None:
            raise RecordNotFoundError(f"No record found matching where={where}")
        return result

    async def find_many(
        self,
        *,
        where: dict[str, Any] | None = None,
        include: dict[str, Any] | None = None,
        order: dict[str, str] | list[dict[str, str]] | None = None,
        take: int | None = None,
        skip: int | None = None,
        select: dict[str, bool] | None = None,
        distinct: list[str] | None = None,
        cursor: dict[str, Any] | None = None,
    ) -> list[T]:
        if select:
            self._validate_select(select)
        stmt = select_sa(self._table)
        if where:
            stmt = apply_where(stmt, self._table, where, self._field_column_map, self._relations, self._all_metadata)
        if cursor:
            # Look up the cursor record to read sort-column values, then build a
            # proper OR-expanded keyset condition across all ORDER BY columns.
            cursor_rows = await self._conn.execute(select_sa(self._table).where(self._build_unique_where(cursor)))
            if cursor_rows:
                cursor_row = dict(cursor_rows[0])
                orders_list = (
                    ([order] if isinstance(order, dict) else order) if order else [{next(iter(cursor)): "asc"}]
                )
                sort_specs = [
                    (self._table.c[self._field_column_map.get(f, f)], d, cursor_row[self._field_column_map.get(f, f)])
                    for o in orders_list
                    for f, d in o.items()
                ]
                stmt = stmt.where(self._cursor_condition(sort_specs))
        # PostgreSQL supports DISTINCT ON; prepend distinct cols to ORDER BY as required
        if distinct and self._conn.dialect_name == "postgresql":
            pg_cols = [self._table.c[self._field_column_map.get(f, f)] for f in distinct]
            stmt = stmt.distinct(*pg_cols)
            for col in pg_cols:
                stmt = stmt.order_by(col)
        if order:
            orders = [order] if isinstance(order, dict) else order
            for o in orders:
                for field, direction in o.items():
                    col_name = self._field_column_map.get(field, field)
                    col = self._table.c[col_name]
                    stmt = stmt.order_by(col.asc() if direction == "asc" else col.desc())
        # For non-PostgreSQL with distinct, skip SQL pagination; apply after Python dedup
        if not (distinct and self._conn.dialect_name != "postgresql"):
            if skip:
                stmt = stmt.offset(skip)
            if take:
                stmt = stmt.limit(take)
        rows = await self._conn.execute(stmt)
        row_dicts = [dict(r) for r in rows]
        # Python-level deduplication for databases that don't support DISTINCT ON
        if distinct and self._conn.dialect_name != "postgresql":
            seen: set = set()
            deduped: list[dict[str, Any]] = []
            for row in row_dicts:
                key = tuple(row.get(self._field_column_map.get(f, f)) for f in distinct)
                if key not in seen:
                    seen.add(key)
                    deduped.append(row)
            row_dicts = deduped
            if skip:
                row_dicts = row_dicts[skip:]
            if take:
                row_dicts = row_dicts[:take]
        await self._attach_includes(row_dicts, include)
        if select:
            return [self._partial_row_to_model(r, select) for r in row_dicts]
        return [self._row_to_model(r) for r in row_dicts]

    async def create(
        self,
        *,
        data: dict[str, Any],
        include: dict[str, Any] | None = None,
    ) -> T:
        data = await self._resolve_nested_writes(data)
        clean = self._strip_relation_keys(self._inject_updated_at(data))
        stmt = insert(self._table).values(**clean).returning(self._table)
        try:
            rows = await self._conn.execute_write(stmt)
        except Exception as e:
            raise self._wrap_integrity_error(e) from e
        if not rows:
            raise RuntimeError("INSERT returned no rows")
        row_dict = dict(rows[0])
        await self._attach_includes([row_dict], include)
        return self._row_to_model(row_dict)

    async def create_many(
        self,
        *,
        data: list[dict[str, Any]],
        skip_duplicates: bool = False,
    ) -> int:
        if not data:
            return 0
        rows_clean = [self._strip_relation_keys(self._inject_updated_at(d)) for d in data]
        try:
            if skip_duplicates and self._conn.dialect_name == "postgresql":
                # Use a single multi-row INSERT with RETURNING to count only inserted rows
                from sqlalchemy import literal
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = pg_insert(self._table).values(rows_clean).on_conflict_do_nothing().returning(literal(1))
                rows = await self._conn.execute_write(stmt)
                return len(rows)
            elif skip_duplicates:
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert

                stmt = sqlite_insert(self._table).prefix_with("OR IGNORE")
                return await self._conn.execute_dml(stmt, rows_clean)
            else:
                stmt = insert(self._table)
                count = await self._conn.execute_dml(stmt, rows_clean)
                # asyncpg executemany always returns -1; all rows inserted or exception raised
                return len(rows_clean) if count == -1 else count
        except Exception as e:
            raise self._wrap_integrity_error(e) from e

    async def update(
        self,
        *,
        where: dict[str, Any],
        data: dict[str, Any],
        include: dict[str, Any] | None = None,
    ) -> T:
        data = await self._resolve_nested_writes(data)
        vals = self._build_update_values(self._inject_updated_at(data))
        clause = self._build_unique_where(where)
        stmt = update(self._table).where(clause).values(vals).returning(self._table)
        rows = await self._conn.execute_write(stmt)
        if not rows:
            raise RecordNotFoundError(f"No record found matching {where}")
        row_dict = dict(rows[0])
        await self._attach_includes([row_dict], include)
        return self._row_to_model(row_dict)

    async def update_many(
        self,
        *,
        where: dict[str, Any],
        data: dict[str, Any],
    ) -> int:
        vals = self._build_update_values(self._inject_updated_at(data))
        stmt = (
            update(self._table)
            .where(build_where(self._table, where, self._field_column_map, self._relations, self._all_metadata))
            .values(vals)
        )
        return await self._conn.execute_dml(stmt)

    async def delete(
        self,
        *,
        where: dict[str, Any],
    ) -> T | None:
        clause = self._build_unique_where(where)
        # Fetch first so we can return the deleted record
        existing = await self.find_unique(where=where)
        if existing is None:
            return None
        stmt = delete(self._table).where(clause)
        await self._conn.execute_write(stmt)
        return existing

    async def delete_many(
        self,
        *,
        where: dict[str, Any] | None = None,
    ) -> int:
        stmt = delete(self._table)
        if where:
            stmt = stmt.where(
                build_where(self._table, where, self._field_column_map, self._relations, self._all_metadata)
            )
        return await self._conn.execute_dml(stmt)

    async def upsert(
        self,
        *,
        where: dict[str, Any],
        create: dict[str, Any],
        update: dict[str, Any],
        include: dict[str, Any] | None = None,
    ) -> T:
        existing = await self.find_unique(where=where)
        if existing is None:
            return await self.create(data=create, include=include)
        return await self.update(where=where, data=update, include=include)

    async def count(
        self,
        *,
        where: dict[str, Any] | None = None,
        take: int | None = None,
        skip: int | None = None,
        select: dict[str, bool] | None = None,
    ) -> "int | dict[str, int]":
        if select:
            # COUNT(col) counts non-null values per field
            cols = [
                func.count(self._table.c[self._field_column_map.get(f, f)]).label(f) for f, v in select.items() if v
            ]
            stmt = select_sa(*cols).select_from(self._table)
            if where:
                stmt = stmt.where(
                    build_where(self._table, where, self._field_column_map, self._relations, self._all_metadata)
                )
            rows = await self._conn.execute(stmt)
            return dict(rows[0]) if rows else {f: 0 for f, v in select.items() if v}

        # Scalar count — optionally scoped to a take/skip window via subquery
        inner = select_sa(self._table)
        if where:
            inner = inner.where(
                build_where(self._table, where, self._field_column_map, self._relations, self._all_metadata)
            )
        if skip:
            inner = inner.offset(skip)
        if take is not None:
            inner = inner.limit(take)
        if take is not None or skip:
            stmt = select_sa(func.count().label("n")).select_from(inner.subquery())
        else:
            stmt = select_sa(func.count().label("n")).select_from(self._table)
            if where:
                stmt = stmt.where(
                    build_where(self._table, where, self._field_column_map, self._relations, self._all_metadata)
                )
        rows = await self._conn.execute(stmt)
        return rows[0]["n"] if rows else 0

    async def group_by(
        self,
        *,
        by: list[str],
        where: dict[str, Any] | None = None,
        count: dict[str, bool] | bool | None = None,
        avg: dict[str, bool] | None = None,
        sum_: dict[str, bool] | None = None,
        min_: dict[str, bool] | None = None,
        max_: dict[str, bool] | None = None,
        order_by: dict[str, str] | list[dict[str, str]] | None = None,
        take: int | None = None,
        skip: int | None = None,
    ) -> list[dict[str, Any]]:
        group_cols = [self._table.c[self._field_column_map.get(f, f)] for f in by]
        select_exprs: list[Any] = list(group_cols)

        if count is not None:
            if count is True or (isinstance(count, dict) and count.get("_all")):
                select_exprs.append(func.count().label("_count___all"))
            if isinstance(count, dict):
                for field, enabled in count.items():
                    if enabled and field != "_all":
                        col_name = self._field_column_map.get(field, field)
                        select_exprs.append(func.count(self._table.c[col_name]).label(f"_count__{field}"))

        for prefix, agg_dict, agg_fn in [
            ("_avg", avg, func.avg),
            ("_sum", sum_, func.sum),
            ("_min", min_, func.min),
            ("_max", max_, func.max),
        ]:
            if agg_dict:
                for field, enabled in agg_dict.items():
                    if enabled:
                        col_name = self._field_column_map.get(field, field)
                        select_exprs.append(agg_fn(self._table.c[col_name]).label(f"{prefix}__{field}"))

        stmt = select_sa(*select_exprs).select_from(self._table)
        if where:
            stmt = stmt.where(
                build_where(self._table, where, self._field_column_map, self._relations, self._all_metadata)
            )
        stmt = stmt.group_by(*group_cols)
        if order_by:
            orders = [order_by] if isinstance(order_by, dict) else order_by
            for o in orders:
                for field, direction in o.items():
                    col_name = self._field_column_map.get(field, field)
                    col = self._table.c[col_name]
                    stmt = stmt.order_by(col.asc() if direction == "asc" else col.desc())
        if skip:
            stmt = stmt.offset(skip)
        if take is not None:
            stmt = stmt.limit(take)

        rows = await self._conn.execute(stmt)

        results = []
        for row in rows:
            row_dict = dict(row)
            result: dict[str, Any] = {}
            for field in by:
                col_name = self._field_column_map.get(field, field)
                result[field] = row_dict.get(col_name)
            for key, value in row_dict.items():
                if "__" not in key:
                    continue
                agg_prefix, _, agg_field = key.partition("__")
                bucket = result.setdefault(agg_prefix, {})
                bucket[agg_field] = value
            results.append(result)
        return results
