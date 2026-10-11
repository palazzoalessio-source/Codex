import { beforeAll, afterAll, describe, it, expect } from "vitest";
import { copyFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { Repository } from "../server/database";
import {
  documentSchema,
  newEntity,
  allowedSemantics,
  isType,
  type ProcessDocument,
  type Catalog,
} from "../src/domain/model";
import { applyCommand, execute, undo, redo } from "../src/domain/commands";
import {
  analyze,
  compare,
  durationSeconds,
  evaluateRule,
  evaluateStates,
} from "../src/domain/analysis";
import { validate } from "../src/domain/validation";
import { cycles } from "../src/domain/graph";

let repo: Repository, doc: ProcessDocument, catalog: Catalog, folder: string;
beforeAll(() => {
  folder = mkdtempSync(join(tmpdir(), "ipf-domain-"));
  const path = join(folder, "test.db");
  copyFileSync(resolve("legacy/IPF_Mapper_M7.2/resources/demo_m71.db"), path);
  repo = new Repository(path);
  repo.migrate();
  doc = repo.read(1);
  catalog = repo.catalog();
});
afterAll(() => {
  repo.close();
  rmSync(folder, { recursive: true });
});
describe("Metamodello e legacy adapter", () => {
  it("apre tutte le entità, relazioni e regole del database reale", () => {
    expect(doc.entities).toHaveLength(57);
    expect(doc.relations).toHaveLength(97);
    expect(doc.rules).toHaveLength(10);
    expect(
      validate(doc, catalog).filter((i) => i.severity === "error"),
    ).toEqual([]);
  });
  it("default sicuro e serializzazione UTF-8 lossless", () => {
    expect(doc.entities.every((e) => e.classification === "UNCLASSIFIED")).toBe(
      true,
    );
    const d = structuredClone(doc);
    d.entities[0].name = "È già pronto — “T/C” · l’azione 日本語";
    expect(documentSchema.parse(JSON.parse(JSON.stringify(d)))).toEqual(d);
  });
  it("eredita le firme di ACTION per DECISION e di PARTICIPANT per function", () => {
    expect(isType("DECISION", "ACTION", catalog)).toBe(true);
    expect(isType("INTERNAL_FUNCTION", "PARTICIPANT", catalog)).toBe(true);
    expect(
      allowedSemantics(
        newEntity("DECISION", "Scelta", 0, 0),
        newEntity("INFORMATION", "Dato", 0, 0),
        catalog,
      ),
    ).toContain("OUTPUT");
  });
  it("rifiuta tipi esterni, classificazioni e geometrie non valide", () => {
    expect(
      documentSchema.safeParse({ ...doc, viewport: { x: 0, y: 0, zoom: 0 } })
        .success,
    ).toBe(false);
    const d = structuredClone(doc);
    d.entities[0].type = "NOT_IN_CATALOG";
    expect(validate(d, catalog).some((i) => i.code === "UNKNOWN_TYPE")).toBe(
      true,
    );
  });
});
describe("Command architecture", () => {
  it("undo/redo di create e proprietà preserva documenti immutabili", () => {
    const e = newEntity("ACTION", "Nuova", 0, 0),
      h = { past: [], present: doc, future: [] };
    const next = execute(h, { type: "upsert", entity: e }, catalog);
    expect(doc.entities).toHaveLength(57);
    expect(next.present.entities).toHaveLength(58);
    expect(undo(next).present).toEqual(doc);
    expect(redo(undo(next)).present).toEqual(next.present);
  });
  it("sposta più elementi ma rispetta lock", () => {
    const d = structuredClone(doc);
    d.entities[0].layout.locked = true;
    const p = d.entities[0].layout;
    const n = applyCommand(
      d,
      {
        type: "move",
        positions: [
          { id: d.entities[0].id, x: 500, y: 500 },
          { id: d.entities[1].id, x: 500, y: 500 },
        ],
      },
      catalog,
    );
    expect(n.entities[0].layout).toEqual(p);
    expect(n.entities[1].layout.x).toBe(500);
  });
  it("crea un gruppo e impedisce cicli gerarchici", () => {
    const a = newEntity("PROCESS_GROUP", "A", 0, 0),
      b = newEntity("PROCESS_GROUP", "B", 0, 0);
    let d = { ...doc, entities: [...doc.entities, a, b] };
    d = applyCommand(
      d,
      {
        type: "relation",
        relation: {
          id: "r1",
          semantic: "CONTAINS",
          source: a.id,
          target: b.id,
        },
      },
      catalog,
    );
    expect(() =>
      applyCommand(
        d,
        {
          type: "relation",
          relation: {
            id: "r2",
            semantic: "CONTAINS",
            source: b.id,
            target: a.id,
          },
        },
        catalog,
      ),
    ).toThrow(/antenato/);
  });
  it("sposta membership senza assegnazioni duplicate", () => {
    const child = doc.entities.find((e) => e.type === "ACTION")!,
      g = newEntity("PROCESS_GROUP", "G", 0, 0);
    let d = applyCommand(doc, { type: "upsert", entity: g }, catalog);
    d = applyCommand(
      d,
      {
        type: "relation",
        relation: {
          id: "contains",
          semantic: "CONTAINS",
          source: g.id,
          target: child.id,
        },
      },
      catalog,
    );
    expect(
      d.relations.filter(
        (r) => r.semantic === "CONTAINS" && r.target === child.id,
      ),
    ).toHaveLength(1);
  });
  it("blocca modifiche a revisioni pubblicate", () => {
    expect(() =>
      applyCommand(
        { ...doc, revision: { ...doc.revision, status: "PUBLISHED" } },
        { type: "delete", ids: [doc.entities[0].id] },
        catalog,
      ),
    ).toThrow(/immutabile/);
  });
});
describe("Analisi e validazione", () => {
  it("converte unità esplicite senza inventare tempi", () => {
    expect(durationSeconds("30 min")).toBe(1800);
    expect(durationSeconds("PT1H30M")).toBe(5400);
    expect(durationSeconds("2h")).toBe(7200);
    expect(durationSeconds("4")).toBeNull();
    expect(durationSeconds("un giorno")).toBeNull();
  });
  it("distingue totale attività da lead time e rende nota la copertura", () => {
    const m = analyze(doc, catalog);
    expect(m.actions).toBe(16);
    expect(m.values.UNCLASSIFIED).toBe(16);
    expect(m.durationCoverage.known).toBe(16);
    expect(m.cycleTimeSeconds).toBeGreaterThan(0);
    expect(m.criticalities).toBe(3);
  });
  it("confronta identità stabili, proprietà, ownership e flussi", () => {
    const next = structuredClone(doc),
      action = next.entities.find((e) => e.type === "ACTION")!;
    action.name = "Modificata";
    action.classification = "VA";
    next.relations = next.relations.filter(
      (r) => !(r.source === action.id && r.semantic === "PERFORMER"),
    );
    const result = compare(doc, next, catalog);
    expect(result.added).toEqual([]);
    expect(result.modified.find((e) => e.id === action.id)?.fields).toEqual(
      expect.arrayContaining(["name", "classification", "PERFORMER"]),
    );
    expect(result.after.values.VA).toBe(1);
    expect(result.relationsRemoved.length).toBeGreaterThan(0);
  });
  it("rifiuta confronto tra processi diversi", () => {
    expect(() =>
      compare(
        doc,
        { ...doc, revision: { ...doc.revision, modelId: 999 } },
        catalog,
      ),
    ).toThrow(/stesso processo/);
  });
  it("trova cicli e riferimenti mancanti", () => {
    expect(
      cycles([
        { source: "a", target: "b" },
        { source: "b", target: "a" },
        { source: "c", target: "c" },
      ]),
    ).toEqual(expect.arrayContaining([["a", "b"], ["c"]]));
    expect(
      validate(
        {
          ...doc,
          relations: [
            ...doc.relations,
            { id: "bad", source: "missing", target: "1", semantic: "OUTPUT" },
          ],
        },
        catalog,
      ).some((i) => i.code === "MISSING_REFERENCE"),
    ).toBe(true);
  });
  it("analizza catene profonde senza overflow dello stack", () => {
    const edges = Array.from({ length: 20000 }, (_, n) => ({
      source: String(n),
      target: String(n + 1),
    }));
    expect(cycles(edges)).toEqual([]);
    edges.push({ source: "20000", target: "0" });
    expect(cycles(edges)[0]).toHaveLength(20001);
  });
  it("ricalcola policy usando parametri salvati, senza soglie nel codice", () => {
    const rule = doc.rules.find(
      (r) =>
        r.purpose === "REQUIREMENT" &&
        r.recipe &&
        "op" in r.recipe &&
        r.recipe.op === "GTE",
    )!;
    expect(evaluateRule(rule, doc)).toBe(true);
    const next = {
      ...doc,
      parameters: { ...doc.parameters, MANAGEMENT_APPROVAL_THRESHOLD: 750000 },
    };
    expect(evaluateRule(rule, next)).toBe(false);
    expect(
      evaluateStates(next).find((e) => e.id === rule.target)?.requirement,
    ).toBe("OPTIONAL");
  });
  it("propaga UNKNOWN e conflitti senza inventare stati", () => {
    const rule = doc.rules.find(
      (r) =>
        r.purpose === "REQUIREMENT" &&
        r.recipe &&
        "op" in r.recipe &&
        r.recipe.op === "GTE",
    )!;
    expect(evaluateRule(rule, { ...doc, parameters: {} })).toBeNull();
    const next = {
      ...doc,
      rules: [...doc.rules, { ...rule, id: 999, trueState: "OPTIONAL" }],
    };
    expect(
      evaluateStates(next).find((e) => e.id === rule.target)?.requirement,
    ).toBe("CONFLICT");
  });
});
