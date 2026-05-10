"""Integration tests for composite primary key operations (PostTag model)."""

from .prisma_test_case import PrismaTestCase


class TestCompositeKey(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(data={"email": "ck@test.com", "username": "ck_user", "displayName": "CK"})
        self.post = await self.db.post.create(
            data={
                "title": "CK Post",
                "slug": "ck-post",
                "content": "body",
                "authorId": self.user.id,
            }
        )
        self.tag1 = await self.db.tag.create(data={"name": "ck-tag-1"})
        self.tag2 = await self.db.tag.create(data={"name": "ck-tag-2"})

    async def asyncTearDown(self) -> None:
        try:
            await self.db.postTag.delete_many(where={"postId": self.post.id})
        except Exception:
            pass
        for delete_call in [
            lambda: self.db.post.delete(where={"id": self.post.id}),
            lambda: self.db.tag.delete(where={"id": self.tag1.id}),
            lambda: self.db.tag.delete(where={"id": self.tag2.id}),
            lambda: self.db.user.delete(where={"id": self.user.id}),
        ]:
            try:
                await delete_call()
            except Exception:
                pass
        await super().asyncTearDown()

    # ------------------------------------------------------------------
    # find_unique with composite key
    # ------------------------------------------------------------------

    async def test_find_unique_with_both_keys_returns_row(self) -> None:
        await self.db.postTag.create(data={"postId": self.post.id, "tagId": self.tag1.id})
        row = await self.db.postTag.find_unique(where={"postId": self.post.id, "tagId": self.tag1.id})
        self.assertIsNotNone(row)
        self.assertEqual(row.postId, self.post.id)
        self.assertEqual(row.tagId, self.tag1.id)

    async def test_find_unique_returns_none_when_no_match(self) -> None:
        row = await self.db.postTag.find_unique(where={"postId": self.post.id, "tagId": self.tag1.id})
        self.assertIsNone(row)

    async def test_find_unique_distinguishes_rows_by_both_keys(self) -> None:
        await self.db.postTag.create(data={"postId": self.post.id, "tagId": self.tag1.id})
        await self.db.postTag.create(data={"postId": self.post.id, "tagId": self.tag2.id})

        row1 = await self.db.postTag.find_unique(where={"postId": self.post.id, "tagId": self.tag1.id})
        row2 = await self.db.postTag.find_unique(where={"postId": self.post.id, "tagId": self.tag2.id})
        self.assertIsNotNone(row1)
        self.assertIsNotNone(row2)
        self.assertEqual(row1.tagId, self.tag1.id)
        self.assertEqual(row2.tagId, self.tag2.id)

    # ------------------------------------------------------------------
    # delete with composite key
    # ------------------------------------------------------------------

    async def test_delete_with_both_keys_removes_correct_row(self) -> None:
        await self.db.postTag.create(data={"postId": self.post.id, "tagId": self.tag1.id})
        await self.db.postTag.create(data={"postId": self.post.id, "tagId": self.tag2.id})

        await self.db.postTag.delete(where={"postId": self.post.id, "tagId": self.tag1.id})

        remaining = await self.db.postTag.find_many(where={"postId": self.post.id})
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].tagId, self.tag2.id)

    async def test_delete_nonexistent_composite_key_returns_none(self) -> None:
        result = await self.db.postTag.delete(where={"postId": self.post.id, "tagId": self.tag1.id})
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # create and find_many
    # ------------------------------------------------------------------

    async def test_create_and_find_many_for_post(self) -> None:
        await self.db.postTag.create(data={"postId": self.post.id, "tagId": self.tag1.id})
        await self.db.postTag.create(data={"postId": self.post.id, "tagId": self.tag2.id})

        rows = await self.db.postTag.find_many(where={"postId": self.post.id})
        self.assertEqual(len(rows), 2)
        tag_ids = {r.tagId for r in rows}
        self.assertIn(self.tag1.id, tag_ids)
        self.assertIn(self.tag2.id, tag_ids)
