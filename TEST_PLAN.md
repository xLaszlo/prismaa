# TEST_PLAN.md

## Progress Checklist

### Steps (compatibility work)
- [x] Step 1 — `find_first` coverage
- [x] Step 2 — Connection lifecycle
- [x] Step 3 — Scalar type round-trips
- [x] Step 4 — Composite primary key operations
- [x] Step 5 — Nested include (multi-level)
- [x] Step 6 — Error types and constraints
- [x] Step 7 — `select` field subset
- [ ] Step 8 — PostgreSQL parity
- [ ] Step 9 — Ordering by multiple fields
- [ ] Step 10 — `distinct` and field-level aggregation

### Issues not covered by tests
- [ ] 1. `where` with `None` value → `IS NULL`
- [ ] 2. `in_` with empty list
- [ ] 3. `not_in` with empty list
- [ ] 4. `startswith`/`endswith`/`contains` case sensitivity on PostgreSQL
- [ ] 5. `order_by` with `None` or empty dict guard
- [ ] 6. `include` with `where` sub-filter
- [ ] 7. `include` on `create`
- [ ] 8. `include` on `update`
- [ ] 9. `include` on `upsert`
- [ ] 10. Self-referential relations
- [ ] 11. `DateTime` storage format on SQLite
- [ ] 12. `Json` field query filters
- [ ] 13. `Decimal` in `where` filter
- [ ] 14. `create` with explicit `id` on autoincrement field
- [ ] 15. `update_many` with no matching rows returns `0`
- [ ] 16. `upsert` with `include`
- [ ] 17. `create_many` with `skip_duplicates=True` on PostgreSQL
- [ ] 18. Custom SQLAlchemy dialect documentation/test
- [ ] 19. Connection pool exhaustion
- [ ] 20. Transaction support
- [ ] 21. `@@unique` composite uniqueness in `find_unique`
- [ ] 22. `@map` column names in `where` filters (explicit test)
- [ ] 23. `@@ignore` model exclusion from generated client

---

## Scope

This plan covers test coverage needed for drop-in compatibility with the legacy `prisma-client-py` public API, constrained to the Prismaa implementation spec:

- **SQLAlchemy query execution with runtime (dynamic) query generation** — no Rust engine, no pre-generated per-method query builders
- **Migration is out of scope** — Prisma CLI (`npx prisma db push` / `migrate`) handles schema changes
- **Database targets**: SQLite (primary) and PostgreSQL — additional databases available via SQLAlchemy driver URL
- **Async-first** — sync wrapper is a later concern
- **Test style** — all new integration tests use `unittest.IsolatedAsyncioTestCase` with `self.assertXXX` assertions; DB is created once per class in `setUpClass`, client is connected/disconnected in `asyncSetUp`/`asyncTearDown`
- **Running tests** — always use `uv run --locked pytest ...`; the `--locked` flag prevents uv from silently updating the venv. Same applies to `uv sync` → `uv sync --locked`. All CI workflow steps follow this convention.

---

## Current Test Coverage

### Unit tests
- `tests/unit/test_lexer.py` — tokenizer (complete for parser spec)
- `tests/unit/test_parser.py` — AST construction (complete for parser spec)

### Integration tests (SQLite only)
- `tests/integration/test_user_crud.py` — create, find_unique, find_many, update, delete, upsert, count
- `tests/integration/test_create_many.py` — create_many (skip_duplicates), delete_many, update_many
- `tests/integration/test_where_filters.py` — string/float/bool filters, AND/OR/NOT, ordering, pagination
- `tests/integration/test_include.py` — 1-1, 1-n, n-m relation loading

---

## Steps to Reach Compatibility

Steps are ordered by value/risk. Each step maps to a new or expanded test file.

### Step 1 — `find_first` coverage

`AsyncModelDelegate.find_first` exists but has no tests. It is part of the public API and differs from `find_unique` (returns first match, no uniqueness requirement, supports `order_by` + `skip`).

**New file**: `tests/integration/test_find_first.py`

- Returns `None` when no rows match
- Returns first row when multiple match (respects `order_by` for determinism)
- Supports `skip` to offset before taking first
- `where` filter is optional (no args returns first overall row)

---

### Step 2 — Connection lifecycle

There are no tests for client connect/disconnect or context-manager usage. These are the first things a user touches.

**New file**: `tests/integration/test_connection.py`

