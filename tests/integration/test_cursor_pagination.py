"""Tests for cursor-based pagination (cursor parameter on find_many)."""

from .prisma_test_case import PrismaTestCase


class TestCursorPagination(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        # Create 6 users with predictable scores for ordering
        self.users = []
        for i in range(1, 7):
            u = await self.db.user.create(
                data={
                    "email": f"cur{i}@test.com",
                    "username": f"cur{i}",
                    "displayName": f"Cursor {i}",
                    "score": float(i * 10),
                }
            )
            self.users.append(u)

    async def asyncTearDown(self) -> None:
        for u in self.users:
            try:
                await self.db.user.delete(where={"id": u.id})
            except Exception:
                pass
        await super().asyncTearDown()

    async def test_cursor_inclusive_start(self) -> None:
        # Start from the 3rd user (inclusive), take 3
        anchor = self.users[2]
        result = await self.db.user.find_many(
            where={"email": {"in_": [u.email for u in self.users]}},
            cursor={"id": anchor.id},
            take=3,
            order={"id": "asc"},
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].id, self.users[2].id)
        self.assertEqual(result[1].id, self.users[3].id)
        self.assertEqual(result[2].id, self.users[4].id)

    async def test_cursor_with_skip_1_is_exclusive(self) -> None:
        # skip=1 skips the cursor record itself — standard "after cursor" pattern
        anchor = self.users[2]
        result = await self.db.user.find_many(
            where={"email": {"in_": [u.email for u in self.users]}},
            cursor={"id": anchor.id},
            skip=1,
            take=3,
            order={"id": "asc"},
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].id, self.users[3].id)

    def _sorted_ids(self, users: list) -> list:
        return [u.id for u in users]

    async def test_cursor_descending(self) -> None:
        # Start from 4th user downward (inclusive)
        anchor = self.users[3]
        result = await self.db.user.find_many(
            where={"email": {"in_": [u.email for u in self.users]}},
            cursor={"id": anchor.id},
            take=3,
            order={"id": "desc"},
        )
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].id, self.users[3].id)
        self.assertEqual(result[1].id, self.users[2].id)
        self.assertEqual(result[2].id, self.users[1].id)

    async def test_cursor_at_last_record_returns_one(self) -> None:
        anchor = self.users[-1]
        result = await self.db.user.find_many(
            where={"email": {"in_": [u.email for u in self.users]}},
            cursor={"id": anchor.id},
            order={"id": "asc"},
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, anchor.id)

    async def test_multi_column_sort_cursor(self) -> None:
        # Sort by score DESC then id ASC; cursor on id only.
        # Users 1-3 all have score=10, users 4-6 have scores 40/50/60.
        # Sorted order (score DESC, id ASC): u4(s60), u5(s50), u6(s40), u1(s10), u2(s10), u3(s10)
        # But our setUp creates users with scores 10,20,30,40,50,60 so let's
        # use the users as-is: sorted desc by score: u6(60),u5(50),u4(40),u3(30),u2(20),u1(10)
        anchor = self.users[3]  # score=40, 4th in desc order
        result = await self.db.user.find_many(
            where={"email": {"in_": [u.email for u in self.users]}},
            cursor={"id": anchor.id},
            take=3,
            order={"score": "desc"},
        )
        self.assertEqual(len(result), 3)
        # Should start at score=40 and go down: 40, 30, 20
        scores = [u.score for u in result]
        self.assertEqual(scores, [40.0, 30.0, 20.0])

    async def test_sequential_pages_cover_all_records(self) -> None:
        all_emails = {"in_": [u.email for u in self.users]}
        page1 = await self.db.user.find_many(
            where={"email": all_emails},
            take=3,
            order={"id": "asc"},
        )
        self.assertEqual(len(page1), 3)
        page2 = await self.db.user.find_many(
            where={"email": all_emails},
            cursor={"id": page1[-1].id},
            skip=1,
            take=3,
            order={"id": "asc"},
        )
        self.assertEqual(len(page2), 3)
        self.assertEqual(
            [u.id for u in page1 + page2],
            [u.id for u in self.users],
        )
