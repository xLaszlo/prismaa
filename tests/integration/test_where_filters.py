"""Tests for WhereInput filter operations: scalar filters, AND/OR/NOT, ordering, pagination."""

import pytest
from prisma import Prisma


@pytest.fixture
async def three_users(db: Prisma):
    """Create three users for filter tests; yield them; clean up."""
    u1 = await db.user.create(
        data={
            "email": "filter_alpha@test.com",
            "username": "filter_alpha",
            "displayName": "Alpha",
            "score": 1.0,
            "isActive": True,
        }
    )
    u2 = await db.user.create(
        data={
            "email": "filter_beta@test.com",
            "username": "filter_beta",
            "displayName": "Beta",
            "score": 5.0,
            "isActive": True,
        }
    )
    u3 = await db.user.create(
        data={
            "email": "filter_gamma@test.com",
            "username": "filter_gamma",
            "displayName": "Gamma",
            "score": 9.0,
            "isActive": False,
        }
    )
    yield u1, u2, u3
    for u in (u1, u2, u3):
        await db.user.delete(where={"id": u.id})


class TestStringFilter:
    async def test_contains(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(where={"email": {"contains": "filter_"}})
        assert len(users) == 3

    async def test_startswith(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(where={"email": {"startswith": "filter_alpha"}})
        assert len(users) == 1
        assert users[0].username == "filter_alpha"

    async def test_endswith(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(where={"email": {"endswith": "@test.com"}})
        # at least the 3 fixture users
        assert any(u.username == "filter_beta" for u in users)

    async def test_equals(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(where={"email": {"equals": "filter_gamma@test.com"}})
        assert len(users) == 1

    async def test_in(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(where={"email": {"in_": ["filter_alpha@test.com", "filter_beta@test.com"]}})
        assert len(users) == 2

    async def test_not_in(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(where={"email": {"not_in": ["filter_alpha@test.com", "filter_gamma@test.com"]}})
        emails = [u.email for u in users]
        assert "filter_beta@test.com" in emails
        assert "filter_alpha@test.com" not in emails


class TestFloatFilter:
    async def test_gt(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(where={"score": {"gt": 4.0}, "email": {"startswith": "filter_"}})
        assert all(u.score > 4.0 for u in users)
        assert len(users) == 2

    async def test_lt(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(where={"score": {"lt": 5.0}, "email": {"startswith": "filter_"}})
        assert all(u.score < 5.0 for u in users)

    async def test_gte(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(where={"score": {"gte": 5.0}, "email": {"startswith": "filter_"}})
        assert all(u.score >= 5.0 for u in users)
        assert len(users) == 2

    async def test_lte(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(where={"score": {"lte": 5.0}, "email": {"startswith": "filter_"}})
        assert all(u.score <= 5.0 for u in users)
        assert len(users) == 2


class TestBoolFilter:
    async def test_bool_equality(self, db: Prisma, three_users) -> None:
        active = await db.user.find_many(where={"isActive": True, "email": {"startswith": "filter_"}})
        inactive = await db.user.find_many(where={"isActive": False, "email": {"startswith": "filter_"}})
        assert len(active) == 2
        assert len(inactive) == 1
        assert inactive[0].username == "filter_gamma"


class TestLogicFilters:
    async def test_and(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(
            where={"AND": [{"isActive": True}, {"score": {"gt": 3.0}}, {"email": {"startswith": "filter_"}}]}
        )
        assert len(users) == 1
        assert users[0].username == "filter_beta"

    async def test_or(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(
            where={"OR": [{"score": {"lt": 2.0}}, {"score": {"gt": 8.0}}], "email": {"startswith": "filter_"}}
        )
        assert len(users) == 2
        usernames = {u.username for u in users}
        assert usernames == {"filter_alpha", "filter_gamma"}

    async def test_not(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(where={"NOT": {"isActive": True}, "email": {"startswith": "filter_"}})
        assert len(users) == 1
        assert users[0].username == "filter_gamma"


class TestOrderingAndPagination:
    async def test_order_asc(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(
            where={"email": {"startswith": "filter_"}},
            order={"score": "asc"},
        )
        scores = [u.score for u in users]
        assert scores == sorted(scores)

    async def test_order_desc(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(
            where={"email": {"startswith": "filter_"}},
            order={"score": "desc"},
        )
        scores = [u.score for u in users]
        assert scores == sorted(scores, reverse=True)

    async def test_take_limits_results(self, db: Prisma, three_users) -> None:
        users = await db.user.find_many(
            where={"email": {"startswith": "filter_"}},
            order={"score": "asc"},
            take=2,
        )
        assert len(users) == 2

    async def test_skip_offsets_results(self, db: Prisma, three_users) -> None:
        all_users = await db.user.find_many(
            where={"email": {"startswith": "filter_"}},
            order={"score": "asc"},
        )
        skipped = await db.user.find_many(
            where={"email": {"startswith": "filter_"}},
            order={"score": "asc"},
            skip=1,
        )
        assert len(skipped) == len(all_users) - 1
        assert skipped[0].id == all_users[1].id
