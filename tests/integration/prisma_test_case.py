"""Base test case for integration tests that work against SQLite or PostgreSQL."""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from prisma import Prisma
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

_SCHEMA_PATH = Path(__file__).parent.parent / "fixtures" / "schema.prisma"
_PG_SCHEMA_PATH = Path(__file__).parent.parent / "fixtures" / "schema.postgresql.prisma"


def _prisma_push(cmd: list[str]) -> None:
    """Run prisma db push, raising RuntimeError with full CLI output on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"prisma db push failed (exit {result.returncode}):\n" f"{result.stdout}\n{result.stderr}".strip()
        )


async def _truncate_all_pg(url: str) -> None:
    """Truncate all public tables in PostgreSQL to give each test class a clean slate."""
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
            tables = [row[0] for row in result]
            if tables:
                quoted = ", ".join(f'"{t}"' for t in tables)
                await conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
    finally:
        await engine.dispose()


class PrismaTestCase(unittest.IsolatedAsyncioTestCase):
    """Spins up (or reuses) a DB once per class and connects a Prisma client per test.

    Set TEST_DATABASE_URL to run the full suite against PostgreSQL instead of SQLite.
    """

    _db_url: str
    db: Prisma

    @classmethod
    def setUpClass(cls) -> None:
        pg_url = os.environ.get("TEST_DATABASE_URL")
        if pg_url:
            # Prisma v7 requires --url on the CLI; strip the SQLAlchemy dialect prefix
            prisma_url = pg_url.replace("postgresql+asyncpg://", "postgresql://")
            _prisma_push(
                [
                    "npx",
                    "--yes",
                    "prisma",
                    "db",
                    "push",
                    "--schema",
                    str(_PG_SCHEMA_PATH),
                    f"--url={prisma_url}",
                    "--accept-data-loss",
                ]
            )
            asyncio.run(_truncate_all_pg(pg_url))
            cls._db_url = pg_url
        else:
            tmp = tempfile.mkdtemp()
            db_path = Path(tmp) / "test.db"
            _prisma_push(
                [
                    "npx",
                    "--yes",
                    "prisma",
                    "db",
                    "push",
                    "--schema",
                    str(_SCHEMA_PATH),
                    f"--url=file:{db_path}",
                    "--accept-data-loss",
                ]
            )
            cls._db_url = f"sqlite+aiosqlite:///{db_path}"

    async def asyncSetUp(self) -> None:
        self.db = Prisma()
        await self.db.connect(self._db_url)

    async def asyncTearDown(self) -> None:
        await self.db.disconnect()
