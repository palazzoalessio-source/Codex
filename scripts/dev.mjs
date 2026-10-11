import { createServer } from "node:net";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

process.chdir(fileURLToPath(new URL("..", import.meta.url)));
const production = process.argv.includes("--production");
const children = [];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  process.exitCode = code;
  for (const child of children)
    if (child.exitCode === null) child.kill("SIGTERM");
}
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => stop(0));
function preferred(value, fallback) {
  const port = value === undefined ? fallback : Number(value);
  if (!Number.isInteger(port) || port < 1024 || port > 65535)
    throw new Error("La porta deve essere un numero intero tra 1024 e 65535.");
  return port;
}
export async function freePort(start, excluded = []) {
  for (let port = start; port <= Math.min(start + 100, 65535); port++) {
    if (excluded.includes(port)) continue;
    const available = await new Promise((resolve, reject) => {
      const probe = createServer();
      probe.once("error", (e) =>
        e.code === "EADDRINUSE" || e.code === "EACCES"
          ? resolve(false)
          : reject(e),
      );
      probe.listen(port, "127.0.0.1", () => probe.close(() => resolve(true)));
    });
    if (available) return port;
  }
  throw new Error(`Nessuna porta libera trovata a partire da ${start}.`);
}
function launch(args, env) {
  const child = spawn(process.execPath, args, { env, stdio: "inherit" });
  children.push(child);
  child.once("error", (e) => {
    console.error(e.message);
    stop(1);
  });
  child.once("exit", (code, signal) => {
    if (!stopping) {
      console.error(`Servizio terminato (${signal ?? code}).`);
      stop(code || 1);
    }
  });
  return child;
}
async function waitReady(url, child) {
  for (let n = 0; n < 100; n++) {
    if (stopping || child.exitCode !== null)
      throw new Error("Il servizio è terminato durante l’avvio.");
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(500) });
      if (response.ok) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error(`Il servizio non risponde: ${url}`);
}
try {
  if (Number(process.versions.node.split(".")[0]) < 24)
    throw new Error("IPF Mapper richiede Node 24 o successivo.");
  if (production && !existsSync(resolve("dist/index.html")))
    throw new Error("La build manca. Esegui npm run build, poi npm start.");
  const requestedApi = preferred(process.env.IPF_PORT, 3001),
    requestedWeb = preferred(process.env.IPF_WEB_PORT, 5173);
  const apiPort = await freePort(requestedApi);
  const webPort = production
    ? apiPort
    : await freePort(requestedWeb, [apiPort]);
  const env = {
    ...process.env,
    IPF_PORT: String(apiPort),
    IPF_WEB_PORT: String(webPort),
  };
  if (apiPort !== requestedApi)
    console.log(`Porta API ${requestedApi} occupata: uso ${apiPort}.`);
  if (!production && webPort !== requestedWeb)
    console.log(`Porta web ${requestedWeb} occupata: uso ${webPort}.`);
  const api = launch(["--import", "tsx", "server/index.ts"], env);
  await waitReady(`http://127.0.0.1:${apiPort}/api/health`, api);
  if (!production) {
    const vite = launch(
      ["node_modules/vite/bin/vite.js", "--host", "127.0.0.1"],
      env,
    );
    await waitReady(`http://127.0.0.1:${webPort}/api/health`, vite);
  }
  console.log(
    `\nIPF Mapper pronto. Apri nel browser: http://127.0.0.1:${webPort}/\nLascia aperto questo terminale. Ctrl+C arresta i servizi.\n`,
  );
} catch (e) {
  console.error(`Avvio non riuscito: ${e.message}`);
  stop(1);
}
