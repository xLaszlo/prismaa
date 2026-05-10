"""Tests for distinct and count aggregation."""

from .prisma_test_case import PrismaTestCase

_EMAILS = ["agg1@test.com", "agg2@test.com", "agg3@test.com"]


class TestDistinct(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await self.db.user.create_many(
            data=[
                {"email": "agg1@test.com", "username": "agg1", "displayName": "AGG1", "isActive": True},
                {"email": "agg2@test.com", "username": "agg2", "displayName": "AGG2", "isActive": True},
                {"email": "agg3@test.com", "username": "agg3", "displayName": "AGG3", "isActive": False},
            ]
        )

    async def asyncTearDown(self) -> None:
        await self.db.user.delete_many(where={"email": {"in_": _EMAILS}})
        await super().asyncTearDown()

    async def test_distinct_returns_one_row_per_value(self) -> None:
        results = await self.db.user.find_many(
            where={"email": {"in_": _EMAILS}},
            distinct=["isActive"],
        )
        self.assertEqual(len(results), 2)
        self.assertEqual({r.isActive for r in results}, {True, False})

    async def test_distinct_with_order(self) -> None:
        results = await self.db.user.find_many(
            where={"email": {"in_": _EMAILS}},
            distinct=["isActive"],
            order={"isActive": "asc"},
        )
        self.assertEqual(len(results), 2)
        self.assertFalse(results[0].isActive)
        self.assertTrue(results[1].isActive)

    async def test_distinct_with_take(self) -> None:
        results = await self.db.user.find_many(
            where={"email": {"in_": _EMAILS}},
            distinct=["isActive"],
            take=1,
        )
        self.assertEqual(len(results), 1)


class TestCount(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        await self.db.user.create_many(
            data=[
                {"email": "cnt1@test.com", "username": "cnt1", "displayName": "C1", "isActive": True},
                {"email": "cnt2@test.com", "username": "cnt2", "displayName": "C2", "isActive": True},
                {"email": "cnt3@test.com", "username": "cnt3", "displayName": "C3", "isActive": False},
            ]
        )

    async def asyncTearDown(self) -> None:
        await self.db.user.delete_many(where={"email": {"in_": ["cnt1@test.com", "cnt2@test.com", "cnt3@test.com"]}})
        await super().asyncTearDown()

    async def test_count_with_bool_filter(self) -> None:
        count = await self.db.user.count(
            where={"isActive": True, "email": {"in_": ["cnt1@test.com", "cnt2@test.com", "cnt3@test.com"]}}
        )
        self.assertEqual(count, 2)

    async def test_count_with_string_filter(self) -> None:
        count = await self.db.user.count(where={"email": {"startswith": "cnt"}})
        self.assertEqual(count, 3)


class TestCountEmptyTable(PrismaTestCase):
    async def test_count_empty_returns_zero(self) -> None:
        count = await self.db.category.count()
        self.assertEqual(count, 0)
