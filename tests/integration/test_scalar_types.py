"""Integration tests for scalar type round-trips."""

import datetime
from decimal import Decimal

from .prisma_test_case import PrismaTestCase


class TestScalarTypes(PrismaTestCase):
    # ------------------------------------------------------------------
    # Bytes
    # ------------------------------------------------------------------

    async def test_bytes_round_trip(self) -> None:
        payload = b"\x00\xff\x1a\x2b hello"
        asset = await self.db.asset.create(
            data={
                "name": "test.bin",
                "mimeType": "application/octet-stream",
                "data": payload,
                "sizeBytes": len(payload),
            }
        )
        fetched = await self.db.asset.find_unique(where={"id": asset.id})
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.data, payload)
        await self.db.asset.delete(where={"id": asset.id})

    # ------------------------------------------------------------------
    # BigInt
    # ------------------------------------------------------------------

    async def test_bigint_beyond_32bit(self) -> None:
        big = 2**40  # ~1 TB; beyond 32-bit, within SQLite's signed 64-bit range
        asset = await self.db.asset.create(
            data={
                "name": "big.bin",
                "mimeType": "application/octet-stream",
                "data": b"x",
                "sizeBytes": big,
            }
        )
        fetched = await self.db.asset.find_unique(where={"id": asset.id})
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.sizeBytes, big)
        await self.db.asset.delete(where={"id": asset.id})

    async def test_bigint_default_zero(self) -> None:
        user = await self.db.user.create(
            data={
                "email": "st_bigint@test.com",
                "username": "st_bigint",
                "displayName": "BT",
            }
        )
        post = await self.db.post.create(
            data={
                "title": "BigInt Default",
                "slug": "bigint-default",
                "content": "body",
                "authorId": user.id,
            }
        )
        self.assertEqual(post.viewCount, 0)
        await self.db.post.delete(where={"id": post.id})
        await self.db.user.delete(where={"id": user.id})

    # ------------------------------------------------------------------
    # Decimal
    # ------------------------------------------------------------------

    async def test_decimal_precision_round_trip(self) -> None:
        user = await self.db.user.create(
            data={
                "email": "st_dec@test.com",
                "username": "st_dec",
                "displayName": "Dec",
            }
        )
        post = await self.db.post.create(
            data={
                "title": "Decimal Test",
                "slug": "decimal-test",
                "content": "body",
                "authorId": user.id,
                "rating": Decimal("123.456"),
            }
        )
        fetched = await self.db.post.find_unique(where={"id": post.id})
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.rating, Decimal("123.456"))
        await self.db.post.delete(where={"id": post.id})
        await self.db.user.delete(where={"id": user.id})

    # ------------------------------------------------------------------
    # Json
    # ------------------------------------------------------------------

    async def test_json_round_trip(self) -> None:
        user = await self.db.user.create(
            data={
                "email": "st_json@test.com",
                "username": "st_json",
                "displayName": "Json",
            }
        )
        profile = await self.db.profile.create(
            data={
                "userId": user.id,
                "metadata": {"key": [1, 2]},
            }
        )
        fetched = await self.db.profile.find_unique(where={"id": profile.id})
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.metadata, {"key": [1, 2]})
        await self.db.profile.delete(where={"id": profile.id})
        await self.db.user.delete(where={"id": user.id})

    # ------------------------------------------------------------------
    # DateTime
    # ------------------------------------------------------------------

    async def test_datetime_naive_round_trip(self) -> None:
        dt = datetime.datetime(2024, 6, 15, 12, 30, 45)
        asset = await self.db.asset.create(
            data={
                "name": "dt.bin",
                "mimeType": "application/octet-stream",
                "data": b"x",
                "sizeBytes": 1,
            }
        )
        await self.db.asset.update(where={"id": asset.id}, data={"createdAt": dt})
        fetched = await self.db.asset.find_unique(where={"id": asset.id})
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.createdAt.replace(tzinfo=None), dt)
        await self.db.asset.delete(where={"id": asset.id})