- `await db.connect()` + `await db.disconnect()` explicit lifecycle
- `async with Prisma(datasource=...) as db` context manager connects and disconnects automatically
- Using a delegate before `connect()` raises a clear error (not `AttributeError` or `NoneType`)
- Double `connect()` is idempotent or raises a clear error
- `disconnect()` without prior `connect()` is safe

---

### Step 3 — Scalar type round-trips

Currently only `String`, `Int`, `Float`, `Boolean`, and `DateTime` receive incidental coverage. The schema includes models with `Bytes`, `BigInt`, `Decimal`, and `Json` fields but none are exercised in integration tests.

**New file**: `tests/integration/test_scalar_types.py`

Using the `Asset` model (has `Bytes`) and extending fixture schema if needed:

- `Bytes` field: create with `b"..."`, read back, assert equality
- `BigInt` field: values beyond `sys.maxsize`, round-trip
- `Decimal` field: `Decimal("123.456")`, precision preserved on round-trip
- `Json` field: store `{"key": [1, 2]}`, read back as equivalent Python object
- `DateTime` field: naive datetime stored and retrieved, timezone-aware value stored and retrieved (PostgreSQL-relevant)

---

### Step 4 — Composite primary key operations

`PostTag` uses `@@id([postId, tagId])` — a composite PK. There are no tests verifying that `find_unique`, `update`, and `delete` work correctly when the `where` dict must specify multiple fields.

**Extend**: `tests/integration/test_include.py` (or new `test_composite_key.py`)

- `find_unique(where={"postId": ..., "tagId": ...})` — returns correct row
- `delete(where={"postId": ..., "tagId": ...})` — deletes correct row
- `find_unique` with only one key field raises a clear error (not a silent miss)

---

### Step 5 — Nested include (multi-level)

Current include tests load one level deep. Legacy client supports nested includes: `include={"posts": {"include": {"tags": True}}}`. This is important for real applications.

**New file**: `tests/integration/test_nested_include.py`

- `User` → `posts` → `tags` (two levels deep)
- `User` → `profile` + `posts` (multiple relations at same level)
- `Post` → `author` (reverse 1-n, back to parent)
- Nested include with empty intermediate relation (no posts → tags list is empty, not error)

---

### Step 6 — Error types and constraints

No tests verify that the right exception types are raised on constraint violations or missing records.

**New file**: `tests/integration/test_errors.py`

- `create` with duplicate unique field raises an exception (not silent); verify it is a subclass of the documented error hierarchy (not raw `sqlalchemy.exc`)
- `update(where=...)` on non-existent record raises `RecordNotFoundError` (or returns `None` — verify which behavior is intended and test it consistently)
- `create` violating a foreign key constraint raises a clear error
- `find_unique` on a field that is not `@id` or `@unique` raises a clear error at call time

---

### Step 7 — `select` field subset

Legacy client supports `select={"id": True, "email": True}` to limit which fields are returned. This reduces data transfer and is expected by users coming from the legacy API.

**New file**: `tests/integration/test_select.py`

- `find_unique(where=..., select={"id": True, "email": True})` returns model with only those fields populated, others are `None` or absent
- `find_many(select=...)` applies to all rows
- `select` combined with `include` returns relation plus selected scalars
- Requesting a field that does not exist raises a clear error

---

### Step 8 — PostgreSQL parity

All current integration tests run only against SQLite. Compatibility with PostgreSQL must be validated with the same test scenarios.

**New conftest option**: `tests/conftest.py` should support a `--db-url` CLI flag or `TEST_DATABASE_URL` environment variable so the full integration suite runs unchanged against `postgresql+asyncpg://...`.

**CI matrix**: add a second job in `.github/workflows/ci.yml` that spins up PostgreSQL (via `services:`) and runs `pytest tests/integration/ --db-url postgresql+asyncpg://...`.

PostgreSQL-specific edge cases to test:

- `RETURNING *` after insert (already used but validate field order independence)
- `DateTime` with timezone-aware values (PostgreSQL `TIMESTAMPTZ` vs SQLite text)
- Case sensitivity of identifiers (all table/column names must be lower-cased or quoted)
- `ILIKE` vs `LIKE` for `contains`/`startswith`/`endswith` (SQLite is case-insensitive by default; PostgreSQL is not)

---

### Step 9 — Ordering by multiple fields and by relation fields

Current ordering tests cover a single `order_by` field with `asc`/`desc`. Legacy client accepts a list of order expressions.

