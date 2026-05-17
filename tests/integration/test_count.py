"""Tests for count with select (field-level counts), take, and skip."""

from .prisma_test_case import PrismaTestCase


class TestCountSelect(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.users = [
            await self.db.user.create(
                data={"email": f"cnt{i}@test.com", "username": f"cnt{i}", "displayName": f"Count {i}"}
            )
            for i in range(1, 4)
        ]
        # Give one user a null-equivalent by creating a profile only for user 1
        self.profile = await self.db.profile.create(data={"userId": self.users[0].id, "bio": "hello"})

    async def asyncTearDown(self) -> None:
        await self.db.profile.delete(where={"id": self.profile.id})
        for u in self.users:
            try:
                await self.db.user.delete(where={"id": u.id})
            except Exception:
                pass
        await super().asyncTearDown()

    async def test_select_counts_non_null_values(self) -> None:
        result = await self.db.user.count(
            where={"email": {"in_": [u.email for u in self.users]}},
            select={"id": True, "email": True},
        )
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], 3)
        self.assertEqual(result["email"], 3)

    async def test_select_single_field(self) -> None:
        result = await self.db.user.count(
            where={"email": {"in_": [u.email for u in self.users]}},
            select={"id": True},
        )
        self.assertEqual(result["id"], 3)

    async def test_select_with_where_filter(self) -> None:
        result = await self.db.user.count(
            where={"email": {"in_": [self.users[0].email, self.users[1].email]}},
            select={"id": True},
        )
        self.assertEqual(result["id"], 2)

    async def test_profile_bio_nullable_count(self) -> None:
        # bio is nullable — only 1 profile has a bio set
        result = await self.db.profile.count(select={"bio": True})
        self.assertGreaterEqual(result["bio"], 1)


class TestCountTakeSkip(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.users = [
            await self.db.user.create(
                data={"email": f"cnts{i}@test.com", "username": f"cnts{i}", "displayName": f"CntS {i}"}
            )
            for i in range(1, 6)
        ]

    async def asyncTearDown(self) -> None:
        for u in self.users:
            try:
                await self.db.user.delete(where={"id": u.id})
            except Exception:
                pass
        await super().asyncTearDown()

    async def test_count_with_take(self) -> None:
        result = await self.db.user.count(
            where={"email": {"in_": [u.email for u in self.users]}},
            take=3,
        )
        self.assertEqual(result, 3)

    async def test_count_with_skip(self) -> None:
        result = await self.db.user.count(
            where={"email": {"in_": [u.email for u in self.users]}},
            skip=2,
        )
        self.assertEqual(result, 3)

    async def test_count_with_take_larger_than_set(self) -> None:
        result = await self.db.user.count(
            where={"email": {"in_": [u.email for u in self.users]}},
            take=100,
        )
        self.assertEqual(result, 5)

    async def test_count_with_take_and_skip(self) -> None:
        result = await self.db.user.count(
            where={"email": {"in_": [u.email for u in self.users]}},
            take=2,
            skip=2,
        )
        self.assertEqual(result, 2)

    async def test_count_skip_past_end_returns_zero(self) -> None:
        result = await self.db.user.count(
            where={"email": {"in_": [u.email for u in self.users]}},
            skip=10,
        )
        self.assertEqual(result, 0)
