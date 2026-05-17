from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import CursorResult, TextClause, event, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.sql import ClauseElement


class AsyncConnectionManager:
    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None

    async def connect(self, url: str) -> None:
        engine = create_async_engine(url)
        if url.startswith("sqlite"):

            @event.listens_for(engine.sync_engine, "connect")
            def _set_sqlite_pragma(dbapi_conn, _):
                dbapi_conn.execute("PRAGMA foreign_keys=ON")

        self._engine = engine

    async def disconnect(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    async def execute(self, stmt: ClauseElement | TextClause) -> Sequence[Any]:
        if self._engine is None:
            raise RuntimeError("Not connected — call connect() first")
        async with self._engine.connect() as conn:
            result: CursorResult = await conn.execute(stmt)
            return result.mappings().all()

    async def execute_write(self, stmt: ClauseElement) -> Sequence[Any]:
        """Execute a DML statement inside a committed transaction, returning rows if available."""
        if self._engine is None:
            raise RuntimeError("Not connected — call connect() first")
        async with self._engine.begin() as conn:
            result: CursorResult = await conn.execute(stmt)
            return result.mappings().all() if result.returns_rows else []

    async def execute_dml(self, stmt: ClauseElement, data: Any = None) -> int:
        if self._engine is None:
            raise RuntimeError("Not connected — call connect() first")
        async with self._engine.begin() as conn:
            result: CursorResult = await conn.execute(stmt, data) if data is not None else await conn.execute(stmt)
            return result.rowcount

    @property
    def dialect_name(self) -> str:
        if self._engine is None:
            return "sqlite"
        return self._engine.dialect.name

    @staticmethod
    def _prepare_raw(sql: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[TextClause, dict[str, Any]]:
        """Convert positional ? placeholders to :p0, :p1, … and merge with kwargs."""
        params = dict(kwargs)
        if args:
            parts = sql.split("?")
            if len(parts) != len(args) + 1:
                raise ValueError(f"Expected {len(parts) - 1} positional parameter(s), got {len(args)}")
            sql = "".join(seg + (f":p{i}" if i < len(args) else "") for i, seg in enumerate(parts))
            params.update({f"p{i}": v for i, v in enumerate(args)})
        return text(sql), params

    async def query_raw(self, sql: str, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        if self._engine is None:
            raise RuntimeError("Not connected — call connect() first")
        stmt, params = self._prepare_raw(sql, args, kwargs)
        async with self._engine.connect() as conn:
            result = await conn.execute(stmt, params)
            return [dict(row) for row in result.mappings()]

    async def execute_raw(self, sql: str, *args: Any, **kwargs: Any) -> int:
        if self._engine is None:
            raise RuntimeError("Not connected — call connect() first")
        stmt, params = self._prepare_raw(sql, args, kwargs)
        async with self._engine.begin() as conn:
            result = await conn.execute(stmt, params)
            return result.rowcount

    async def query_first(self, sql: str, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        rows = await self.query_raw(sql, *args, **kwargs)
        return rows[0] if rows else None

    async def __aenter__(self) -> AsyncConnectionManager:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.disconnect()


class TransactionConnectionManager:
    """Wraps a single open AsyncConnection for use within an explicit transaction.

    SQLAlchemy's engine.begin() handles commit/rollback automatically, so this
    class just forwards operations to the shared connection without lifecycle methods.
    """

    def __init__(self, conn: AsyncConnection) -> None:
        self._conn = conn

    @property
    def dialect_name(self) -> str:
        return self._conn.dialect.name

    async def execute(self, stmt: ClauseElement | TextClause) -> Sequence[Any]:
        result: CursorResult = await self._conn.execute(stmt)
        return result.mappings().all()

    async def execute_write(self, stmt: ClauseElement) -> Sequence[Any]:
        result: CursorResult = await self._conn.execute(stmt)
        return result.mappings().all() if result.returns_rows else []

    async def execute_dml(self, stmt: ClauseElement, data: Any = None) -> int:
        result: CursorResult = (
            await self._conn.execute(stmt, data) if data is not None else await self._conn.execute(stmt)
        )
        return result.rowcount
