import { z } from "zod";

export const valueSchema = z.union([
  z.string(),
  z.number().finite(),
  z.boolean(),
  z.null(),
]);
export type Value = z.infer<typeof valueSchema>;
export const classificationSchema = z.enum([
  "UNCLASSIFIED",
  "VA",
  "NVA",
  "NNVA",
]);
export type Classification = z.infer<typeof classificationSchema>;
export const layoutSchema = z.object({
  x: z.number().finite(),
  y: z.number().finite(),
  width: z.number().positive().optional(),
  height: z.number().positive().optional(),
  collapsed: z.boolean().default(false),
  locked: z.boolean().default(false),
});
export const entitySchema = z.object({
  id: z.string().min(1),
  uid: z.string().min(1),
  definitionId: z.number().int().positive().optional(),
  type: z.string().min(1),
  name: z.string().trim().min(1),
  description: z.string(),
  code: z.string(),
  properties: z.record(z.string(), valueSchema),
  classification: classificationSchema.default("UNCLASSIFIED"),
  layout: layoutSchema,
});
export type Entity = z.infer<typeof entitySchema>;
export const relationSchema = z.object({
  id: z.string().min(1),
  semantic: z.string().min(1),
  source: z.string().min(1),
  target: z.string().min(1),
});
export type Relation = z.infer<typeof relationSchema>;
export const operandSchema = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("parameter"), code: z.string() }),
  z.object({
    kind: z.literal("property"),
    code: z.string(),
    identity_id: z.number().int().positive(),
  }),
  z.object({ kind: z.literal("literal"), value: valueSchema }),
]);
export const recipeSchema = z.union([
  z.object({
    kind: z.literal("completed"),
    identity_id: z.number().int().positive(),
  }),
  z.object({
    op: z.enum(["EQ", "NEQ", "GT", "GTE", "LT", "LTE"]),
    left: operandSchema,
    right: operandSchema,
  }),
]);
export const ruleSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  purpose: z.string(),
  target: z.string().nullable(),
  trueState: z.string().nullable(),
  falseState: z.string().nullable(),
  recipe: recipeSchema.nullable(),
});
export type Rule = z.infer<typeof ruleSchema>;
export const documentSchema = z.object({
  schemaVersion: z.literal(1),
  revision: z.object({
    id: z.number().int().positive(),
    modelId: z.number().int().positive(),
    workspaceId: z.number().int().positive(),
    name: z.string(),
    code: z.string(),
    purpose: z.string(),
    status: z.enum(["DRAFT", "PUBLISHED", "ARCHIVED"]),
    version: z.number().int().nonnegative(),
  }),
  entities: z.array(entitySchema).max(20000),
  relations: z.array(relationSchema).max(100000),
  parameters: z.record(z.string(), valueSchema),
  rules: z.array(ruleSchema),
  viewport: z.object({
    x: z.number().finite(),
    y: z.number().finite(),
    zoom: z.number().min(0.02).max(4),
  }),
});
export type ProcessDocument = z.infer<typeof documentSchema>;
export interface Catalog {
  types: { code: string; name: string; parent: string | null }[];
  semantics: { code: string; name: string; acyclic: boolean }[];
  signatures: { semantic: string; source: string; target: string }[];
  properties: {
    code: string;
    name: string;
    valueType: string;
    scope: string;
    types: string[];
    unit: string | null;
  }[];
}
export const catalogSchema = z.object({
  types: z.array(
    z.object({
      code: z.string(),
      name: z.string(),
      parent: z.string().nullable(),
    }),
  ),
  semantics: z.array(
    z.object({ code: z.string(), name: z.string(), acyclic: z.boolean() }),
  ),
  signatures: z.array(
    z.object({ semantic: z.string(), source: z.string(), target: z.string() }),
  ),
  properties: z.array(
    z.object({
      code: z.string(),
      name: z.string(),
      valueType: z.string(),
      scope: z.string(),
      types: z.array(z.string()),
      unit: z.string().nullable(),
    }),
  ),
});
export function isType(type: string, base: string, catalog: Catalog): boolean {
  const seen = new Set<string>();
  let current: string | null = type;
  while (current && !seen.has(current)) {
    if (current === base) return true;
    seen.add(current);
    current = catalog.types.find((t) => t.code === current)?.parent ?? null;
  }
  return false;
}
export function allowedSemantics(
  source: Entity,
  target: Entity,
  catalog: Catalog,
): string[] {
  if (source.id === target.id) return [];
  return [
    ...new Set(
      catalog.signatures
        .filter(
          (s) =>
            isType(source.type, s.source, catalog) &&
            isType(target.type, s.target, catalog),
        )
        .map((s) => s.semantic),
    ),
  ];
}
export function propertyApplicable(
  entity: Entity,
  property: Catalog["properties"][number],
  catalog: Catalog,
) {
  return (
    property.scope !== "INSTANCE" &&
    property.types.some((t) => isType(entity.type, t, catalog))
  );
}
export const classificationLabels: Record<Classification, string> = {
  UNCLASSIFIED: "Non classificata",
  VA: "VA · Value Added",
  NVA: "NVA · Non Value Added",
  NNVA: "NNVA · Necessary Non Value Added",
};
export function newEntity(
  type: string,
  name: string,
  x: number,
  y: number,
): Entity {
  const id = crypto.randomUUID();
  return {
    id,
    uid: id,
    type,
    name,
    description: "",
    code: "",
    properties: {},
    classification: "UNCLASSIFIED",
    layout: {
      x,
      y,
      collapsed: false,
      locked: false,
      ...(type === "PROCESS_GROUP" ? { width: 460, height: 240 } : {}),
    },
  };
}
