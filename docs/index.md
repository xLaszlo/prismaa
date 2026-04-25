# Prismaa

A production-grade Python Prisma client — no Node.js runtime, no Rust binary.

Prismaa reads your `schema.prisma` file and generates a fully-typed async/sync Python client backed by SQLAlchemy Core. Schema migrations are handled by the [official Prisma CLI](https://www.prisma.io/docs/orm/prisma-migrate/getting-started).

## Quick start

```bash
pip install prismaa
```

Generate the client from your schema:

```bash
prismaa generate --schema schema.prisma
```

Use it:

```python
from prisma import Prisma

async with Prisma(url="sqlite+aiosqlite:///./dev.db") as db:
    user = await db.user.create(data={"name": "Alice", "email": "alice@example.com"})
    users = await db.user.find_many(where={"email": {"contains": "@example.com"}})
```

## Features

- Pure Python — no Node.js or Rust required at runtime
- Async (`asyncio`) and sync clients generated from the same schema
- SQLAlchemy Core query layer — supports SQLite, PostgreSQL, and any other SQLAlchemy dialect
- Fully typed: Pydantic v2 models, TypedDict inputs, typed relations
- Prisma v7 schema compatibility
