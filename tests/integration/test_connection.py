"""Integration tests for Prisma client connection lifecycle."""

from prisma import Prisma

from .prisma_test_case import PrismaTestCase


class TestConnectionLifecycle(PrismaTestCase):
    # Each test manages its own Prisma instance; disable the default connect/disconnect.
    async def asyncSetUp(self) -> None:
        pass

    async def asyncTearDown(self) -> None:
        pass

    async def test_explicit_connect_and_disconnect(self) -> None:
        db = Prisma()
        await db.connect(self._db_url)
        count = await db.user.count()
        self.assertGreaterEqual(count, 0)
        await db.disconnect()
        with self.assertRaises(RuntimeError):
            await db.user.count()

    async def test_query_before_connect_raises(self) -> None:
        db = Prisma()
        with self.assertRaises(RuntimeError):
            await db.user.count()

    async def test_context_manager_disconnects_on_exit(self) -> None:
        db = Prisma()
        async with db:
            await db.connect(self._db_url)
            count = await db.user.count()
            self.assertGreaterEqual(count, 0)
        with self.assertRaises(RuntimeError):
            await db.user.count()

    async def test_disconnect_without_connect_is_safe(self) -> None:
        db = Prisma()
        await db.disconnect()

    async def test_double_connect_is_safe(self) -> None:
        db = Prisma()
        await db.connect(self._db_url)
        await db.connect(self._db_url)
        await db.disconnect()
