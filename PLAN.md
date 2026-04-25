# Prismaa — Implementation Plan

A production-grade, pure-Python Prisma client — no Node.js, no Rust binary, no external runtime dependencies. SQLAlchemy Core is used as the query layer, giving first-class support for every database SQLAlchemy supports.

---

## 1. Vision & Goals

**What:** A drop-in replacement for the retired `prisma-client-py` (RobertCraigie) that works entirely in Python.

**Target Prisma version:** v7 (the retired library's last supported version was v6).

**How it differs from the original:**
- The original required the Prisma CLI (Node.js) and a Rust query-engine binary at runtime.
- Prismaa ships a **Python-native schema parser**, a **Python code generator**, and **Python database adapters**. No Node, no Rust.
- Migrations remain the responsibility of the official Prisma CLI (v7). Prismaa reads the schema only.

**Non-goals (v1):**
- Full Prisma feature parity (no raw queries with typed results, no Prisma Accelerate/Pulse)
- MySQL/MariaDB support (PostgreSQL is Phase 7, SQLite is v1 target — but the architecture is DB-agnostic via SQLAlchemy)
- Schema introspection from an existing database
- Migrations — the official Prisma CLI (Node.js) is used for all schema migrations; Prismaa only reads the schema, never modifies it

---

## 2. Architecture

```
schema.prisma
     │
     ▼
┌─────────────────┐
│  Parser         │  Lexer + recursive descent parser → typed AST
│  (prismaa.parser)│
└────────┬────────┘
         │ AST
         ▼
┌─────────────────┐
│  Generator      │  AST → Jinja2 → generated Python package
│  (prismaa.gen)  │  (Pydantic models, SQLAlchemy Table defs,
│                 │   typed inputs, client stubs)
└────────┬────────┘
         │ generated code
         ▼
┌──────────────────────────────────────────────┐
│  Generated Client  (prisma/)                 │
│  db.user.find_many(where={...})              │
│  db.post.create(data={...})                  │
│                                              │
│  • models.py   — Pydantic v2 model classes   │
│  • tables.py   — SQLAlchemy Core Table objs  │
│  • types.py    — WhereInput, CreateInput …   │
│  • client.py   — typed Prisma class          │
└────────┬─────────────────────────────────────┘
         │ calls generic ModelDelegate
         ▼
┌──────────────────────────────────────┐
│  ModelDelegate  (prismaa.engine)     │  runtime, not generated
│  Builds SQLAlchemy Core expressions  │  from Prisma-style where/
│  at runtime from method arguments    │  order_by/include dicts
└────────┬─────────────────────────────┘
         │ SQLAlchemy Core select/insert/…
         ▼
┌──────────────────────────────────────┐
│  SQLAlchemy Engine                   │
│  AsyncEngine (async)                 │
│  Engine      (sync)                  │
│                                      │
│  SQLite  — sqlite+aiosqlite:// (v1)  │
│  Postgres — postgresql+asyncpg://    │
│  Any other SQLAlchemy dialect        │
└──────────────────────────────────────┘
```

### Runtime query building vs. code generation

Queries are built at **runtime** from the method arguments using SQLAlchemy Core expressions. The alternative — generating per-model query functions at code-generation time — would produce far more generated code with no meaningful speed benefit: SQLAlchemy's compiled statement cache transparently reuses compiled query shapes across calls, so the first call per unique query shape pays ~5–50 µs of Python overhead; subsequent calls with different parameter values hit the cache. Database I/O (even for SQLite in-process) is always ≥ 1 ms and dominates completely.

### 2.1 Core Packages

| Package | Responsibility |
|---------|---------------|
| `prismaa.parser` | Lex and parse `schema.prisma` into an AST |
| `prismaa.generator` | Walk the AST and render Jinja2 templates into the client package |
| `prismaa.engine.delegate` | Generic `AsyncModelDelegate[M]` / `SyncModelDelegate[M]` — runtime query construction via SQLAlchemy Core |
| `prismaa.engine.query` | Translates Prisma-style `where`/`order_by`/`include` dicts → SQLAlchemy Core clauses |
| `prismaa.engine.connection` | Manages `AsyncEngine` / `Engine` lifecycle (connect, disconnect, transactions) |
| `prismaa.cli` | Click-based CLI (`generate` only) |

### 2.2 Generated Output

Running `prismaa generate` writes a `prisma/` package next to `schema.prisma`:

```
prisma/
├── __init__.py        # re-exports Prisma, SyncPrisma
├── client.py          # generated async Prisma class (typed delegates per model)
├── sync_client.py     # generated sync SyncPrisma class
├── models.py          # Pydantic v2 BaseModel per schema model
├── tables.py          # SQLAlchemy Core Table objects (one per model, column types mapped)
└── types.py           # per-model TypedDicts: WhereInput, WhereUniqueInput,
                       # CreateInput, UpdateInput, OrderByInput + scalar filters
```

`models.py` and `tables.py` are kept separate intentionally: Pydantic models are the public API (what callers receive back), SQLAlchemy `Table` objects are the internal query layer (never exposed to callers).

### 2.3 Client API (target)

```python
# Async
from prisma import Prisma

db = Prisma()
await db.connect()

user  = await db.user.create(data={"name": "Alice", "email": "a@ex.com"})
users = await db.user.find_many(where={"email": {"contains": "@ex.com"}},
                                order_by={"name": "asc"}, take=10)
user  = await db.user.find_unique(where={"id": 1})
user  = await db.user.update(where={"id": 1}, data={"name": "Bob"})
n     = await db.user.delete_many(where={"name": "Bob"})
n     = await db.user.count(where={"email": {"ends_with": "@ex.com"}})

# Include relations
u = await db.user.find_unique(where={"id": 1}, include={"posts": True})

await db.disconnect()

# Sync
from prisma import SyncPrisma

with SyncPrisma() as db:
    user = db.user.create(data={"name": "Alice"})
```

---

## 3. Project Layout

```
prismaa/
├── .github/
│   └── workflows/
│       ├── ci.yml              # lint + test on every PR/push
│       ├── release.yml         # tag vX.Y.Z → build + publish to PyPI
│       └── docs.yml            # push to gh-pages on main merge
├── package.json                # prisma dev dependency (Node.js — for test DB setup only)
├── package-lock.json
├── src/
│   └── prismaa/
│       ├── __init__.py
│       ├── cli.py              # click entry point
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── lexer.py        # regex-based tokeniser
│       │   ├── parser.py       # recursive descent parser
│       │   └── ast.py          # dataclass AST nodes
│       ├── generator/
│       │   ├── __init__.py
│       │   ├── generator.py    # orchestrates rendering
│       │   └── templates/
│       │       ├── client.py.j2
│       │       ├── sync_client.py.j2
│       │       ├── models.py.j2
│       │       └── types.py.j2
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── delegate.py     # generic AsyncModelDelegate / SyncModelDelegate
│       │   ├── query.py        # where/order_by/include → SQLAlchemy Core clauses
│       │   └── connection.py   # AsyncEngine / Engine lifecycle
│       └── types/
│           └── common.py       # SortOrder, NullsOrder, etc.
├── tests/
│   ├── conftest.py             # shared fixtures (tmp db path, schema loader)
│   ├── unit/
│   │   ├── test_lexer.py
│   │   ├── test_parser.py
│   │   ├── test_generator.py
│   │   └── test_query_builder.py
│   └── integration/
│       ├── test_crud.py
│       ├── test_relations.py
│       └── test_filters.py
├── example/
│   └── schema.prisma           # canonical test schema (used by conftest to push DB)
├── docs/
│   ├── index.md
│   ├── getting-started.md
│   ├── schema-reference.md
│   ├── api/
│   │   ├── find-many.md
│   │   ├── find-unique.md
│   │   ├── create.md
│   │   ├── update.md
│   │   └── delete.md
│   └── overrides/              # MkDocs Material customisation
├── pyproject.toml
├── .pre-commit-config.yaml
├── .gitignore
├── LICENSE
├── README.md
└── PLAN.md
```

---

## 4. Dependencies

### Runtime

| Package | Purpose |
|---------|---------|
| `pydantic >= 2.0` | Generated model validation + serialisation |
| `sqlalchemy >= 2.0` | Core query building + async/sync engine |
| `aiosqlite >= 0.19` | SQLAlchemy async SQLite dialect (`sqlite+aiosqlite://`) |
| `click >= 8.0` | CLI |
| `jinja2 >= 3.1` | Code generation templates |

**Future database support is just a SQLAlchemy URL change** — `asyncpg` for PostgreSQL, `aiomysql` for MySQL, etc. No new adapter code needed.

### Dev / CI (Python)

| Package | Purpose |
|---------|---------|
| `pytest` | Test runner |
| `pytest-asyncio` | Async test support |
| `pytest-cov` | Coverage |
| `ruff` | Lint + format |
| `pre-commit` | Git hooks |
| `mkdocs-material` | Documentation site |
| `mkdocstrings[python]` | Auto API docs from docstrings |

### Node.js / Prisma CLI (test DB setup only)

`package.json` at the repo root — **not** part of the Python package, never installed by end users.

```json
{
  "devDependencies": {
    "prisma": "^7"
  }
}
```

Used exclusively to run `npx prisma db push` in the test fixture and in CI to create the SQLite test database from `example/schema.prisma`. No other Node tooling is involved.

**Node.js version requirement:** ≥ 18 (Prisma v7 minimum).

---

## 5. Phases & Milestones

### Phase 1 — Project Scaffolding
*Goal: empty repo → runnable `uv run pytest` and green CI*

- [ ] `pyproject.toml` — uv-managed, src layout, all deps declared
- [ ] Ruff configuration (user-provided options) in `pyproject.toml`
- [ ] `.pre-commit-config.yaml` — ruff-check, ruff-format, end-of-file-fixer, trailing-whitespace
- [ ] `package.json` with `prisma ^7` dev dependency
- [ ] `tests/conftest.py` — session-scoped fixture that runs `npx prisma db push` to create a fresh SQLite DB in `tmp_path`
- [ ] GitHub Actions `ci.yml` — matrix (Python 3.11, 3.12, 3.13); steps: setup-node (≥18) → `npm install` → uv install → ruff → pytest
- [ ] GitHub Actions `release.yml` — triggered on `v*` tag, build wheel + sdist, publish to PyPI via Trusted Publisher (OIDC, no token in repo)
- [ ] GitHub Actions `docs.yml` — `mkdocs gh-deploy` on push to `main`
- [ ] MkDocs Material config (`mkdocs.yml`) with placeholder `docs/index.md`
- [ ] PyPI Trusted Publisher setup instructions in `CONTRIBUTING.md`

### Phase 2 — Schema Parser
*Goal: `prismaa.parser.parse(text)` returns a typed AST for any valid Prisma schema*

**AST nodes** (dataclasses):
- `Schema(datasource, generator, models)`
- `Datasource(name, provider, url)`
- `Generator(name, provider, interface, output, recursive_type_depth, enable_experimental_decimal)`
- `Model(name, fields, block_attributes, is_ignored)` — `@@id`, `@@unique`, `@@index`, `@@map`, `@@ignore`
- `Field(name, type, is_list, is_optional, attributes)` — `@id`, `@unique`, `@default(...)`, `@map(...)`, `@relation(...), @updatedAt`
- `Attribute(name, args)`

**Prisma v7 PSL features to handle:**
- `@@ignore` — model is skipped entirely in code generation (no Pydantic model, no Table, no delegate)
- `@@map("table_name")` — maps model to a differently-named DB table; used in `sa.Table` name
- `@map("col_name")` — maps field to a differently-named DB column; used in `sa.Column` name
- `@updatedAt` — the delegate sets this field to `datetime.utcnow()` before every `UPDATE`
- `@default(now())` — DB-level `DEFAULT CURRENT_TIMESTAMP` (set by Prisma CLI DDL); delegate omits field from `INSERT` and uses `RETURNING *` to read the generated value back
- `@default(autoincrement())` — mapped to `sa.Integer` with `autoincrement=True` in the Table; not set on insert
- `Unsupported("…")` — field is excluded from the generated model and table; a `# WARNING: unsupported field …` comment is emitted
- `///` doc comments — captured and emitted as docstrings on the generated Pydantic model
- `env("VAR")` in datasource URL — resolved at client construction time via `os.environ`
- `previewFeatures = ["prismaSchemaFolder"]` — parsed but ignored in v1 (single-file schema only)

**Field types mapped to Python and SQLAlchemy:**

| Prisma | Python type | SQLAlchemy type |
|--------|-------------|-----------------|
| `String` | `str` | `sa.String` |
| `Int` | `int` | `sa.Integer` |
| `Float` | `float` | `sa.Float` |
| `Boolean` | `bool` | `sa.Boolean` |
| `DateTime` | `datetime` | `sa.DateTime` |
| `Json` | `dict \| list` | `sa.JSON` |
| `Bytes` | `bytes` | `sa.LargeBinary` |
| `BigInt` | `int` | `sa.BigInteger` |
| `Decimal` | `Decimal` | `sa.Numeric` |

SQLAlchemy handles all dialect-specific serialisation (e.g. booleans as 0/1 in SQLite). The generated `tables.py` uses `sa.Table` with `autoload_with=None` (explicit columns) so no DB round-trip is needed at startup.

**Parser implementation:**
- Hand-written lexer (regex tokeniser) — avoids heavy parser-generator dep for a well-understood grammar
- Recursive descent parser matching the [Prisma PSL spec](https://www.prisma.io/docs/orm/reference/prisma-schema-reference)

**Tests:** every AST node type, optional/list fields, multi-field relations, `@@` block attributes, `@@ignore`, `@@map`, `@map`, `@updatedAt`, `Unsupported(...)`, env() in datasource URL. The `example/schema.prisma` in the repo is the canonical fixture.

### Phase 3 — Code Generator
*Goal: `prismaa generate` writes a correct, typed, importable `prisma/` package*

**Templates (Jinja2):**
1. `models.py.j2` — one Pydantic `BaseModel` per non-`@@ignore` model; correct Python types, `Optional[T]` for nullable fields, `model_config = ConfigDict(from_attributes=True)`, `///` doc comments → class docstrings
2. `tables.py.j2` — one `sa.Table` per non-`@@ignore` model; `@@map` → table name override, `@map` → column name override, `@unique` / `@@unique` → `UniqueConstraint`; shared `metadata = sa.MetaData()`
3. `types.py.j2` — per-model TypedDicts: `WhereInput`, `WhereUniqueInput`, `CreateInput` (excludes `@updatedAt` and `@default(now())` fields — DB or delegate handles them), `UpdateInput` (excludes `@updatedAt` — delegate always overwrites it), `OrderByInput`; scalar filters: `StringFilter`, `IntFilter`, `FloatFilter`, `DateTimeFilter`, `BoolFilter`, `BytesFilter`
4. `client.py.j2` — `Prisma` class; one `AsyncModelDelegate[Model]` attribute per model, wired to the correct `Table` and Pydantic class; constructed with a SQLAlchemy URL string
5. `sync_client.py.j2` — `SyncPrisma` class; one `SyncModelDelegate[Model]` attribute per model
6. `__init__.py.j2` — clean re-exports

**Generator options parsed from the schema** (`generator client { … }`):
- `output` — where to write the generated package (default: `./prisma`)
- `interface` — `asyncio` or `sync`; if `sync`, only `sync_client.py` is generated
- `recursive_type_depth` — stored in metadata, used to bound self-referential `include` type depth
- `enable_experimental_decimal` — when true, map `Decimal` fields to `Decimal` Python type (otherwise `float`)

**ModelDelegate methods (async):**
- `find_unique(where, include?)` → `Model | None`
- `find_first(where?, include?, order_by?, skip?)` → `Model | None`
- `find_many(where?, include?, order_by?, skip?, take?)` → `list[Model]`
- `create(data, include?)` → `Model`
- `create_many(data)` → `int` (count)
- `update(where, data, include?)` → `Model | None`
- `update_many(where, data)` → `int`
- `upsert(where, create, update, include?)` → `Model`
- `delete(where, include?)` → `Model | None`
- `delete_many(where?)` → `int`
- `count(where?)` → `int`

**Tests:** snapshot-test generated code for a reference schema, verify the generated package imports cleanly.

### Phase 4 — Query Engine
*Goal: integration tests pass — full CRUD + relations against a real SQLite file*

The database schema is assumed to already exist (created by the official Prisma CLI). The engine issues DML only via SQLAlchemy Core (`select`, `insert`, `update`, `delete`).

**`engine/connection.py`:**
- `ConnectionManager` holds a SQLAlchemy `AsyncEngine` (async path) or `Engine` (sync path)
- URL passed at `Prisma(url="sqlite+aiosqlite:///./dev.db")` construction time
- `connect()` / `disconnect()` / async context manager support

**`engine/query.py` — where/filter translator:**
- Maps Prisma-style filter dicts to SQLAlchemy `ColumnElement` expressions
- Scalar filters: `equals`, `not`, `in`, `not_in`, `lt`, `lte`, `gt`, `gte`, `contains`, `starts_with`, `ends_with`
- Logical: `AND`, `OR`, `NOT` (maps to SQLAlchemy `and_`, `or_`, `not_`)
- `order_by` dict → `asc()` / `desc()` column expressions
- `include` dict → separate `select` per relation + Python-side assembly (avoids N+1 by batching related IDs)

**`engine/delegate.py` — generic CRUD:**
- `AsyncModelDelegate[M](table, model_cls, engine)` — one instance per model in the generated client
- `SyncModelDelegate[M](table, model_cls, engine)` — sync counterpart
- Both classes live in the **library**, not in generated code
- Each method builds a SQLAlchemy Core statement, executes it, and returns `model_cls(**row)` or a list

**Integration test setup:**
- `example/schema.prisma` is the canonical test schema (Company → Filing → Fact/Chunk, Error, `@@ignore` models)
- Session-scoped `conftest.py` fixture runs:
  ```
  npx prisma db push \
    --schema example/schema.prisma \
    --url "file:<tmp_path>/test.db" \
    --skip-generate
  ```
  `--skip-generate` prevents Prisma from trying to run the `prisma-client-py` generator. `--url` overrides the `env("TENK_DATABASE_URL")` in the schema so no env var is needed in tests.
- Each test module gets a fresh DB via an `autouse` async fixture that re-runs `db push` into a new `tmp_path`

**Integration tests** cover:
- Basic CRUD for all scalar types (String, Int, Float, DateTime, Bytes, optional fields)
- `@updatedAt` is auto-set on every `update` call
- `@default(now())` is auto-set on `create` (not passed by caller)
- `find_many` with `where`, `order_by`, `take`, `skip`
- One-to-many relations (`include={"filings": True}` on Company)
- Many-to-one relations (`include={"company": True}` on Filing)
- `@@unique` constraints enforced at DB level; tested via duplicate-insert error handling
- `@@map` / `@map` round-trips (sqliteai_vector-style model, though `@@ignore` so tested via raw SA)
- `count`, `upsert`, `create_many`, `update_many`, `delete_many`
- `async with Prisma(…) as db:` context manager usage

### Phase 5 — Documentation
*Goal: `https://<org>.github.io/prismaa` is live with full API docs*

- MkDocs Material with `mkdocstrings[python]`
- Pages: Getting Started, Schema Reference, API (per method), Contributing
- Auto-deployed on every push to `main` via `docs.yml`

### Phase 6 — PostgreSQL Support *(future)*
- Add `asyncpg` (async) and `psycopg2`/`psycopg` (sync) as optional deps
- No new adapter code — SQLAlchemy handles the dialect; just change the URL scheme
- Any Prisma type-mapping differences (e.g. `Json` → native `JSONB` in Postgres) handled in `tables.py.j2` via dialect-aware SQLAlchemy types
- Integration tests via `pytest` + Docker service in CI (`postgresql+asyncpg://`)

---

## 6. CI/CD Detail

### `ci.yml` (runs on every push and PR)
```
jobs:
  lint:
    - uv run ruff format --check .   # fail if formatter would change any file
    - uv run ruff check .            # fail on any lint error (no --fix in CI)
  test:
    strategy.matrix.python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: npm install              # installs prisma CLI into node_modules
      - uv sync --dev
      - uv run pytest --cov=prismaa --cov-report=xml
  coverage: upload to Codecov
```

### `release.yml` (runs on `v*` tag push)
```
jobs:
  build:  uv build → dist/
  publish: PyPI Trusted Publisher (pypa/gh-action-pypi-publish)
  github-release: gh release create with wheel + sdist assets
```

### `docs.yml` (runs on push to `main`)
```
jobs:
  deploy: uv run mkdocs gh-deploy --force
```

### Versioning
- Tags: `v0.1.0`, `v0.1.1`, `v0.2.0` (semver)
- Version source: `pyproject.toml` `[project] version` — updated manually or via `bump-my-version` (optional)
- The release workflow reads the tag and validates it matches `pyproject.toml` version before publishing

---

## 7. Ruff Configuration & Pre-commit Hooks

The following goes into `pyproject.toml`:

```toml
[tool.ruff]
line-length = 120
exclude = ["excluded_file.py"]

lint.select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "C",  # flake8-comprehensions
    "B",  # flake8-bugbear
]
lint.ignore = [
    "E501",  # line too long
    "C901",  # too complex
]

[tool.ruff.format]
quote-style = "preserve"

[tool.ruff.lint.isort]
order-by-type = true
relative-imports-order = "closest-to-furthest"
extra-standard-library = ["typing"]
section-order = ["future", "standard-library", "third-party", "first-party", "local-folder"]
known-first-party = []
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.x.x   # pin to latest stable
    hooks:
      - id: ruff-format          # ruff format  (auto-fixes in place)
      - id: ruff                 # ruff check --fix  (lint + auto-fixable fixes)
        args: [--fix]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.x.x
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
```

Hook order matters: `ruff-format` runs before `ruff check` so the formatter normalises whitespace before the linter sees the file.

---

## 8. Testing Strategy

- **Unit tests** (`tests/unit/`) — pure Python, no DB, fast
  - Parser: round-trip every Prisma grammar construct
  - Generator: snapshot tests on rendered templates
  - Query builder: assert generated SQL strings + params
- **Integration tests** (`tests/integration/`) — real SQLite in a `tmp_path` fixture
  - One `schema.prisma` file covers all supported field types and relations
  - Each test file is independent (fresh DB via autouse fixture)
- **pytest-asyncio** mode: `asyncio_mode = "auto"` in `pyproject.toml`
- **Coverage target:** 90 %+ for `prismaa.engine` and `prismaa.parser`

---

## 9. Open Questions (need user input)

1. ~~**Ruff configuration**~~ — resolved, see Section 7.
2. ~~**Example `schema.prisma`**~~ — resolved: `example/schema.prisma` in repo.
3. ~~**Package name on PyPI**~~ — resolved: `prismaa`.
4. ~~**Python version floor**~~ — resolved: 3.11+.
5. ~~**Sync client strategy**~~ — resolved: `asyncio.run` wrapper; `SyncModelDelegate` calls the async delegate methods via `asyncio.run(...)`. No separate sync SQLAlchemy engine.
6. ~~**`@default(now())` and `@updatedAt`**~~ — resolved:
   - `@default(now())` → DB-level `DEFAULT CURRENT_TIMESTAMP` (set by Prisma CLI DDL); delegate omits the field from `INSERT` and uses `RETURNING *` to fetch the generated value back.
   - `@updatedAt` → application-layer concern (matches Prisma JS behaviour — no DB trigger used); delegate injects `datetime.utcnow()` before every `UPDATE`.

---

## 10. Implementation Order (first PR sequence)

| PR | Description |
|----|-------------|
| #1 | Scaffolding: `pyproject.toml`, ruff, pre-commit, CI/CD workflows, MkDocs skeleton |
| #2 | Parser: lexer, recursive descent parser, AST, unit tests |
| #3 | Generator: `models.py.j2`, `tables.py.j2`, `types.py.j2`, `client.py.j2`, `prismaa generate` CLI, snapshot tests |
| #4 | Engine — connection manager + async CRUD: `delegate.py`, `query.py`, `connection.py`, aiosqlite integration tests |
| #5 | Engine — sync CRUD: `SyncModelDelegate`, sync client, integration tests |
| #6 | Relations: `include`, batched related-row loading, integration tests |
| #7 | Filters: full scalar filter set (`StringFilter`, `IntFilter`, `DateTimeFilter`, …), integration tests |
| #8 | Documentation: full MkDocs site, API reference, getting-started guide |
| #9 | PostgreSQL support: `asyncpg`/`psycopg` optional deps, CI Docker service, integration tests |
