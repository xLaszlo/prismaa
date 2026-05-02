"""Tests for include: loading related records across 1-1, 1-n, and n-m relations."""

from prisma import Prisma


class TestIncludeOneToOne:
    """User → Profile (1-1)."""

    async def test_include_profile_when_present(self, db: Prisma) -> None:
        user = await db.user.create(data={"email": "inc_11@test.com", "username": "inc_11", "displayName": "IncOne"})
        profile = await db.profile.create(data={"userId": user.id, "bio": "Hello world"})
        fetched = await db.user.find_unique(where={"id": user.id}, include={"profile": True})
        assert fetched is not None
        assert fetched.profile is not None
        assert fetched.profile.bio == "Hello world"
        await db.profile.delete(where={"id": profile.id})
        await db.user.delete(where={"id": user.id})

    async def test_include_profile_when_absent(self, db: Prisma) -> None:
        user = await db.user.create(
            data={"email": "inc_11b@test.com", "username": "inc_11b", "displayName": "NoProfile"}
        )
        fetched = await db.user.find_unique(where={"id": user.id}, include={"profile": True})
        assert fetched is not None
        assert fetched.profile is None
        await db.user.delete(where={"id": user.id})


class TestIncludeOneToMany:
    """User → Post[] (1-n)."""

    async def test_include_posts(self, db: Prisma) -> None:
        user = await db.user.create(data={"email": "inc_1n@test.com", "username": "inc_1n", "displayName": "IncMany"})
        p1 = await db.post.create(
            data={"title": "Post 1", "slug": "post-1-inc", "content": "body", "authorId": user.id}
        )
        p2 = await db.post.create(
            data={"title": "Post 2", "slug": "post-2-inc", "content": "body", "authorId": user.id}
        )
        fetched = await db.user.find_unique(where={"id": user.id}, include={"posts": True})
        assert fetched is not None
        assert fetched.posts is not None
        assert len(fetched.posts) == 2
        slugs = {p.slug for p in fetched.posts}
        assert slugs == {"post-1-inc", "post-2-inc"}
        await db.post.delete(where={"id": p1.id})
        await db.post.delete(where={"id": p2.id})
        await db.user.delete(where={"id": user.id})

    async def test_include_posts_empty_list(self, db: Prisma) -> None:
        user = await db.user.create(
            data={"email": "inc_1n_empty@test.com", "username": "inc_1n_empty", "displayName": "NoPosts"}
        )
        fetched = await db.user.find_unique(where={"id": user.id}, include={"posts": True})
        assert fetched is not None
        assert fetched.posts == []
        await db.user.delete(where={"id": user.id})

    async def test_include_posts_on_find_many(self, db: Prisma) -> None:
        u1 = await db.user.create(data={"email": "fm_inc1@test.com", "username": "fm_inc1", "displayName": "FM1"})
        u2 = await db.user.create(data={"email": "fm_inc2@test.com", "username": "fm_inc2", "displayName": "FM2"})
        p = await db.post.create(data={"title": "FM Post", "slug": "fm-post-inc", "content": "body", "authorId": u1.id})
        users = await db.user.find_many(
            where={"email": {"in_": ["fm_inc1@test.com", "fm_inc2@test.com"]}},
            include={"posts": True},
        )
        by_id = {u.id: u for u in users}
        assert len(by_id[u1.id].posts) == 1
        assert len(by_id[u2.id].posts) == 0
        await db.post.delete(where={"id": p.id})
        await db.user.delete(where={"id": u1.id})
        await db.user.delete(where={"id": u2.id})


class TestIncludeManyToMany:
    """Post ↔ Tag via PostTag (n-m explicit join table)."""

    async def test_include_tags_on_post(self, db: Prisma) -> None:
        user = await db.user.create(data={"email": "nm_user@test.com", "username": "nm_user", "displayName": "NM"})
        post = await db.post.create(
            data={"title": "Tagged Post", "slug": "tagged-post-nm", "content": "body", "authorId": user.id}
        )
        tag1 = await db.tag.create(data={"name": "python-nm"})
        tag2 = await db.tag.create(data={"name": "prisma-nm"})
        await db.postTag.create(data={"postId": post.id, "tagId": tag1.id})
        await db.postTag.create(data={"postId": post.id, "tagId": tag2.id})

        fetched = await db.post.find_unique(where={"id": post.id}, include={"tags": True})
        assert fetched is not None
        assert fetched.tags is not None
        assert len(fetched.tags) == 2

        # cleanup
        await db.postTag.delete(where={"postId": post.id, "tagId": tag1.id})
        await db.postTag.delete(where={"postId": post.id, "tagId": tag2.id})
        await db.tag.delete(where={"id": tag1.id})
        await db.tag.delete(where={"id": tag2.id})
        await db.post.delete(where={"id": post.id})
        await db.user.delete(where={"id": user.id})
