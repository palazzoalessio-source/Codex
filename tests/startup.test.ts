import { test, expect } from "vitest";
import { createServer } from "node:net";
import { spawn, type ChildProcess } from "node:child_process";
import { mkdtempSync, copyFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

async function fixture() {
  const directory = mkdtempSync(join(tmpdir(), "ipf-startup-"));
  const database = join(directory, "test.db");
  copyFileSync("legacy/IPF_Mapper_M7.2/resources/demo_m71.db", database);
  const occupied = createServer((socket) => socket.end());
  await new Promise<void>((resolve) =>
    occupied.listen(0, "127.0.0.1", resolve),
  );
  const address = occupied.address();
  if (!address || typeof address === "string") throw new Error("Missing port");
  return { directory, database, occupied, port: address.port };
}
function start(args: string[], database: string, port: number) {
  const child = spawn(process.execPath, args, {
    env: {
      ...process.env,
      IPF_DB_PATH: database,
      IPF_PORT: String(port),
      IPF_WEB_PORT: String(port),
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let output = "";
  child.stdout.on("data", (chunk) => (output += chunk));
  child.stderr.on("data", (chunk) => (output += chunk));
  return { child, output: () => output };
}
async function terminate(child: ChildProcess) {
  if (child.exitCode !== null) return;
  const exited = new Promise<void>((resolve) =>
    child.once("exit", () => resolve()),
  );
  child.kill("SIGTERM");
  await exited;
}

test("occupied ports are replaced and the frontend proxy accepts the selected origin", async () => {
  const f = await fixture();
  const run = start(["scripts/dev.mjs"], f.database, f.port);
  try {
    await expect
      .poll(run.output, { timeout: 15000 })
      .toContain("IPF Mapper pronto.");
    const url = run
      .output()
      .match(/Apri nel browser: (http:\/\/127\.0\.0\.1:\d+)\//)?.[1];
    expect(url).toBeTruthy();
    expect(new URL(url!).port).not.toBe(String(f.port));
    const health = await fetch(`${url}/api/health`, {
      headers: { Origin: url! },
    });
    expect(health.status).toBe(200);
    expect(await health.json()).toMatchObject({ ok: true });
    expect((await fetch(`${url}/`)).status).toBe(200);
    const blocked = await fetch(`${url}/api/health`, {
      headers: { Origin: "https://example.org" },
    });
    expect(blocked.status).toBe(403);
  } finally {
    await terminate(run.child);
    await new Promise<void>((resolve) => f.occupied.close(() => resolve()));
    rmSync(f.directory, { recursive: true, force: true });
  }
}, 20000);

test("API bind failure exits with an error and never claims readiness", async () => {
  const f = await fixture();
  const run = start(["--import", "tsx", "server/index.ts"], f.database, f.port);
  try {
    const code = await new Promise<number | null>((resolve) =>
      run.child.once("exit", resolve),
    );
    expect(code).toBe(1);
    expect(run.output()).toContain("EADDRINUSE");
    expect(run.output()).not.toContain("API pronta");
  } finally {
    await terminate(run.child);
    await new Promise<void>((resolve) => f.occupied.close(() => resolve()));
    rmSync(f.directory, { recursive: true, force: true });
  }
}, 20000);
