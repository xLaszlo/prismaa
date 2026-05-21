# Schema Reference

Aprisma uses the standard [Prisma schema language](https://www.prisma.io/docs/concepts/components/prisma-schema). This page covers the features Aprisma supports and any Aprisma-specific generator options.

---

## Generator block

```prisma
generator client {
  provider  = "aprisma"
  output    = "./prisma"      # where to write the generated client
  interface = "asyncio"       # only asyncio is supported
}
```

| Option | Values | Description |
|---|---|---|
| `provider` | `"aprisma"` | Required — selects the Aprisma generator |
| `output` | path | Directory for the generated `client.py` |
| `interface` | `"asyncio"` | Client interface style |

---

## Datasource block

```prisma
datasource db {
  provider = "sqlite"   # or "postgresql"
}
```

No `url` is set in the schema — the connection URL is passed to `db.connect()` at runtime. The `provider` field is used by the Prisma CLI for migrations.

---

## Scalar types

| Prisma type | Python type | Notes |
|---|---|---|
| `String` | `str` | |
| `Int` | `int` | |
| `BigInt` | `int` | Python `int` handles arbitrary precision |
| `Float` | `float` | |
| `Decimal` | `Decimal` | `decimal.Decimal` |
| `Boolean` | `bool` | |
| `DateTime` | `datetime` | `datetime.datetime` (naive UTC) |
| `Bytes` | `bytes` | |
| `Json` | `Any` | Stored as text; round-trips as Python object |

Append `?` to make any field nullable (`String?`, `Int?`, etc.). A nullable field is `None` in Python when no value is stored.

---

## Default values

```prisma
id        Int      @id @default(autoincrement())
createdAt DateTime @default(now())
isActive  Boolean  @default(true)
score     Float    @default(0.0)
```

---

## Field attributes

| Attribute | Description |
|---|---|
| `@id` | Marks the primary key |
| `@unique` | Adds a unique constraint; field can be used in `find_unique` |
| `@default(...)` | Sets a default value |
| `@map("col_name")` | Maps the Prisma field to a different column name |
| `@updatedAt` | Automatically set to the current time on every update |

---

## Model attributes

| Attribute | Description |
|---|---|
| `@@id([fieldA, fieldB])` | Composite primary key |
| `@@unique([fieldA, fieldB])` | Composite unique constraint |
| `@@index([fieldA, fieldB])` | Creates an index (handled by Prisma CLI) |
| `@@map("table_name")` | Maps the model to a different table name |
| `@@ignore` | Excludes the model from the generated client |

---

## Relations

### One-to-many

```prisma
model User {
  id    Int    @id @default(autoincrement())
  posts Post[]
}

model Post {
  id       Int  @id @default(autoincrement())
  authorId Int
  author   User @relation(fields: [authorId], references: [id])
}
```

`Post.authorId` is the foreign key. `User.posts` is the back-reference list.

### One-to-one

```prisma
model User {
  id      Int      @id @default(autoincrement())
  profile Profile?
}

model Profile {
  id     Int  @id @default(autoincrement())
  userId Int  @unique
  user   User @relation(fields: [userId], references: [id])
}
```

### Many-to-many (explicit join table)

```prisma
model Post {
  id   Int       @id @default(autoincrement())
  tags PostTag[]
}

model Tag {
  id    Int       @id @default(autoincrement())
  name  String    @unique
  posts PostTag[]
}

model PostTag {
  postId Int  @map("post_id")
  tagId  Int  @map("tag_id")
  post   Post @relation(fields: [postId], references: [id])
  tag    Tag  @relation(fields: [tagId], references: [id])

  @@id([postId, tagId])
}
```

---

## Enums

```prisma
enum Role {
  USER
  ADMIN
  MODERATOR
}

model User {
  id   Int    @id @default(autoincrement())
  role Role   @default(USER)
}
```

Enums are stored as strings. The generated Python client exposes them as `str` values matching the Prisma enum member names.

---

## Unsupported types

Fields declared with `Unsupported("...")` are excluded from the generated client. Use raw queries (`query_raw`, `execute_raw`) to interact with those columns.
