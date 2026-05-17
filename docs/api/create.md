# create / create_many

## create

Creates a single record and returns it.

```python
user = await db.user.create(
    data={"email": "alice@example.com", "name": "Alice"}
)
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `data` | `dict` | Field values for the new record |
| `include` | `dict` | Relations to load on the returned record |

### Nullable fields

Omitting a nullable field stores `NULL`. You can also pass `None` explicitly:

```python
post = await db.post.create(
    data={"title": "Draft", "content": "...", "authorId": 1, "publishedAt": None}
)
```

### Nested writes — connect

Link to an existing related record by its unique field:

```python
post = await db.post.create(
    data={
        "title": "My post",
        "content": "...",
        "author": {"connect": {"email": "alice@example.com"}},
    },
    include={"author": True},
)
```

### Nested writes — connectOrCreate

Connect to an existing record or create it if it does not exist:

```python
post = await db.post.create(
    data={
        "title": "My post",
        "content": "...",
        "author": {
            "connectOrCreate": {
                "where": {"email": "alice@example.com"},
                "create": {"email": "alice@example.com", "name": "Alice"},
            }
        },
    }
)
```

### Errors

- Unique constraint violation → `UniqueViolationError`
- Foreign key constraint violation → `ForeignKeyViolationError`

---

## create_many

Creates multiple records in a single round-trip. Returns the number of rows inserted.

```python
count = await db.post.create_many(
    data=[
        {"title": "Post 1", "content": "...", "authorId": 1},
        {"title": "Post 2", "content": "...", "authorId": 1},
    ]
)
print(count)  # 2
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `data` | `list[dict]` | List of records to insert |
| `skip_duplicates` | `bool` | Skip rows that violate a unique constraint instead of raising |

`create_many` does not support `include` — use `find_many` afterwards if you need the created records with relations.
