"""Integration tests for select field subset."""

from .prisma_test_case import PrismaTestCase


class TestSelectFindUnique(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "sel@test.com", "username": "sel_user", "displayName": "Sel"}
        )

    async def asyncTearDown(self) -> None:
        try:
            await self.db.user.delete(where={"id": self.user.id})
        except Exception:
            pass
        await super().asyncTearDown()

    async def test_select_returns_only_specified_fields(self) -> None:
        result = await self.db.user.find_unique(
            where={"id": self.user.id},
            select={"id": True, "email": True},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.user.id)
        self.assertEqual(result.email, "sel@test.com")
        # unselected fields are absent from the constructed model
        self.assertFalse(hasattr(result, "username") and result.username is not None)

    async def test_select_single_field(self) -> None:
        result = await self.db.user.find_unique(
            where={"id": self.user.id},
            select={"email": True},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.email, "sel@test.com")

    async def test_select_unknown_field_raises(self) -> None:
        with self.assertRaises(ValueError):
            await self.db.user.find_unique(
                where={"id": self.user.id},
                select={"nonExistentField": True},
            )

    async def test_select_returns_none_when_no_match(self) -> None:
        result = await self.db.user.find_unique(
            where={"id": 999999},
            select={"id": True, "email": True},
        )
        self.assertIsNone(result)


class TestSelectFindMany(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.u1 = await self.db.user.create(
            data={"email": "smany1@test.com", "username": "smany1", "displayName": "SM1", "score": 1.0}
        )
        self.u2 = await self.db.user.create(
            data={"email": "smany2@test.com", "username": "smany2", "displayName": "SM2", "score": 2.0}
        )

    async def asyncTearDown(self) -> None:
        for u in (self.u1, self.u2):
            try:
                await self.db.user.delete(where={"id": u.id})
            except Exception:
                pass
        await super().asyncTearDown()

    async def test_select_applies_to_all_rows(self) -> None:
        results = await self.db.user.find_many(
            where={"email": {"in_": ["smany1@test.com", "smany2@test.com"]}},
            select={"id": True, "email": True},
        )
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIsNotNone(r.id)
            self.assertIsNotNone(r.email)

    async def test_select_with_order(self) -> None:
        results = await self.db.user.find_many(
            where={"email": {"in_": ["smany1@test.com", "smany2@test.com"]}},
            select={"email": True, "score": True},
            order={"score": "asc"},
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].email, "smany1@test.com")
        self.assertEqual(results[1].email, "smany2@test.com")


class TestSelectWithInclude(PrismaTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.user = await self.db.user.create(
            data={"email": "sinc@test.com", "username": "sinc_user", "displayName": "SInc"}
        )
        self.profile = await self.db.profile.create(data={"userId": self.user.id, "bio": "select+include bio"})

    async def asyncTearDown(self) -> None:
        try:
            await self.db.profile.delete(where={"id": self.profile.id})
        except Exception:
            pass
        try:
            await self.db.user.delete(where={"id": self.user.id})
        except Exception:
            pass
        await super().asyncTearDown()

    async def test_select_with_include_returns_relation_and_selected_scalars(self) -> None:
        result = await self.db.user.find_unique(
            where={"id": self.user.id},
            select={"id": True, "email": True},
            include={"profile": True},
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.user.id)
        self.assertEqual(result.email, "sinc@test.com")
        self.assertIsNotNone(result.profile)
        self.assertEqual(result.profile.bio, "select+include bio")
