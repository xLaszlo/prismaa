"""Tests for nullable field round-trips in create, update, and where filters."""

from .prisma_test_case import PrismaTestCase


class TestNullableCreate(PrismaTestCase):
    """Nullable fields in create: explicit None and omitted fields both store NULL."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(data={"email": "nf_u@test.com", "username": "nf_u", "displayName": "NF"})

    async def asyncTearDown(self) -> None:
        await self.db.profile.delete_many(where={"userId": self.user.id})
        await self.db.user.delete_many(where={"email": "nf_u@test.com"})
        await super().asyncTearDown()

    async def test_create_with_explicit_none_stores_null(self) -> None:
        profile = await self.db.profile.create(data={"userId": self.user.id, "bio": None, "avatarUrl": None})
        self.assertIsNone(profile.bio)
        self.assertIsNone(profile.avatarUrl)

    async def test_create_omitting_nullable_field_stores_null(self) -> None:
        profile = await self.db.profile.create(data={"userId": self.user.id})
        self.assertIsNone(profile.bio)
        self.assertIsNone(profile.avatarUrl)

    async def test_create_with_value_then_read_back(self) -> None:
        profile = await self.db.profile.create(data={"userId": self.user.id, "bio": "hello"})
        self.assertEqual(profile.bio, "hello")
        fetched = await self.db.profile.find_unique(where={"id": profile.id})
        self.assertEqual(fetched.bio, "hello")


class TestNullableUpdate(PrismaTestCase):
    """Setting a populated nullable field to None in update stores NULL."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "nf_upd@test.com", "username": "nf_upd", "displayName": "NFUpd"}
        )
        self.profile = await self.db.profile.create(
            data={"userId": self.user.id, "bio": "initial bio", "avatarUrl": "http://img"}
        )

    async def asyncTearDown(self) -> None:
        await self.db.profile.delete_many(where={"userId": self.user.id})
        await self.db.user.delete_many(where={"email": "nf_upd@test.com"})
        await super().asyncTearDown()

    async def test_update_to_none_clears_field(self) -> None:
        updated = await self.db.profile.update(
            where={"id": self.profile.id},
            data={"bio": None},
        )
        self.assertIsNone(updated.bio)
        # avatarUrl untouched
        self.assertEqual(updated.avatarUrl, "http://img")

    async def test_update_none_to_value_sets_field(self) -> None:
        # First clear, then set
        await self.db.profile.update(where={"id": self.profile.id}, data={"bio": None})
        updated = await self.db.profile.update(
            where={"id": self.profile.id},
            data={"bio": "new bio"},
        )
        self.assertEqual(updated.bio, "new bio")

    async def test_update_to_none_persists_on_read(self) -> None:
        await self.db.profile.update(where={"id": self.profile.id}, data={"bio": None})
        fetched = await self.db.profile.find_unique(where={"id": self.profile.id})
        self.assertIsNone(fetched.bio)


class TestNullablePostFields(PrismaTestCase):
    """Nullable FK (categoryId) and DateTime (publishedAt) on Post."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "nf_post@test.com", "username": "nf_post", "displayName": "NFPost"}
        )
        self.cat = await self.db.category.create(data={"name": "nf_cat"})

    async def asyncTearDown(self) -> None:
        await self.db.post.delete_many(where={"slug": {"in_": ["nf-p1", "nf-p2"]}})
        await self.db.category.delete_many(where={"name": "nf_cat"})
        await self.db.user.delete_many(where={"email": "nf_post@test.com"})
        await super().asyncTearDown()

    async def test_create_post_nullable_fk_none(self) -> None:
        post = await self.db.post.create(
            data={"title": "NF1", "slug": "nf-p1", "content": "x", "authorId": self.user.id}
        )
        self.assertIsNone(post.categoryId)

    async def test_update_nullable_fk_to_none(self) -> None:
        post = await self.db.post.create(
            data={
                "title": "NF2",
                "slug": "nf-p2",
                "content": "x",
                "authorId": self.user.id,
                "categoryId": self.cat.id,
            }
        )
        self.assertEqual(post.categoryId, self.cat.id)
        updated = await self.db.post.update(
            where={"id": post.id},
            data={"categoryId": None},
        )
        self.assertIsNone(updated.categoryId)


class TestNullableWhereFilter(PrismaTestCase):
    """`where` with None translates to IS NULL; non-None translates to IS NOT NULL."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.u1 = await self.db.user.create(
            data={"email": "nf_wh1@test.com", "username": "nf_wh1", "displayName": "W1"}
        )
        self.u2 = await self.db.user.create(
            data={"email": "nf_wh2@test.com", "username": "nf_wh2", "displayName": "W2"}
        )
        # u1 has bio; u2 has no bio
        self.p1 = await self.db.profile.create(data={"userId": self.u1.id, "bio": "has bio"})
        self.p2 = await self.db.profile.create(data={"userId": self.u2.id})

    async def asyncTearDown(self) -> None:
        await self.db.profile.delete_many(where={"userId": {"in_": [self.u1.id, self.u2.id]}})
        await self.db.user.delete_many(where={"email": {"in_": ["nf_wh1@test.com", "nf_wh2@test.com"]}})
        await super().asyncTearDown()

    async def test_where_none_returns_null_rows(self) -> None:
        profiles = await self.db.profile.find_many(where={"userId": {"in_": [self.u1.id, self.u2.id]}, "bio": None})
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].userId, self.u2.id)

    async def test_where_not_none_returns_non_null_rows(self) -> None:
        profiles = await self.db.profile.find_many(
            where={"userId": {"in_": [self.u1.id, self.u2.id]}, "bio": {"not_": None}}
        )
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].userId, self.u1.id)

    async def test_where_equals_none_is_null(self) -> None:
        profiles = await self.db.profile.find_many(
            where={"userId": {"in_": [self.u1.id, self.u2.id]}, "bio": {"equals": None}}
        )
        self.assertEqual(len(profiles), 1)
        self.assertIsNone(profiles[0].bio)
