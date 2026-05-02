"""Tests for create_many (bulk insert) and delete_many / update_many."""

from prisma import Prisma


class TestCreateMany:
    async def test_bulk_insert_returns_count(self, db: Prisma) -> None:
        count = await db.user.create_many(
            data=[
                {"email": "bulk1@test.com", "username": "bulk1", "displayName": "B1"},
                {"email": "bulk2@test.com", "username": "bulk2", "displayName": "B2"},
                {"email": "bulk3@test.com", "username": "bulk3", "displayName": "B3"},
            ]
        )
        assert count == 3
        await db.user.delete_many(where={"email": {"in_": ["bulk1@test.com", "bulk2@test.com", "bulk3@test.com"]}})

    async def test_bulk_insert_empty_list_returns_zero(self, db: Prisma) -> None:
        count = await db.user.create_many(data=[])
        assert count == 0

    async def test_skip_duplicates_ignores_conflicts(self, db: Prisma) -> None:
        await db.user.create(data={"email": "dup@test.com", "username": "dup1", "displayName": "Dup"})
        count = await db.user.create_many(
            data=[
                {"email": "dup@test.com", "username": "dup1", "displayName": "Dup"},  # duplicate
                {"email": "new_dup@test.com", "username": "new_dup", "displayName": "New"},
            ],
            skip_duplicates=True,
        )
        # Only the non-duplicate should be inserted
        assert count == 1
        await db.user.delete_many(where={"email": {"in_": ["dup@test.com", "new_dup@test.com"]}})


class TestDeleteMany:
    async def test_delete_many_with_where(self, db: Prisma) -> None:
        await db.user.create_many(
            data=[
                {"email": "dm1@test.com", "username": "dm1", "displayName": "DM", "isActive": False},
                {"email": "dm2@test.com", "username": "dm2", "displayName": "DM", "isActive": False},
                {"email": "dm3@test.com", "username": "dm3", "displayName": "DM", "isActive": True},
            ]
        )
        deleted = await db.user.delete_many(
            where={"isActive": False, "email": {"in_": ["dm1@test.com", "dm2@test.com", "dm3@test.com"]}}
        )
        assert deleted == 2
        remaining = await db.user.find_many(where={"email": {"in_": ["dm1@test.com", "dm2@test.com", "dm3@test.com"]}})
        assert len(remaining) == 1
        assert remaining[0].email == "dm3@test.com"
        await db.user.delete(where={"email": "dm3@test.com"})


class TestUpdateMany:
    async def test_update_many_matching_records(self, db: Prisma) -> None:
        await db.user.create_many(
            data=[
                {"email": "um1@test.com", "username": "um1", "displayName": "UM", "score": 1.0},
                {"email": "um2@test.com", "username": "um2", "displayName": "UM", "score": 1.0},
                {"email": "um3@test.com", "username": "um3", "displayName": "Other", "score": 1.0},
            ]
        )
        updated = await db.user.update_many(
            where={"displayName": "UM", "email": {"in_": ["um1@test.com", "um2@test.com", "um3@test.com"]}},
            data={"score": 99.0},
        )
        assert updated == 2
        users = await db.user.find_many(where={"email": {"in_": ["um1@test.com", "um2@test.com"]}})
        assert all(u.score == 99.0 for u in users)
        await db.user.delete_many(where={"email": {"in_": ["um1@test.com", "um2@test.com", "um3@test.com"]}})
