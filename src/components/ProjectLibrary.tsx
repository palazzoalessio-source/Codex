import { useEffect, useState, type FormEvent } from "react";
import { Layers, Plus, ArrowRight, X, Search } from "lucide-react";
import { api } from "../services/api";
import type { Project, ProcessDocument } from "../domain/model";

export function ProjectLibrary({
  onClose,
  onOpen,
  onCreate,
}: {
  onClose: () => void;
  onOpen: (id: number) => Promise<void>;
  onCreate: (doc: ProcessDocument) => Promise<void>;
}) {
  const [projects, setProjects] = useState<Project[]>([]),
    [creating, setCreating] = useState(false),
    [query, setQuery] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    void api
      .projects()
      .then(setProjects)
      .catch((e) => setError(String(e)));
  }, []);
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const doc = await api.createProject({
        name: String(form.get("name")),
        processName: String(form.get("processName")),
        description: String(form.get("description")),
      });
      await onCreate(doc);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-overlay">
      <section
        className="project-library"
        role="dialog"
        aria-modal="true"
        aria-label="Libreria progetti"
      >
        <div className="project-library-heading">
          <div>
            <small>IL TUO WORKSPACE</small>
            <h1>Libreria progetti</h1>
            <p>Apri un processo esistente o inizia da un canvas vuoto.</p>
          </div>
          <button title="Chiudi libreria progetti" onClick={onClose}>
            <X size={24} />
          </button>
        </div>
        {error && (
          <p role="alert" className="error-banner">
            {error}
          </p>
        )}
        {creating ? (
          <form onSubmit={(e) => void submit(e)} className="new-project-form">
            <h2>Nuovo progetto vuoto</h2>
            <label>
              Nome progetto
              <input
                name="name"
                aria-label="Nome progetto"
                required
                maxLength={160}
                autoFocus
                placeholder="Es. Acquisti 2026"
              />
            </label>
            <label>
              Nome processo
              <input
                name="processName"
                aria-label="Nome processo"
                required
                maxLength={160}
                defaultValue="Processo principale"
              />
            </label>
            <label>
              Descrizione
              <textarea name="description" maxLength={4000} />
            </label>
            <p>
              Il progetto partirà senza elementi, relazioni o regole, con una
              revisione AS-IS modificabile.
            </p>
            <div className="project-form-actions">
              <button type="button" onClick={() => setCreating(false)}>
                Torna alla libreria
              </button>
              <button className="primary-button" disabled={busy}>
                {busy ? "Creazione…" : "Crea progetto vuoto"}
              </button>
            </div>
          </form>
        ) : (
          <>
            <div className="project-library-tools">
              <div className="search-field">
                <Search size={20} />
                <input
                  aria-label="Cerca progetti"
                  placeholder="Cerca un progetto o un processo…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              <button
                className="primary-button"
                onClick={() => setCreating(true)}
              >
                <Plus size={20} />
                Nuovo progetto
              </button>
            </div>
            <div className="project-cards">
              {projects
                .filter((p) =>
                  `${p.projectName} ${p.name}`
                    .toLocaleLowerCase()
                    .includes(query.toLocaleLowerCase()),
                )
                .map((p) => (
                  <article key={p.id}>
                    <div className="project-card-icon">
                      <Layers size={28} />
                    </div>
                    <h2>{p.projectName}</h2>
                    <h3>{p.name}</h3>
                    <p>{p.description || "Nessuna descrizione"}</p>
                    <div className="project-card-meta">
                      {p.entityCount} elementi · {p.revisionCount} revisioni
                    </div>
                    <button
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          await onOpen(p.revisionId);
                        } catch (e) {
                          setError(String(e));
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Apri processo
                      <ArrowRight size={18} />
                    </button>
                  </article>
                ))}
            </div>
            {!projects.length && (
              <p>Non ci sono progetti. Crea il primo per iniziare.</p>
            )}
          </>
        )}
      </section>
    </div>
  );
}
