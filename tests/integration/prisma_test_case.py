"""Base test case for integration tests that need a real SQLite database."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from prisma import Prisma

_SCHEMA_PATH = Path(__file__).parent.parent / "fixtures" / "schema.prisma"


class PrismaTestCase(unittest.IsolatedAsyncioTestCase):
    """Spins up a fresh SQLite DB once per class and connects a Prisma client per test."""

    _db_url: str
    db: Prisma

    @classmethod
    def setUpClass(cls) -> None:
        tmp = tempfile.mkdtemp()
        db_path = Path(tmp) / "test.db"
        subprocess.run(
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
            ],
            check=True,
        )
        cls._db_url = f"sqlite+aiosqlite:///{db_path}"

    async def asyncSetUp(self) -> None:
        self.db = Prisma()
        await self.db.connect(self._db_url)

    async def asyncTearDown(self) -> None:
        await self.db.disconnect()
