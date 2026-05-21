"""End-to-end CRUD tests for the User model against a real SQLite database."""

import asyncio

from aprisma.runtime.errors import RecordNotFoundError

from .prisma_test_case import PrismaTestCase


class TestUserCreate(PrismaTestCase):
    async def test_create_returns_model_with_id(self) -> None:
        user = await self.db.user.create(data={"email": "alice@test.com", "username": "alice", "displayName": "Alice"})
        self.assertIsNotNone(user.id)
        self.assertGreater(user.id, 0)
        self.assertEqual(user.email, "alice@test.com")
        self.assertEqual(user.username, "alice")
        self.assertEqual(user.displayName, "Alice")
        await self.db.user.delete(where={"id": user.id})

    async def test_create_applies_scalar_defaults(self) -> None:
        user = await self.db.user.create(data={"email": "bob@test.com", "username": "bob", "displayName": "Bob"})
        self.assertTrue(user.isActive)
        self.assertEqual(user.score, 0.0)
        self.assertIsNotNone(user.createdAt)
        self.assertIsNotNone(user.updatedAt)
        await self.db.user.delete(where={"id": user.id})

    async def test_create_with_optional_fields_overridden(self) -> None:
        user = await self.db.user.create(
            data={
                "email": "carol@test.com",
                "username": "carol",
                "displayName": "Carol",
                "isActive": False,
                "score": 9.5,
            }
        )
        self.assertFalse(user.isActive)
        self.assertEqual(user.score, 9.5)
        await self.db.user.delete(where={"id": user.id})


class TestUserFindUnique(PrismaTestCase):
    async def test_find_unique_by_id(self) -> None:
        created = await self.db.user.create(data={"email": "find1@test.com", "username": "find1", "displayName": "F1"})
        found = await self.db.user.find_unique(where={"id": created.id})
        self.assertIsNotNone(found)
        self.assertEqual(found.id, created.id)
        self.assertEqual(found.email, "find1@test.com")
        await self.db.user.delete(where={"id": created.id})

    async def test_find_unique_by_email(self) -> None:
        created = await self.db.user.create(data={"email": "find2@test.com", "username": "find2", "displayName": "F2"})
        found = await self.db.user.find_unique(where={"email": "find2@test.com"})
        self.assertIsNotNone(found)
        self.assertEqual(found.id, created.id)
        await self.db.user.delete(where={"id": created.id})

    async def test_find_unique_returns_none_when_missing(self) -> None:
        result = await self.db.user.find_unique(where={"id": 999999})
        self.assertIsNone(result)


class TestUserFindMany(PrismaTestCase):
    async def test_find_many_returns_all(self) -> None:
        u1 = await self.db.user.create(data={"email": "many1@test.com", "username": "many1", "displayName": "M1"})
        u2 = await self.db.user.create(data={"email": "many2@test.com", "username": "many2", "displayName": "M2"})
        users = await self.db.user.find_many(where={"email": {"in_": ["many1@test.com", "many2@test.com"]}})
        self.assertEqual(len(users), 2)
        await self.db.user.delete(where={"id": u1.id})
        await self.db.user.delete(where={"id": u2.id})

    async def test_find_many_with_take(self) -> None:
        ids = []
        for i in range(3):
            u = await self.db.user.create(
                data={"email": f"take{i}@test.com", "username": f"take{i}", "displayName": f"T{i}"}
            )
            ids.append(u.id)
        users = await self.db.user.find_many(where={"email": {"in_": [f"take{i}@test.com" for i in range(3)]}}, take=2)
        self.assertEqual(len(users), 2)
        for uid in ids:
            await self.db.user.delete(where={"id": uid})

    async def test_find_many_with_order(self) -> None:
        u1 = await self.db.user.create(data={"email": "ord1@test.com", "username": "ord1", "displayName": "Z"})
        u2 = await self.db.user.create(data={"email": "ord2@test.com", "username": "ord2", "displayName": "A"})
        users = await self.db.user.find_many(
            where={"email": {"in_": ["ord1@test.com", "ord2@test.com"]}},
            order={"displayName": "asc"},
        )
        self.assertEqual(users[0].displayName, "A")
        self.assertEqual(users[1].displayName, "Z")
        await self.db.user.delete(where={"id": u1.id})
        await self.db.user.delete(where={"id": u2.id})


class TestUserUpdate(PrismaTestCase):
    async def test_update_scalar_field(self) -> None:
        user = await self.db.user.create(data={"email": "upd1@test.com", "username": "upd1", "displayName": "Before"})
        updated = await self.db.user.update(where={"id": user.id}, data={"displayName": "After"})
        self.assertEqual(updated.displayName, "After")
        await self.db.user.delete(where={"id": user.id})

    async def test_update_sets_updated_at(self) -> None:
        user = await self.db.user.create(data={"email": "upd2@test.com", "username": "upd2", "displayName": "Name"})
        original_ts = user.updatedAt
        await asyncio.sleep(0.01)
        updated = await self.db.user.update(where={"id": user.id}, data={"score": 5.0})
        self.assertGreaterEqual(updated.updatedAt, original_ts)
        await self.db.user.delete(where={"id": user.id})

    async def test_update_raises_on_missing_record(self) -> None:
        with self.assertRaises(RecordNotFoundError):
            await self.db.user.update(where={"id": 999999}, data={"displayName": "X"})


class TestUserDelete(PrismaTestCase):
    async def test_delete_returns_record(self) -> None:
        user = await self.db.user.create(data={"email": "del1@test.com", "username": "del1", "displayName": "Del"})
        deleted = await self.db.user.delete(where={"id": user.id})
        self.assertIsNotNone(deleted)
        self.assertEqual(deleted.id, user.id)
        self.assertIsNone(await self.db.user.find_unique(where={"id": user.id}))

    async def test_delete_returns_none_when_missing(self) -> None:
        result = await self.db.user.delete(where={"id": 999999})
        self.assertIsNone(result)


class TestUserUpsert(PrismaTestCase):
    async def test_upsert_creates_when_absent(self) -> None:
        user = await self.db.user.upsert(
            where={"email": "upsert1@test.com"},
            create={"email": "upsert1@test.com", "username": "upsert1", "displayName": "Created"},
            update={"displayName": "Updated"},
        )
        self.assertEqual(user.displayName, "Created")
        await self.db.user.delete(where={"id": user.id})

    async def test_upsert_updates_when_present(self) -> None:
        created = await self.db.user.create(
            data={"email": "upsert2@test.com", "username": "upsert2", "displayName": "Original"}
        )
        user = await self.db.user.upsert(
            where={"email": "upsert2@test.com"},
            create={"email": "upsert2@test.com", "username": "upsert2", "displayName": "Created"},
            update={"displayName": "Updated"},
        )
        self.assertEqual(user.id, created.id)
        self.assertEqual(user.displayName, "Updated")
        await self.db.user.delete(where={"id": user.id})


class TestUserCount(PrismaTestCase):
    async def test_count_all(self) -> None:
        before = await self.db.user.count()
        u = await self.db.user.create(data={"email": "cnt1@test.com", "username": "cnt1", "displayName": "C"})
        after = await self.db.user.count()
        self.assertEqual(after, before + 1)
        await self.db.user.delete(where={"id": u.id})

    async def test_count_with_where(self) -> None:
        u = await self.db.user.create(
            data={"email": "cnt2@test.com", "username": "cnt2", "displayName": "C", "isActive": False}
        )
        count = await self.db.user.count(where={"email": "cnt2@test.com"})
        self.assertEqual(count, 1)
        await self.db.user.delete(where={"id": u.id})
