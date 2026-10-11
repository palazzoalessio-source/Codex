import {
  allowedSemantics,
  type Catalog,
  type Entity,
  type ProcessDocument,
  type Relation,
} from "./model";
import { cycles } from "./graph";
export type Command =
  | { type: "upsert"; entity: Entity }
  | {
      type: "move";
      positions: {
        id: string;
        x: number;
        y: number;
        width?: number;
        height?: number;
      }[];
    }
  | { type: "delete"; ids: string[] }
  | { type: "relation"; relation: Relation }
  | { type: "unlink"; id: string }
  | { type: "replace"; document: ProcessDocument };
export function applyCommand(
  doc: ProcessDocument,
  command: Command,
  catalog: Catalog,
): ProcessDocument {
  if (doc.revision.status !== "DRAFT")
    throw new Error("Revisione immutabile: crea una copia DRAFT.");
  switch (command.type) {
    case "replace":
      return command.document;
    case "upsert":
      return {
        ...doc,
        entities: doc.entities.some((e) => e.id === command.entity.id)
          ? doc.entities.map((e) =>
              e.id === command.entity.id ? command.entity : e,
            )
          : [...doc.entities, command.entity],
      };
    case "move":
      return {
        ...doc,
        entities: doc.entities.map((e) => {
          const p = command.positions.find((p) => p.id === e.id);
          return p && !e.layout.locked
            ? { ...e, layout: { ...e.layout, ...p } }
            : e;
        }),
      };
    case "delete": {
      const deleted = new Set(command.ids);
      for (const e of doc.entities.filter((e) => e.type === "INFORMATION_FLOW"))
        if (
          doc.relations.some(
            (r) =>
              r.source === e.id &&
              ["SOURCE", "TARGET"].includes(r.semantic) &&
              deleted.has(r.target),
          )
        )
          deleted.add(e.id);
      const rules = doc.rules.filter(
        (r) => !r.target || !deleted.has(r.target),
      );
      if (
        rules.some(
          (r) =>
            r.recipe &&
            ("kind" in r.recipe
              ? deleted.has(String(r.recipe.identity_id))
              : [r.recipe.left, r.recipe.right].some(
                  (o) =>
                    o.kind === "property" && deleted.has(String(o.identity_id)),
                )),
        )
      )
        throw new Error(
          "Elemento usato da una regola: rimuovere prima il riferimento nel client legacy.",
        );
      return {
        ...doc,
        entities: doc.entities.filter((e) => !deleted.has(e.id)),
        relations: doc.relations.filter(
          (r) => !deleted.has(r.source) && !deleted.has(r.target),
        ),
        rules,
      };
    }
    case "unlink":
      return {
        ...doc,
        relations: doc.relations.filter((r) => r.id !== command.id),
      };
    case "relation": {
      const r = command.relation,
        s = doc.entities.find((e) => e.id === r.source),
        t = doc.entities.find((e) => e.id === r.target);
      if (!s || !t || !allowedSemantics(s, t, catalog).includes(r.semantic))
        throw new Error("Relazione non ammessa dal catalogo.");
      if (
        doc.relations.some(
          (x) =>
            x.semantic === r.semantic &&
            x.source === r.source &&
            x.target === r.target,
        )
      )
        return doc;
      let rels = doc.relations;
      if (
        ["PERFORMER", "SOURCE", "TARGET", "VIA", "CARRIES"].includes(r.semantic)
      )
        rels = rels.filter(
          (x) => x.semantic !== r.semantic || x.source !== r.source,
        );
      if (r.semantic === "CONTAINS") {
        rels = rels.filter(
          (x) => x.semantic !== "CONTAINS" || x.target !== r.target,
        );
        if (
          cycles([...rels.filter((x) => x.semantic === "CONTAINS"), r]).length
        )
          throw new Error("Un gruppo non può contenere un antenato.");
      }
      return { ...doc, relations: [...rels, r] };
    }
  }
}
export interface History {
  past: ProcessDocument[];
  present: ProcessDocument;
  future: ProcessDocument[];
}
export function execute(
  history: History,
  command: Command,
  catalog: Catalog,
): History {
  const next = applyCommand(history.present, command, catalog);
  if (next === history.present) return history;
  return {
    past: [...history.past.slice(-99), history.present],
    present: next,
    future: [],
  };
}
export function undo(h: History): History {
  const p = h.past.at(-1);
  return p
    ? {
        past: h.past.slice(0, -1),
        present: p,
        future: [h.present, ...h.future],
      }
    : h;
}
export function redo(h: History): History {
  const n = h.future[0];
  return n
    ? { past: [...h.past, h.present], present: n, future: h.future.slice(1) }
    : h;
}
