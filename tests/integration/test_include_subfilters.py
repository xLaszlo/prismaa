"""Tests for include with sub-filters: where, take, skip, orderBy inside include."""

from .prisma_test_case import PrismaTestCase


class TestIncludeWhere(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "isf_user@test.com", "username": "isf_user", "displayName": "ISF"}
        )
        self.pub = await self.db.post.create(
            data={
                "title": "Published",
                "slug": "isf-pub",
                "content": "body",
                "authorId": self.user.id,
                "isPublished": True,
            }
        )
        self.draft = await self.db.post.create(
            data={
                "title": "Draft",
                "slug": "isf-draft",
                "content": "body",
                "authorId": self.user.id,
                "isPublished": False,
            }
        )

    async def asyncTearDown(self) -> None:
        await self.db.post.delete_many(where={"authorId": self.user.id})
        await self.db.user.delete(where={"id": self.user.id})
        await super().asyncTearDown()

    async def test_where_filters_list_relation(self) -> None:
        fetched = await self.db.user.find_unique(
            where={"id": self.user.id},
            include={"posts": {"where": {"isPublished": True}}},
        )
        self.assertEqual(len(fetched.posts), 1)
        self.assertEqual(fetched.posts[0].slug, "isf-pub")

    async def test_where_no_matches_returns_empty_list(self) -> None:
        fetched = await self.db.user.find_unique(
            where={"id": self.user.id},
            include={"posts": {"where": {"title": "nonexistent"}}},
        )
        self.assertEqual(fetched.posts, [])


class TestIncludeOrderBy(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "isf_ord@test.com", "username": "isf_ord", "displayName": "ISFOrd"}
        )
        self.p1 = await self.db.post.create(
            data={"title": "Alpha", "slug": "isf-ord-a", "content": "body", "authorId": self.user.id}
        )
        self.p2 = await self.db.post.create(
            data={"title": "Beta", "slug": "isf-ord-b", "content": "body", "authorId": self.user.id}
        )
        self.p3 = await self.db.post.create(
            data={"title": "Gamma", "slug": "isf-ord-c", "content": "body", "authorId": self.user.id}
        )

    async def asyncTearDown(self) -> None:
        await self.db.post.delete_many(where={"authorId": self.user.id})
        await self.db.user.delete(where={"id": self.user.id})
        await super().asyncTearDown()

    async def test_order_by_asc(self) -> None:
        fetched = await self.db.user.find_unique(
            where={"id": self.user.id},
            include={"posts": {"orderBy": {"title": "asc"}}},
        )
        titles = [p.title for p in fetched.posts]
        self.assertEqual(titles, ["Alpha", "Beta", "Gamma"])

    async def test_order_by_desc(self) -> None:
        fetched = await self.db.user.find_unique(
            where={"id": self.user.id},
            include={"posts": {"orderBy": {"title": "desc"}}},
        )
        titles = [p.title for p in fetched.posts]
        self.assertEqual(titles, ["Gamma", "Beta", "Alpha"])


class TestIncludeTakeSkip(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "isf_ts@test.com", "username": "isf_ts", "displayName": "ISFTs"}
        )
        for i in range(1, 5):
            await self.db.post.create(
                data={
                    "title": f"Post {i}",
                    "slug": f"isf-ts-{i}",
                    "content": "body",
                    "authorId": self.user.id,
                }
            )

    async def asyncTearDown(self) -> None:
        await self.db.post.delete_many(where={"authorId": self.user.id})
        await self.db.user.delete(where={"id": self.user.id})
        await super().asyncTearDown()

    async def test_take_limits_per_parent(self) -> None:
        fetched = await self.db.user.find_unique(
            where={"id": self.user.id},
            include={"posts": {"take": 2, "orderBy": {"title": "asc"}}},
        )
        self.assertEqual(len(fetched.posts), 2)
        self.assertEqual(fetched.posts[0].title, "Post 1")
        self.assertEqual(fetched.posts[1].title, "Post 2")

    async def test_skip_offsets_per_parent(self) -> None:
        fetched = await self.db.user.find_unique(
            where={"id": self.user.id},
            include={"posts": {"skip": 2, "orderBy": {"title": "asc"}}},
        )
        self.assertEqual(len(fetched.posts), 2)
        self.assertEqual(fetched.posts[0].title, "Post 3")

    async def test_take_limits_across_multiple_parents(self) -> None:
        other = await self.db.user.create(
            data={"email": "isf_ts2@test.com", "username": "isf_ts2", "displayName": "ISFTs2"}
        )
        for i in range(1, 4):
            await self.db.post.create(
                data={
                    "title": f"Other {i}",
                    "slug": f"isf-ts2-{i}",
                    "content": "body",
                    "authorId": other.id,
                }
            )
        users = await self.db.user.find_many(
            where={"email": {"in_": ["isf_ts@test.com", "isf_ts2@test.com"]}},
            include={"posts": {"take": 1, "orderBy": {"title": "asc"}}},
        )
        by_id = {u.id: u for u in users}
        self.assertEqual(len(by_id[self.user.id].posts), 1)
        self.assertEqual(len(by_id[other.id].posts), 1)
        await self.db.post.delete_many(where={"authorId": other.id})
        await self.db.user.delete(where={"id": other.id})

    async def test_where_and_take_combined(self) -> None:
        # mark posts 1 and 2 as published
        await self.db.post.update_many(
            where={"slug": {"in_": ["isf-ts-1", "isf-ts-2"]}},
            data={"isPublished": True},
        )
        fetched = await self.db.user.find_unique(
            where={"id": self.user.id},
            include={"posts": {"where": {"isPublished": True}, "take": 1, "orderBy": {"title": "asc"}}},
        )
        self.assertEqual(len(fetched.posts), 1)
        self.assertEqual(fetched.posts[0].title, "Post 1")
