from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import CursorResult, TextClause, event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
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

    async def __aenter__(self) -> AsyncConnectionManager:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.disconnect()
