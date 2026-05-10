"""Integration tests for find_first on the User model."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from prisma import Prisma

_SCHEMA_PATH = Path(__file__).parent.parent / "fixtures" / "schema.prisma"


class TestFindFirst(unittest.IsolatedAsyncioTestCase):
    _db_path: Path

    @classmethod
    def setUpClass(cls) -> None:
        tmp = tempfile.mkdtemp()
        cls._db_path = Path(tmp) / "test.db"
        subprocess.run(
            [
                "npx",
                "--yes",
                "prisma",
                "db",
                "push",
                "--schema",
                str(_SCHEMA_PATH),
                f"--url=file:{cls._db_path}",
                "--accept-data-loss",
            ],
            check=True,
        )

    async def asyncSetUp(self) -> None:
        self.db = Prisma()
        await self.db.connect(f"sqlite+aiosqlite:///{self._db_path}")

    async def asyncTearDown(self) -> None:
        await self.db.disconnect()

    async def test_returns_none_when_no_rows_match(self) -> None:
        result = await self.db.user.find_first(where={"email": "nonexistent@test.com"})
        self.assertIsNone(result)

    async def test_returns_a_row_when_match_exists(self) -> None:
        u = await self.db.user.create(data={"email": "ff1@test.com", "username": "ff1", "displayName": "FF1"})
        result = await self.db.user.find_first(where={"email": "ff1@test.com"})
        self.assertIsNotNone(result)
        self.assertEqual(result.id, u.id)
        await self.db.user.delete(where={"id": u.id})

    async def test_respects_order_when_multiple_match(self) -> None:
        u1 = await self.db.user.create(data={"email": "ff2a@test.com", "username": "ff2a", "displayName": "Beta"})
        u2 = await self.db.user.create(data={"email": "ff2b@test.com", "username": "ff2b", "displayName": "Alpha"})
        result = await self.db.user.find_first(
            where={"email": {"in_": ["ff2a@test.com", "ff2b@test.com"]}},
            order={"displayName": "asc"},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.displayName, "Alpha")
        await self.db.user.delete(where={"id": u1.id})
        await self.db.user.delete(where={"id": u2.id})

    async def test_skip_offsets_before_taking_first(self) -> None:
        u1 = await self.db.user.create(data={"email": "ff3a@test.com", "username": "ff3a", "displayName": "First"})
        u2 = await self.db.user.create(data={"email": "ff3b@test.com", "username": "ff3b", "displayName": "Second"})
        result = await self.db.user.find_first(
            where={"email": {"in_": ["ff3a@test.com", "ff3b@test.com"]}},
            order={"displayName": "asc"},
            skip=1,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.displayName, "Second")
        await self.db.user.delete(where={"id": u1.id})
        await self.db.user.delete(where={"id": u2.id})

    async def test_without_where_returns_some_row(self) -> None:
        u = await self.db.user.create(data={"email": "ff4@test.com", "username": "ff4", "displayName": "FF4"})
        result = await self.db.user.find_first()
        self.assertIsNotNone(result)
        await self.db.user.delete(where={"id": u.id})
