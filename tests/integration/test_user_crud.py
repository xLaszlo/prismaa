"""End-to-end CRUD tests for the User model against a real SQLite database."""

import pytest
from prisma import Prisma

from prismaa.runtime.errors import RecordNotFoundError


class TestUserCreate:
    async def test_create_returns_model_with_id(self, db: Prisma) -> None:
        user = await db.user.create(data={"email": "alice@test.com", "username": "alice", "displayName": "Alice"})
        assert user.id is not None
        assert user.id > 0
        assert user.email == "alice@test.com"
        assert user.username == "alice"
        assert user.displayName == "Alice"
        await db.user.delete(where={"id": user.id})

    async def test_create_applies_scalar_defaults(self, db: Prisma) -> None:
        user = await db.user.create(data={"email": "bob@test.com", "username": "bob", "displayName": "Bob"})
        assert user.isActive is True
        assert user.score == 0.0
        assert user.createdAt is not None
        assert user.updatedAt is not None
        await db.user.delete(where={"id": user.id})

    async def test_create_with_optional_fields_overridden(self, db: Prisma) -> None:
        user = await db.user.create(
            data={
                "email": "carol@test.com",
                "username": "carol",
                "displayName": "Carol",
                "isActive": False,
                "score": 9.5,
            }
        )
        assert user.isActive is False
        assert user.score == 9.5
        await db.user.delete(where={"id": user.id})


class TestUserFindUnique:
    async def test_find_unique_by_id(self, db: Prisma) -> None:
        created = await db.user.create(data={"email": "find1@test.com", "username": "find1", "displayName": "F1"})
        found = await db.user.find_unique(where={"id": created.id})
        assert found is not None
        assert found.id == created.id
        assert found.email == "find1@test.com"
        await db.user.delete(where={"id": created.id})

    async def test_find_unique_by_email(self, db: Prisma) -> None:
        created = await db.user.create(data={"email": "find2@test.com", "username": "find2", "displayName": "F2"})
        found = await db.user.find_unique(where={"email": "find2@test.com"})
        assert found is not None
        assert found.id == created.id
        await db.user.delete(where={"id": created.id})

    async def test_find_unique_returns_none_when_missing(self, db: Prisma) -> None:
        result = await db.user.find_unique(where={"id": 999999})
        assert result is None


class TestUserFindMany:
    async def test_find_many_returns_all(self, db: Prisma) -> None:
        u1 = await db.user.create(data={"email": "many1@test.com", "username": "many1", "displayName": "M1"})
        u2 = await db.user.create(data={"email": "many2@test.com", "username": "many2", "displayName": "M2"})
        users = await db.user.find_many(where={"email": {"in_": ["many1@test.com", "many2@test.com"]}})
        assert len(users) == 2
        await db.user.delete(where={"id": u1.id})
        await db.user.delete(where={"id": u2.id})

    async def test_find_many_with_take(self, db: Prisma) -> None:
        ids = []
        for i in range(3):
            u = await db.user.create(
                data={"email": f"take{i}@test.com", "username": f"take{i}", "displayName": f"T{i}"}
            )
            ids.append(u.id)
        users = await db.user.find_many(where={"email": {"in_": [f"take{i}@test.com" for i in range(3)]}}, take=2)
        assert len(users) == 2
        for uid in ids:
            await db.user.delete(where={"id": uid})

    async def test_find_many_with_order(self, db: Prisma) -> None:
        u1 = await db.user.create(data={"email": "ord1@test.com", "username": "ord1", "displayName": "Z"})
        u2 = await db.user.create(data={"email": "ord2@test.com", "username": "ord2", "displayName": "A"})
        users = await db.user.find_many(
            where={"email": {"in_": ["ord1@test.com", "ord2@test.com"]}},
            order={"displayName": "asc"},
        )
        assert users[0].displayName == "A"
        assert users[1].displayName == "Z"
        await db.user.delete(where={"id": u1.id})
        await db.user.delete(where={"id": u2.id})


class TestUserUpdate:
    async def test_update_scalar_field(self, db: Prisma) -> None:
        user = await db.user.create(data={"email": "upd1@test.com", "username": "upd1", "displayName": "Before"})
        updated = await db.user.update(where={"id": user.id}, data={"displayName": "After"})
        assert updated.displayName == "After"
        await db.user.delete(where={"id": user.id})

    async def test_update_sets_updated_at(self, db: Prisma) -> None:
        user = await db.user.create(data={"email": "upd2@test.com", "username": "upd2", "displayName": "Name"})
        original_ts = user.updatedAt
        import asyncio

        await asyncio.sleep(0.01)
        updated = await db.user.update(where={"id": user.id}, data={"score": 5.0})
        assert updated.updatedAt >= original_ts
        await db.user.delete(where={"id": user.id})

    async def test_update_raises_on_missing_record(self, db: Prisma) -> None:
        with pytest.raises(RecordNotFoundError):
            await db.user.update(where={"id": 999999}, data={"displayName": "X"})


class TestUserDelete:
    async def test_delete_returns_record(self, db: Prisma) -> None:
        user = await db.user.create(data={"email": "del1@test.com", "username": "del1", "displayName": "Del"})
        deleted = await db.user.delete(where={"id": user.id})
        assert deleted is not None
        assert deleted.id == user.id
        assert await db.user.find_unique(where={"id": user.id}) is None

    async def test_delete_returns_none_when_missing(self, db: Prisma) -> None:
        result = await db.user.delete(where={"id": 999999})
        assert result is None


class TestUserUpsert:
    async def test_upsert_creates_when_absent(self, db: Prisma) -> None:
        user = await db.user.upsert(
            where={"email": "upsert1@test.com"},
            create={"email": "upsert1@test.com", "username": "upsert1", "displayName": "Created"},
            update={"displayName": "Updated"},
        )
        assert user.displayName == "Created"
        await db.user.delete(where={"id": user.id})

    async def test_upsert_updates_when_present(self, db: Prisma) -> None:
        created = await db.user.create(
            data={"email": "upsert2@test.com", "username": "upsert2", "displayName": "Original"}
        )
        user = await db.user.upsert(
            where={"email": "upsert2@test.com"},
            create={"email": "upsert2@test.com", "username": "upsert2", "displayName": "Created"},
            update={"displayName": "Updated"},
        )
        assert user.id == created.id
        assert user.displayName == "Updated"
        await db.user.delete(where={"id": user.id})


class TestUserCount:
    async def test_count_all(self, db: Prisma) -> None:
        before = await db.user.count()
        u = await db.user.create(data={"email": "cnt1@test.com", "username": "cnt1", "displayName": "C"})
        after = await db.user.count()
        assert after == before + 1
        await db.user.delete(where={"id": u.id})

    async def test_count_with_where(self, db: Prisma) -> None:
        u = await db.user.create(
            data={"email": "cnt2@test.com", "username": "cnt2", "displayName": "C", "isActive": False}
        )
        count = await db.user.count(where={"email": "cnt2@test.com"})
        assert count == 1
        await db.user.delete(where={"id": u.id})
