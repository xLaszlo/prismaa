# Contributing

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — Python package and project manager
- [fnm](https://github.com/Schniz/fnm) — Fast Node Manager (manages the Node.js version for the Prisma CLI)

For a detailed explanation of why Node.js is needed and how Prisma fits into a Python project, see [docs/prisma-setup.md](docs/prisma-setup.md).

## Local setup

### 1. Node.js via fnm

```bash
# Install fnm (if not already installed)
curl -fsSL https://fnm.vercel.app/install | bash

# In the repo root — installs the Node.js version from .node-version and activates it
fnm install
fnm use

# Install the Prisma CLI (commit the generated package-lock.json)
npm install
```

### 2. Python environment

```bash
uv sync --group dev
```

### 3. Pre-commit hooks

```bash
uv run pre-commit install
```

## Running tests

```bash
uv run pytest
```

The test suite uses `prisma db push` (via the local `npx` from step 1) to create a SQLite database in a temporary directory before running integration tests. Make sure `npm install` has been run first.

## Linting and formatting

```bash
uv run ruff format .       # format in place
uv run ruff check --fix .  # lint + auto-fix
```

CI runs both in check-only mode (no `--fix`) and will fail on any violation.

## Generating the client locally

After implementing the generator (Phase 3):

```bash
uv run prismaa generate --schema example/schema.prisma
```

## Releasing a new version

Publishing is fully automated via GitHub Actions — no manual PyPI upload needed.

1. Update `version` in [pyproject.toml](pyproject.toml)
2. Commit: `git commit -m "chore: bump version to vX.Y.Z"`
3. Tag and push: `git tag vX.Y.Z && git push --tags`

The `release.yml` workflow picks up the tag, builds the wheel + sdist, and publishes to PyPI via **Trusted Publisher (OIDC)** — no API token is stored in the repository.

> **First-time setup:** the project must exist on PyPI before the Trusted Publisher can be linked.
> 1. Build and upload the first release manually once:
>    ```bash
>    uv build
>    uv run twine upload dist/*   # needs twine: uv add --dev twine
>    ```
> 2. Then on PyPI go to *Your projects → prismaa → Manage → Trusted Publishers → Add* and fill in:
>    - Owner: your GitHub username
>    - Repository: `prismaa`
>    - Workflow filename: `release.yml`
>    - Environment name: `pypi`
> 3. All future releases via `git tag vX.Y.Z && git push --tags` are fully automated — no token needed.
