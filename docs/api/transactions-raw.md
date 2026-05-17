# Transactions & Raw Queries

## Transactions

Use the `tx()` async context manager to run multiple operations atomically. If any operation raises an exception, all changes are rolled back.

```python
async with db.tx() as tx:
    user = await tx.user.create(data={"email": "alice@example.com", "name": "Alice"})
    await tx.post.create(
        data={"title": "First post", "content": "...", "authorId": user.id}
    )
    # both writes commit when the block exits without error
```

Every model delegate is available on `tx` with the same API as on `db`. An exception inside the block (including a constraint violation) automatically rolls back the transaction.

---

## Raw queries

For queries that go beyond the generated API — complex JOINs, database-specific functions, bulk operations — use the raw query methods on the client.

### query_raw

Executes a SELECT and returns a list of `dict` rows.

```python
rows = await db.query_raw(
    'SELECT id, email FROM "User" WHERE id = :uid',
    uid=1,
)
# [{"id": 1, "email": "alice@example.com"}]
```

**Positional parameters** — use `?` placeholders and pass values as positional arguments:

```python
rows = await db.query_raw('SELECT * FROM "Post" WHERE id = ?', 42)
```

**Named parameters** — use `:name` placeholders and pass values as keyword arguments:

```python
rows = await db.query_raw(
    'SELECT * FROM "Post" WHERE author_id = :aid AND published = :pub',
    aid=1, pub=True,
)
```

---

### query_first

Like `query_raw` but returns only the first row as a `dict`, or `None` if there are no results.

```python
row = await db.query_first('SELECT * FROM "User" WHERE email = :e', e="alice@example.com")
if row:
    print(row["id"])
```

---

### execute_raw

Executes a non-SELECT statement (INSERT, UPDATE, DELETE, DDL) and returns the number of rows affected.

```python
count = await db.execute_raw(
    'UPDATE "Post" SET published = ? WHERE author_id = ?',
    True, 1,
)
print(f"{count} row(s) updated")
```
