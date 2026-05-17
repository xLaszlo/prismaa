"""Tests for group_by with aggregations: avg, sum, min_, max_, count."""

from .prisma_test_case import PrismaTestCase


class TestGroupBy(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        # active users: scores 10, 20, 30
        self.active = []
        for i, score in enumerate([10.0, 20.0, 30.0], start=1):
            u = await self.db.user.create(
                data={
                    "email": f"gb_a{i}@test.com",
                    "username": f"gb_a{i}",
                    "displayName": f"Active {i}",
                    "isActive": True,
                    "score": score,
                }
            )
            self.active.append(u)
        # inactive users: scores 5, 15
        self.inactive = []
        for i, score in enumerate([5.0, 15.0], start=1):
            u = await self.db.user.create(
                data={
                    "email": f"gb_i{i}@test.com",
                    "username": f"gb_i{i}",
                    "displayName": f"Inactive {i}",
                    "isActive": False,
                    "score": score,
                }
            )
            self.inactive.append(u)

    async def asyncTearDown(self) -> None:
        all_emails = [u.email for u in self.active + self.inactive]
        await self.db.user.delete_many(where={"email": {"in_": all_emails}})
        await super().asyncTearDown()

    async def test_group_by_count_all(self) -> None:
        results = await self.db.user.group_by(
            by=["isActive"],
            where={"email": {"in_": [u.email for u in self.active + self.inactive]}},
            count=True,
            order_by={"isActive": "desc"},
        )
        self.assertEqual(len(results), 2)
        active_row = next(r for r in results if r["isActive"] is True)
        inactive_row = next(r for r in results if r["isActive"] is False)
        self.assertEqual(active_row["_count"]["_all"], 3)
        self.assertEqual(inactive_row["_count"]["_all"], 2)

    async def test_group_by_avg(self) -> None:
        results = await self.db.user.group_by(
            by=["isActive"],
            where={"email": {"in_": [u.email for u in self.active + self.inactive]}},
            avg={"score": True},
            order_by={"isActive": "desc"},
        )
        active_row = next(r for r in results if r["isActive"] is True)
        inactive_row = next(r for r in results if r["isActive"] is False)
        self.assertAlmostEqual(active_row["_avg"]["score"], 20.0)
        self.assertAlmostEqual(inactive_row["_avg"]["score"], 10.0)

    async def test_group_by_sum(self) -> None:
        results = await self.db.user.group_by(
            by=["isActive"],
            where={"email": {"in_": [u.email for u in self.active + self.inactive]}},
            sum_={"score": True},
            order_by={"isActive": "desc"},
        )
        active_row = next(r for r in results if r["isActive"] is True)
        self.assertAlmostEqual(active_row["_sum"]["score"], 60.0)

    async def test_group_by_min_max(self) -> None:
        results = await self.db.user.group_by(
            by=["isActive"],
            where={"email": {"in_": [u.email for u in self.active + self.inactive]}},
            min_={"score": True},
            max_={"score": True},
            order_by={"isActive": "desc"},
        )
        active_row = next(r for r in results if r["isActive"] is True)
        self.assertAlmostEqual(active_row["_min"]["score"], 10.0)
        self.assertAlmostEqual(active_row["_max"]["score"], 30.0)

    async def test_group_by_all_aggregations(self) -> None:
        results = await self.db.user.group_by(
            by=["isActive"],
            where={"email": {"in_": [u.email for u in self.active + self.inactive]}},
            count=True,
            avg={"score": True},
            sum_={"score": True},
            min_={"score": True},
            max_={"score": True},
            order_by={"isActive": "desc"},
        )
        active_row = next(r for r in results if r["isActive"] is True)
        self.assertEqual(active_row["_count"]["_all"], 3)
        self.assertAlmostEqual(active_row["_avg"]["score"], 20.0)
        self.assertAlmostEqual(active_row["_sum"]["score"], 60.0)
        self.assertAlmostEqual(active_row["_min"]["score"], 10.0)
        self.assertAlmostEqual(active_row["_max"]["score"], 30.0)

    async def test_group_by_with_where(self) -> None:
        results = await self.db.user.group_by(
            by=["isActive"],
            where={"email": {"in_": [u.email for u in self.active]}, "isActive": True},
            count=True,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["_count"]["_all"], 3)

    async def test_group_by_with_take(self) -> None:
        results = await self.db.user.group_by(
            by=["isActive"],
            where={"email": {"in_": [u.email for u in self.active + self.inactive]}},
            count=True,
            order_by={"isActive": "desc"},
            take=1,
        )
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["isActive"])
