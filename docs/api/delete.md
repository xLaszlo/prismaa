# delete / delete_many

## delete

Deletes a single record and returns it. Returns `None` if no record matches `where`.

```python
deleted = await db.post.delete(where={"id": 1})
if deleted:
    print(f"Deleted: {deleted.title}")
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `where` | `dict` | Unique field(s) to identify the record |

`where` must reference a field marked `@id` or `@unique` in the schema.

---

## delete_many

Deletes all records matching `where`. Returns the number of rows deleted.

```python
count = await db.post.delete_many(where={"published": False})
print(f"Deleted {count} draft(s)")
```

Delete everything in a table:

```python
count = await db.post.delete_many()
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `where` | `dict` | Filter conditions (same syntax as `find_many`). Omit to delete all rows. |

`where` supports the same filter and relation-filter syntax as `find_many`. Returns `0` if no records match.
