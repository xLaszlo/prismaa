"""Tests for transaction support: tx() context manager, commit, and rollback."""

from prismaa.runtime.errors import UniqueViolationError

from .prisma_test_case import PrismaTestCase


class TestTransactionCommit(PrismaTestCase):
    async def test_all_operations_commit_on_success(self) -> None:
        async with self.db.tx() as tx:
            user = await tx.user.create(data={"email": "tx_ok@test.com", "username": "tx_ok", "displayName": "TxOk"})
            await tx.post.create(
                data={"title": "Tx Post", "slug": "tx-post-ok", "content": "body", "authorId": user.id}
            )

        # After the context exits cleanly both records must be visible
        fetched_user = await self.db.user.find_unique(where={"email": "tx_ok@test.com"})
        self.assertIsNotNone(fetched_user)
        fetched_post = await self.db.post.find_unique(where={"slug": "tx-post-ok"})
        self.assertIsNotNone(fetched_post)

        await self.db.post.delete(where={"id": fetched_post.id})
        await self.db.user.delete(where={"id": fetched_user.id})

    async def test_reads_within_tx_see_own_writes(self) -> None:
        async with self.db.tx() as tx:
            user = await tx.user.create(
                data={"email": "tx_read@test.com", "username": "tx_read", "displayName": "TxRead"}
            )
            # Read the just-written row within the same transaction
            found = await tx.user.find_unique(where={"id": user.id})
            self.assertIsNotNone(found)
            self.assertEqual(found.email, "tx_read@test.com")

        await self.db.user.delete(where={"email": "tx_read@test.com"})


class TestTransactionRollback(PrismaTestCase):
    async def test_exception_rolls_back_all_operations(self) -> None:
        email = "tx_rollback@test.com"
        try:
            async with self.db.tx() as tx:
                await tx.user.create(data={"email": email, "username": "tx_rb", "displayName": "TxRb"})
                # Force a failure — duplicate unique field
                await tx.user.create(data={"email": email, "username": "tx_rb2", "displayName": "TxRb2"})
        except (UniqueViolationError, Exception):
            pass

        # The first create must have been rolled back
        result = await self.db.user.find_unique(where={"email": email})
        self.assertIsNone(result)

    async def test_explicit_raise_rolls_back(self) -> None:
        email = "tx_raise@test.com"
        try:
            async with self.db.tx() as tx:
                await tx.user.create(data={"email": email, "username": "tx_raise", "displayName": "TxRaise"})
                raise ValueError("intentional rollback")
        except ValueError:
            pass

        result = await self.db.user.find_unique(where={"email": email})
        self.assertIsNone(result)

    async def test_rolled_back_tx_does_not_affect_outside_writes(self) -> None:
        outside = await self.db.user.create(
            data={"email": "tx_outside@test.com", "username": "tx_outside", "displayName": "Outside"}
        )
        try:
            async with self.db.tx() as tx:
                await tx.user.create(
                    data={"email": "tx_inside@test.com", "username": "tx_inside", "displayName": "Inside"}
                )
                raise ValueError("force rollback")
        except ValueError:
            pass

        # outside write persists; inside write was rolled back
        self.assertIsNotNone(await self.db.user.find_unique(where={"id": outside.id}))
        self.assertIsNone(await self.db.user.find_unique(where={"email": "tx_inside@test.com"}))

        await self.db.user.delete(where={"id": outside.id})


class TestTransactionErrors(PrismaTestCase):
    async def test_tx_before_connect_raises(self) -> None:
        from prisma import Prisma

        db = Prisma()
        with self.assertRaises(RuntimeError):
            async with db.tx():
                pass
