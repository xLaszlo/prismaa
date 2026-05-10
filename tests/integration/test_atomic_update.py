"""Tests for atomic update operators: increment, decrement, multiply, divide."""

from .prisma_test_case import PrismaTestCase


class TestAtomicUpdate(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "atomic@test.com", "username": "atomic_user", "displayName": "Atomic", "score": 10.0}
        )

    async def asyncTearDown(self) -> None:
        try:
            await self.db.user.delete(where={"id": self.user.id})
        except Exception:
            pass
        await super().asyncTearDown()

    async def test_increment(self) -> None:
        updated = await self.db.user.update(
            where={"id": self.user.id},
            data={"score": {"increment": 5.0}},
        )
        self.assertEqual(updated.score, 15.0)

    async def test_decrement(self) -> None:
        updated = await self.db.user.update(
            where={"id": self.user.id},
            data={"score": {"decrement": 3.0}},
        )
        self.assertEqual(updated.score, 7.0)

    async def test_multiply(self) -> None:
        updated = await self.db.user.update(
            where={"id": self.user.id},
            data={"score": {"multiply": 2.0}},
        )
        self.assertEqual(updated.score, 20.0)

    async def test_divide(self) -> None:
        updated = await self.db.user.update(
            where={"id": self.user.id},
            data={"score": {"divide": 4.0}},
        )
        self.assertEqual(updated.score, 2.5)

    async def test_atomic_mixed_with_plain_field(self) -> None:
        updated = await self.db.user.update(
            where={"id": self.user.id},
            data={"score": {"increment": 1.0}, "displayName": "Updated"},
        )
        self.assertEqual(updated.score, 11.0)
        self.assertEqual(updated.displayName, "Updated")

    async def test_atomic_update_many(self) -> None:
        await self.db.user.create(
            data={"email": "atomic2@test.com", "username": "atomic2", "displayName": "Atomic2", "score": 10.0}
        )
        count = await self.db.user.update_many(
            where={"email": {"in_": ["atomic@test.com", "atomic2@test.com"]}},
            data={"score": {"increment": 5.0}},
        )
        self.assertEqual(count, 2)
        users = await self.db.user.find_many(where={"email": {"in_": ["atomic@test.com", "atomic2@test.com"]}})
        self.assertTrue(all(u.score == 15.0 for u in users))
        await self.db.user.delete(where={"email": "atomic2@test.com"})
