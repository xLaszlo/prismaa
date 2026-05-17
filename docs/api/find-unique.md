# find_unique / find_first

## find_unique

Returns a single record by a unique field (`@id` or `@unique`). Returns `None` if no match is found.

```python
user = await db.user.find_unique(where={"id": 1})
user = await db.user.find_unique(where={"email": "alice@example.com"})

# With relations
user = await db.user.find_unique(
    where={"id": 1},
    include={"posts": True, "profile": True},
)
```

`where` must contain at least one field marked `@id` or `@unique` in the schema. Passing a non-unique field raises `ValueError`.

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `where` | `dict` | Unique field(s) to match |
| `include` | `dict` | Relations to load |
| `select` | `dict[str, bool]` | Return only selected fields |

---

## find_unique_or_raise

Same as `find_unique` but raises `RecordNotFoundError` instead of returning `None`:

```python
from prismaa.errors import RecordNotFoundError

try:
    user = await db.user.find_unique_or_raise(where={"id": 999})
except RecordNotFoundError:
    print("not found")
```

---

## find_first

Returns the first record matching the filter, or `None`. Unlike `find_unique`, there is no uniqueness requirement on the `where` fields:

```python
# First published post, newest first
post = await db.post.find_first(
    where={"published": True},
    order={"createdAt": "desc"},
)
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `where` | `dict` | Filter conditions (same syntax as `find_many`) |
| `include` | `dict` | Relations to load |
| `order` | `dict` or `list[dict]` | Sort order |
| `skip` | `int` | Skip this many records before taking the first |
| `select` | `dict[str, bool]` | Return only selected fields |

---

## find_first_or_raise

Same as `find_first` but raises `RecordNotFoundError` instead of returning `None`.
