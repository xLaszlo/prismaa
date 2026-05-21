# Aprisma

**A Python Prisma client backed by SQLAlchemy — no Node.js or Rust at runtime.**

Aprisma reads a standard `schema.prisma` file and generates a fully-typed async Python client. All queries run through [SQLAlchemy Core](https://docs.sqlalchemy.org/en/20/core/) — SQLite, PostgreSQL, and any other SQLAlchemy dialect work out of the box.

```python
db = Prisma()
await db.connect("sqlite+aiosqlite:///dev.db")

alice = await db.user.create(data={"email": "alice@example.com", "name": "Alice"})

posts = await db.post.find_many(
    where={"author": {"email": "alice@example.com"}, "published": True},
    include={"author": True},
    order={"createdAt": "desc"},
)

await db.disconnect()
```

---

## Why Aprisma?

The original [prisma-client-py](https://github.com/RobertCraigie/prisma-client-py) is no longer maintained and requires a Rust query engine and a Node.js subprocess at **every query**. Aprisma replaces that with a pure-Python SQLAlchemy layer — the Prisma CLI is only used during development to manage migrations, never at runtime.

| | prisma-client-py | **Aprisma** |
|---|---|---|
| Runtime dependency | Rust engine + Node.js | None |
| Query layer | Prisma Query Engine | SQLAlchemy Core |
| Schema format | Prisma schema | Prisma schema |
| Async support | Yes | Yes |
| Type safety | Yes | Yes (Pydantic v2) |

---

## Features

- **Pure Python runtime** — no Node.js process, no Rust binary, no subprocess at query time
- **Async-first** — every method is `async`; built for `asyncio`
- **Fully typed** — Pydantic v2 models, TypedDict query inputs, typed relation attributes
- **Prisma v7 schema** — use the standard schema format and the official Prisma CLI for migrations
- **SQLAlchemy backend** — JOIN-based relation filtering, correlated EXISTS subqueries, connection pooling
- **Rich query API** — filtering, ordering, pagination (offset and cursor), `distinct`, `include`, `select`, transactions, raw queries, `group_by` aggregations

---

## Installation

```bash
pip install aprisma
```

For PostgreSQL:

```bash
pip install "aprisma[postgresql]"
```

> Aprisma uses the Prisma CLI (a Node.js tool) for schema migrations. It is only needed during development — see [Prisma CLI Setup](https://xlaszlo.github.io/aprisma/prisma-setup/) for a one-time setup guide.

---

## Quick start

### 1. Write a schema

```prisma
# schema.prisma

generator client {
  provider  = "aprisma"
  output    = "./prisma"
  interface = "asyncio"
}

datasource db {
  provider = "sqlite"
}

model User {
  id    Int    @id @default(autoincrement())
  email String @unique
  name  String
  posts Post[]
}

model Post {
  id        Int     @id @default(autoincrement())
  title     String
  content   String
  published Boolean @default(false)
  authorId  Int
  author    User    @relation(fields: [authorId], references: [id])
}
```

### 2. Push the schema and generate the client

```bash
# Push schema to the database (creates tables)
npx prisma db push --url "file:./dev.db"

# Generate the Python client
aprisma generate --schema schema.prisma
```

### 3. Use it

```python
import asyncio
from prisma import Prisma

async def main():
    db = Prisma()
    await db.connect("sqlite+aiosqlite:///dev.db")

    # Create a user
    alice = await db.user.create(
        data={"email": "alice@example.com", "name": "Alice"}
    )

    # Create a post linked to that user
    post = await db.post.create(
        data={"title": "Hello world", "content": "My first post.", "authorId": alice.id},
        include={"author": True},
    )
    print(post.author.name)  # Alice

    # Filter posts through a related model
    posts = await db.post.find_many(
        where={"author": {"email": "alice@example.com"}},
        include={"author": True},
        order={"title": "asc"},
    )

    # Update
    await db.post.update(
        where={"id": post.id},
        data={"published": True},
    )

    # Count
    n = await db.post.count(where={"published": True})
    print(f"{n} published post(s)")

    # Delete
    await db.post.delete(where={"id": post.id})

    await db.disconnect()

asyncio.run(main())
```

---

## Database support

| Database | Driver | Install |
|---|---|---|
| SQLite | `aiosqlite` | included |
| PostgreSQL | `asyncpg` | `pip install "aprisma[postgresql]"` |
| Any SQLAlchemy dialect | bring your own | pass the URL to `connect()` |

---

## Documentation

Full documentation: **[xlaszlo.github.io/aprisma](https://xlaszlo.github.io/aprisma)**

---

## Contributing

Found a bug or have a feature idea? Please open an issue on [GitHub Issues](https://github.com/xLaszlo/aprisma/issues) with a minimal reproducible description of the problem or feature. **Please do not open pull requests** — a clear issue description is more useful than a PR without prior discussion.
