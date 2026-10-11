import { useEffect, useState } from "react";
import { X, LockKeyhole, Unlock, Trash2 } from "lucide-react";
import {
  classificationLabels,
  isType,
  propertyApplicable,
  type Catalog,
  type Entity,
  type ProcessDocument,
  type Value,
  type Classification,
} from "../domain/model";

export function Inspector({
  entity,
  doc,
  catalog,
  onSave,
  onClose,
  onDelete,
}: {
  entity: Entity;
  doc: ProcessDocument;
  catalog: Catalog;
  onSave: (entity: Entity, performer: string, parent: string) => void;
  onClose: () => void;
  onDelete: () => void;
}) {
  const [draft, setDraft] = useState(entity),
    [performer, setPerformer] = useState(""),
    [parent, setParent] = useState("");
  const editable = doc.revision.status === "DRAFT";
  useEffect(() => {
    setDraft(entity);
    setPerformer(
      doc.relations.find(
        (r) => r.semantic === "PERFORMER" && r.source === entity.id,
      )?.target ?? "",
    );
    setParent(
      doc.relations.find(
        (r) => r.semantic === "CONTAINS" && r.target === entity.id,
      )?.source ?? "",
    );
  }, [entity, doc.relations]);
  const setProperty = (code: string, value: Value) =>
    setDraft((d) => ({ ...d, properties: { ...d.properties, [code]: value } }));
  return (
    <aside className="inspector">
      <div className="panel-heading">
        <div>
          <small>ELEMENTO SELEZIONATO</small>
          <h2>Proprietà</h2>
        </div>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Chiudi proprietà"
        >
          <X size={18} />
        </button>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSave(draft, performer, parent);
        }}
      >
        <fieldset disabled={!editable}>
          <div className="type-tag">{entity.type.replaceAll("_", " ")}</div>
          <label>
            Nome
            <input
              aria-label="Nome elemento"
              required
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          </label>
          <label>
            Codice
            <input
              value={draft.code}
              onChange={(e) => setDraft({ ...draft, code: e.target.value })}
            />
          </label>
          <label>
            Descrizione
            <textarea
              value={draft.description}
              onChange={(e) =>
                setDraft({ ...draft, description: e.target.value })
              }
              rows={3}
            />
          </label>
          {isType(entity.type, "ACTION", catalog) && (
            <>
              <label>
                Funzione / performer
                <select
                  aria-label="Performer"
                  value={performer}
                  onChange={(e) => setPerformer(e.target.value)}
                >
                  <option value="">Non assegnato</option>
                  {doc.entities
                    .filter((e) => isType(e.type, "PARTICIPANT", catalog))
                    .map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.name}
                      </option>
                    ))}
                </select>
              </label>
              <label>
                Valore operativo
                <select
                  aria-label="Classificazione valore"
                  value={draft.classification}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      classification: e.target.value as Classification,
                    })
                  }
                >
                  {Object.entries(classificationLabels).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          {catalog.signatures.some(
            (s) =>
              s.semantic === "CONTAINS" &&
              isType(entity.type, s.target, catalog),
          ) && (
            <label>
              Gruppo
              <select
                value={parent}
                onChange={(e) => setParent(e.target.value)}
              >
                <option value="">Nessun gruppo</option>
                {doc.entities
                  .filter(
                    (e) => e.type === "PROCESS_GROUP" && e.id !== entity.id,
                  )
                  .map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.name}
                    </option>
                  ))}
              </select>
            </label>
          )}
          <div className="section-label">PROPRIETÀ DEL METAMODELLO</div>
          {catalog.properties
            .filter(
              (p) =>
                propertyApplicable(entity, p, catalog) &&
                !["ENTITY_CODE", "VALUE_CLASSIFICATION"].includes(p.code),
            )
            .map((p) => (
              <label key={p.code}>
                {p.name}
                {p.unit && ` (${p.unit})`}
                {p.valueType === "BOOLEAN" ? (
                  <select
                    value={
                      draft.properties[p.code] === undefined ||
                      draft.properties[p.code] === null
                        ? ""
                        : String(!!draft.properties[p.code])
                    }
                    onChange={(e) =>
                      setProperty(
                        p.code,
                        e.target.value === ""
                          ? null
                          : e.target.value === "true",
                      )
                    }
                  >
                    <option value="">Non impostato</option>
                    <option value="true">Sì</option>
                    <option value="false">No</option>
                  </select>
                ) : (
                  <input
                    type={
                      ["NUMBER", "INTEGER"].includes(p.valueType)
                        ? "number"
                        : "text"
                    }
                    step={p.valueType === "INTEGER" ? "1" : "any"}
                    value={
                      draft.properties[p.code] === null
                        ? ""
                        : String(draft.properties[p.code] ?? "")
                    }
                    onChange={(e) =>
                      setProperty(
                        p.code,
                        e.target.value === ""
                          ? null
                          : ["NUMBER", "INTEGER"].includes(p.valueType)
                            ? Number(e.target.value)
                            : e.target.value,
                      )
                    }
                  />
                )}
              </label>
            ))}
          <button
            type="button"
            className="secondary-button full"
            onClick={() =>
              setDraft({
                ...draft,
                layout: { ...draft.layout, locked: !draft.layout.locked },
              })
            }
          >
            {draft.layout.locked ? (
              <LockKeyhole size={15} />
            ) : (
              <Unlock size={15} />
            )}{" "}
            {draft.layout.locked ? "Sblocca elemento" : "Blocca elemento"}
          </button>
          <button type="submit" className="primary-button full">
            Applica proprietà
          </button>
          <button
            type="button"
            className="danger-button full"
            onClick={onDelete}
          >
            <Trash2 size={15} />
            Rimuovi dalla revisione
          </button>
        </fieldset>
      </form>
    </aside>
  );
}
