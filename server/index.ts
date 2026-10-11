import express from "express";
import { resolve } from "node:path";
import { existsSync } from "node:fs";
import { z } from "zod";
import { openRepository, ConflictError } from "./database";

const repo = await openRepository();
const app = express();
app.disable("x-powered-by");
// Local application: reject cross-origin browser writes and DNS-rebinding hosts.
app.use((req, res, next) => {
  const host = req.hostname;
  if (!["localhost", "127.0.0.1", "[::1]"].includes(host)) {
    res.status(403).json({ error: "Host non consentito." });
    return;
  }
  const origin = req.get("origin");
  if (origin) {
    try {
      const url = new URL(origin);
      if (
        !["localhost", "127.0.0.1"].includes(url.hostname) ||
        !["3001", "5173"].includes(url.port)
      ) {
        res.status(403).json({ error: "Origine non consentita." });
        return;
      }
    } catch {
      res.status(403).end();
      return;
    }
  }
  next();
});
app.use(express.json({ limit: "20mb" }));
app.get("/api/health", (_req, res) =>
  res.json({
    ok: true,
    database: "SQLite",
    source: process.env.IPF_DB_PATH
      ? "configured"
      : "bundled-demo-working-copy",
  }),
);
app.get("/api/catalog", (_req, res) => res.json(repo.catalog()));
app.get("/api/group-templates", (_req, res) => res.json(repo.groupTemplates()));
app.post("/api/group-templates", (req, res) =>
  res.status(201).json(repo.saveGroupTemplate(req.body)),
);
app.get("/api/projects", (_req, res) => res.json(repo.projects()));
app.post("/api/projects", (req, res) =>
  res.status(201).json(repo.createProject(req.body)),
);
app.get("/api/revisions", (_req, res) => res.json(repo.list()));
app.post("/api/revisions/:id/rules", (req, res) =>
  res
    .status(201)
    .json(
      repo.saveStateRule(
        z.coerce.number().int().positive().parse(req.params.id),
        req.body,
      ),
    ),
);
app.delete("/api/revisions/:id/rules/:ruleId", (req, res) =>
  res.json(
    repo.deleteRule(
      z.coerce.number().int().positive().parse(req.params.id),
      z.coerce.number().int().positive().parse(req.params.ruleId),
      z.object({ version: z.number().int().nonnegative() }).parse(req.body)
        .version,
    ),
  ),
);
app.get("/api/revisions/:id", (req, res) =>
  res.json(repo.read(z.coerce.number().int().positive().parse(req.params.id))),
);
app.put("/api/revisions/:id", (req, res) => {
  const body = req.body as unknown;
  const rid = z.object({ revision: z.object({ id: z.number() }) }).parse(body)
    .revision.id;
  if (rid !== Number(req.params.id)) throw new Error("ID incoerente.");
  res.json(repo.save(body));
});
app.post("/api/revisions/:id/clone", (req, res) => {
  const data = z
    .object({
      code: z.string().trim().min(1).max(120),
      purpose: z.enum(["AS_IS", "TO_BE"]),
    })
    .parse(req.body);
  res
    .status(201)
    .json(repo.clone(Number(req.params.id), data.code, data.purpose));
});
app.get("/api/models/:id/executions", (req, res) =>
  res.json(
    repo.executions(z.coerce.number().int().positive().parse(req.params.id)),
  ),
);
app.get("/api/executions/:id", (req, res) =>
  res.json(
    repo.execution(z.coerce.number().int().positive().parse(req.params.id)),
  ),
);
if (existsSync("dist")) {
  app.use(express.static(resolve("dist")));
  app.get("/{*path}", (_req, res) => res.sendFile(resolve("dist/index.html")));
}
app.use(
  (
    error: unknown,
    _req: express.Request,
    res: express.Response,
    _next: express.NextFunction,
  ) => {
    res.status(error instanceof ConflictError ? 409 : 400).json({
      error: error instanceof Error ? error.message : "Errore inatteso.",
    });
  },
);
const server = app.listen(
  Number(process.env.IPF_PORT ?? 3001),
  "127.0.0.1",
  () =>
    console.log(
      "IPF Mapper API pronta sulla porta " + (process.env.IPF_PORT ?? 3001),
    ),
);
for (const signal of ["SIGINT", "SIGTERM"] as const)
  process.on(signal, () =>
    server.close(() => {
      repo.close();
      process.exit(0);
    }),
  );
