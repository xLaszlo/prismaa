# Setting up Prisma CLI in a Python project

Prismaa handles all Python-side database access, but **schema migrations are managed by the official Prisma CLI** (a Node.js tool). This guide walks through adding the Prisma CLI to a Python project from scratch.

You do not need to know JavaScript or Node.js beyond running the commands below.

---

## 1. Install fnm (Fast Node Manager)

[fnm](https://github.com/Schniz/fnm) manages Node.js versions the same way `pyenv` manages Python versions.

=== "macOS / Linux"

    ```bash
    curl -fsSL https://fnm.vercel.app/install | bash
    ```

    Then follow the printed instructions to add fnm to your shell profile (`.bashrc`, `.zshrc`, etc.), or restart your terminal.

=== "Windows (PowerShell)"

    ```powershell
    winget install Schniz.fnm
    ```

Verify:

```bash
fnm --version
```

---

## 2. Create a `.node-version` file

In your project root, create a file that pins the Node.js version:

```bash
echo "22" > .node-version
```

This tells fnm (and CI) which Node version to use. Commit this file.

---

## 3. Install Node.js and activate it

```bash
fnm install   # installs the version from .node-version
fnm use       # activates it in the current shell
node --version  # should print v22.x.x
```

To make activation automatic when you `cd` into the project, add this to your shell profile:

=== "bash"

    ```bash
    eval "$(fnm env --use-on-cd)"
    ```

=== "zsh"

    ```zsh
    eval "$(fnm env --use-on-cd)"
    ```

---

## 4. Create `package.json`

Create a minimal `package.json` in your project root. The `private: true` flag prevents accidental npm publishing.

```bash
npm init -y
```

Then open `package.json` and set `"private": true`:

```json
{
  "name": "my-project-dev",
  "private": true,
  "devDependencies": {}
}
```

---

## 5. Install the Prisma CLI

```bash
npm install prisma --save-dev
```

Commit both `package.json` and `package-lock.json`. Colleagues and CI will use `npm ci` (faster, uses the lockfile exactly) instead of `npm install`.

Verify:

```bash
npx prisma --version
```

---

## 6. Configure Prisma v7 (`prisma.config.ts`)

Prisma v7 moves the database connection URL out of `schema.prisma` and into a TypeScript config file.

Create `prisma.config.ts` in your project root:

```typescript
import { defineConfig } from "prisma/config";

export default defineConfig({
  schema: "schema.prisma",        // path to your schema.prisma
  migrate: {
    datasourceUrl: process.env.DATABASE_URL ?? "file:./dev.db",
  },
});
```

Set your `DATABASE_URL` environment variable (e.g. in a `.env` file — add `.env` to `.gitignore`):

```bash
DATABASE_URL="file:./dev.db"
```

---

## 7. Write your `schema.prisma`

Create `schema.prisma` (the `url` property is no longer in the datasource block in v7):

```prisma
generator client {
  provider = "prismaa"
  output   = "./prisma"
  interface = "asyncio"
}

datasource db {
  provider = "sqlite"
}

model User {
  id    Int    @id @default(autoincrement())
  name  String
  email String @unique
}
```

---

## 8. Run your first migration

```bash
npx prisma migrate dev --name init
```

This creates a `prisma/migrations/` directory, generates a SQL migration file, and applies it to your local database. Commit the migration files — they are your schema history.

For subsequent schema changes:

```bash
# after editing schema.prisma
npx prisma migrate dev --name describe_your_change
```

---

## 9. Apply migrations in production / CI

```bash
npx prisma migrate deploy
```

This applies all pending migrations without prompting. Use this in deployment pipelines and CI.

---

## Common commands

| Command | Description |
|---------|-------------|
| `npx prisma migrate dev --name <name>` | Create and apply a new migration locally |
| `npx prisma migrate deploy` | Apply pending migrations (production / CI) |
| `npx prisma migrate status` | Show which migrations are applied / pending |
| `npx prisma db push` | Sync schema to DB without a migration file (prototyping only) |
| `npx prisma studio` | Open a web UI to browse your data |
| `npx prisma format` | Format `schema.prisma` |

---

## `.gitignore` additions

```gitignore
# Node.js
node_modules/

# Local database files
*.db
*.db-journal

# Environment variables
.env
```

Commit `package.json`, `package-lock.json`, `prisma.config.ts`, `schema.prisma`, and everything under `prisma/migrations/`. Do **not** commit `node_modules/` or `.env`.
