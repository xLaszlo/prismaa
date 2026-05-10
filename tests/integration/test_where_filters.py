"""Tests for WhereInput filter operations: scalar filters, AND/OR/NOT, ordering, pagination."""

from .prisma_test_case import PrismaTestCase


class ThreeUsersTestCase(PrismaTestCase):
    """Provides three pre-created users scoped to each test method."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.u1 = await self.db.user.create(
            data={
                "email": "filter_alpha@test.com",
                "username": "filter_alpha",
                "displayName": "Alpha",
                "score": 1.0,
                "isActive": True,
            }
        )
        self.u2 = await self.db.user.create(
            data={
                "email": "filter_beta@test.com",
                "username": "filter_beta",
                "displayName": "Beta",
                "score": 5.0,
                "isActive": True,
            }
        )
        self.u3 = await self.db.user.create(
            data={
                "email": "filter_gamma@test.com",
                "username": "filter_gamma",
                "displayName": "Gamma",
                "score": 9.0,
                "isActive": False,
            }
        )

    async def asyncTearDown(self) -> None:
        for u in (self.u1, self.u2, self.u3):
            try:
                await self.db.user.delete(where={"id": u.id})
            except Exception:
                pass
        await super().asyncTearDown()


class TestStringFilter(ThreeUsersTestCase):
    async def test_contains(self) -> None:
        users = await self.db.user.find_many(where={"email": {"contains": "filter_"}})
        self.assertEqual(len(users), 3)

    async def test_startswith(self) -> None:
        users = await self.db.user.find_many(where={"email": {"startswith": "filter_alpha"}})
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].username, "filter_alpha")

    async def test_endswith(self) -> None:
        users = await self.db.user.find_many(where={"email": {"endswith": "@test.com"}})
        self.assertTrue(any(u.username == "filter_beta" for u in users))

    async def test_equals(self) -> None:
        users = await self.db.user.find_many(where={"email": {"equals": "filter_gamma@test.com"}})
        self.assertEqual(len(users), 1)

    async def test_in(self) -> None:
        users = await self.db.user.find_many(
            where={"email": {"in_": ["filter_alpha@test.com", "filter_beta@test.com"]}}
        )
        self.assertEqual(len(users), 2)

    async def test_not_in(self) -> None:
        users = await self.db.user.find_many(
            where={"email": {"not_in": ["filter_alpha@test.com", "filter_gamma@test.com"]}}
        )
        emails = [u.email for u in users]
        self.assertIn("filter_beta@test.com", emails)
        self.assertNotIn("filter_alpha@test.com", emails)


class TestFloatFilter(ThreeUsersTestCase):
    async def test_gt(self) -> None:
        users = await self.db.user.find_many(where={"score": {"gt": 4.0}, "email": {"startswith": "filter_"}})
        self.assertTrue(all(u.score > 4.0 for u in users))
        self.assertEqual(len(users), 2)

    async def test_lt(self) -> None:
        users = await self.db.user.find_many(where={"score": {"lt": 5.0}, "email": {"startswith": "filter_"}})
        self.assertTrue(all(u.score < 5.0 for u in users))

    async def test_gte(self) -> None:
        users = await self.db.user.find_many(where={"score": {"gte": 5.0}, "email": {"startswith": "filter_"}})
        self.assertTrue(all(u.score >= 5.0 for u in users))
        self.assertEqual(len(users), 2)

    async def test_lte(self) -> None:
        users = await self.db.user.find_many(where={"score": {"lte": 5.0}, "email": {"startswith": "filter_"}})
        self.assertTrue(all(u.score <= 5.0 for u in users))
        self.assertEqual(len(users), 2)


class TestBoolFilter(ThreeUsersTestCase):
    async def test_bool_equality(self) -> None:
        active = await self.db.user.find_many(where={"isActive": True, "email": {"startswith": "filter_"}})
        inactive = await self.db.user.find_many(where={"isActive": False, "email": {"startswith": "filter_"}})
        self.assertEqual(len(active), 2)
        self.assertEqual(len(inactive), 1)
        self.assertEqual(inactive[0].username, "filter_gamma")


class TestLogicFilters(ThreeUsersTestCase):
    async def test_and(self) -> None:
        users = await self.db.user.find_many(
            where={"AND": [{"isActive": True}, {"score": {"gt": 3.0}}, {"email": {"startswith": "filter_"}}]}
        )
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].username, "filter_beta")

    async def test_or(self) -> None:
        users = await self.db.user.find_many(
            where={"OR": [{"score": {"lt": 2.0}}, {"score": {"gt": 8.0}}], "email": {"startswith": "filter_"}}
        )
        self.assertEqual(len(users), 2)
        self.assertEqual({u.username for u in users}, {"filter_alpha", "filter_gamma"})

    async def test_not(self) -> None:
        users = await self.db.user.find_many(where={"NOT": {"isActive": True}, "email": {"startswith": "filter_"}})
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].username, "filter_gamma")


class TestOrderingAndPagination(ThreeUsersTestCase):
    async def test_order_asc(self) -> None:
        users = await self.db.user.find_many(
            where={"email": {"startswith": "filter_"}},
            order={"score": "asc"},
        )
        scores = [u.score for u in users]
        self.assertEqual(scores, sorted(scores))

    async def test_order_desc(self) -> None:
        users = await self.db.user.find_many(
            where={"email": {"startswith": "filter_"}},
            order={"score": "desc"},
        )
        scores = [u.score for u in users]
        self.assertEqual(scores, sorted(scores, reverse=True))

    async def test_take_limits_results(self) -> None:
        users = await self.db.user.find_many(
            where={"email": {"startswith": "filter_"}},
            order={"score": "asc"},
            take=2,
        )
        self.assertEqual(len(users), 2)

    async def test_skip_offsets_results(self) -> None:
        all_users = await self.db.user.find_many(
            where={"email": {"startswith": "filter_"}},
            order={"score": "asc"},
        )
        skipped = await self.db.user.find_many(
            where={"email": {"startswith": "filter_"}},
            order={"score": "asc"},
            skip=1,
        )
        self.assertEqual(len(skipped), len(all_users) - 1)
        self.assertEqual(skipped[0].id, all_users[1].id)
