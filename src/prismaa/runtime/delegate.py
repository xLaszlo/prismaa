from __future__ import annotations

import datetime
from typing import Any, Generic, Type, TypeVar

from sqlalchemy import Table, and_, delete, func, insert, select, update

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
        now = datetime.datetime.now(datetime.timezone.utc)
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
    ) -> T | None:
        self._validate_unique_where(where)
        clause = self._build_unique_where(where)
        stmt = select(self._table).where(clause)
        rows = await self._conn.execute(stmt)
        if not rows:
            return None
        row_dicts = [dict(r) for r in rows]
        await self._attach_includes(row_dicts, include)
        return self._row_to_model(row_dicts[0])

    async def find_first(
        self,
        *,
        where: dict[str, Any] | None = None,
        include: dict[str, Any] | None = None,
        order: dict[str, str] | list[dict[str, str]] | None = None,
        skip: int | None = None,
    ) -> T | None:
        results = await self.find_many(where=where, include=include, order=order, skip=skip, take=1)
        return results[0] if results else None

    async def find_many(
        self,
        *,
        where: dict[str, Any] | None = None,
        include: dict[str, Any] | None = None,
        order: dict[str, str] | list[dict[str, str]] | None = None,
        take: int | None = None,
        skip: int | None = None,
    ) -> list[T]:
        stmt = select(self._table)
        if where:
            stmt = stmt.where(build_where(self._table, where, self._field_column_map))
        if order:
            orders = [order] if isinstance(order, dict) else order
            for o in orders:
                for field, direction in o.items():
                    col_name = self._field_column_map.get(field, field)
                    col = self._table.c[col_name]
                    stmt = stmt.order_by(col.asc() if direction == "asc" else col.desc())
        if skip:
            stmt = stmt.offset(skip)
        if take:
            stmt = stmt.limit(take)
        rows = await self._conn.execute(stmt)
        row_dicts = [dict(r) for r in rows]
        await self._attach_includes(row_dicts, include)
        return [self._row_to_model(r) for r in row_dicts]

    async def create(
        self,
        *,
        data: dict[str, Any],
        include: dict[str, Any] | None = None,
    ) -> T:
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
        stmt = insert(self._table)
        if skip_duplicates:
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            stmt = sqlite_insert(self._table).prefix_with("OR IGNORE")
        try:
            return await self._conn.execute_dml(stmt, rows_clean)
        except Exception as e:
            raise self._wrap_integrity_error(e) from e

    async def update(
        self,
        *,
        where: dict[str, Any],
        data: dict[str, Any],
        include: dict[str, Any] | None = None,
    ) -> T:
        clean = self._strip_relation_keys(self._inject_updated_at(data))
        clause = self._build_unique_where(where)
        stmt = update(self._table).where(clause).values(**clean).returning(self._table)
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
        clean = self._strip_relation_keys(self._inject_updated_at(data))
        stmt = update(self._table).where(build_where(self._table, where, self._field_column_map)).values(**clean)
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
        stmt = select(func.count().label("n")).select_from(self._table)
        if where:
            stmt = stmt.where(build_where(self._table, where, self._field_column_map))
        rows = await self._conn.execute(stmt)
        return rows[0]["n"] if rows else 0
