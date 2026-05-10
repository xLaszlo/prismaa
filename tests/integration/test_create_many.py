"""Tests for create_many (bulk insert) and delete_many / update_many."""

from .prisma_test_case import PrismaTestCase


class TestCreateMany(PrismaTestCase):
    async def test_bulk_insert_returns_count(self) -> None:
        count = await self.db.user.create_many(
            data=[
                {"email": "bulk1@test.com", "username": "bulk1", "displayName": "B1"},
                {"email": "bulk2@test.com", "username": "bulk2", "displayName": "B2"},
                {"email": "bulk3@test.com", "username": "bulk3", "displayName": "B3"},
            ]
        )
        self.assertEqual(count, 3)
        await self.db.user.delete_many(where={"email": {"in_": ["bulk1@test.com", "bulk2@test.com", "bulk3@test.com"]}})

    async def test_bulk_insert_empty_list_returns_zero(self) -> None:
        count = await self.db.user.create_many(data=[])
        self.assertEqual(count, 0)

    async def test_skip_duplicates_ignores_conflicts(self) -> None:
        await self.db.user.create(data={"email": "dup@test.com", "username": "dup1", "displayName": "Dup"})
        count = await self.db.user.create_many(
            data=[
                {"email": "dup@test.com", "username": "dup1", "displayName": "Dup"},
                {"email": "new_dup@test.com", "username": "new_dup", "displayName": "New"},
            ],
            skip_duplicates=True,
        )
        self.assertEqual(count, 1)
        await self.db.user.delete_many(where={"email": {"in_": ["dup@test.com", "new_dup@test.com"]}})


class TestDeleteMany(PrismaTestCase):
    async def test_delete_many_with_where(self) -> None:
        await self.db.user.create_many(
            data=[
                {"email": "dm1@test.com", "username": "dm1", "displayName": "DM", "isActive": False},
                {"email": "dm2@test.com", "username": "dm2", "displayName": "DM", "isActive": False},
                {"email": "dm3@test.com", "username": "dm3", "displayName": "DM", "isActive": True},
            ]
        )
        deleted = await self.db.user.delete_many(
            where={"isActive": False, "email": {"in_": ["dm1@test.com", "dm2@test.com", "dm3@test.com"]}}
        )
        self.assertEqual(deleted, 2)
        remaining = await self.db.user.find_many(
            where={"email": {"in_": ["dm1@test.com", "dm2@test.com", "dm3@test.com"]}}
        )
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].email, "dm3@test.com")
        await self.db.user.delete(where={"email": "dm3@test.com"})


class TestUpdateMany(PrismaTestCase):
    async def test_update_many_matching_records(self) -> None:
        await self.db.user.create_many(
            data=[
                {"email": "um1@test.com", "username": "um1", "displayName": "UM", "score": 1.0},
                {"email": "um2@test.com", "username": "um2", "displayName": "UM", "score": 1.0},
                {"email": "um3@test.com", "username": "um3", "displayName": "Other", "score": 1.0},
            ]
        )
        updated = await self.db.user.update_many(
            where={"displayName": "UM", "email": {"in_": ["um1@test.com", "um2@test.com", "um3@test.com"]}},
            data={"score": 99.0},
        )
        self.assertEqual(updated, 2)
        users = await self.db.user.find_many(where={"email": {"in_": ["um1@test.com", "um2@test.com"]}})
        self.assertTrue(all(u.score == 99.0 for u in users))
        await self.db.user.delete_many(where={"email": {"in_": ["um1@test.com", "um2@test.com", "um3@test.com"]}})
