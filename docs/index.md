# Prismaa

A Python Prisma client backed by SQLAlchemy — no Node.js or Rust at runtime.

Prismaa reads a standard `schema.prisma` file and generates a fully-typed async Python client. All queries run through SQLAlchemy Core — SQLite, PostgreSQL, and any other SQLAlchemy dialect work out of the box.

---

## Install

```bash
pip install prismaa
```

For PostgreSQL:

```bash
pip install "prismaa[postgresql]"
```

---

## Quick start

```bash
# Generate the Python client from your schema
prismaa generate --schema schema.prisma
```

```python
from prisma import Prisma

db = Prisma()
await db.connect("sqlite+aiosqlite:///dev.db")

user = await db.user.create(data={"email": "alice@example.com", "name": "Alice"})

posts = await db.post.find_many(
    where={"author": {"email": "alice@example.com"}, "published": True},
    include={"author": True},
    order={"createdAt": "desc"},
)

await db.disconnect()
```

---

## Features

- **Pure Python runtime** — no Node.js process, no Rust binary at query time
- **Async-first** — every method is `async`; built for `asyncio`
- **Fully typed** — Pydantic v2 models, TypedDict query inputs, typed relation attributes
- **Prisma v7 schema** — standard schema format; official Prisma CLI handles migrations
- **SQLAlchemy backend** — JOIN-based relation filtering, connection pooling, any dialect
- **Rich query API** — filtering, ordering, pagination, `distinct`, `include`, `select`, transactions, raw queries, aggregations

---

## Why Prismaa?

The original [prisma-client-py](https://github.com/RobertCraigie/prisma-client-py) is no longer maintained and requires a Rust query engine and a Node.js subprocess at every query. Prismaa replaces that runtime with a pure SQLAlchemy layer — the Prisma CLI is only needed during development for schema migrations, never at runtime.

---

## Next steps

- [Getting Started](getting-started.md) — build a working app from scratch
- [Prisma CLI Setup](prisma-setup.md) — one-time Node.js and migrations setup
- [Schema Reference](schema-reference.md) — field types, relations, attributes
- [API Reference](api/find-many.md) — all query methods
