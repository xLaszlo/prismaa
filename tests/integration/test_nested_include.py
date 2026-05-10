"""Integration tests for nested (multi-level) include."""

from .prisma_test_case import PrismaTestCase


class TestNestedInclude(PrismaTestCase):
    # ------------------------------------------------------------------
    # User → posts → tags  (two levels deep)
    # ------------------------------------------------------------------

    async def test_user_posts_tags_two_levels(self) -> None:
        user = await self.db.user.create(data={"email": "ni1@test.com", "username": "ni1", "displayName": "NI1"})
        post = await self.db.post.create(
            data={"title": "NI Post", "slug": "ni-post", "content": "body", "authorId": user.id}
        )
        tag1 = await self.db.tag.create(data={"name": "ni-tag-a"})
        tag2 = await self.db.tag.create(data={"name": "ni-tag-b"})
        await self.db.postTag.create(data={"postId": post.id, "tagId": tag1.id})
        await self.db.postTag.create(data={"postId": post.id, "tagId": tag2.id})

        fetched = await self.db.user.find_unique(
            where={"id": user.id},
            include={"posts": {"include": {"tags": True}}},
        )

        self.assertIsNotNone(fetched)
        self.assertEqual(len(fetched.posts), 1)
        self.assertEqual(len(fetched.posts[0].tags), 2)
        tag_names = {pt.tagId for pt in fetched.posts[0].tags}
        self.assertIn(tag1.id, tag_names)
        self.assertIn(tag2.id, tag_names)

        await self.db.postTag.delete_many(where={"postId": post.id})
        await self.db.tag.delete(where={"id": tag1.id})
        await self.db.tag.delete(where={"id": tag2.id})
        await self.db.post.delete(where={"id": post.id})
        await self.db.user.delete(where={"id": user.id})

    async def test_nested_include_with_no_tags(self) -> None:
        user = await self.db.user.create(data={"email": "ni2@test.com", "username": "ni2", "displayName": "NI2"})
        post = await self.db.post.create(
            data={"title": "NI Post2", "slug": "ni-post-2", "content": "body", "authorId": user.id}
        )

        fetched = await self.db.user.find_unique(
            where={"id": user.id},
            include={"posts": {"include": {"tags": True}}},
        )

        self.assertIsNotNone(fetched)
        self.assertEqual(len(fetched.posts), 1)
        self.assertEqual(fetched.posts[0].tags, [])

        await self.db.post.delete(where={"id": post.id})
        await self.db.user.delete(where={"id": user.id})

    async def test_nested_include_when_intermediate_list_is_empty(self) -> None:
        user = await self.db.user.create(data={"email": "ni3@test.com", "username": "ni3", "displayName": "NI3"})

        fetched = await self.db.user.find_unique(
            where={"id": user.id},
            include={"posts": {"include": {"tags": True}}},
        )

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.posts, [])

        await self.db.user.delete(where={"id": user.id})

    # ------------------------------------------------------------------
    # User → profile + posts  (multiple relations at same level)
    # ------------------------------------------------------------------

    async def test_multiple_relations_at_same_level(self) -> None:
        user = await self.db.user.create(data={"email": "ni4@test.com", "username": "ni4", "displayName": "NI4"})
        profile = await self.db.profile.create(data={"userId": user.id, "bio": "hello"})
        post = await self.db.post.create(
            data={"title": "NI Post4", "slug": "ni-post-4", "content": "body", "authorId": user.id}
        )

        fetched = await self.db.user.find_unique(
            where={"id": user.id},
            include={"profile": True, "posts": True},
        )

        self.assertIsNotNone(fetched)
        self.assertIsNotNone(fetched.profile)
        self.assertEqual(fetched.profile.bio, "hello")
        self.assertEqual(len(fetched.posts), 1)
        self.assertEqual(fetched.posts[0].slug, "ni-post-4")

        await self.db.post.delete(where={"id": post.id})
        await self.db.profile.delete(where={"id": profile.id})
        await self.db.user.delete(where={"id": user.id})

    # ------------------------------------------------------------------
    # Post → author  (reverse 1-n, back to parent)
    # ------------------------------------------------------------------

    async def test_post_includes_author(self) -> None:
        user = await self.db.user.create(data={"email": "ni5@test.com", "username": "ni5", "displayName": "NI5"})
        post = await self.db.post.create(
            data={"title": "NI Post5", "slug": "ni-post-5", "content": "body", "authorId": user.id}
        )

        fetched = await self.db.post.find_unique(
            where={"id": post.id},
            include={"author": True},
        )

        self.assertIsNotNone(fetched)
        self.assertIsNotNone(fetched.author)
        self.assertEqual(fetched.author.id, user.id)
        self.assertEqual(fetched.author.email, "ni5@test.com")

        await self.db.post.delete(where={"id": post.id})
        await self.db.user.delete(where={"id": user.id})
