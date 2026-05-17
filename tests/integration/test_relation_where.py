"""Tests for relation-based where filtering (filter through related model fields)."""

from .prisma_test_case import PrismaTestCase


class TestManyToOneRelationWhere(PrismaTestCase):
    """Filter through FK-side relations (this table holds the FK)."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.alice = await self.db.user.create(
            data={"email": "rw_alice@test.com", "username": "rw_alice", "displayName": "Alice"}
        )
        self.bob = await self.db.user.create(
            data={"email": "rw_bob@test.com", "username": "rw_bob", "displayName": "Bob"}
        )
        self.p1 = await self.db.post.create(
            data={"title": "Alice Post", "slug": "rw-alice-post", "content": "body", "authorId": self.alice.id}
        )
        self.p2 = await self.db.post.create(
            data={"title": "Bob Post", "slug": "rw-bob-post", "content": "body", "authorId": self.bob.id}
        )

    async def asyncTearDown(self) -> None:
        await self.db.post.delete_many(where={"slug": {"in_": ["rw-alice-post", "rw-bob-post"]}})
        await self.db.user.delete_many(where={"email": {"in_": ["rw_alice@test.com", "rw_bob@test.com"]}})
        await super().asyncTearDown()

    async def test_filter_posts_by_author_email(self) -> None:
        posts = await self.db.post.find_many(where={"author": {"email": "rw_alice@test.com"}})
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].slug, "rw-alice-post")

    async def test_filter_posts_by_author_field_filter(self) -> None:
        posts = await self.db.post.find_many(where={"author": {"displayName": {"contains": "Bob"}}})
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].slug, "rw-bob-post")

    async def test_relation_where_combined_with_scalar_where(self) -> None:
        posts = await self.db.post.find_many(
            where={
                "author": {"email": "rw_alice@test.com"},
                "title": {"contains": "Alice"},
            }
        )
        self.assertEqual(len(posts), 1)

    async def test_relation_where_no_match_returns_empty(self) -> None:
        posts = await self.db.post.find_many(where={"author": {"email": "nonexistent@test.com"}})
        self.assertEqual(posts, [])


class TestOneToManyRelationWhere(PrismaTestCase):
    """Filter through back-reference relations (other table holds the FK)."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.with_posts = await self.db.user.create(
            data={"email": "rw_wp@test.com", "username": "rw_wp", "displayName": "WithPosts"}
        )
        self.no_posts = await self.db.user.create(
            data={"email": "rw_np@test.com", "username": "rw_np", "displayName": "NoPosts"}
        )
        self.pub = await self.db.post.create(
            data={
                "title": "Published",
                "slug": "rw-pub",
                "content": "body",
                "authorId": self.with_posts.id,
                "isPublished": True,
            }
        )
        self.draft = await self.db.post.create(
            data={
                "title": "Draft",
                "slug": "rw-draft",
                "content": "body",
                "authorId": self.with_posts.id,
                "isPublished": False,
            }
        )

    async def asyncTearDown(self) -> None:
        await self.db.post.delete_many(where={"slug": {"in_": ["rw-pub", "rw-draft"]}})
        await self.db.user.delete_many(where={"email": {"in_": ["rw_wp@test.com", "rw_np@test.com"]}})
        await super().asyncTearDown()

    async def test_some_returns_users_with_matching_posts(self) -> None:
        users = await self.db.user.find_many(
            where={
                "email": {"in_": ["rw_wp@test.com", "rw_np@test.com"]},
                "posts": {"some": {"isPublished": True}},
            }
        )
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].email, "rw_wp@test.com")

    async def test_some_no_match_returns_empty(self) -> None:
        users = await self.db.user.find_many(
            where={
                "email": {"in_": ["rw_np@test.com"]},
                "posts": {"some": {"isPublished": True}},
            }
        )
        self.assertEqual(users, [])

    async def test_none_returns_users_without_matching_posts(self) -> None:
        users = await self.db.user.find_many(
            where={
                "email": {"in_": ["rw_wp@test.com", "rw_np@test.com"]},
                "posts": {"none": {"isPublished": True}},
            }
        )
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].email, "rw_np@test.com")

    async def test_implicit_some_plain_dict(self) -> None:
        # Plain dict without some/none/every treated as implicit some
        users = await self.db.user.find_many(
            where={
                "email": {"in_": ["rw_wp@test.com", "rw_np@test.com"]},
                "posts": {"isPublished": False},
            }
        )
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].email, "rw_wp@test.com")
