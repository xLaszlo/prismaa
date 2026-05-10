"""Tests for nested write operations: connect, disconnect, connectOrCreate."""

from .prisma_test_case import PrismaTestCase


class TestConnect(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "nw_user@test.com", "username": "nw_user", "displayName": "NW"}
        )

    async def asyncTearDown(self) -> None:
        await self.db.post.delete_many(where={"authorId": self.user.id})
        await self.db.user.delete(where={"id": self.user.id})
        await super().asyncTearDown()

    async def test_create_with_connect(self) -> None:
        post = await self.db.post.create(
            data={
                "title": "Connected Post",
                "slug": "connected-post",
                "content": "body",
                "author": {"connect": {"id": self.user.id}},
            }
        )
        self.assertEqual(post.authorId, self.user.id)

    async def test_update_with_connect_replaces_fk(self) -> None:
        other = await self.db.user.create(
            data={"email": "nw_other@test.com", "username": "nw_other", "displayName": "Other"}
        )
        post = await self.db.post.create(
            data={"title": "Post", "slug": "post-nw", "content": "body", "authorId": self.user.id}
        )
        updated = await self.db.post.update(
            where={"id": post.id},
            data={"author": {"connect": {"id": other.id}}},
        )
        self.assertEqual(updated.authorId, other.id)
        await self.db.post.delete(where={"id": post.id})
        await self.db.user.delete(where={"id": other.id})


class TestDisconnect(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "disc_user@test.com", "username": "disc_user", "displayName": "Disc"}
        )
        self.category = await self.db.category.create(data={"name": "disc-cat"})
        self.post = await self.db.post.create(
            data={
                "title": "Post with category",
                "slug": "disc-post",
                "content": "body",
                "authorId": self.user.id,
                "categoryId": self.category.id,
            }
        )

    async def asyncTearDown(self) -> None:
        await self.db.post.delete(where={"id": self.post.id})
        await self.db.category.delete(where={"id": self.category.id})
        await self.db.user.delete(where={"id": self.user.id})
        await super().asyncTearDown()

    async def test_disconnect_sets_nullable_fk_to_none(self) -> None:
        updated = await self.db.post.update(
            where={"id": self.post.id},
            data={"category": {"disconnect": True}},
        )
        self.assertIsNone(updated.categoryId)


class TestConnectOrCreate(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "coc_user@test.com", "username": "coc_user", "displayName": "COC"}
        )

    async def asyncTearDown(self) -> None:
        await self.db.post.delete_many(where={"authorId": self.user.id})
        await self.db.category.delete_many(where={"name": {"startswith": "coc-"}})
        await self.db.user.delete(where={"id": self.user.id})
        await super().asyncTearDown()

    async def test_connect_or_create_connects_existing(self) -> None:
        existing_cat = await self.db.category.create(data={"name": "coc-existing"})
        post = await self.db.post.create(
            data={
                "title": "COC Post",
                "slug": "coc-post-existing",
                "content": "body",
                "authorId": self.user.id,
                "category": {
                    "connectOrCreate": {
                        "where": {"name": "coc-existing"},
                        "create": {"name": "coc-existing"},
                    }
                },
            }
        )
        self.assertEqual(post.categoryId, existing_cat.id)

    async def test_connect_or_create_creates_when_missing(self) -> None:
        post = await self.db.post.create(
            data={
                "title": "COC New Post",
                "slug": "coc-post-new",
                "content": "body",
                "authorId": self.user.id,
                "category": {
                    "connectOrCreate": {
                        "where": {"name": "coc-brand-new"},
                        "create": {"name": "coc-brand-new"},
                    }
                },
            }
        )
        self.assertIsNotNone(post.categoryId)
        cat = await self.db.category.find_unique(where={"id": post.categoryId})
        self.assertEqual(cat.name, "coc-brand-new")
