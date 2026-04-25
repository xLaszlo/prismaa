import { defineConfig } from "prisma/config";

export default defineConfig({
  schema: "example/schema.prisma",
  migrate: {
    datasourceUrl: process.env.DATABASE_URL ?? "file:./dev.db",
  },
});
