import { useEffect, useState } from "react";
import { z } from "zod";
import { Layers, X } from "lucide-react";
import { request } from "../services/api";
import { groupTemplateSchema, insertGroup } from "../domain/templates";
import type { ProcessDocument } from "../domain/model";
const entriesSchema = z.array(
  z.object({ id: z.number(), name: z.string(), template: groupTemplateSchema }),
);
export function GroupLibrary({
  doc,
  onClose,
  onInsert,
}: {
  doc: ProcessDocument;
  onClose: () => void;
  onInsert: (d: ProcessDocument) => void;
}) {
  const [entries, setEntries] = useState<z.infer<typeof entriesSchema>>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const load = async () =>
    setEntries(entriesSchema.parse(await request("/group-templates")));
  useEffect(() => {
    void load().catch((e) => setError(String(e)));
  }, []);
  return (
    <div className="modal-overlay">
      <section
        className="project-library"
        role="dialog"
        aria-modal="true"
        aria-label="Libreria gruppi"
      >
        <div className="project-library-heading">
          <div>
            <h1>Libreria gruppi</h1>
            <p>
              Salva gruppi del processo e inserisci copie indipendenti nei tuoi
              progetti.
            </p>
          </div>
          <button title="Chiudi libreria gruppi" onClick={onClose}>
            <X size={24} />
          </button>
        </div>
        {error && <p role="alert">{error}</p>}
        <form
          className="save-group-template"
          onSubmit={async (e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            setBusy(true);
            try {
              await request("/group-templates", {
                method: "POST",
                body: JSON.stringify({
                  revisionId: doc.revision.id,
                  groupId: f.get("groupId"),
                  name: f.get("name"),
                }),
              });
              await load();
            } catch (e) {
              setError(String(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Gruppo del processo
            <select name="groupId" aria-label="Gruppo da salvare" required>
              {doc.entities
                .filter((e) => e.type === "PROCESS_GROUP")
                .map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Nome template
            <input
              name="name"
              aria-label="Nome template gruppo"
              required
              maxLength={160}
            />
          </label>
          <button
            className="primary-button"
            disabled={
              busy || !doc.entities.some((e) => e.type === "PROCESS_GROUP")
            }
          >
            Salva nella libreria
          </button>
        </form>
        <div className="project-cards">
          {entries.map((t) => (
            <article key={t.id}>
              <Layers size={28} />
              <h2>{t.name}</h2>
              <p>
                {t.template.entities.length} elementi ·{" "}
                {t.template.relations.length} relazioni interne
              </p>
              <button
                disabled={doc.revision.status !== "DRAFT"}
                onClick={() => {
                  onInsert(
                    insertGroup(
                      doc,
                      t.template,
                      (280 - doc.viewport.x) / doc.viewport.zoom,
                      (100 - doc.viewport.y) / doc.viewport.zoom,
                    ),
                  );
                  onClose();
                }}
              >
                Inserisci gruppo
              </button>
            </article>
          ))}
        </div>
        {!entries.length && (
          <p>
            Nessun gruppo salvato. Crea un gruppo nel canvas e salvalo qui per
            riutilizzarlo.
          </p>
        )}
      </section>
    </div>
  );
}
