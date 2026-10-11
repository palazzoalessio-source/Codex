import { z } from "zod";
import { entitySchema, relationSchema, type ProcessDocument } from "./model";
export const groupTemplateSchema = z.object({
  root: z.string(),
  entities: z.array(entitySchema),
  relations: z.array(relationSchema),
});
export type GroupTemplate = z.infer<typeof groupTemplateSchema>;
export function captureGroup(
  doc: ProcessDocument,
  root: string,
): GroupTemplate {
  if (doc.entities.find((e) => e.id === root)?.type !== "PROCESS_GROUP")
    throw new Error("Seleziona un gruppo del processo.");
  const members = new Set([root]);
  const queue = [root];
  for (let i = 0; i < queue.length; i++)
    for (const r of doc.relations)
      if (
        r.semantic === "CONTAINS" &&
        r.source === queue[i] &&
        !members.has(r.target)
      ) {
        members.add(r.target);
        queue.push(r.target);
      }
  for (const e of doc.entities.filter((e) => e.type === "INFORMATION_FLOW")) {
    const refs = doc.relations.filter(
      (r) =>
        r.source === e.id &&
        ["SOURCE", "TARGET", "VIA", "CARRIES"].includes(r.semantic),
    );
    if (
      refs.some((r) => r.semantic === "SOURCE") &&
      refs.some((r) => r.semantic === "TARGET") &&
      refs.every((r) => members.has(r.target))
    )
      members.add(e.id);
  }
  return groupTemplateSchema.parse({
    root,
    entities: doc.entities.filter((e) => members.has(e.id)),
    relations: doc.relations.filter(
      (r) => members.has(r.source) && members.has(r.target),
    ),
  });
}
export function insertGroup(
  doc: ProcessDocument,
  template: GroupTemplate,
  x: number,
  y: number,
): ProcessDocument {
  const t = groupTemplateSchema.parse(template),
    root = t.entities.find((e) => e.id === t.root);
  if (root?.type !== "PROCESS_GROUP")
    throw new Error("Template gruppo non valido.");
  const ids = new Map(t.entities.map((e) => [e.id, crypto.randomUUID()]));
  const dx = x - root.layout.x,
    dy = y - root.layout.y;
  return {
    ...doc,
    entities: [
      ...doc.entities,
      ...t.entities.map((e) => ({
        ...e,
        id: ids.get(e.id)!,
        uid: crypto.randomUUID(),
        code: e.code ? `${e.code}_COPY_${ids.get(e.id)!.slice(0, 8)}` : "",
        definitionId: undefined,
        layout: { ...e.layout, x: e.layout.x + dx, y: e.layout.y + dy },
      })),
    ],
    relations: [
      ...doc.relations,
      ...t.relations.map((r) => ({
        ...r,
        id: crypto.randomUUID(),
        source: ids.get(r.source)!,
        target: ids.get(r.target)!,
      })),
    ],
  };
}
