import { useState } from "react";
import { z } from "zod";
import { Plus, X, Pencil, Trash2 } from "lucide-react";
import { api } from "../services/api";
import { evaluateRule } from "../domain/analysis";
import {
  ruleStates,
  stateRuleInputSchema,
  type ProcessDocument,
  type Catalog,
  type Rule,
  type Value,
} from "../domain/model";

type Input = z.infer<typeof stateRuleInputSchema>;
type Operand = Extract<NonNullable<Rule["recipe"]>, { op: string }>["left"];
const constant = (value: string): Value => {
  try {
    const v: unknown = JSON.parse(value);
    if (v === null || ["string", "number", "boolean"].includes(typeof v))
      return v as Value;
  } catch {}
  return value;
};

export function RuleLibrary({
  doc,
  catalog,
  onClose,
  onSaved,
}: {
  doc: ProcessDocument;
  catalog: Catalog;
  onClose: () => void;
  onSaved: (d: ProcessDocument) => void;
}) {
  const [editing, setEditing] = useState<Rule | "new" | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const editable = doc.revision.status === "DRAFT";
  const save = async (data: Omit<Input, "version">) => {
    setBusy(true);
    setError("");
    try {
      onSaved(
        await api.saveRule(doc.revision.id, {
          ...data,
          version: doc.revision.version,
        }),
      );
      setEditing(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-overlay">
      <section
        className="project-library rule-library"
        role="dialog"
        aria-modal="true"
        aria-label="Gestione regole"
      >
        <div className="project-library-heading">
          <div>
            <small>
              {doc.revision.name} · {doc.revision.code}
            </small>
            <h1>Regole del processo</h1>
            <p>
              Configura applicabilità, obbligatorietà e abilitazione degli
              elementi.
            </p>
          </div>
          <button title="Chiudi gestione regole" onClick={onClose}>
            <X size={24} />
          </button>
        </div>
        {error && (
          <p className="error-banner" role="alert">
            {error}
          </p>
        )}
        {editing ? (
          <RuleForm
            key={editing === "new" ? "new" : editing.id}
            rule={editing === "new" ? null : editing}
            doc={doc}
            catalog={catalog}
            busy={busy}
            onCancel={() => setEditing(null)}
            onSave={save}
          />
        ) : (
          <>
            <button
              className="primary-button"
              disabled={!editable || !doc.entities.length}
              onClick={() => setEditing("new")}
            >
              <Plus size={20} />
              Nuova regola
            </button>
            {!editable && (
              <p>
                Revisione pubblicata: copia la revisione per modificare le
                regole.
              </p>
            )}
            {!doc.entities.length && (
              <p>
                Aggiungi almeno un elemento al processo per creare una regola.
              </p>
            )}
            <div className="rule-cards">
              {doc.rules.map((r) => {
                const truth = evaluateRule(r, doc);
                return (
                  <article key={r.id}>
                    <div>
                      <h2>{r.name}</h2>
                      <p>
                        {r.purpose} ·{" "}
                        {doc.entities.find((e) => e.id === r.target)?.name ??
                          "Regola generale"}
                      </p>
                      <div className="rule-expression">
                        {r.recipe
                          ? "kind" in r.recipe
                            ? `Prerequisito completato: ${doc.entities.find((e) => e.id === String(r.recipe && "kind" in r.recipe ? r.recipe.identity_id : ""))?.name}`
                            : `${describe(r.recipe.left, doc)} ${r.recipe.op} ${describe(r.recipe.right, doc)}`
                          : "Espressione avanzata legacy"}
                      </div>
                      <p>
                        Se vero: {r.trueState ?? "—"} · Se falso:{" "}
                        {r.falseState ?? "—"}
                      </p>
                      <small>
                        Valutazione del modello:{" "}
                        {truth === null ? "UNKNOWN" : truth ? "TRUE" : "FALSE"}
                        {r.recipe && "kind" in r.recipe
                          ? " · senza osservazioni di completamento"
                          : ""}
                      </small>
                    </div>
                    <div className="rule-actions">
                      <button
                        disabled={!editable || !r.recipe || busy}
                        onClick={() => setEditing(r)}
                      >
                        <Pencil size={16} />
                        Modifica
                      </button>
                      <button
                        disabled={!editable || busy}
                        onClick={async () => {
                          setBusy(true);
                          try {
                            onSaved(
                              await api.deleteRule(
                                doc.revision.id,
                                r.id,
                                doc.revision.version,
                              ),
                            );
                          } catch (e) {
                            setError(String(e));
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        <Trash2 size={16} />
                        Rimuovi dalla revisione
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
            {!doc.rules.length && (
              <p>Nessuna regola. Crea la prima con “Nuova regola”.</p>
            )}
          </>
        )}
      </section>
    </div>
  );
}
function describe(o: Operand, doc: ProcessDocument): string {
  return o.kind === "literal"
    ? JSON.stringify(o.value)
    : o.kind === "parameter"
      ? `Parametro ${o.code}`
      : `${doc.entities.find((e) => e.id === String(o.identity_id))?.name ?? o.identity_id} · ${o.code}`;
}
function OperandField({
  label,
  value,
  onChange,
  doc,
  catalog,
}: {
  label: string;
  value: Operand;
  onChange: (o: Operand) => void;
  doc: ProcessDocument;
  catalog: Catalog;
}) {
  const options: { label: string; value: Operand }[] = [
    { label: "Valore costante", value: { kind: "literal", value: true } },
    ...Object.keys(doc.parameters).map((code) => ({
      label: `Parametro · ${code}`,
      value: { kind: "parameter" as const, code },
    })),
    ...doc.entities
      .filter((e) => /^\d+$/.test(e.id))
      .flatMap((e) =>
        catalog.properties
          .filter(
            (p) =>
              p.scope !== "INSTANCE" &&
              p.types.some((t) => {
                let type: string | null = e.type;
                const seen = new Set<string>();
                while (type && !seen.has(type)) {
                  if (type === t) return true;
                  seen.add(type);
                  type =
                    catalog.types.find((x) => x.code === type)?.parent ?? null;
                }
                return false;
              }),
          )
          .filter(
            (p) => !["ENTITY_CODE", "VALUE_CLASSIFICATION"].includes(p.code),
          )
          .map((p) => ({
            label: `${e.name} · ${p.name}`,
            value: {
              kind: "property" as const,
              identity_id: Number(e.id),
              code: p.code,
            },
          })),
      ),
  ];
  const selected = options.findIndex((o) =>
    value.kind === "literal"
      ? o.value.kind === "literal"
      : JSON.stringify(o.value) === JSON.stringify(value),
  );
  return (
    <fieldset className="operand-field">
      <legend>{label}</legend>
      <label>
        Origine
        <select
          aria-label={`Origine ${label.toLowerCase()}`}
          value={selected}
          onChange={(e) => onChange(options[Number(e.target.value)].value)}
        >
          {options.map((o, i) => (
            <option key={i} value={i}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      {value.kind === "literal" && (
        <label>
          Valore costante
          <input
            aria-label={`Costante ${label.toLowerCase()}`}
            defaultValue={JSON.stringify(value.value)}
            onChange={(e) =>
              onChange({ kind: "literal", value: constant(e.target.value) })
            }
          />
        </label>
      )}
    </fieldset>
  );
}
function RuleForm({
  rule,
  doc,
  catalog,
  busy,
  onCancel,
  onSave,
}: {
  rule: Rule | null;
  doc: ProcessDocument;
  catalog: Catalog;
  busy: boolean;
  onCancel: () => void;
  onSave: (data: Omit<Input, "version">) => Promise<void>;
}) {
  const [purpose, setPurpose] = useState<Input["purpose"]>(
      (rule?.purpose as Input["purpose"]) ?? "REQUIREMENT",
    ),
    [kind, setKind] = useState(
      rule?.recipe && "kind" in rule.recipe ? "completed" : "compare",
    ),
    [left, setLeft] = useState<Operand>(
      rule?.recipe && "op" in rule.recipe
        ? rule.recipe.left
        : { kind: "literal", value: true },
    ),
    [right, setRight] = useState<Operand>(
      rule?.recipe && "op" in rule.recipe
        ? rule.recipe.right
        : { kind: "literal", value: true },
    ),
    [error, setError] = useState("");
  const states = ruleStates[purpose];
  return (
    <form
      className="rule-form"
      onSubmit={(e) => {
        e.preventDefault();
        const form = new FormData(e.currentTarget);
        try {
          const input = stateRuleInputSchema.parse({
            version: doc.revision.version,
            ruleId: rule?.id,
            name: form.get("name"),
            target: form.get("target"),
            purpose,
            trueState: form.get("trueState"),
            falseState: form.get("falseState"),
            recipe:
              kind === "completed"
                ? {
                    kind: "completed",
                    identity_id: Number(form.get("prerequisite")),
                  }
                : { op: form.get("op"), left, right },
          });
          void onSave(input);
        } catch (e) {
          setError(String(e));
        }
      }}
    >
      <h2>{rule ? "Modifica regola" : "Nuova regola di stato"}</h2>
      {error && <p role="alert">{error}</p>}
      <label>
        Nome regola
        <input
          name="name"
          aria-label="Nome regola"
          defaultValue={rule?.name ?? ""}
          required
          maxLength={200}
        />
      </label>
      <label>
        Elemento destinatario
        <select
          name="target"
          aria-label="Elemento destinatario"
          defaultValue={rule?.target ?? doc.entities[0]?.id}
        >
          {doc.entities
            .filter((e) => /^\d+$/.test(e.id))
            .map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
        </select>
      </label>
      <label>
        Scopo
        <select
          aria-label="Scopo regola"
          value={purpose}
          onChange={(e) => setPurpose(e.target.value as Input["purpose"])}
        >
          {Object.keys(ruleStates).map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
      </label>
      <label>
        Tipo di condizione
        <select
          aria-label="Tipo di condizione"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          <option value="compare">
            Confronto di proprietà, parametri o valori
          </option>
          <option value="completed">Attività prerequisito completata</option>
        </select>
      </label>
      {kind === "completed" ? (
        <label>
          Prerequisito
          <select
            name="prerequisite"
            aria-label="Prerequisito"
            required
            defaultValue={
              rule?.recipe && "kind" in rule.recipe
                ? rule.recipe.identity_id
                : undefined
            }
          >
            {doc.entities
              .filter((e) => ["ACTION", "DECISION"].includes(e.type))
              .map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
          </select>
        </label>
      ) : (
        <div className="rule-condition">
          <OperandField
            label="Sinistra"
            value={left}
            onChange={setLeft}
            doc={doc}
            catalog={catalog}
          />
          <label>
            Operatore
            <select
              name="op"
              aria-label="Operatore confronto"
              defaultValue={
                rule?.recipe && "op" in rule.recipe ? rule.recipe.op : "EQ"
              }
            >
              {[
                ["EQ", "Uguale (=)"],
                ["NEQ", "Diverso (≠)"],
                ["GT", "Maggiore (>)"],
                ["GTE", "Maggiore o uguale (≥)"],
                ["LT", "Minore (<)"],
                ["LTE", "Minore o uguale (≤)"],
              ].map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <OperandField
            label="Destra"
            value={right}
            onChange={setRight}
            doc={doc}
            catalog={catalog}
          />
        </div>
      )}
      <div className="rule-outcomes" key={purpose}>
        <label>
          Se vero
          <select
            name="trueState"
            aria-label="Se vero"
            defaultValue={
              rule?.purpose === purpose
                ? (rule.trueState ?? states[0])
                : states[0]
            }
          >
            {states.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          Se falso
          <select
            name="falseState"
            aria-label="Se falso"
            defaultValue={
              rule?.purpose === purpose
                ? (rule.falseState ?? states[1])
                : states[1]
            }
          >
            {states.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="project-form-actions">
        <button type="button" onClick={onCancel}>
          Annulla
        </button>
        <button className="primary-button" disabled={busy}>
          {busy ? "Salvataggio…" : "Salva regola"}
        </button>
      </div>
    </form>
  );
}
