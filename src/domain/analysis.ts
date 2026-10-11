import {
  isType,
  type Catalog,
  type ProcessDocument,
  type Rule,
  type Value,
} from "./model";
import { arcs, cycles } from "./graph";
/** Explicit units only. Unparseable durations remain unknown, never zero. */
export function durationSeconds(value: Value | undefined): number | null {
  if (typeof value !== "string") return null;
  const v = value.trim();
  const iso =
    /^P(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?$/i.exec(
      v,
    );
  if (iso && iso.slice(1).some(Boolean))
    return (
      Number(iso[1] ?? 0) * 86400 +
      Number(iso[2] ?? 0) * 3600 +
      Number(iso[3] ?? 0) * 60 +
      Number(iso[4] ?? 0)
    );
  const simple = /^(\d+(?:\.\d+)?)\s*(s|sec|min|m|h|d)$/i.exec(v);
  return simple
    ? Number(simple[1]) *
        ({ s: 1, sec: 1, min: 60, m: 60, h: 3600, d: 86400 }[
          simple[2].toLowerCase()
        ] ?? 1)
    : null;
}
export function critical(value: Value | undefined) {
  return (
    value !== undefined &&
    value !== null &&
    value !== false &&
    value !== 0 &&
    value !== "" &&
    value !== "NONE"
  );
}
export function analyze(doc: ProcessDocument, catalog: Catalog) {
  const actions = doc.entities.filter((e) => isType(e.type, "ACTION", catalog)),
    edges = arcs(doc),
    owners = new Map(
      doc.relations
        .filter((r) => r.semantic === "PERFORMER")
        .map((r) => [r.source, r.target]),
    );
  const timed = actions.map((e) =>
      durationSeconds(e.properties.TARGET_CYCLE_TIME),
    ),
    known = timed.filter((n): n is number => n !== null);
  const lt = doc.entities
    .filter((e) => e.type === "INFORMATION_FLOW")
    .map((e) => durationSeconds(e.properties.TARGET_LEAD_TIME));
  const values = { VA: 0, NVA: 0, NNVA: 0, UNCLASSIFIED: 0 };
  for (const e of actions) values[e.classification]++;
  const handoffs = edges.filter(
    (e) =>
      e.kind === "flow" &&
      owners.has(e.source) &&
      owners.has(e.target) &&
      owners.get(e.source) !== owners.get(e.target),
  );
  return {
    actions: actions.length,
    information: doc.entities.filter((e) => e.type === "INFORMATION").length,
    flows: doc.entities.filter((e) => e.type === "INFORMATION_FLOW").length,
    relations: doc.relations.length,
    groups: doc.entities.filter((e) => e.type === "PROCESS_GROUP").length,
    decisions: doc.entities.filter((e) => e.type === "DECISION").length,
    criticalities: doc.entities.filter((e) =>
      critical(e.properties.CRITICALITY),
    ).length,
    handoffs: handoffs.length,
    unknownHandoffOwners: edges.filter(
      (e) =>
        e.kind === "flow" && (!owners.has(e.source) || !owners.has(e.target)),
    ).length,
    loops: cycles(edges).length,
    dependencies: edges.filter((e) => e.kind === "dependency").length,
    values,
    cycleTimeSeconds: known.reduce((a, b) => a + b, 0),
    durationCoverage: { known: known.length, total: actions.length },
    flowTimeSeconds: lt.reduce<number>((a, b) => a + (b ?? 0), 0),
    flowDurationCoverage: {
      known: lt.filter((n) => n !== null).length,
      total: lt.length,
    },
  };
}
function canonical(value: unknown): string {
  if (Array.isArray(value))
    return JSON.stringify(
      value.map((v) => JSON.parse(canonical(v)) as unknown),
    );
  if (value && typeof value === "object")
    return JSON.stringify(
      Object.fromEntries(
        Object.entries(value)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([k, v]) => [k, JSON.parse(canonical(v)) as unknown]),
      ),
    );
  return JSON.stringify(value) ?? "null";
}
export function compare(
  before: ProcessDocument,
  after: ProcessDocument,
  catalog: Catalog,
) {
  if (before.revision.modelId !== after.revision.modelId)
    throw new Error("Confrontare revisioni dello stesso processo.");
  const old = new Map(before.entities.map((e) => [e.uid, e])),
    next = new Map(after.entities.map((e) => [e.uid, e]));
  const fields = [
    "name",
    "description",
    "code",
    "type",
    "properties",
    "classification",
  ] as const;
  const modified = [...next.values()].flatMap((e) => {
    const prev = old.get(e.uid);
    if (!prev) return [];
    const changes: string[] = fields.filter(
      (k) => canonical(prev[k]) !== canonical(e[k]),
    );
    for (const sem of [
      "PERFORMER",
      "CONTAINS",
      "SOURCE",
      "TARGET",
      "VIA",
      "CARRIES",
    ]) {
      const links = (doc: ProcessDocument, id: string) =>
        doc.relations
          .filter((r) => r.source === id && r.semantic === sem)
          .map(
            (r) => doc.entities.find((e) => e.id === r.target)?.uid ?? r.target,
          )
          .sort();
      if (canonical(links(before, prev.id)) !== canonical(links(after, e.id)))
        changes.push(sem);
    }
    return changes.length ? [{ id: e.id, name: e.name, fields: changes }] : [];
  });
  const relkeys = (d: ProcessDocument) =>
    new Set(
      d.relations.map((r) =>
        canonical([
          r.semantic,
          d.entities.find((e) => e.id === r.source)?.uid ?? r.source,
          d.entities.find((e) => e.id === r.target)?.uid ?? r.target,
        ]),
      ),
    );
  const a = relkeys(before),
    b = relkeys(after);
  const metricsBefore = analyze(before, catalog),
    metricsAfter = analyze(after, catalog);
  return {
    added: [...next.values()].filter((e) => !old.has(e.uid)),
    removed: [...old.values()].filter((e) => !next.has(e.uid)),
    modified,
    relationsAdded: [...b].filter((k) => !a.has(k)),
    relationsRemoved: [...a].filter((k) => !b.has(k)),
    parametersChanged:
      canonical(before.parameters) !== canonical(after.parameters),
    rulesChanged: canonical(before.rules) !== canonical(after.rules),
    before: metricsBefore,
    after: metricsAfter,
  };
}
export type Truth = true | false | null;
export function evaluateRule(
  rule: Rule,
  doc: ProcessDocument,
  completed: Set<string> = new Set(),
): Truth {
  const recipe = rule.recipe;
  if (!recipe) return null;
  if ("kind" in recipe) return completed.has(String(recipe.identity_id));
  const operand = (o: typeof recipe.left): Value | undefined => {
    switch (o.kind) {
      case "literal":
        return o.value;
      case "parameter":
        return doc.parameters[o.code];
      case "property":
        return doc.entities.find((e) => e.id === String(o.identity_id))
          ?.properties[o.code];
    }
  };
  const a = operand(recipe.left),
    b = operand(recipe.right);
  if (a === undefined || b === undefined || a === null || b === null)
    return null;
  if (recipe.op === "EQ") return a === b;
  if (recipe.op === "NEQ") return a !== b;
  if (typeof a !== "number" || typeof b !== "number") return null;
  switch (recipe.op) {
    case "GT":
      return a > b;
    case "GTE":
      return a >= b;
    case "LT":
      return a < b;
    case "LTE":
      return a <= b;
  }
}
export function evaluateStates(
  doc: ProcessDocument,
  completed: Set<string> = new Set(),
) {
  const resolve = (id: string, purpose: string, fallback: string) => {
    const rs = doc.rules.filter(
      (r) => r.target === id && r.purpose === purpose,
    );
    if (!rs.length) return fallback;
    const states = rs.map((r) => {
      const t = evaluateRule(r, doc, completed);
      return t === null ? null : t ? r.trueState : r.falseState;
    });
    if (states.includes(null)) return "UNKNOWN";
    return new Set(states).size > 1 ? "CONFLICT" : (states[0] ?? "UNKNOWN");
  };
  return doc.entities.map((e) => {
    const applicability = resolve(e.id, "APPLICABILITY", "APPLICABLE");
    let requirement: string, enablement: string;
    if (applicability === "NOT_APPLICABLE") {
      requirement = enablement = "NOT_APPLICABLE";
    } else if (applicability === "UNKNOWN" || applicability === "CONFLICT") {
      requirement = enablement = "UNKNOWN";
    } else {
      requirement = resolve(e.id, "REQUIREMENT", "OPTIONAL");
      enablement =
        requirement === "FORBIDDEN"
          ? "NOT_APPLICABLE"
          : requirement === "UNKNOWN" || requirement === "CONFLICT"
            ? "UNKNOWN"
            : resolve(e.id, "ENABLEMENT", "ENABLED");
    }
    return { id: e.id, name: e.name, applicability, requirement, enablement };
  });
}
