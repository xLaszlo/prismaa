"""Tests for find_unique_or_raise and find_first_or_raise."""

from prismaa.runtime.errors import RecordNotFoundError

from .prisma_test_case import PrismaTestCase


class TestFindUniqueOrRaise(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "raise@test.com", "username": "raise_user", "displayName": "Raise"}
        )

    async def asyncTearDown(self) -> None:
        try:
            await self.db.user.delete(where={"id": self.user.id})
        except Exception:
            pass
        await super().asyncTearDown()

    async def test_returns_record_when_found(self) -> None:
        result = await self.db.user.find_unique_or_raise(where={"id": self.user.id})
        self.assertEqual(result.id, self.user.id)
        self.assertEqual(result.email, "raise@test.com")

    async def test_raises_when_not_found(self) -> None:
        with self.assertRaises(RecordNotFoundError):
            await self.db.user.find_unique_or_raise(where={"id": 999999})

    async def test_supports_include(self) -> None:
        result = await self.db.user.find_unique_or_raise(
            where={"id": self.user.id},
            include={"profile": True},
        )
        self.assertEqual(result.id, self.user.id)
        self.assertIsNone(result.profile)

    async def test_supports_select(self) -> None:
        result = await self.db.user.find_unique_or_raise(
            where={"id": self.user.id},
            select={"id": True, "email": True},
        )
        self.assertEqual(result.email, "raise@test.com")


class TestFindFirstOrRaise(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.u1 = await self.db.user.create(
            data={"email": "for1@test.com", "username": "for1", "displayName": "FOR1", "score": 1.0}
        )
        self.u2 = await self.db.user.create(
            data={"email": "for2@test.com", "username": "for2", "displayName": "FOR2", "score": 2.0}
        )

    async def asyncTearDown(self) -> None:
        for u in (self.u1, self.u2):
            try:
                await self.db.user.delete(where={"id": u.id})
            except Exception:
                pass
        await super().asyncTearDown()

    async def test_returns_first_matching_record(self) -> None:
        result = await self.db.user.find_first_or_raise(
            where={"email": {"startswith": "for"}},
            order={"score": "asc"},
        )
        self.assertEqual(result.email, "for1@test.com")

    async def test_raises_when_no_match(self) -> None:
        with self.assertRaises(RecordNotFoundError):
            await self.db.user.find_first_or_raise(where={"email": "nonexistent@test.com"})

    async def test_raises_on_empty_table_result(self) -> None:
        with self.assertRaises(RecordNotFoundError):
            await self.db.user.find_first_or_raise(where={"score": {"gt": 9999.0}})
