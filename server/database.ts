import { DatabaseSync, backup, type SQLInputValue } from "node:sqlite";
import { mkdirSync, existsSync, copyFileSync, realpathSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { randomUUID } from "node:crypto";
import { z } from "zod";
import {
  documentSchema,
  projectCreateSchema,
  stateRuleInputSchema,
  recipeSchema,
  isType,
  type ProcessDocument,
  type Catalog,
  type Value,
} from "../src/domain/model";
import { captureGroup } from "../src/domain/templates";
import { structural } from "../src/domain/validation";

const rowSchema = z.record(
  z.string(),
  z.union([z.string(), z.number(), z.null()]),
);
type Row = z.infer<typeof rowSchema>;
const id = () => randomUUID(),
  now = () => new Date().toISOString();
export class Repository {
  readonly db: DatabaseSync;
  constructor(readonly path: string) {
    this.db = new DatabaseSync(path);
    this.db.exec("PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000;");
  }
  rows(sql: string, ...args: SQLInputValue[]): Row[] {
    return this.db
      .prepare(sql)
      .all(...args)
      .map((r) => rowSchema.parse(r));
  }
  row(sql: string, ...args: SQLInputValue[]): Row {
    const r = this.db.prepare(sql).get(...args);
    if (!r) throw new Error("Record non trovato.");
    return rowSchema.parse(r);
  }
  run(sql: string, ...args: SQLInputValue[]) {
    return this.db.prepare(sql).run(...args);
  }
  transaction<T>(f: () => T): T {
    this.db.exec("BEGIN IMMEDIATE");
    try {
      const result = f();
      this.db.exec("COMMIT");
      return result;
    } catch (e) {
      this.db.exec("ROLLBACK");
      throw e;
    }
  }
  close() {
    this.db.close();
  }
  migrate() {
    // Additive only. The backup is completed by openRepository BEFORE this call.
    this.transaction(() => {
      this.db
        .exec(`CREATE TABLE IF NOT EXISTS web_revision_version(revision_id INTEGER PRIMARY KEY REFERENCES model_revision(id),version INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS web_group_template(id INTEGER PRIMARY KEY,uid TEXT NOT NULL UNIQUE,workspace_id INTEGER NOT NULL REFERENCES workspace(id),name TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS web_entity_ui(revision_id INTEGER NOT NULL REFERENCES model_revision(id),identity_id INTEGER NOT NULL REFERENCES entity_identity(id),locked INTEGER NOT NULL DEFAULT 0 CHECK(locked IN (0,1)),PRIMARY KEY(revision_id,identity_id));`);
      if (
        !this.rows(
          "SELECT id FROM property_definition WHERE code='VALUE_CLASSIFICATION' AND workspace_id IS NULL",
        ).length
      ) {
        const pid = this.run(
          "INSERT INTO property_definition(uid,code,name,value_type,scope,is_core) VALUES(?,?,?,?,?,1)",
          id(),
          "VALUE_CLASSIFICATION",
          "Value classification",
          "ENUM",
          "DEFINITION",
        ).lastInsertRowid;
        this.run(
          "INSERT INTO property_applicability SELECT ?,id FROM entity_type WHERE code='ACTION' AND workspace_id IS NULL",
          pid,
        );
      }
      if (
        !this.rows(
          "SELECT id FROM entity_type WHERE code='DECISION' AND workspace_id IS NULL",
        ).length
      )
        this.run(
          "INSERT INTO entity_type(uid,parent_type_id,code,name,is_core) VALUES(?,(SELECT id FROM entity_type WHERE code='ACTION' AND workspace_id IS NULL),?,?,1)",
          id(),
          "DECISION",
          "Decision",
        );
    });
  }
  catalog(): Catalog {
    return {
      types: this.rows(
        "SELECT t.code,t.name,p.code parent FROM entity_type t LEFT JOIN entity_type p ON p.id=t.parent_type_id",
      ).map((r) => ({
        code: String(r.code),
        name: String(r.name),
        parent: r.parent === null ? null : String(r.parent),
      })),
      semantics: this.rows(
        "SELECT code,name,is_acyclic FROM relation_semantic",
      ).map((r) => ({
        code: String(r.code),
        name: String(r.name),
        acyclic: !!r.is_acyclic,
      })),
      signatures: this.rows(
        "SELECT rs.code semantic,s.code source,t.code target FROM relation_signature sig JOIN relation_semantic rs ON rs.id=sig.relation_semantic_id JOIN entity_type s ON s.id=sig.source_entity_type_id JOIN entity_type t ON t.id=sig.target_entity_type_id",
      ).map((r) => ({
        semantic: String(r.semantic),
        source: String(r.source),
        target: String(r.target),
      })),
      properties: this.rows("SELECT * FROM property_definition").map((r) => ({
        code: String(r.code),
        name: String(r.name),
        valueType: String(r.value_type),
        scope: String(r.scope),
        unit: r.unit === null ? null : String(r.unit),
        types: this.rows(
          "SELECT t.code FROM property_applicability a JOIN entity_type t ON t.id=a.entity_type_id WHERE a.property_definition_id=?",
          r.id,
        ).map((t) => String(t.code)),
      })),
    };
  }
  list() {
    return this.rows(
      "SELECT r.id,r.revision_code code,r.purpose,r.status,r.process_model_id modelId,m.name,m.workspace_id workspaceId FROM model_revision r JOIN process_model m ON m.id=r.process_model_id WHERE m.retired_at IS NULL ORDER BY r.id",
    );
  }
  groupTemplates() {
    return this.rows(
      "SELECT id,name,payload FROM web_group_template ORDER BY id DESC",
    ).map((r) => ({
      id: Number(r.id),
      name: String(r.name),
      template: JSON.parse(String(r.payload)),
    }));
  }
  saveGroupTemplate(input: unknown) {
    const data = z
      .object({
        revisionId: z.number().int().positive(),
        groupId: z.string(),
        name: z.string().trim().min(1).max(160),
      })
      .parse(input);
    const doc = this.read(data.revisionId),
      template = captureGroup(doc, data.groupId);
    const result = this.run(
      "INSERT INTO web_group_template(uid,workspace_id,name,payload,created_at) VALUES(?,?,?,?,?)",
      id(),
      doc.revision.workspaceId,
      data.name,
      JSON.stringify(template),
      now(),
    );
    return { id: Number(result.lastInsertRowid), name: data.name, template };
  }
  projects() {
    return this
      .rows(`SELECT m.id,m.workspace_id workspaceId,m.name,w.name projectName,COALESCE(m.description,'') description,m.created_at createdAt,
      (SELECT COUNT(*) FROM model_revision r WHERE r.process_model_id=m.id) revisionCount,
      (SELECT r.id FROM model_revision r WHERE r.process_model_id=m.id ORDER BY r.status='DRAFT' DESC,r.id DESC LIMIT 1) revisionId,
      (SELECT COUNT(*) FROM model_revision_entity e WHERE e.model_revision_id=(SELECT r.id FROM model_revision r WHERE r.process_model_id=m.id ORDER BY r.status='DRAFT' DESC,r.id DESC LIMIT 1)) entityCount
      FROM process_model m JOIN workspace w ON w.id=m.workspace_id WHERE m.retired_at IS NULL ORDER BY m.created_at DESC,m.id DESC`);
  }
  createProject(input: unknown): ProcessDocument {
    const data = projectCreateSchema.parse(input);
    const rid = this.transaction(() => {
      const wid = this.run(
        "INSERT INTO workspace(uid,name,description,created_at) VALUES(?,?,?,?)",
        id(),
        data.name,
        data.description,
        now(),
      ).lastInsertRowid;
      const mid = this.run(
        "INSERT INTO process_model(uid,workspace_id,name,description,created_at) VALUES(?,?,?,?,?)",
        id(),
        wid,
        data.processName,
        data.description,
        now(),
      ).lastInsertRowid;
      const rid = this.run(
        "INSERT INTO model_revision(uid,process_model_id,revision_code,purpose,status,created_at) VALUES(?,?,?,'AS_IS','DRAFT',?)",
        id(),
        mid,
        "AS-IS-1",
        now(),
      ).lastInsertRowid;
      this.run(
        "INSERT INTO web_revision_version(revision_id,version) VALUES(?,0)",
        rid,
      );
      return Number(rid);
    });
    return this.read(rid);
  }
  saveStateRule(rid: number, input: unknown): ProcessDocument {
    const data = stateRuleInputSchema.parse(input);
    return this.transaction(() => {
      const doc = this.read(rid);
      if (doc.revision.status !== "DRAFT")
        throw new Error("Revisione immutabile.");
      if (doc.revision.version !== data.version)
        throw new ConflictError(
          "La revisione è cambiata: ricaricare prima di salvare.",
        );
      const old = data.ruleId
        ? doc.rules.find((r) => r.id === data.ruleId)
        : undefined;
      if (data.ruleId && (!old || !old.recipe))
        throw new Error("Regola di stato non appartenente alla revisione.");
      const proposed = {
        id: data.ruleId ?? -1,
        name: data.name,
        purpose: data.purpose,
        target: data.target,
        trueState: data.trueState,
        falseState: data.falseState,
        recipe: data.recipe,
      };
      const errors = structural(
        { ...doc, rules: [proposed] },
        this.catalog(),
      ).filter(
        (i) => i.severity === "error" || i.code === "RULE_PARAMETER_UNKNOWN",
      );
      if (errors.length)
        throw new Error(errors.map((e) => e.message).join("\n"));
      const expr = this.run(
        "INSERT INTO expression(uid,created_at) VALUES(?,?)",
        id(),
        now(),
      ).lastInsertRowid;
      const operation = (
        code: string,
        parent: SQLInputValue = null,
        position = 0,
      ) =>
        this.run(
          "INSERT INTO expression_node(expression_id,parent_node_id,position,node_kind,operation_code) VALUES(?,?,?,'OPERATION',?)",
          expr,
          parent,
          position,
          code,
        ).lastInsertRowid;
      const reference = (
        kind: string,
        scope: string,
        entity: SQLInputValue,
        property: SQLInputValue,
        variable: SQLInputValue,
        parent: SQLInputValue,
        position: number,
      ) =>
        this.run(
          "INSERT INTO expression_node(expression_id,parent_node_id,position,node_kind,reference_kind,reference_scope,entity_identity_id,property_definition_id,variable_name) VALUES(?,?,?,'REFERENCE',?,?,?,?,?)",
          expr,
          parent,
          position,
          kind,
          scope,
          entity,
          property,
          variable,
        );
      const literal = (
        value: Value,
        parent: SQLInputValue,
        position: number,
        type?: string,
      ) => {
        if (value === null)
          throw new Error("Usare un valore costante esplicito.");
        const typ =
          type ??
          (typeof value === "boolean"
            ? "BOOLEAN"
            : typeof value === "number"
              ? "NUMBER"
              : "TEXT");
        this.run(
          "INSERT INTO expression_node(expression_id,parent_node_id,position,node_kind,literal_type,literal_text,literal_integer,literal_real,literal_boolean) VALUES(?,?,?,'LITERAL',?,?,?,?,?)",
          expr,
          parent,
          position,
          typ,
          ...this.columns(typ, value),
        );
      };
      if ("kind" in data.recipe) {
        const pre = data.recipe.identity_id;
        if (
          !isType(
            doc.entities.find((e) => e.id === String(pre))!.type,
            "ACTION",
            this.catalog(),
          )
        )
          throw new Error("Il prerequisito deve essere un’attività.");
        const root = operation("ANY");
        reference("ENTITY", "INSTANCE", pre, null, null, root, 0);
        const equal = operation("EQ", root, 1);
        const property = this.row(
          "SELECT id FROM property_definition WHERE code='STATUS' AND workspace_id IS NULL",
        ).id;
        reference("PROPERTY", "INSTANCE", pre, property, null, equal, 0);
        literal("COMPLETED", equal, 1, "ENUM");
      } else {
        const root = operation(data.recipe.op);
        for (const [position, operand] of [
          data.recipe.left,
          data.recipe.right,
        ].entries()) {
          if (operand.kind === "literal")
            literal(operand.value, root, position);
          else if (operand.kind === "parameter")
            reference(
              "CONTEXT",
              "CONTEXT",
              null,
              null,
              operand.code,
              root,
              position,
            );
          else {
            const property = this.row(
              "SELECT id FROM property_definition WHERE code=? AND (workspace_id IS NULL OR workspace_id=?) ORDER BY workspace_id DESC LIMIT 1",
              operand.code,
              doc.revision.workspaceId,
            ).id;
            reference(
              "PROPERTY",
              "DEFINITION",
              operand.identity_id,
              property,
              null,
              root,
              position,
            );
          }
        }
      }
      const identity = old
        ? this.row(
            "SELECT rule_identity_id FROM rule_definition WHERE id=?",
            old.id,
          ).rule_identity_id
        : this.run(
            "INSERT INTO rule_identity(uid,workspace_id,created_at) VALUES(?,?,?)",
            id(),
            doc.revision.workspaceId,
            now(),
          ).lastInsertRowid;
      const did = this.run(
        "INSERT INTO rule_definition(uid,rule_identity_id,semantic,name,body_expression_id,created_at,purpose) VALUES(?,?,'ASSERTION',?,?,?,?)",
        id(),
        identity,
        data.name,
        expr,
        now(),
        data.purpose,
      ).lastInsertRowid;
      this.run(
        "INSERT INTO state_rule_config(rule_definition_id,target_identity_id,true_state,false_state,recipe) VALUES(?,?,?,?,?)",
        did,
        Number(data.target),
        data.trueState,
        data.falseState,
        JSON.stringify(data.recipe),
      );
      if (old)
        this.run(
          "DELETE FROM model_revision_rule WHERE model_revision_id=? AND rule_definition_id=?",
          rid,
          old.id,
        );
      this.run("INSERT INTO model_revision_rule VALUES(?,?)", rid, did);
      this.run(
        "INSERT INTO web_revision_version VALUES(?,1) ON CONFLICT(revision_id) DO UPDATE SET version=version+1",
        rid,
      );
      return this.read(rid);
    });
  }
  deleteRule(rid: number, ruleId: number, version: number): ProcessDocument {
    return this.transaction(() => {
      const doc = this.read(rid);
      if (doc.revision.status !== "DRAFT")
        throw new Error("Revisione immutabile.");
      if (doc.revision.version !== version)
        throw new ConflictError(
          "La revisione è cambiata: ricaricare prima di salvare.",
        );
      if (!doc.rules.some((r) => r.id === ruleId))
        throw new Error("Regola non appartenente alla revisione.");
      this.run(
        "DELETE FROM model_revision_rule WHERE model_revision_id=? AND rule_definition_id=?",
        rid,
        ruleId,
      );
      this.run(
        "INSERT INTO web_revision_version VALUES(?,1) ON CONFLICT(revision_id) DO UPDATE SET version=version+1",
        rid,
      );
      return this.read(rid);
    });
  }
  decode(r: Row): Value {
    if (r.value_boolean !== undefined && r.value_boolean !== null)
      return !!r.value_boolean;
    return r.value_text ?? r.value_integer ?? r.value_real ?? null;
  }
  read(rid: number): ProcessDocument {
    const r = this.row(
      "SELECT r.*,m.name,m.workspace_id FROM model_revision r JOIN process_model m ON m.id=r.process_model_id WHERE r.id=?",
      rid,
    );
    const catalog = this.catalog();
    const entities = this.rows(
      `SELECT i.id,i.uid,i.stable_code,d.id definitionId,d.name,d.description,t.code type,l.x,l.y,l.width,l.height,l.collapsed,u.locked FROM model_revision_entity m JOIN entity_definition d ON d.id=m.entity_definition_id JOIN entity_identity i ON i.id=d.entity_identity_id JOIN entity_type t ON t.id=i.entity_type_id LEFT JOIN entity_view_layout l ON l.model_revision_id=m.model_revision_id AND l.entity_identity_id=i.id LEFT JOIN web_entity_ui u ON u.revision_id=m.model_revision_id AND u.identity_id=i.id WHERE m.model_revision_id=? ORDER BY i.id`,
      rid,
    ).map((e, index) => {
      const properties = Object.fromEntries(
        this.rows(
          "SELECT p.code,v.* FROM definition_property_value v JOIN property_definition p ON p.id=v.property_definition_id WHERE v.entity_definition_id=?",
          e.definitionId,
        ).map((p) => [String(p.code), this.decode(p)]),
      );
      const classification = properties.VALUE_CLASSIFICATION ?? "UNCLASSIFIED",
        code = String(properties.ENTITY_CODE ?? e.stable_code ?? "");
      delete properties.VALUE_CLASSIFICATION;
      delete properties.ENTITY_CODE;
      return {
        id: String(e.id),
        uid: String(e.uid),
        definitionId: Number(e.definitionId),
        type: String(e.type),
        name: String(e.name),
        description: String(e.description ?? ""),
        code,
        properties,
        classification,
        layout: {
          x: Number(e.x ?? 220 + (index % 7) * 240),
          y: Number(e.y ?? 110 + Math.floor(index / 7) * 150),
          ...(e.width ? { width: Number(e.width) } : {}),
          ...(e.height ? { height: Number(e.height) } : {}),
          collapsed: !!e.collapsed,
          locked: !!e.locked,
        },
      };
    });
    // Fixed query joins membership directly, so missing endpoints remain visible to validation.
    const relations = this.rows(
      "SELECT r.id,s.code semantic,r.source_entity_identity_id source,r.target_entity_identity_id target FROM model_revision_relation m JOIN relation_definition r ON r.id=m.relation_definition_id JOIN relation_semantic s ON s.id=r.semantic_id WHERE m.model_revision_id=?",
      rid,
    ).map((r) => ({
      id: String(r.id),
      semantic: String(r.semantic),
      source: String(r.source),
      target: String(r.target),
    }));
    const rules = this.rows(
      "SELECT r.id,r.name,r.purpose,s.target_identity_id target,s.true_state,s.false_state,s.recipe FROM model_revision_rule m JOIN rule_definition r ON r.id=m.rule_definition_id LEFT JOIN state_rule_config s ON s.rule_definition_id=r.id WHERE m.model_revision_id=?",
      rid,
    ).map((r) => {
      let recipe = null;
      if (r.recipe) {
        const parsed = recipeSchema.safeParse(JSON.parse(String(r.recipe)));
        if (parsed.success) recipe = parsed.data;
      }
      return {
        id: Number(r.id),
        name: String(r.name),
        purpose: String(r.purpose),
        target: r.target === null ? null : String(r.target),
        trueState: r.true_state === null ? null : String(r.true_state),
        falseState: r.false_state === null ? null : String(r.false_state),
        recipe,
      };
    });
    const parameters = Object.fromEntries(
      this.rows(
        "SELECT p.code,v.* FROM model_revision_parameter_value v JOIN model_parameter_definition p ON p.id=v.parameter_definition_id WHERE v.model_revision_id=?",
        rid,
      ).map((p) => [String(p.code), this.decode(p)]),
    );
    const view = this.rows(
      "SELECT * FROM model_revision_view WHERE model_revision_id=?",
      rid,
    )[0];
    void catalog;
    return documentSchema.parse({
      schemaVersion: 1,
      revision: {
        id: rid,
        modelId: r.process_model_id,
        workspaceId: r.workspace_id,
        name: r.name,
        code: r.revision_code,
        purpose: r.purpose ?? "AS_IS",
        status: r.status,
        version:
          this.rows(
            "SELECT version FROM web_revision_version WHERE revision_id=?",
            rid,
          )[0]?.version ?? 0,
      },
      entities,
      relations,
      rules,
      parameters,
      viewport: {
        x: view?.pan_x ?? 0,
        y: view?.pan_y ?? 0,
        zoom: view?.zoom ?? 1,
      },
    });
  }
  columns(type: string, value: Value): SQLInputValue[] {
    if (value === null) return [null, null, null, null];
    if (type === "BOOLEAN") {
      if (typeof value !== "boolean" && value !== 0 && value !== 1)
        throw new Error("Valore booleano richiesto.");
      return [null, null, null, value ? 1 : 0];
    }
    if (type === "INTEGER" || type === "NUMBER") {
      if (
        typeof value !== "number" ||
        !Number.isFinite(value) ||
        (type === "INTEGER" && !Number.isInteger(value))
      )
        throw new Error("Numero non valido.");
      return [
        null,
        type === "INTEGER" ? value : null,
        type === "NUMBER" ? value : null,
        null,
      ];
    }
    if (typeof value !== "string")
      throw new Error("Valore testuale richiesto.");
    if (
      type === "DATETIME" &&
      (!Number.isFinite(Date.parse(value)) ||
        !/(Z|[+-]\d{2}:\d{2})$/.test(value))
    )
      throw new Error("Timestamp valido con fuso orario richiesto.");
    if (
      type === "DATE" &&
      (!/^\d{4}-\d{2}-\d{2}$/.test(value) ||
        !Number.isFinite(Date.parse(value)) ||
        new Date(value).toISOString().slice(0, 10) !== value)
    )
      throw new Error("Data ISO non valida.");
    return [value, null, null, null];
  }
  setProperty(did: number, code: string, value: Value, workspace: number) {
    const p = this.row(
      "SELECT * FROM property_definition WHERE code=? AND (workspace_id IS NULL OR workspace_id=?) ORDER BY workspace_id DESC LIMIT 1",
      code,
      workspace,
    );
    if (value === null) {
      this.run(
        "DELETE FROM definition_property_value WHERE entity_definition_id=? AND property_definition_id=?",
        did,
        p.id,
      );
      return;
    }
    this.run(
      "INSERT INTO definition_property_value VALUES(?,?,?,?,?,?) ON CONFLICT(entity_definition_id,property_definition_id) DO UPDATE SET value_text=excluded.value_text,value_integer=excluded.value_integer,value_real=excluded.value_real,value_boolean=excluded.value_boolean",
      did,
      p.id,
      ...this.columns(String(p.value_type), value),
    );
  }
  save(input: unknown): ProcessDocument {
    const doc = documentSchema.parse(input),
      rid = doc.revision.id;
    return this.transaction(() => {
      const previous = this.read(rid);
      if (previous.revision.status !== "DRAFT")
        throw new Error("Revisione pubblicata o archiviata: immutabile.");
      if (previous.revision.version !== doc.revision.version)
        throw new ConflictError(
          "La revisione è cambiata: ricaricare prima di salvare.",
        );
      if (
        previous.revision.modelId !== doc.revision.modelId ||
        previous.revision.workspaceId !== doc.revision.workspaceId
      )
        throw new Error("Il processo non può cambiare.");
      const errors = structural(doc, this.catalog()).filter(
        (i) => i.severity === "error",
      );
      if (errors.length)
        throw new Error(errors.map((e) => e.message).join("\n"));
      // Rule definitions are retained verbatim; deleting membership never deletes historical rows.
      for (const rule of doc.rules) {
        const original = previous.rules.find((r) => r.id === rule.id);
        if (!original || JSON.stringify(original) !== JSON.stringify(rule))
          throw new Error(
            "La modifica delle espressioni di regola resta nel client legacy.",
          );
      }
      const mapping = new Map<string, number>();
      for (const e of doc.entities) {
        const old = previous.entities.find((o) => o.id === e.id);
        let iid: number, did: number;
        if (old) {
          if (old.uid !== e.uid || old.type !== e.type)
            throw new Error("Identità e tipo esistenti sono immutabili.");
          iid = Number(old.id);
          did = old.definitionId!;
          const shared = this.rows(
            "SELECT 1 FROM model_revision_entity WHERE entity_definition_id=? AND model_revision_id<>?",
            did,
            rid,
          ).length;

          if (shared) {
            const origin = this.row(
              "SELECT origin FROM entity_definition WHERE id=?",
              did,
            ).origin;
            const next = Number(
              this.run(
                "INSERT INTO entity_definition(uid,entity_identity_id,name,description,origin,created_at) VALUES(?,?,?,?,?,?)",
                id(),
                iid,
                e.name,
                e.description,
                origin,
                now(),
              ).lastInsertRowid,
            );
            this.run(
              "INSERT INTO definition_property_value SELECT ?,property_definition_id,value_text,value_integer,value_real,value_boolean FROM definition_property_value WHERE entity_definition_id=?",
              next,
              did,
            );
            this.run(
              "DELETE FROM model_revision_entity WHERE model_revision_id=? AND entity_definition_id=?",
              rid,
              did,
            );
            this.run(
              "INSERT INTO model_revision_entity VALUES(?,?)",
              rid,
              next,
            );
            did = next;
          }
        } else {
          if (/^\d+$/.test(e.id)) {
            const retained = this.row(
              "SELECT i.id,i.uid,t.code type FROM entity_identity i JOIN entity_type t ON t.id=i.entity_type_id WHERE i.id=? AND i.workspace_id=?",
              Number(e.id),
              doc.revision.workspaceId,
            );
            if (retained.uid !== e.uid || retained.type !== e.type)
              throw new Error("Identità incoerente.");
          }
          const t = this.row(
            "SELECT id FROM entity_type WHERE code=? AND (workspace_id IS NULL OR workspace_id=?) ORDER BY workspace_id DESC LIMIT 1",
            e.type,
            doc.revision.workspaceId,
          );
          iid = /^\d+$/.test(e.id)
            ? Number(e.id)
            : Number(
                this.run(
                  "INSERT INTO entity_identity(uid,workspace_id,entity_type_id,stable_code,created_at) VALUES(?,?,?,?,?)",
                  e.uid,
                  doc.revision.workspaceId,
                  t.id,
                  e.code || null,
                  now(),
                ).lastInsertRowid,
              );
          did = Number(
            this.run(
              "INSERT INTO entity_definition(uid,entity_identity_id,name,description,created_at) VALUES(?,?,?,?,?)",
              id(),
              iid,
              e.name,
              e.description,
              now(),
            ).lastInsertRowid,
          );
          this.run("INSERT INTO model_revision_entity VALUES(?,?)", rid, did);
        }
        mapping.set(e.id, iid);
        this.run(
          "UPDATE entity_definition SET name=?,description=? WHERE id=?",
          e.name,
          e.description,
          did,
        );
        // Patch only explicit property differences. Unknown values remain untouched.
        const properties = {
          ...e.properties,
          ENTITY_CODE: e.code,
          ...(isType(e.type, "ACTION", this.catalog())
            ? { VALUE_CLASSIFICATION: e.classification }
            : {}),
        };
        for (const [code, value] of Object.entries(properties))
          this.setProperty(did, code, value, doc.revision.workspaceId);
        for (const code of Object.keys(old?.properties ?? {}))
          if (!(code in properties))
            this.setProperty(did, code, null, doc.revision.workspaceId);
        this.run(
          "INSERT INTO entity_view_layout(model_revision_id,entity_identity_id,x,y,width,height,collapsed,z_index) VALUES(?,?,?,?,?,?,?,0) ON CONFLICT(model_revision_id,entity_identity_id) DO UPDATE SET x=excluded.x,y=excluded.y,width=excluded.width,height=excluded.height,collapsed=excluded.collapsed",
          rid,
          iid,
          e.layout.x,
          e.layout.y,
          e.layout.width ?? null,
          e.layout.height ?? null,
          +e.layout.collapsed,
        );
        this.run(
          "INSERT INTO web_entity_ui VALUES(?,?,?) ON CONFLICT(revision_id,identity_id) DO UPDATE SET locked=excluded.locked",
          rid,
          iid,
          +e.layout.locked,
        );
      }
      for (const e of previous.entities)
        if (!mapping.has(e.id))
          this.run(
            "DELETE FROM model_revision_entity WHERE model_revision_id=? AND entity_definition_id=?",
            rid,
            e.definitionId!,
          );
      this.run(
        "DELETE FROM model_revision_relation WHERE model_revision_id=?",
        rid,
      );
      for (const r of doc.relations) {
        const source = mapping.get(r.source)!,
          target = mapping.get(r.target)!;
        const existing = previous.relations.find(
          (x) =>
            x.id === r.id &&
            x.semantic === r.semantic &&
            Number(x.source) === source &&
            Number(x.target) === target,
        );
        let relation: number;
        if (existing) relation = Number(existing.id);
        else {
          const sem = this.row(
            "SELECT id FROM relation_semantic WHERE code=? AND (workspace_id IS NULL OR workspace_id=?) ORDER BY workspace_id DESC LIMIT 1",
            r.semantic,
            doc.revision.workspaceId,
          );
          relation = Number(
            this.run(
              "INSERT INTO relation_definition(uid,workspace_id,semantic_id,source_entity_identity_id,target_entity_identity_id,created_at) VALUES(?,?,?,?,?,?)",
              id(),
              doc.revision.workspaceId,
              sem.id,
              source,
              target,
              now(),
            ).lastInsertRowid,
          );
        }
        this.run(
          "INSERT INTO model_revision_relation VALUES(?,?)",
          rid,
          relation,
        );
      }
      for (const rule of previous.rules)
        if (!doc.rules.some((r) => r.id === rule.id))
          this.run(
            "DELETE FROM model_revision_rule WHERE model_revision_id=? AND rule_definition_id=?",
            rid,
            rule.id,
          );
      for (const [code, value] of Object.entries(doc.parameters)) {
        const p = this.row(
          "SELECT * FROM model_parameter_definition WHERE workspace_id=? AND code=?",
          doc.revision.workspaceId,
          code,
        );
        this.run(
          "INSERT INTO model_revision_parameter_value VALUES(?,?,?,?,?,?) ON CONFLICT(model_revision_id,parameter_definition_id) DO UPDATE SET value_text=excluded.value_text,value_integer=excluded.value_integer,value_real=excluded.value_real,value_boolean=excluded.value_boolean",
          rid,
          p.id,
          ...this.columns(String(p.value_type), value),
        );
      }
      this.run(
        "INSERT INTO model_revision_view VALUES(?,?,?,?,?) ON CONFLICT(model_revision_id) DO UPDATE SET zoom=excluded.zoom,pan_x=excluded.pan_x,pan_y=excluded.pan_y,updated_at=excluded.updated_at",
        rid,
        doc.viewport.zoom,
        doc.viewport.x,
        doc.viewport.y,
        now(),
      );
      this.run(
        "INSERT INTO web_revision_version VALUES(?,1) ON CONFLICT(revision_id) DO UPDATE SET version=version+1",
        rid,
      );
      return this.read(rid);
    });
  }
  clone(rid: number, code: string, purpose: string): ProcessDocument {
    if (!code.trim() || !["AS_IS", "TO_BE"].includes(purpose))
      throw new Error("Codice e scopo della revisione non validi.");
    return this.transaction(() => {
      const src = this.row("SELECT * FROM model_revision WHERE id=?", rid);
      const next = Number(
        this.run(
          "INSERT INTO model_revision(uid,process_model_id,parent_revision_id,revision_code,purpose,status,created_at) VALUES(?,?,?,?,?,?,?)",
          id(),
          src.process_model_id,
          rid,
          code,
          purpose,
          "DRAFT",
          now(),
        ).lastInsertRowid,
      );
      for (const d of this.rows(
        "SELECT d.* FROM model_revision_entity m JOIN entity_definition d ON d.id=m.entity_definition_id WHERE m.model_revision_id=?",
        rid,
      )) {
        const did = Number(
          this.run(
            "INSERT INTO entity_definition(uid,entity_identity_id,name,description,origin,created_at) VALUES(?,?,?,?,?,?)",
            id(),
            d.entity_identity_id,
            d.name,
            d.description,
            d.origin,
            now(),
          ).lastInsertRowid,
        );
        this.run("INSERT INTO model_revision_entity VALUES(?,?)", next, did);
        this.run(
          "INSERT INTO definition_property_value SELECT ?,property_definition_id,value_text,value_integer,value_real,value_boolean FROM definition_property_value WHERE entity_definition_id=?",
          did,
          d.id,
        );
      }
      for (const [table, col] of [
        ["model_revision_relation", "relation_definition_id"],
        ["model_revision_rule", "rule_definition_id"],
      ] as const)
        this.run(
          `INSERT INTO ${table} SELECT ?,${col} FROM ${table} WHERE model_revision_id=?`,
          next,
          rid,
        );
      this.run(
        "INSERT INTO model_revision_parameter_value SELECT ?,parameter_definition_id,value_text,value_integer,value_real,value_boolean FROM model_revision_parameter_value WHERE model_revision_id=?",
        next,
        rid,
      );
      this.run(
        "INSERT INTO entity_view_layout SELECT ?,entity_identity_id,x,y,width,height,collapsed,z_index FROM entity_view_layout WHERE model_revision_id=?",
        next,
        rid,
      );
      this.run(
        "INSERT INTO web_entity_ui SELECT ?,identity_id,locked FROM web_entity_ui WHERE revision_id=?",
        next,
        rid,
      );
      this.run(
        "INSERT INTO model_revision_view SELECT ?,zoom,pan_x,pan_y,updated_at FROM model_revision_view WHERE model_revision_id=?",
        next,
        rid,
      );
      return this.read(next);
    });
  }
  executions(modelId: number) {
    return this.rows(
      "SELECT e.id,e.model_revision_id revisionId,c.name FROM model_execution e JOIN execution_context c ON c.id=e.execution_context_id JOIN model_revision r ON r.id=e.model_revision_id WHERE r.process_model_id=?",
      modelId,
    );
  }
  execution(eid: number) {
    const execution = this.row("SELECT * FROM model_execution WHERE id=?", eid);
    const instances = this.rows(
      "SELECT i.id,d.entity_identity_id identityId,d.name FROM model_execution_entity m JOIN entity_instance i ON i.id=m.entity_instance_id JOIN entity_definition d ON d.id=i.entity_definition_id WHERE m.model_execution_id=?",
      eid,
    ).map((i) => ({
      ...i,
      values: Object.fromEntries(
        this.rows(
          "SELECT p.code,v.* FROM instance_property_value v JOIN property_definition p ON p.id=v.property_definition_id WHERE v.entity_instance_id=?",
          i.id,
        ).map((v) => [String(v.code), this.decode(v)]),
      ),
      observations: this.rows(
        "SELECT p.code,o.* FROM property_observation o JOIN property_definition p ON p.id=o.property_definition_id WHERE o.entity_instance_id=? ORDER BY o.observed_at,o.id",
        i.id,
      ),
    }));
    return {
      execution,
      instances,
      corrections: this.rows(
        "SELECT * FROM runtime_correction WHERE execution_id=?",
        eid,
      ),
    };
  }
}
export class ConflictError extends Error {}
export async function openRepository(path?: string): Promise<Repository> {
  const root = resolve(".");
  const original = resolve(
    root,
    "legacy/IPF_Mapper_M7.2/resources/demo_m71.db",
  );
  const target = resolve(
    path ?? process.env.IPF_DB_PATH ?? ".local/demo-working.db",
  );
  mkdirSync(dirname(target), { recursive: true });
  if (!existsSync(target)) {
    if (path || process.env.IPF_DB_PATH)
      throw new Error(
        "Database richiesto non esistente: nessun database vuoto verrà creato.",
      );
    copyFileSync(original, target);
  }
  if (realpathSync(target) === realpathSync(original))
    throw new Error(
      "Il database originale incluso è protetto. Usare una copia di lavoro.",
    );
  const repo = new Repository(target);
  try {
    if (
      repo.row("PRAGMA integrity_check").integrity_check !== "ok" ||
      repo.rows("PRAGMA foreign_key_check").length
    )
      throw new Error("Database non integro.");
    for (const table of [
      "workspace",
      "process_model",
      "entity_type",
      "relation_semantic",
      "relation_signature",
      "property_definition",
      "property_applicability",
      "entity_identity",
      "entity_definition",
      "relation_definition",
      "definition_property_value",
      "model_revision",
      "model_revision_entity",
      "model_revision_relation",
      "model_revision_rule",
      "model_revision_parameter_value",
      "model_parameter_definition",
      "rule_definition",
      "state_rule_config",
      "model_revision_view",
      "entity_view_layout",
      "execution_context",
      "model_execution",
      "model_execution_entity",
      "entity_instance",
      "instance_property_value",
      "property_observation",
      "runtime_correction",
    ])
      repo.row(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        table,
      );
    const folder = resolve(".local/backups");
    mkdirSync(folder, { recursive: true });
    await backup(repo.db, resolve(folder, `${Date.now()}-${id()}.db`));
    repo.migrate();
    return repo;
  } catch (e) {
    repo.close();
    throw e;
  }
}
