"""Integration tests for Prisma client connection lifecycle."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from prisma import Prisma

_SCHEMA_PATH = Path(__file__).parent.parent / "fixtures" / "schema.prisma"


class TestConnectionLifecycle(unittest.IsolatedAsyncioTestCase):
    _db_url: str

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

    async def test_explicit_connect_and_disconnect(self) -> None:
        db = Prisma()
        await db.connect(self._db_url)
        count = await db.user.count()
        self.assertGreaterEqual(count, 0)
        await db.disconnect()
        with self.assertRaises(RuntimeError):
            await db.user.count()

    async def test_query_before_connect_raises(self) -> None:
        db = Prisma()
        with self.assertRaises(RuntimeError):
            await db.user.count()

    async def test_context_manager_disconnects_on_exit(self) -> None:
        db = Prisma()
        async with db:
            await db.connect(self._db_url)
            count = await db.user.count()
            self.assertGreaterEqual(count, 0)
        with self.assertRaises(RuntimeError):
            await db.user.count()

    async def test_disconnect_without_connect_is_safe(self) -> None:
        db = Prisma()
        await db.disconnect()

    async def test_double_connect_is_safe(self) -> None:
        db = Prisma()
        await db.connect(self._db_url)
        await db.connect(self._db_url)
        await db.disconnect()
