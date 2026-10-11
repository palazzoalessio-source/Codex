import { mkdirSync, copyFileSync } from "node:fs";
// Dedicated disposable fixture. Never touches .local/demo-working.db or IPF_DB_PATH.
mkdirSync(".local", { recursive: true });
copyFileSync("legacy/IPF_Mapper_M7.2/resources/demo_m71.db", ".local/e2e.db");
