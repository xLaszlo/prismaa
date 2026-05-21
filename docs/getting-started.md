# Getting Started

This guide walks through building a small blog application with Aprisma from scratch — from installation to running queries.

---

## Prerequisites

- Python 3.11+
- Node.js (for the Prisma CLI — only needed during development). If you haven't set this up yet, follow the [Prisma CLI Setup](prisma-setup.md) guide first.

---

## 1. Install Aprisma

```bash
pip install aprisma
```

For PostgreSQL, add the driver:

```bash
pip install "aprisma[postgresql]"
```

---

## 2. Write the schema

Create `schema.prisma` in your project root:

```prisma
generator client {
  provider  = "aprisma"
  output    = "./prisma"
  interface = "asyncio"
}

datasource db {
  provider = "sqlite"
}

model User {
  id        Int      @id @default(autoincrement())
  email     String   @unique
  name      String
  createdAt DateTime @default(now())
  posts     Post[]
}

model Post {
  id        Int      @id @default(autoincrement())
  title     String
  content   String
  published Boolean  @default(false)
  createdAt DateTime @default(now())
  authorId  Int
  author    User     @relation(fields: [authorId], references: [id])
}
```

The `generator` block tells Aprisma to generate the client into the `./prisma` directory. The `datasource` block sets the database engine — no connection URL is needed here (it is passed at runtime).

---

## 3. Push the schema to the database

For local development, `db push` is the fastest way to apply the schema without creating a migration history:

```bash
npx prisma db push --url "file:./dev.db"
```

For a real project with migrations, use:

```bash
npx prisma migrate dev --name init
```

See the [Prisma CLI Setup](prisma-setup.md) guide for how migrations work.

---

## 4. Generate the Python client

```bash
aprisma generate --schema schema.prisma
```

This creates `./prisma/__init__.py` and `./prisma/client.py`. The generated `Prisma` class is what you import in your application.

---

## 5. Write the application

Create `app.py`:

```python
import asyncio
from prisma import Prisma


async def main() -> None:
    db = Prisma()
    await db.connect("sqlite+aiosqlite:///dev.db")

    # --- Create ---
    alice = await db.user.create(
        data={"email": "alice@example.com", "name": "Alice"}
    )
    bob = await db.user.create(
        data={"email": "bob@example.com", "name": "Bob"}
    )

    post1 = await db.post.create(
        data={"title": "Hello from Alice", "content": "First post.", "authorId": alice.id},
        include={"author": True},
    )
    print(f"Created: '{post1.title}' by {post1.author.name}")

    post2 = await db.post.create(
        data={"title": "Hello from Bob", "content": "Bob's post.", "authorId": bob.id},
    )

    # --- Read ---
    # All published posts, newest first
    published = await db.post.find_many(
        where={"published": True},
        order={"createdAt": "desc"},
        include={"author": True},
    )
    print(f"Published: {len(published)} post(s)")

    # Filter through a relation — posts by Alice
    alice_posts = await db.post.find_many(
        where={"author": {"email": "alice@example.com"}},
    )
    print(f"Alice has {len(alice_posts)} post(s)")

    # --- Update ---
    updated = await db.post.update(
        where={"id": post1.id},
        data={"published": True},
    )
    print(f"Published: {updated.title}")

    # --- Count ---
    n = await db.post.count(where={"published": True})
    print(f"{n} published post(s)")

    # --- Upsert ---
    carol = await db.user.upsert(
        where={"email": "carol@example.com"},
        create={"email": "carol@example.com", "name": "Carol"},
        update={"name": "Carol (updated)"},
    )
    print(f"Upserted: {carol.name}")

    # --- Delete ---
    await db.post.delete_many(where={"authorId": bob.id})
    await db.user.delete(where={"id": bob.id})

    await db.disconnect()


asyncio.run(main())
```

Run it:

```bash
python app.py
```

---

## 6. Transactions

Wrap multiple writes in a transaction using the `tx()` context manager. If any operation raises, all changes are rolled back:

```python
async with db.tx() as tx:
    user = await tx.user.create(data={"email": "dave@example.com", "name": "Dave"})
    await tx.post.create(
        data={"title": "Dave's post", "content": "...", "authorId": user.id}
    )
    # both writes commit together; an exception here rolls back both
```

---

## 7. Raw queries

For queries that go beyond the generated API:

```python
rows = await db.query_raw('SELECT id, email FROM "User" WHERE id = :uid', uid=alice.id)
count = await db.execute_raw('DELETE FROM "Post" WHERE published = ?', False)
```

---

## Next steps

- [Schema Reference](schema-reference.md) — field types, relations, indexes
- [API Reference](api/find-many.md) — all query methods and parameters
- [Prisma CLI Setup](prisma-setup.md) — migrations in production
