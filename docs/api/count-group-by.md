# count / group_by

## count

Returns the number of records matching the filter.

```python
n = await db.post.count()                           # total rows
n = await db.post.count(where={"published": True})  # filtered
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `where` | `dict` | Filter conditions |
| `take` | `int` | Count only within a window of this size |
| `skip` | `int` | Skip this many rows before the window |
| `select` | `dict[str, bool]` | Count non-null values per field (returns `dict`) |

### Field-level counts

```python
counts = await db.post.count(select={"title": True, "publishedAt": True})
# {"title": 42, "publishedAt": 17}
# publishedAt is lower because nullable rows are not counted
```

---

## group_by

Groups records by one or more fields and computes aggregations.

```python
results = await db.post.group_by(
    by=["authorId"],
    count={"_all": True},
    avg={"score": True},
    order_by={"_avg": {"score": "desc"}},
)
for row in results:
    print(row["authorId"], row["_count"]["_all"], row["_avg"]["score"])
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `by` | `list[str]` | Fields to group by |
| `where` | `dict` | Filter applied before grouping |
| `count` | `dict` or `True` | Count records per group |
| `avg` | `dict[str, bool]` | Average of numeric fields |
| `sum_` | `dict[str, bool]` | Sum of numeric fields |
| `min_` | `dict[str, bool]` | Minimum value |
| `max_` | `dict[str, bool]` | Maximum value |
| `order_by` | `dict` or `list[dict]` | Sort the groups |
| `take` | `int` | Limit number of groups returned |
| `skip` | `int` | Skip this many groups |

### Return shape

Each item in the result list contains the group-by field values plus nested aggregation dicts:

```python
{
    "authorId": 1,
    "_count": {"_all": 5},
    "_avg": {"score": 3.8},
    "_sum": {"score": 19.0},
}
```
