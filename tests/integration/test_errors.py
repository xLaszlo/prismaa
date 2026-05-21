"""Integration tests for error types and constraint violations."""

from aprisma.runtime.errors import (
    ForeignKeyViolationError,
    PrismaError,
    RecordNotFoundError,
    UniqueViolationError,
)

from .prisma_test_case import PrismaTestCase


class TestUniqueConstraint(PrismaTestCase):
    async def test_create_duplicate_unique_raises_unique_violation(self) -> None:
        await self.db.user.create(data={"email": "dup_err@test.com", "username": "dup_err", "displayName": "D"})
        with self.assertRaises(UniqueViolationError):
            await self.db.user.create(data={"email": "dup_err@test.com", "username": "dup_err2", "displayName": "D2"})
        await self.db.user.delete(where={"email": "dup_err@test.com"})

    def test_unique_violation_is_prisma_error(self) -> None:
        self.assertTrue(issubclass(UniqueViolationError, PrismaError))

    async def test_create_duplicate_unique_username_raises(self) -> None:
        await self.db.user.create(data={"email": "uniq_a@test.com", "username": "shared_username", "displayName": "A"})
        with self.assertRaises(UniqueViolationError):
            await self.db.user.create(
                data={"email": "uniq_b@test.com", "username": "shared_username", "displayName": "B"}
            )
        await self.db.user.delete(where={"email": "uniq_a@test.com"})


class TestForeignKeyConstraint(PrismaTestCase):
    async def test_create_with_invalid_fk_raises_foreign_key_violation(self) -> None:
        with self.assertRaises(ForeignKeyViolationError):
            await self.db.post.create(
                data={
                    "title": "Orphan Post",
                    "slug": "orphan-post",
                    "content": "body",
                    "authorId": 999999,
                }
            )

    def test_foreign_key_violation_is_prisma_error(self) -> None:
        self.assertTrue(issubclass(ForeignKeyViolationError, PrismaError))


class TestRecordNotFound(PrismaTestCase):
    async def test_update_nonexistent_record_raises_record_not_found(self) -> None:
        with self.assertRaises(RecordNotFoundError):
            await self.db.user.update(where={"id": 999999}, data={"displayName": "X"})

    def test_record_not_found_is_prisma_error(self) -> None:
        self.assertTrue(issubclass(RecordNotFoundError, PrismaError))

    async def test_delete_nonexistent_record_returns_none(self) -> None:
        result = await self.db.user.delete(where={"id": 999999})
        self.assertIsNone(result)

    async def test_find_unique_nonexistent_returns_none(self) -> None:
        result = await self.db.user.find_unique(where={"id": 999999})
        self.assertIsNone(result)


class TestFindUniqueValidation(PrismaTestCase):
    async def test_find_unique_on_non_unique_field_raises(self) -> None:
        with self.assertRaises(ValueError):
            await self.db.user.find_unique(where={"displayName": "Alice"})

    async def test_find_unique_on_id_field_is_valid(self) -> None:
        result = await self.db.user.find_unique(where={"id": 999999})
        self.assertIsNone(result)

    async def test_find_unique_on_unique_field_is_valid(self) -> None:
        result = await self.db.user.find_unique(where={"email": "nobody@test.com"})
        self.assertIsNone(result)
