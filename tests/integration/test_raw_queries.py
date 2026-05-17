"""Tests for raw query execution: query_raw, execute_raw, query_first."""

from .prisma_test_case import PrismaTestCase


class TestQueryRaw(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "raw@test.com", "username": "raw_user", "displayName": "Raw", "score": 42.0}
        )

    async def asyncTearDown(self) -> None:
        try:
            await self.db.user.delete(where={"id": self.user.id})
        except Exception:
            pass
        await super().asyncTearDown()

    async def test_query_raw_returns_rows(self) -> None:
        rows = await self.db.query_raw('SELECT id, email FROM "User" WHERE id = ?', self.user.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["email"], "raw@test.com")

    async def test_query_raw_named_param(self) -> None:
        rows = await self.db.query_raw('SELECT id, email FROM "User" WHERE id = :uid', uid=self.user.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], self.user.id)

    async def test_query_raw_no_results(self) -> None:
        rows = await self.db.query_raw('SELECT * FROM "User" WHERE id = ?', -1)
        self.assertEqual(rows, [])

    async def test_query_raw_multiple_rows(self) -> None:
        other = await self.db.user.create(data={"email": "raw2@test.com", "username": "raw2", "displayName": "Raw2"})
        rows = await self.db.query_raw(
            'SELECT id FROM "User" WHERE email IN (:e1, :e2)',
            e1="raw@test.com",
            e2="raw2@test.com",
        )
        self.assertEqual(len(rows), 2)
        await self.db.user.delete(where={"id": other.id})


class TestQueryFirst(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "rawf@test.com", "username": "rawf_user", "displayName": "RawFirst"}
        )

    async def asyncTearDown(self) -> None:
        try:
            await self.db.user.delete(where={"id": self.user.id})
        except Exception:
            pass
        await super().asyncTearDown()

    async def test_query_first_returns_single_row(self) -> None:
        row = await self.db.query_first('SELECT id, email FROM "User" WHERE id = ?', self.user.id)
        self.assertIsNotNone(row)
        self.assertEqual(row["email"], "rawf@test.com")

    async def test_query_first_returns_none_when_no_match(self) -> None:
        row = await self.db.query_first('SELECT * FROM "User" WHERE id = ?', -1)
        self.assertIsNone(row)


class TestExecuteRaw(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "rawe@test.com", "username": "rawe_user", "displayName": "RawExec", "score": 1.0}
        )

    async def asyncTearDown(self) -> None:
        try:
            await self.db.user.delete(where={"id": self.user.id})
        except Exception:
            pass
        await super().asyncTearDown()

    async def test_execute_raw_returns_affected_count(self) -> None:
        count = await self.db.execute_raw('UPDATE "User" SET score = ? WHERE id = ?', 99.0, self.user.id)
        self.assertEqual(count, 1)
        updated = await self.db.user.find_unique(where={"id": self.user.id})
        self.assertAlmostEqual(updated.score, 99.0)

    async def test_execute_raw_no_match_returns_zero(self) -> None:
        count = await self.db.execute_raw('UPDATE "User" SET score = ? WHERE id = ?', 0.0, -1)
        self.assertEqual(count, 0)
