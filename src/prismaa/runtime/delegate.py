from __future__ import annotations

import datetime
from typing import Any, Generic, Type, TypeVar

from sqlalchemy import Table, and_, delete, func, insert, update
from sqlalchemy import select as select_sa

from .connection import AsyncConnectionManager
from .errors import ForeignKeyViolationError, RecordNotFoundError, UniqueViolationError
from .include import load_relations
from .where import build_where

T = TypeVar("T")


class AsyncModelDelegate(Generic[T]):
    def __init__(
        self,
        *,
        table: Table,
        model_cls: Type[T],
        field_column_map: dict[str, str],
        relations: list[dict[str, Any]],
        unique_fields: list[str],
        updated_at_fields: list[str],
        all_tables: dict[str, Table],
        all_models: dict[str, Any],
        all_field_column_maps: dict[str, dict[str, str]],
        all_relations: dict[str, list[dict[str, Any]]],
        conn: AsyncConnectionManager,
    ) -> None:
        self._table = table
        self._model_cls = model_cls
        self._field_column_map = field_column_map
        self._col_to_field_map = {v: k for k, v in field_column_map.items()}
        self._relations = relations
        self._unique_fields = unique_fields
        self._updated_at_fields = updated_at_fields
        self._all_tables = all_tables
        self._all_models = all_models
        self._all_field_column_maps = all_field_column_maps
        self._all_relations = all_relations
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
                self._all_tables,
                self._all_models,
                self._conn,
                all_field_column_maps=self._all_field_column_maps,
                all_relations=self._all_relations,
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
            name = rel["name"]
            fk_fields: list[str] = rel.get("fk_fields", [])
            references: list[str] = rel.get("references", [])
            if name not in result or not fk_fields:
                continue
            val = result.pop(name)
            if not isinstance(val, dict):
                continue
            if "connect" in val:
                connect_where = val["connect"]
                for fk_col, ref_field in zip(fk_fields, references, strict=True):
                    field_name = self._col_to_field_map.get(fk_col, fk_col)
                    result[field_name] = connect_where.get(ref_field)
            elif "disconnect" in val:
                for fk_col in fk_fields:
                    field_name = self._col_to_field_map.get(fk_col, fk_col)
                    result[field_name] = None
            elif "connectOrCreate" in val:
                coc = val["connectOrCreate"]
                where_data: dict[str, Any] = coc["where"]
                create_data: dict[str, Any] = coc["create"]
                related_model = rel["model"]
                related_table = self._all_tables[related_model]
                related_fcm = self._all_field_column_maps[related_model]
                # Try to find the existing related record
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
                for fk_col, ref_field in zip(fk_fields, references, strict=True):
                    field_name = self._col_to_field_map.get(fk_col, fk_col)
                    result[field_name] = row.get(ref_field)
        return result

    @staticmethod
    def _wrap_integrity_error(exc: Exception) -> Exception:
        msg = str(exc).upper()
        if "FOREIGN KEY" in msg:
            return ForeignKeyViolationError(str(exc))
        if "UNIQUE" in msg:
            return UniqueViolationError(str(exc))
        return exc

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
    ) -> list[T]:
        if select:
            self._validate_select(select)
        stmt = select_sa(self._table)
        if where:
            stmt = stmt.where(build_where(self._table, where, self._field_column_map))
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
        stmt = update(self._table).where(build_where(self._table, where, self._field_column_map)).values(vals)
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
            stmt = stmt.where(build_where(self._table, where, self._field_column_map))
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

    async def count(self, *, where: dict[str, Any] | None = None) -> int:
        stmt = select_sa(func.count().label("n")).select_from(self._table)
        if where:
            stmt = stmt.where(build_where(self._table, where, self._field_column_map))
        rows = await self._conn.execute(stmt)
        return rows[0]["n"] if rows else 0
