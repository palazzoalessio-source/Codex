import { it, expect } from "vitest";
import { Repository } from "../server/database";
import { presentationLayouts } from "../src/domain/presentation";
import { captureGroup, insertGroup } from "../src/domain/templates";
import { copyFileSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
it("template reali clonano membri e relazioni con identità indipendenti", () => {
  const folder = mkdtempSync(join(tmpdir(), "ipf-template-"));
  const path = join(folder, "copy.db");
  copyFileSync("legacy/IPF_Mapper_M7.2/resources/demo_m71.db", path);
  const repo = new Repository(path);
  try {
    repo.migrate();
    const doc = repo.read(1),
      group = doc.entities.find((e) => e.type === "PROCESS_GROUP")!;
    const baseline = JSON.stringify(doc),
      action = doc.entities.find((e) => e.code === "RDA_PREP")!;
    expect(presentationLayouts(doc).get(action.id)?.x).toBe(277.5);
    expect(JSON.stringify(doc)).toBe(baseline);
    const moved = {
      ...doc,
      entities: doc.entities.map((e) =>
        e.id === action.id
          ? { ...e, layout: { ...e.layout, x: 900, y: 100 } }
          : e,
      ),
    };
    expect(presentationLayouts(moved).get(action.id)?.x).toBe(900);
    const template = captureGroup(doc, group.id);
    expect(template.entities.length).toBeGreaterThan(1);
    const stored = repo.saveGroupTemplate({
      revisionId: 1,
      groupId: group.id,
      name: "RFQ",
    });
    expect(repo.groupTemplates()[0]).toEqual(stored);
    const inserted = insertGroup(doc, template, 2400, 1200);
    const copies = inserted.entities.slice(doc.entities.length);
    expect(new Set(copies.map((e) => e.uid)).size).toBe(copies.length);
    expect(
      copies.every((e) => !doc.entities.some((o) => o.uid === e.uid)),
    ).toBe(true);
    expect(
      inserted.relations
        .slice(doc.relations.length)
        .every(
          (r) =>
            copies.some((e) => e.id === r.source) &&
            copies.some((e) => e.id === r.target),
        ),
    ).toBe(true);
    const saved = repo.save(inserted);
    expect(saved.entities).toHaveLength(
      doc.entities.length + template.entities.length,
    );
    expect(repo.rows("PRAGMA foreign_key_check")).toEqual([]);
  } finally {
    repo.close();
    rmSync(folder, { recursive: true });
  }
});
