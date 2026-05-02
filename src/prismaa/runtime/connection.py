from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import CursorResult, TextClause
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.sql import ClauseElement


class AsyncConnectionManager:
    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None

    async def connect(self, url: str) -> None:
        self._engine = create_async_engine(url)

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

    async def __aenter__(self) -> AsyncConnectionManager:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.disconnect()