**Extend**: `tests/integration/test_where_filters.py`

- `order_by=[{"score": "desc"}, {"name": "asc"}]` — deterministic tie-break ordering
- `order_by` with a `@map`-renamed column still resolves correctly

---

### Step 10 — `distinct` and field-level aggregation

Legacy client supports `distinct=["field"]` on `find_many` and aggregation via `count` with field selection. These are commonly used.

**New file**: `tests/integration/test_aggregation.py`

- `find_many(distinct=["role"])` returns one row per distinct role value
- `count(where=...)` with string/bool field filters (already present — verify PostgreSQL parity here)
- `count` on a model with zero rows returns `0`, not an error

---

## Issues Not Covered by Tests (Within Spec)

The following gaps exist in the current implementation and test suite. These are not bugs in the existing tests — they are functionality the tests do not verify at all.

### Query building

1. **`where` with `None` value** — `{"bio": None}` should translate to `IS NULL`, not `= NULL`. Currently untested; SQLAlchemy handles it but the `build_where` path may pass `None` directly.

2. **`in_` with empty list** — `{"id": {"in_": []}}` — SQLAlchemy generates `WHERE 1 != 1` (always false) which is correct, but not tested. Important for dynamic queries built from user selections.

3. **`not_in` with empty list** — same concern, inverse: should always match.

4. **`startswith`/`endswith`/`contains` on PostgreSQL** — SQLite `LIKE` is case-insensitive; PostgreSQL `LIKE` is case-sensitive. The behavior difference is undocumented and untested. Either use `ILIKE` on PostgreSQL or document the difference.

5. **`order_by` with `None` or empty dict** — no guard; likely falls through to unsorted, but untested.

### Relation loading

6. **`include` with `where` sub-filter** — e.g., `include={"posts": {"where": {"published": True}}}`. The legacy client supports this. Prismaa's `include.py` currently accepts only `True`, not a sub-query dict. There are no tests that document this limitation, so a user would discover it by breaking.

7. **`include` on `create`** — `create(data=..., include={"profile": True})` should return the newly created record with the related record attached. Not tested.

8. **`include` on `update`** — same gap.

9. **`include` on `upsert`** — same gap.

10. **Self-referential relations** — not in the fixture schema, not tested.

### Type handling

11. **`DateTime` storage format on SQLite** — SQLite stores datetimes as text. The exact format (ISO 8601 with/without microseconds, UTC offset) is never asserted, so interoperability with data written by another tool is unverified.

12. **`Json` field query filters** — legacy client supports `path`-based JSON filters. Prismaa stores `Json` as `Text`; JSON-path filtering is not implemented or tested.

13. **`Decimal` in `where` filter** — `Decimal` comparison operators (`gt`, `lt`, etc.) exist in the generated `DecimalFilter` TypedDict but are not integration-tested.

### Create/update operations

14. **`create` with an explicit `id`** — when the schema has `@default(autoincrement())`, passing `id` in `data` should either override the default or raise; behavior is unspecified and untested.

15. **`update_many` with no matching rows** — should return `0`; not tested.

16. **`upsert` with `include`** — not tested.

17. **`create_many` with `skip_duplicates=True` on PostgreSQL** — translates to `INSERT ... ON CONFLICT DO NOTHING`; SQLite generates the same via `INSERT OR IGNORE`. The PostgreSQL variant needs a test to confirm the translated SQL is correct.

### Connection and dialect extensibility

18. **Custom SQLAlchemy dialect** — the design intent is that any dialect works by changing the URL. There is no test or documented example showing a third dialect (e.g., `mysql+aiomysql://`) being wired in without code changes.

19. **Connection pool exhaustion** — no test for what happens when all pool connections are in use (relevant for high-concurrency use).

20. **Transaction support** — `execute_write` wraps each statement in its own transaction. Multi-statement transactions (rollback on partial failure) are not exposed in the public API and not tested.

### Generated code

21. **`@@unique` composite uniqueness** — `Comment` has `@@unique([postId, authorId])`. `find_unique` with this composite key is not tested.

22. **`@map` column names in `where` filters** — `Profile` maps fields to snake_case column names. Filter dict keys use Prisma field names but must resolve to mapped column names internally. This is tested implicitly in CRUD but not explicitly in filter tests.

23. **`@@ignore` model exclusion** — `FtsIndex` has `@@ignore`. No test verifies that the generated client does not expose a `fts_index` delegate at all.
