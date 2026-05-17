# find_many

Returns a list of records matching the given criteria.

```python
records = await db.post.find_many(
    where={"published": True},
    include={"author": True},
    order={"createdAt": "desc"},
    take=10,
    skip=0,
)
```

---

## Parameters

| Parameter | Type | Description |
|---|---|---|
| `where` | `dict` | Filter conditions |
| `include` | `dict` | Relations to load |
| `order` | `dict` or `list[dict]` | Sort order |
| `take` | `int` | Maximum number of records to return |
| `skip` | `int` | Number of records to skip (offset pagination) |
| `distinct` | `list[str]` | Deduplicate by these fields |
| `cursor` | `dict` | Cursor for keyset pagination |
| `select` | `dict[str, bool]` | Return only selected fields |

---

## where

Scalar fields match by equality or by filter operators:

```python
# Equality
where={"published": True}

# Filter operators
where={"title": {"contains": "hello"}}
where={"score": {"gte": 4.5}}
where={"id": {"in_": [1, 2, 3]}}
```

**Supported operators:** `equals`, `not_`, `in_`, `not_in`, `lt`, `lte`, `gt`, `gte`, `contains`, `startswith`, `endswith`

**Null checks:**
```python
where={"bio": None}              # IS NULL
where={"bio": {"not_": None}}   # IS NOT NULL
```

**Compound operators:**
```python
where={"AND": [{"published": True}, {"score": {"gte": 4.0}}]}
where={"OR": [{"title": {"contains": "hello"}}, {"title": {"contains": "world"}}]}
where={"NOT": {"published": True}}
```

**Relation filters** — filter through a related model's fields:

```python
# Posts whose author has a specific email (uses a JOIN internally)
where={"author": {"email": "alice@example.com"}}

# Users who have at least one published post (correlated EXISTS)
where={"posts": {"some": {"published": True}}}

# Users with no published posts
where={"posts": {"none": {"published": True}}}
```

---

## include

Load related records alongside each result. The value is `True` to load all fields, or a dict for nested options:

```python
# Simple include
include={"author": True}

# Nested include
include={"author": {"include": {"profile": True}}}

# Include with sub-filter
include={"posts": {"where": {"published": True}, "order": {"createdAt": "desc"}, "take": 5}}
```

---

## order

Sort by one or more fields. Each entry is a `{field: "asc" | "desc"}` dict:

```python
order={"createdAt": "desc"}
order=[{"score": "desc"}, {"title": "asc"}]
```

---

## take / skip

Offset pagination:

```python
# Page 2 of 10
records = await db.post.find_many(take=10, skip=10)
```

---

## distinct

Return one record per unique combination of the given fields:

```python
# One post per author
posts = await db.post.find_many(distinct=["authorId"], order={"createdAt": "desc"})
```

---

## cursor

Keyset pagination — more efficient than large `skip` offsets. Pass the unique field(s) of the last record from the previous page:

```python
# First page
page1 = await db.post.find_many(take=10, order={"id": "asc"})

# Next page
page2 = await db.post.find_many(
    take=10,
    cursor={"id": page1[-1].id},
    order={"id": "asc"},
)
```

---

## select

Return only specific scalar fields. Omitted fields are `None` on the returned model:

```python
posts = await db.post.find_many(select={"id": True, "title": True})
# post.content is None
```

`select` and `include` can be combined — selected scalar fields plus loaded relations.
