# Releasing

## One-time setup (do this before the first release)

### 1. Create the GitHub repository

On github.com: **New repository** → name `prismaa`, public, no README/license (we already have them).

### 2. Push the first commit directly to `main`

Do this **before** enabling branch protection — you need at least one commit on `main` first.

```bash
git remote add origin https://github.com/<your-username>/prismaa.git
git add .
git commit -m "chore: initial scaffolding and parser"
git push -u origin main
```

### 3. Enable branch protection on `main`

On GitHub: **Settings → Branches → Add branch ruleset** (or classic protection rule).

| Setting | Value |
|---------|-------|
| Branch name pattern | `main` |
| Require a pull request before merging | ✅ |
| Required approving reviews | 1 (or 0 for solo work) |
| Require status checks to pass | ✅ |
| Required status checks | `Lint`, `Test (Python 3.11)`, `Test (Python 3.12)`, `Test (Python 3.13)` |
| Require branches to be up to date | ✅ |
| Do not allow bypassing the above settings | ✅ |
| Allow force pushes | ❌ |
| Allow deletions | ❌ |

> The status check names must match the `name:` fields in `.github/workflows/ci.yml` exactly. They will only appear in the dropdown after CI has run at least once — push a branch and open a draft PR first if needed.

### 4. Create the `pypi` GitHub environment

**Settings → Environments → New environment** → name it `pypi`.

Optionally add a protection rule requiring manual approval before publish.

### 5. Publish the first release manually (bootstraps PyPI Trusted Publisher)

PyPI's Trusted Publisher requires the project to exist on PyPI first. Do this once:

```bash
# Get a temporary API token from pypi.org → Account Settings → API tokens
# Scope: "Entire account" (project doesn't exist yet, so you can't scope it narrower)
export UV_PUBLISH_TOKEN=pypi-...

uv build
uv publish
```

The project `prismaa` now exists on PyPI.

### 6. Configure Trusted Publisher on PyPI

On pypi.org: **Your projects → prismaa → Manage → Publishing → Add a new publisher**:

| Field | Value |
|-------|-------|
| Owner | your GitHub username |
| Repository | `prismaa` |
| Workflow filename | `release.yml` |
| Environment name | `pypi` |

You can now delete the temporary API token — all future releases use OIDC, no token needed.

---

## Regular release flow (after setup)

### Cutting a release

```bash
# 1. On a branch (not main), bump the version
#    Edit pyproject.toml: version = "X.Y.Z"
git checkout -b release/vX.Y.Z
# edit pyproject.toml
git add pyproject.toml
git commit -m "chore: bump version to vX.Y.Z"
git push -u origin release/vX.Y.Z

# 2. Open a PR → CI must be green → merge to main

# 3. Tag main after the merge
git checkout main
git pull
git tag vX.Y.Z
git push --tags
```

Pushing the tag triggers `release.yml`, which:
1. Builds the wheel and sdist
2. Publishes to PyPI via Trusted Publisher (no token)
3. Creates a GitHub Release with auto-generated notes

---

## Day-to-day contribution flow

```bash
git checkout -b feat/your-feature
# ... make changes, run tests ...
uv run pytest
uv run ruff check . && uv run ruff format .
git push -u origin feat/your-feature
# Open PR on GitHub → CI runs → review → merge
```

Direct pushes to `main` are blocked by branch protection.
