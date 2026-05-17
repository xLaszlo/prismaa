# update / update_many / upsert

## update

Updates a single record and returns it. Raises `RecordNotFoundError` if no record matches `where`.

```python
post = await db.post.update(
    where={"id": 1},
    data={"published": True, "title": "Updated title"},
)
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `where` | `dict` | Unique field(s) to identify the record |
| `data` | `dict` | Fields to update |
| `include` | `dict` | Relations to load on the returned record |

### Setting a field to null

Pass `None` to clear a nullable field:

```python
await db.post.update(where={"id": 1}, data={"publishedAt": None})
```

### Atomic numeric updates

Update numeric fields relative to their current value, without a read-modify-write cycle:

```python
# Increment view count by 1
await db.post.update(
    where={"id": 1},
    data={"viewCount": {"increment": 1}},
)

# Multiply score by 1.1
await db.post.update(
    where={"id": 1},
    data={"score": {"multiply": 1.1}},
)
```

**Supported operators:** `increment`, `decrement`, `multiply`, `divide`

### Nested writes — connect / disconnect

Reassign or clear a FK-side relation:

```python
# Reassign post to a different author
await db.post.update(
    where={"id": 1},
    data={"author": {"connect": {"email": "bob@example.com"}}},
)

# Clear a nullable relation
await db.post.update(
    where={"id": 1},
    data={"category": {"disconnect": True}},
)
```

---

## update_many

Updates all records matching `where`. Returns the number of rows affected.

```python
count = await db.post.update_many(
    where={"published": False},
    data={"published": True},
)
print(count)  # number of rows updated
```

`where` supports the same filter syntax as `find_many`. Returns `0` if no records match.

---

## upsert

Creates a record if it does not exist, or updates it if it does. Returns the record.

```python
user = await db.user.upsert(
    where={"email": "alice@example.com"},
    create={"email": "alice@example.com", "name": "Alice"},
    update={"name": "Alice (updated)"},
)
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `where` | `dict` | Unique field(s) to look up the existing record |
| `create` | `dict` | Data for the new record if it does not exist |
| `update` | `dict` | Data to apply if the record already exists |
| `include` | `dict` | Relations to load on the returned record |
