"""Tests for distinct combined with relation WHERE filters.

Covers:
- distinct on FK/scalar fields
- relation WHERE (JOIN-based) produces no duplicate rows
- distinct + relation WHERE combined
- distinct + include together
"""

from .prisma_test_case import PrismaTestCase


class TestDistinctOnFkField(PrismaTestCase):
    """distinct=["authorId"] on Post: one row per author."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.alice = await self.db.user.create(
            data={"email": "dr_alice@test.com", "username": "dr_alice", "displayName": "Alice"}
        )
        self.bob = await self.db.user.create(
            data={"email": "dr_bob@test.com", "username": "dr_bob", "displayName": "Bob"}
        )
        # Two posts by Alice, one by Bob
        await self.db.post.create(data={"title": "A1", "slug": "dr-a1", "content": "x", "authorId": self.alice.id})
        await self.db.post.create(data={"title": "A2", "slug": "dr-a2", "content": "x", "authorId": self.alice.id})
        await self.db.post.create(data={"title": "B1", "slug": "dr-b1", "content": "x", "authorId": self.bob.id})

    async def asyncTearDown(self) -> None:
        await self.db.post.delete_many(where={"slug": {"in_": ["dr-a1", "dr-a2", "dr-b1"]}})
        await self.db.user.delete_many(where={"email": {"in_": ["dr_alice@test.com", "dr_bob@test.com"]}})
        await super().asyncTearDown()

    async def test_distinct_author_id_returns_one_per_author(self) -> None:
        posts = await self.db.post.find_many(
            where={"slug": {"in_": ["dr-a1", "dr-a2", "dr-b1"]}},
            distinct=["authorId"],
        )
        author_ids = {p.authorId for p in posts}
        self.assertEqual(len(posts), 2)
        self.assertIn(self.alice.id, author_ids)
        self.assertIn(self.bob.id, author_ids)

    async def test_no_distinct_returns_all_posts(self) -> None:
        posts = await self.db.post.find_many(
            where={"slug": {"in_": ["dr-a1", "dr-a2", "dr-b1"]}},
        )
        self.assertEqual(len(posts), 3)


class TestRelationWhereNoDuplicates(PrismaTestCase):
    """Relation WHERE via JOIN must not produce duplicate rows."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.author = await self.db.user.create(
            data={"email": "dr_dup@test.com", "username": "dr_dup", "displayName": "Dup"}
        )
        # Three posts by the same author
        for i in range(3):
            await self.db.post.create(
                data={
                    "title": f"Dup{i}",
                    "slug": f"dr-dup-{i}",
                    "content": "x",
                    "authorId": self.author.id,
                }
            )

    async def asyncTearDown(self) -> None:
        await self.db.post.delete_many(where={"slug": {"in_": ["dr-dup-0", "dr-dup-1", "dr-dup-2"]}})
        await self.db.user.delete_many(where={"email": "dr_dup@test.com"})
        await super().asyncTearDown()

    async def test_relation_where_join_no_duplicates(self) -> None:
        # Filter posts by author email (triggers JOIN in apply_where).
        # Even though there are 3 posts, each must appear exactly once.
        posts = await self.db.post.find_many(where={"author": {"email": "dr_dup@test.com"}})
        self.assertEqual(len(posts), 3)
        slugs = {p.slug for p in posts}
        self.assertEqual(slugs, {"dr-dup-0", "dr-dup-1", "dr-dup-2"})

    async def test_relation_where_combined_no_duplicates(self) -> None:
        # Scalar filter + relation filter — still no duplicate rows.
        posts = await self.db.post.find_many(
            where={
                "author": {"email": "dr_dup@test.com"},
                "title": {"contains": "Dup"},
            }
        )
        self.assertEqual(len(posts), 3)
        ids = [p.id for p in posts]
        self.assertEqual(len(ids), len(set(ids)))  # all unique


class TestDistinctWithRelationWhere(PrismaTestCase):
    """distinct + relation WHERE work together correctly."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.alice = await self.db.user.create(
            data={"email": "dr2_alice@test.com", "username": "dr2_alice", "displayName": "Alice2"}
        )
        self.bob = await self.db.user.create(
            data={"email": "dr2_bob@test.com", "username": "dr2_bob", "displayName": "Bob2"}
        )
        # Two posts by Alice, two by Bob
        for slug in ["dr2-a1", "dr2-a2"]:
            await self.db.post.create(data={"title": slug, "slug": slug, "content": "x", "authorId": self.alice.id})
        for slug in ["dr2-b1", "dr2-b2"]:
            await self.db.post.create(data={"title": slug, "slug": slug, "content": "x", "authorId": self.bob.id})

    async def asyncTearDown(self) -> None:
        await self.db.post.delete_many(where={"slug": {"in_": ["dr2-a1", "dr2-a2", "dr2-b1", "dr2-b2"]}})
        await self.db.user.delete_many(where={"email": {"in_": ["dr2_alice@test.com", "dr2_bob@test.com"]}})
        await super().asyncTearDown()

    async def test_distinct_author_id_with_relation_filter(self) -> None:
        # Filter to Alice's posts, then distinct by authorId → exactly 1 row
        posts = await self.db.post.find_many(
            where={"author": {"email": "dr2_alice@test.com"}},
            distinct=["authorId"],
        )
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].authorId, self.alice.id)

    async def test_distinct_preserves_correct_author(self) -> None:
        # distinct across both authors, filtered by relation displayName containing "2"
        # Both Alice2 and Bob2 match, so we should get one post per author
        posts = await self.db.post.find_many(
            where={
                "slug": {"in_": ["dr2-a1", "dr2-a2", "dr2-b1", "dr2-b2"]},
                "author": {"displayName": {"contains": "2"}},
            },
            distinct=["authorId"],
            order={"authorId": "asc"},
        )
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0].authorId, self.alice.id)
        self.assertEqual(posts[1].authorId, self.bob.id)


class TestDistinctWithInclude(PrismaTestCase):
    """distinct does not break relation loading via include."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "dr3_u@test.com", "username": "dr3_u", "displayName": "U3"}
        )
        await self.db.post.create(data={"title": "P1", "slug": "dr3-p1", "content": "x", "authorId": self.user.id})
        await self.db.post.create(data={"title": "P2", "slug": "dr3-p2", "content": "x", "authorId": self.user.id})

    async def asyncTearDown(self) -> None:
        await self.db.post.delete_many(where={"slug": {"in_": ["dr3-p1", "dr3-p2"]}})
        await self.db.user.delete_many(where={"email": "dr3_u@test.com"})
        await super().asyncTearDown()

    async def test_distinct_with_include_author(self) -> None:
        posts = await self.db.post.find_many(
            where={"slug": {"in_": ["dr3-p1", "dr3-p2"]}},
            distinct=["authorId"],
            include={"author": True},
        )
        self.assertEqual(len(posts), 1)
        self.assertIsNotNone(posts[0].author)
        self.assertEqual(posts[0].author.email, "dr3_u@test.com")
