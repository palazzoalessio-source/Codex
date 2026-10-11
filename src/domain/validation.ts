import {
  allowedSemantics,
  isType,
  propertyApplicable,
  type Catalog,
  type ProcessDocument,
} from "./model";
import { arcs, cycles } from "./graph";
export interface Issue {
  code: string;
  severity: "error" | "warning" | "info";
  message: string;
  entityId?: string;
}
export type ValidationRule = (
  doc: ProcessDocument,
  catalog: Catalog,
) => Issue[];
export const structural: ValidationRule = (doc, catalog) => {
  const issues: Issue[] = [],
    by = new Map(doc.entities.map((e) => [e.id, e]));
  if (by.size !== doc.entities.length)
    issues.push({
      code: "DUPLICATE_ID",
      severity: "error",
      message: "Identità duplicate.",
    });
  if (new Set(doc.entities.map((e) => e.uid)).size !== doc.entities.length)
    issues.push({
      code: "DUPLICATE_UID",
      severity: "error",
      message: "UID duplicati.",
    });
  if (new Set(doc.relations.map((r) => r.id)).size !== doc.relations.length)
    issues.push({
      code: "DUPLICATE_RELATION",
      severity: "error",
      message: "ID di relazioni duplicati.",
    });
  const triples = new Set<string>();
  for (const r of doc.relations) {
    const s = by.get(r.source),
      t = by.get(r.target);
    const key = JSON.stringify([r.semantic, r.source, r.target]);
    if (triples.has(key))
      issues.push({
        code: "DUPLICATE_RELATION",
        severity: "error",
        message: "Relazione duplicata.",
        entityId: r.source,
      });
    triples.add(key);
    if (!s || !t)
      issues.push({
        code: "MISSING_REFERENCE",
        severity: "error",
        message: "Endpoint della relazione assente.",
        entityId: r.source,
      });
    else if (!allowedSemantics(s, t, catalog).includes(r.semantic))
      issues.push({
        code: "INVALID_SIGNATURE",
        severity: "error",
        message: `${r.semantic}: firma non ammessa (${s.type} → ${t.type}).`,
        entityId: s.id,
      });
  }
  for (const e of doc.entities) {
    if (!catalog.types.some((t) => t.code === e.type))
      issues.push({
        code: "UNKNOWN_TYPE",
        severity: "error",
        message: `Tipo sconosciuto: ${e.type}`,
        entityId: e.id,
      });
    for (const [code, value] of Object.entries(e.properties)) {
      const p = catalog.properties.find((p) => p.code === code);
      if (!p || !propertyApplicable(e, p, catalog))
        issues.push({
          code: "INVALID_PROPERTY",
          severity: "error",
          message: `Proprietà non applicabile: ${code}`,
          entityId: e.id,
        });
      else if (value !== null) {
        const valid =
          p.valueType === "BOOLEAN"
            ? typeof value === "boolean" || value === 0 || value === 1
            : p.valueType === "INTEGER"
              ? typeof value === "number" && Number.isInteger(value)
              : p.valueType === "NUMBER"
                ? typeof value === "number"
                : typeof value === "string";
        if (!valid)
          issues.push({
            code: "PROPERTY_TYPE",
            severity: "error",
            message: `Tipo errato: ${code}`,
            entityId: e.id,
          });
      }
    }
    for (const sem of ["SOURCE", "TARGET", "VIA", "CARRIES", "PERFORMER"])
      if (
        doc.relations.filter((r) => r.source === e.id && r.semantic === sem)
          .length > 1
      )
        issues.push({
          code: "CARDINALITY",
          severity: "error",
          message: `Più assegnazioni ${sem}.`,
          entityId: e.id,
        });
    if (
      doc.relations.filter(
        (r) => r.target === e.id && r.semantic === "CONTAINS",
      ).length > 1
    )
      issues.push({
        code: "MULTIPLE_GROUPS",
        severity: "error",
        message: "Elemento contenuto in più gruppi.",
        entityId: e.id,
      });
    if (
      isType(e.type, "ACTION", catalog) &&
      !doc.relations.some(
        (r) => r.source === e.id && r.semantic === "PERFORMER",
      )
    )
      issues.push({
        code: "NO_OWNER",
        severity: "warning",
        message: `${e.name}: performer mancante.`,
        entityId: e.id,
      });
    if (e.type === "INFORMATION_FLOW")
      for (const sem of ["SOURCE", "TARGET"])
        if (!doc.relations.some((r) => r.source === e.id && r.semantic === sem))
          issues.push({
            code: "INCOMPLETE_FLOW",
            severity: "error",
            message: `${e.name}: ${sem} mancante.`,
            entityId: e.id,
          });
    if (
      e.type === "INFORMATION" &&
      !doc.relations.some(
        (r) =>
          (r.semantic === "INPUT" ||
            r.semantic === "OUTPUT" ||
            r.semantic === "CARRIES") &&
          r.target === e.id,
      )
    )
      issues.push({
        code: "ORPHAN_INFORMATION",
        severity: "warning",
        message: `${e.name}: informazione senza origine/destinazione.`,
        entityId: e.id,
      });
  }
  for (const sem of catalog.semantics.filter((s) => s.acyclic))
    for (const c of cycles(
      doc.relations.filter((r) => r.semantic === sem.code),
    ))
      issues.push({
        code: "CONTAINMENT_CYCLE",
        severity: "error",
        message: `Ciclo nella relazione ${sem.code}.`,
        entityId: c[0],
      });
  for (const r of doc.rules) {
    if (r.target && !by.has(r.target))
      issues.push({
        code: "RULE_TARGET",
        severity: "error",
        message: `${r.name}: target assente.`,
      });
    if (r.recipe && "kind" in r.recipe && !by.has(String(r.recipe.identity_id)))
      issues.push({
        code: "DEPENDENCY_REFERENCE",
        severity: "error",
        message: `${r.name}: prerequisito assente.`,
      });
    if (r.recipe && "op" in r.recipe)
      for (const operand of [r.recipe.left, r.recipe.right]) {
        if (
          operand.kind === "property" &&
          (!by.has(String(operand.identity_id)) ||
            !catalog.properties.some((p) => p.code === operand.code))
        )
          issues.push({
            code: "RULE_PROPERTY_REFERENCE",
            severity: "error",
            message: `${r.name}: riferimento a proprietà o elemento assente.`,
          });
        if (operand.kind === "parameter" && !(operand.code in doc.parameters))
          issues.push({
            code: "RULE_PARAMETER_UNKNOWN",
            severity: "warning",
            message: `${r.name}: parametro ${operand.code} assente; risultato UNKNOWN.`,
          });
      }
  }
  return issues;
};
export const processTopology: ValidationRule = (doc, catalog) => {
  const issues: Issue[] = [],
    edges = arcs(doc);
  for (const e of doc.entities.filter((e) =>
    isType(e.type, "ACTION", catalog),
  )) {
    const incoming = edges.filter((r) => r.target === e.id),
      outgoing = edges.filter((r) => r.source === e.id);
    if (!incoming.length && !outgoing.length)
      issues.push({
        code: "DISCONNECTED",
        severity: "warning",
        message: `${e.name}: attività isolata.`,
        entityId: e.id,
      });
    else if (!outgoing.length)
      issues.push({
        code: "TERMINAL",
        severity: "info",
        message: `${e.name}: nodo terminale; verificare che sia un esito previsto.`,
        entityId: e.id,
      });
    if (e.type === "DECISION" && outgoing.length < 2)
      issues.push({
        code: "DECISION_OUTCOMES",
        severity: "warning",
        message: `${e.name}: meno di due esiti.`,
        entityId: e.id,
      });
  }
  for (const c of cycles(edges))
    issues.push({
      code: "PROCESS_LOOP",
      severity: "warning",
      message: `Loop di processo: ${c.length} elementi.`,
      entityId: c[0],
    });
  return issues;
};
export function validate(
  doc: ProcessDocument,
  catalog: Catalog,
  rules: ValidationRule[] = [structural, processTopology],
): Issue[] {
  return rules.flatMap((r) => r(doc, catalog));
}
