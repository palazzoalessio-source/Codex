import { beforeEach, afterEach, it, expect } from "vitest";
import { copyFileSync, mkdtempSync, rmSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { Repository, openRepository, ConflictError } from "../server/database";
import { newEntity, type ProcessDocument } from "../src/domain/model";
import { compare } from "../src/domain/analysis";

let repo: Repository, folder: string;
const original = resolve("legacy/IPF_Mapper_M7.2/resources/demo_m71.db");
beforeEach(() => {
  folder = mkdtempSync(join(tmpdir(), "ipf-sqlite-"));
  const path = join(folder, "copy.db");
  copyFileSync(original, path);
  repo = new Repository(path);
  repo.migrate();
});
afterEach(() => {
  repo.close();
  rmSync(folder, { recursive: true });
});
function historical() {
  return JSON.stringify({
    snapshot: repo.read(2),
    execution: repo.execution(1),
    expressions: repo.rows("SELECT * FROM expression_node ORDER BY id"),
    rules: repo.rows("SELECT * FROM rule_definition ORDER BY id"),
  });
}
it("migrazioni additive ripetibili preservano dati storici", () => {
  const before = historical();
  repo.migrate();
  expect(historical()).toBe(before);
  expect(repo.rows("PRAGMA foreign_key_check")).toEqual([]);
  expect(repo.row("PRAGMA integrity_check").integrity_check).toBe("ok");
  expect(
    createHash("sha256").update(readFileSync(original)).digest("hex"),
  ).toBe("ebc1fa9d166d13b2c3b8d3ee2dbc53e94229eabb60f5ead25a1e06b8b36b96a7");
});
it("salva Unicode, VA e layout senza cambiare snapshot o esecuzioni", () => {
  const before = historical(),
    d = repo.read(1),
    action = d.entities.find((e) => e.type === "ACTION")!;
  action.name = "È già pronta — l’azione “α” 日本語";
  action.classification = "NNVA";
  action.layout = { ...action.layout, x: 1111, locked: true };
  const saved = repo.save(d);
  expect(saved.entities.find((e) => e.uid === action.uid)).toMatchObject({
    name: action.name,
    classification: "NNVA",
    layout: { x: 1111, locked: true },
  });
  expect(historical()).toBe(before);
});
it("crea e persiste gruppi, decisioni, performer e flow reificato", () => {
  const d = repo.read(1),
    group = newEntity("PROCESS_GROUP", "Gruppo", 300, 250),
    decision = newEntity("DECISION", "Decisione", 330, 310),
    flow = newEntity("INFORMATION_FLOW", "Flusso", 0, 0),
    action = d.entities.find((e) => e.type === "ACTION")!,
    lane = d.entities.find((e) => e.type === "INTERNAL_FUNCTION")!;
  const next: ProcessDocument = {
    ...d,
    entities: [...d.entities, group, decision, flow],
    relations: [
      ...d.relations,
      { id: "a", semantic: "CONTAINS", source: group.id, target: decision.id },
      { id: "b", semantic: "PERFORMER", source: decision.id, target: lane.id },
      { id: "c", semantic: "SOURCE", source: flow.id, target: decision.id },
      { id: "d", semantic: "TARGET", source: flow.id, target: action.id },
    ],
  };
  const saved = repo.save(next),
    byUid = new Map(saved.entities.map((e) => [e.uid, e]));
  expect(byUid.get(decision.uid)?.type).toBe("DECISION");
  expect(
    saved.relations.some(
      (r) =>
        r.semantic === "CONTAINS" &&
        r.source === byUid.get(group.uid)?.id &&
        r.target === byUid.get(decision.uid)?.id,
    ),
  ).toBe(true);
  expect(repo.read(1)).toEqual(saved);
});
it("rifiuta conflitti concorrenti e revisioni immutabili", () => {
  const d = repo.read(1);
  repo.save(d);
  expect(() => repo.save(d)).toThrow(ConflictError);
  expect(() => repo.save(repo.read(2))).toThrow(/immutabile/);
});
it("parametri non osservati rimangono null senza impedire altri salvataggi", () => {
  repo.run(
    "UPDATE model_revision_parameter_value SET value_text=NULL,value_integer=NULL,value_real=NULL,value_boolean=NULL WHERE model_revision_id=1",
  );
  const d = repo.read(1);
  expect(Object.values(d.parameters).every((v) => v === null)).toBe(true);
  d.entities[0].description =
    "Modifica indipendente dalla disponibilità dei parametri";
  const saved = repo.save(d);
  expect(saved.parameters).toEqual(d.parameters);
  expect(saved.entities[0].description).toBe(d.entities[0].description);
});
it("rollback di un salvataggio fallito non lascia modifiche parziali", () => {
  const d = repo.read(1),
    before = repo.read(1);
  d.entities[0].name = "Non deve salvarsi";
  d.parameters.MANAGEMENT_APPROVAL_THRESHOLD = "non numero";
  expect(() => repo.save(d)).toThrow(/Numero/);
  expect(repo.read(1)).toEqual(before);
});
it("clone TO-BE conserva identità e proprietà, modifiche indipendenti", () => {
  const before = repo.read(1),
    clone = repo.clone(1, "TO-BE-test", "TO_BE");
  expect(clone.revision.purpose).toBe("TO_BE");
  expect(clone.entities.map((e) => e.uid)).toEqual(
    before.entities.map((e) => e.uid),
  );
  expect(clone.entities[0].definitionId).not.toBe(
    before.entities[0].definitionId,
  );
  clone.entities[0].name = "Solo TO-BE";
  repo.save(clone);
  expect(repo.read(1)).toEqual(before);
  expect(
    compare(before, repo.read(clone.revision.id), repo.catalog()).modified,
  ).toHaveLength(1);
});
it("rimuove membership e consente undo dopo il salvataggio senza perdita di record", () => {
  const d = repo.read(1),
    victim = d.entities.find((e) => e.type === "MEANS")!;
  const count = repo.row("SELECT COUNT(*) n FROM entity_identity").n;
  const deleted = repo.save({
    ...d,
    entities: d.entities.filter((e) => e.id !== victim.id),
    relations: d.relations.filter(
      (r) => r.source !== victim.id && r.target !== victim.id,
    ),
  });
  expect(repo.row("SELECT COUNT(*) n FROM entity_identity").n).toBe(count);
  const restored = repo.save({ ...d, revision: deleted.revision });
  expect(restored.entities.find((e) => e.uid === victim.uid)?.name).toBe(
    victim.name,
  );
  expect(restored.relations).toHaveLength(d.relations.length);
});
it("non crea un database vuoto se il path personale è errato", async () => {
  await expect(openRepository(join(folder, "missing.db"))).rejects.toThrow(
    /non esistente/,
  );
});
it("protegge il database originale incluso", async () => {
  await expect(openRepository(original)).rejects.toThrow(/protetto/);
});
it("progetti vuoti indipendenti con Unicode e validazione input atomica", () => {
  const original = repo.read(1),
    snapshot = repo.read(2);
  const first = repo.createProject({
    name: "Progetto è 日本語",
    processName: "Acquisti",
  });
  const second = repo.createProject({
    name: "Altro progetto",
    processName: "Acquisti",
  });
  expect(first.entities).toEqual([]);
  expect(first.relations).toEqual([]);
  expect(first.rules).toEqual([]);
  expect(first.revision.workspaceId).not.toBe(second.revision.workspaceId);
  expect(
    repo.projects().find((p) => p.id === first.revision.modelId)?.projectName,
  ).toBe("Progetto è 日本語");
  expect(repo.read(1)).toEqual(original);
  expect(repo.read(2)).toEqual(snapshot);
  const count = repo.projects().length;
  expect(() => repo.createProject({ name: " ", processName: "x" })).toThrow();
  expect(repo.projects()).toHaveLength(count);
});
it("authoring regole crea AST compatibili e conserva regole e snapshot precedenti", () => {
  const snapshot = repo.read(2),
    before = repo.read(1),
    old = before.rules.find((r) => r.recipe && "op" in r.recipe)!;
  const ast = repo.rows("SELECT * FROM expression_node ORDER BY id");
  const changed = repo.saveStateRule(1, {
    version: before.revision.version,
    ruleId: old.id,
    name: "Regola è modificata",
    target: old.target,
    purpose: old.purpose,
    trueState: old.trueState,
    falseState: old.falseState,
    recipe: old.recipe,
  });
  expect(
    changed.rules.find((r) => r.name === "Regola è modificata")?.id,
  ).not.toBe(old.id);
  expect(repo.read(2)).toEqual(snapshot);
  for (const row of ast)
    expect(
      repo.row("SELECT * FROM expression_node WHERE id=?", row.id),
    ).toEqual(row);
  expect(
    repo.row("SELECT name FROM rule_definition WHERE id=?", old.id).name,
  ).toBe(old.name);
  const created = repo.saveStateRule(1, {
    version: changed.revision.version,
    name: "Prerequisito",
    target: old.target,
    purpose: "ENABLEMENT",
    trueState: "ENABLED",
    falseState: "BLOCKED",
    recipe: {
      kind: "completed",
      identity_id: Number(before.entities.find((e) => e.type === "ACTION")!.id),
    },
  });
  expect(created.rules).toHaveLength(before.rules.length + 1);
  expect(repo.rows("PRAGMA foreign_key_check")).toEqual([]);
  expect(() =>
    repo.saveStateRule(1, {
      version: 0,
      name: "Conflitto",
      target: old.target,
      purpose: "REQUIREMENT",
      trueState: "REQUIRED",
      falseState: "OPTIONAL",
      recipe: {
        op: "EQ",
        left: { kind: "literal", value: true },
        right: { kind: "literal", value: true },
      },
    }),
  ).toThrow(/cambiata/);
  const last = created.rules.at(-1)!;
  const removed = repo.deleteRule(1, last.id, created.revision.version);
  expect(removed.rules).toHaveLength(before.rules.length);
  expect(
    repo.row("SELECT id FROM rule_definition WHERE id=?", last.id).id,
  ).toBe(last.id);
});
