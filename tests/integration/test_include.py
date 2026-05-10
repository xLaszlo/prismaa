"""Tests for include: loading related records across 1-1, 1-n, and n-m relations."""

from .prisma_test_case import PrismaTestCase


class TestIncludeOneToOne(PrismaTestCase):
    """User → Profile (1-1)."""

    async def test_include_profile_when_present(self) -> None:
        user = await self.db.user.create(
            data={"email": "inc_11@test.com", "username": "inc_11", "displayName": "IncOne"}
        )
        profile = await self.db.profile.create(data={"userId": user.id, "bio": "Hello world"})
        fetched = await self.db.user.find_unique(where={"id": user.id}, include={"profile": True})
        self.assertIsNotNone(fetched)
        self.assertIsNotNone(fetched.profile)
        self.assertEqual(fetched.profile.bio, "Hello world")
        await self.db.profile.delete(where={"id": profile.id})
        await self.db.user.delete(where={"id": user.id})

    async def test_include_profile_when_absent(self) -> None:
        user = await self.db.user.create(
            data={"email": "inc_11b@test.com", "username": "inc_11b", "displayName": "NoProfile"}
        )
        fetched = await self.db.user.find_unique(where={"id": user.id}, include={"profile": True})
        self.assertIsNotNone(fetched)
        self.assertIsNone(fetched.profile)
        await self.db.user.delete(where={"id": user.id})


class TestIncludeOneToMany(PrismaTestCase):
    """User → Post[] (1-n)."""

    async def test_include_posts(self) -> None:
        user = await self.db.user.create(
            data={"email": "inc_1n@test.com", "username": "inc_1n", "displayName": "IncMany"}
        )
        p1 = await self.db.post.create(
            data={"title": "Post 1", "slug": "post-1-inc", "content": "body", "authorId": user.id}
        )
        p2 = await self.db.post.create(
            data={"title": "Post 2", "slug": "post-2-inc", "content": "body", "authorId": user.id}
        )
        fetched = await self.db.user.find_unique(where={"id": user.id}, include={"posts": True})
        self.assertIsNotNone(fetched)
        self.assertIsNotNone(fetched.posts)
        self.assertEqual(len(fetched.posts), 2)
        self.assertEqual({p.slug for p in fetched.posts}, {"post-1-inc", "post-2-inc"})
        await self.db.post.delete(where={"id": p1.id})
        await self.db.post.delete(where={"id": p2.id})
        await self.db.user.delete(where={"id": user.id})

    async def test_include_posts_empty_list(self) -> None:
        user = await self.db.user.create(
            data={"email": "inc_1n_empty@test.com", "username": "inc_1n_empty", "displayName": "NoPosts"}
        )
        fetched = await self.db.user.find_unique(where={"id": user.id}, include={"posts": True})
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.posts, [])
        await self.db.user.delete(where={"id": user.id})

    async def test_include_posts_on_find_many(self) -> None:
        u1 = await self.db.user.create(data={"email": "fm_inc1@test.com", "username": "fm_inc1", "displayName": "FM1"})
        u2 = await self.db.user.create(data={"email": "fm_inc2@test.com", "username": "fm_inc2", "displayName": "FM2"})
        p = await self.db.post.create(
            data={"title": "FM Post", "slug": "fm-post-inc", "content": "body", "authorId": u1.id}
        )
        users = await self.db.user.find_many(
            where={"email": {"in_": ["fm_inc1@test.com", "fm_inc2@test.com"]}},
            include={"posts": True},
        )
        by_id = {u.id: u for u in users}
        self.assertEqual(len(by_id[u1.id].posts), 1)
        self.assertEqual(len(by_id[u2.id].posts), 0)
        await self.db.post.delete(where={"id": p.id})
        await self.db.user.delete(where={"id": u1.id})
        await self.db.user.delete(where={"id": u2.id})


class TestIncludeManyToMany(PrismaTestCase):
    """Post ↔ Tag via PostTag (n-m explicit join table)."""

    async def test_include_tags_on_post(self) -> None:
        user = await self.db.user.create(data={"email": "nm_user@test.com", "username": "nm_user", "displayName": "NM"})
        post = await self.db.post.create(
            data={"title": "Tagged Post", "slug": "tagged-post-nm", "content": "body", "authorId": user.id}
        )
        tag1 = await self.db.tag.create(data={"name": "python-nm"})
        tag2 = await self.db.tag.create(data={"name": "prisma-nm"})
        await self.db.postTag.create(data={"postId": post.id, "tagId": tag1.id})
        await self.db.postTag.create(data={"postId": post.id, "tagId": tag2.id})

        fetched = await self.db.post.find_unique(where={"id": post.id}, include={"tags": True})
        self.assertIsNotNone(fetched)
        self.assertIsNotNone(fetched.tags)
        self.assertEqual(len(fetched.tags), 2)

        await self.db.postTag.delete(where={"postId": post.id, "tagId": tag1.id})
        await self.db.postTag.delete(where={"postId": post.id, "tagId": tag2.id})
        await self.db.tag.delete(where={"id": tag1.id})
        await self.db.tag.delete(where={"id": tag2.id})
        await self.db.post.delete(where={"id": post.id})
        await self.db.user.delete(where={"id": user.id})
