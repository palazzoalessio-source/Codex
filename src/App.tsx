import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ReactFlowProvider, type Connection } from "@xyflow/react";
import {
  Layers,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Undo2,
  Redo2,
  Save,
  Copy,
  Download,
  Upload,
  BarChart3,
  Plus,
  Grid3X3,
  MousePointer2,
  Hand,
  Group,
  Trash2,
  AlignLeft,
  AlignHorizontalSpaceAround,
  X,
  GitCompareArrows,
  FileClock,
  ChevronRight,
} from "lucide-react";
import { z } from "zod";
import {
  api,
  downloadDocument,
  request,
  type RevisionEntry,
} from "./services/api";
import {
  allowedSemantics,
  documentSchema,
  isType,
  newEntity,
  type Catalog,
  type Entity,
  type ProcessDocument,
} from "./domain/model";
import { presentationLayouts } from "./domain/presentation";
import { applyCommand } from "./domain/commands";
import { analyze } from "./domain/analysis";
import { validate } from "./domain/validation";
import { useEditor } from "./state/useEditor";
import { GroupLibrary } from "./components/GroupLibrary";
import { MeansIcon, meansIcons } from "./components/MeansIcon";
import { RuleLibrary } from "./components/RuleLibrary";
import { ProjectLibrary } from "./components/ProjectLibrary";
import { EditorCanvas } from "./components/EditorCanvas";
import { Inspector } from "./components/Inspector";
import { AnalysisPanel } from "./components/AnalysisPanel";
import { ExecutionDetails } from "./components/ExecutionDetails";

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null),
    [revisions, setRevisions] = useState<RevisionEntry[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    void Promise.all([api.catalog(), api.list()])
      .then(([c, r]) => {
        setCatalog(c);
        setRevisions(r);
      })
      .catch((e) => setError(String(e)));
  }, []);
  if (error)
    return (
      <div className="loading">
        <h1>IPF Mapper</h1>
        <p>{error}</p>
      </div>
    );
  if (!catalog) return <div className="loading">Preparazione workspace…</div>;
  return (
    <Workspace
      catalog={catalog}
      revisions={revisions}
      refresh={async () => setRevisions(await api.list())}
    />
  );
}
function Workspace({
  catalog,
  revisions,
  refresh,
}: {
  catalog: Catalog;
  revisions: RevisionEntry[];
  refresh: () => Promise<void>;
}) {
  const editor = useEditor(catalog),
    { doc, dispatch } = editor;
  const [sidebar, setSidebar] = useState(true),
    [selectedUid, setSelectedUid] = useState<string | null>(null),
    [selectedIds, setSelectedIds] = useState<string[]>([]),
    [analysis, setAnalysis] = useState(false),
    [grid, setGrid] = useState(true),
    [pan, setPan] = useState(false),
    [space, setSpace] = useState(false),
    [search, setSearch] = useState(""),
    [focusId, setFocusId] = useState<string | null>(null),
    [flow, setFlow] = useState<{
      source: string;
      target: string;
      id?: string;
    } | null>(null),
    [connection, setConnection] = useState<Connection | null>(null),
    [clone, setClone] = useState(false),
    [projectLibrary, setProjectLibrary] = useState(false),
    [ruleLibrary, setRuleLibrary] = useState(false),
    [groupLibrary, setGroupLibrary] = useState(false),
    [iconLibrary, setIconLibrary] = useState(false),
    [executionData, setExecutionData] = useState<unknown>(null),
    [showExecutions, setShowExecutions] = useState(false);
  const onSelection = useCallback(
    (ids: string[]) =>
      setSelectedIds((previous) =>
        previous.length === ids.length &&
        previous.every((id, n) => id === ids[n])
          ? previous
          : ids,
      ),
    [],
  );
  const clipboard = useRef<ProcessDocument | null>(null),
    importInput = useRef<HTMLInputElement>(null);
  const displayLayouts = useMemo(
    () => (doc ? presentationLayouts(doc) : new Map()),
    [doc?.entities, doc?.relations],
  );
  const selected = doc?.entities.find((e) => e.uid === selectedUid) ?? null,
    editable = doc?.revision.status === "DRAFT",
    metrics = useMemo(
      () => (doc ? analyze(doc, catalog) : null),
      [doc?.entities, doc?.relations, doc?.rules, catalog],
    );
  useEffect(() => {
    const remembered = Number(localStorage.getItem("ipf-last-revision"));
    const first =
      revisions.find((r) => r.id === remembered) ??
      revisions.find((r) => r.status === "DRAFT") ??
      revisions[0];
    if (first && !doc)
      void api
        .read(first.id)
        .then(editor.open)
        .catch((e) => editor.setError(String(e)));
  }, [revisions, doc]);
  const select = (e: Entity | null) => {
    setSelectedUid(e?.uid ?? null);
    if (e?.type === "INFORMATION_FLOW" && doc) {
      const rs = doc.relations.filter((r) => r.source === e.id);
      setFlow({
        id: e.id,
        source: rs.find((r) => r.semantic === "SOURCE")?.target ?? "",
        target: rs.find((r) => r.semantic === "TARGET")?.target ?? "",
      });
    }
  };
  const openRevision = async (id: number) => {
    if (editor.dirty) {
      const success = await editor.save();
      if (success === false) return;
    }
    try {
      editor.open(await api.read(id));
      localStorage.setItem("ipf-last-revision", String(id));
      setSelectedUid(null);
      setSelectedIds([]);
    } catch (e) {
      editor.setError(String(e));
    }
  };
  const replace = (next: ProcessDocument) =>
    dispatch({ type: "replace", document: next });
  const remove = useCallback(() => {
    if (!doc) return;
    dispatch({
      type: "delete",
      ids: selectedIds.length ? selectedIds : selected ? [selected.id] : [],
    });
    setSelectedUid(null);
  }, [doc, selectedIds, selected, dispatch]);
  const duplicate = useCallback(
    (source: ProcessDocument | null = doc) => {
      if (!doc || !source || !editable) return;
      const ids = new Set(
        selectedIds.length ? selectedIds : selected ? [selected.id] : [],
      );
      const chosen =
        clipboard.current === source
          ? source.entities
          : source.entities.filter((e) => ids.has(e.id));
      const mapping = new Map(chosen.map((e) => [e.id, crypto.randomUUID()]));
      const copies = chosen.map((e) => ({
        ...e,
        id: mapping.get(e.id)!,
        uid: crypto.randomUUID(),
        definitionId: undefined,
        name: e.name + " · copia",
        layout: { ...e.layout, x: e.layout.x + 60, y: e.layout.y + 60 },
      }));
      const relations = source.relations
        .filter(
          (r) =>
            mapping.has(r.source) &&
            (mapping.has(r.target) || r.semantic === "PERFORMER"),
        )
        .map((r) => ({
          ...r,
          id: crypto.randomUUID(),
          source: mapping.get(r.source)!,
          target: mapping.get(r.target) ?? r.target,
        }));
      replace({
        ...doc,
        entities: [...doc.entities, ...copies],
        relations: [...doc.relations, ...relations],
      });
      if (copies[0]) select(copies[0]);
    },
    [doc, editable, selectedIds, selected, dispatch],
  );
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLElement &&
        (e.target.closest("input,textarea,select") ||
          e.target.isContentEditable)
      )
        return;
      if (e.code === "Space") {
        e.preventDefault();
        setSpace(true);
      }
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void editor.save();
      }
      if (mod && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) editor.redo();
        else editor.undo();
      }
      if (mod && e.key.toLowerCase() === "y") {
        e.preventDefault();
        editor.redo();
      }
      if (mod && e.key.toLowerCase() === "d") {
        e.preventDefault();
        duplicate();
      }
      if (mod && e.key.toLowerCase() === "c" && doc) {
        e.preventDefault();
        const ids = new Set(selectedIds);
        clipboard.current = {
          ...doc,
          entities: doc.entities.filter((x) => ids.has(x.id)),
          relations: doc.relations.filter(
            (r) =>
              ids.has(r.source) &&
              (ids.has(r.target) || r.semantic === "PERFORMER"),
          ),
        };
      }
      if (mod && e.key.toLowerCase() === "v" && clipboard.current) {
        e.preventDefault();
        duplicate(clipboard.current);
      }
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        remove();
      }
      if (e.key === "Escape") {
        select(null);
        setAnalysis(false);
        setFlow(null);
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space") setSpace(false);
    };
    window.addEventListener("keydown", key);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", key);
      window.removeEventListener("keyup", up);
    };
  }, [
    doc,
    editor.save,
    editor.undo,
    editor.redo,
    duplicate,
    remove,
    selectedIds,
  ]);
  const connect = (c: Connection) => {
    if (!doc || !editable) return;
    const source = doc.entities.find((e) => e.id === c.source),
      target = doc.entities.find((e) => e.id === c.target);
    if (!source || !target || source.id === target.id) return;
    if (
      (isType(source.type, "ACTION", catalog) ||
        isType(source.type, "PARTICIPANT", catalog)) &&
      (isType(target.type, "ACTION", catalog) ||
        isType(target.type, "PARTICIPANT", catalog))
    ) {
      setFlow({ source: source.id, target: target.id });
      return;
    }
    if (
      source.type === "INFORMATION" &&
      isType(target.type, "ACTION", catalog)
    ) {
      dispatch({
        type: "relation",
        relation: {
          id: crypto.randomUUID(),
          semantic: "INPUT",
          source: target.id,
          target: source.id,
        },
      });
      return;
    }
    const allowed = allowedSemantics(source, target, catalog);
    if (allowed.length === 1)
      dispatch({
        type: "relation",
        relation: {
          id: crypto.randomUUID(),
          semantic: allowed[0],
          source: source.id,
          target: target.id,
        },
      });
    else if (allowed.length) setConnection(c);
    else
      editor.setError(
        "Nessuna relazione ammessa tra questi tipi nel catalogo.",
      );
  };
  const group = () => {
    if (!doc || !editable) return;
    const members = doc.entities.filter(
      (e) =>
        selectedIds.includes(e.id) &&
        catalog.signatures.some(
          (s) => s.semantic === "CONTAINS" && isType(e.type, s.target, catalog),
        ),
    );
    if (!members.length) return;
    const x = Math.min(...members.map((e) => e.layout.x)) - 30,
      y = Math.min(...members.map((e) => e.layout.y)) - 55;
    const entity = newEntity("PROCESS_GROUP", "Nuovo gruppo", x, y);
    entity.layout.width =
      Math.max(...members.map((e) => e.layout.x + (e.layout.width ?? 200))) -
      x +
      30;
    entity.layout.height =
      Math.max(...members.map((e) => e.layout.y + (e.layout.height ?? 94))) -
      y +
      30;
    let next = applyCommand(doc, { type: "upsert", entity }, catalog);
    for (const member of members)
      next = applyCommand(
        next,
        {
          type: "relation",
          relation: {
            id: crypto.randomUUID(),
            semantic: "CONTAINS",
            source: entity.id,
            target: member.id,
          },
        },
        catalog,
      );
    replace(next);
    select(entity);
  };
  const align = (distribute = false) => {
    if (!doc) return;
    const members = doc.entities
      .filter((e) => selectedIds.includes(e.id) && !e.layout.locked)
      .sort((a, b) => a.layout.x - b.layout.x);
    if (members.length < 2) return;
    const x = members[0].layout.x,
      last = members.at(-1)!.layout.x;
    dispatch({
      type: "move",
      positions: members.map((e, n) => ({
        id: e.id,
        x: distribute ? x + (n * (last - x)) / (members.length - 1) : x,
        y: e.layout.y,
      })),
    });
  };
  const saveProperties = (
    entity: Entity,
    performer: string,
    parent: string,
  ) => {
    if (!doc) return;
    try {
      let next = applyCommand(doc, { type: "upsert", entity }, catalog);
      const oldOwner = next.relations.find(
        (r) => r.source === entity.id && r.semantic === "PERFORMER",
      )?.target;
      next = {
        ...next,
        relations: next.relations.filter(
          (r) =>
            !(r.source === entity.id && r.semantic === "PERFORMER") &&
            !(r.target === entity.id && r.semantic === "CONTAINS"),
        ),
      };
      if (performer) {
        next = applyCommand(
          next,
          {
            type: "relation",
            relation: {
              id: crypto.randomUUID(),
              semantic: "PERFORMER",
              source: entity.id,
              target: performer,
            },
          },
          catalog,
        );
        if (performer !== oldOwner) {
          const lane = doc.entities.find((e) => e.id === performer);
          if (lane)
            next = applyCommand(
              next,
              {
                type: "move",
                positions: [
                  {
                    id: entity.id,
                    x: entity.layout.x,
                    y: displayLayouts.get(lane.id)!.y + 10,
                  },
                ],
              },
              catalog,
            );
        }
      }
      if (parent)
        next = applyCommand(
          next,
          {
            type: "relation",
            relation: {
              id: crypto.randomUUID(),
              semantic: "CONTAINS",
              source: parent,
              target: entity.id,
            },
          },
          catalog,
        );
      replace(next);
    } catch (e) {
      editor.setError(String(e));
    }
  };
  const importJson = async (file: File) => {
    if (!doc) return;
    try {
      const imported = documentSchema.parse(JSON.parse(await file.text()));
      if (imported.revision.modelId !== doc.revision.modelId)
        throw new Error("Questo file appartiene a un altro processo.");
      const next = { ...imported, revision: doc.revision };
      const issues = validate(next, catalog).filter(
        (i) => i.severity === "error",
      );
      if (issues.length)
        throw new Error(issues.map((i) => i.message).join("\n"));
      replace(next);
    } catch (e) {
      editor.setError(String(e));
    }
  };
  if (!doc && revisions.length === 0)
    return (
      <ProjectLibrary
        onClose={() => {}}
        onOpen={openRevision}
        onCreate={async (next) => {
          await refresh();
          editor.open(next);
          localStorage.setItem("ipf-last-revision", String(next.revision.id));
        }}
      />
    );
  if (!doc || !metrics)
    return (
      <div className="loading">{editor.error || "Caricamento processo…"}</div>
    );
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <div className="brand-mark">
            <Layers size={24} />
          </div>
          <div>
            IPF <b>Mapper</b>
            <small>PROCESS INTELLIGENCE</small>
          </div>
        </div>
        <div className="header-context">
          <span className="environment-dot" />
          Workspace locale
          <span className="header-divider" />
          Modellazione & analisi
        </div>
        <div className="header-actions">
          <button
            className="secondary-button"
            onClick={async () => {
              if (!editor.dirty || (await editor.save()))
                setProjectLibrary(true);
            }}
          >
            <Layers size={18} />
            Progetti
          </button>
          <button
            className="secondary-button"
            onClick={async () => {
              if (!editor.dirty || (await editor.save())) setRuleLibrary(true);
            }}
          >
            Regole <span>{doc.rules.length}</span>
          </button>
          <button className="secondary-button" onClick={() => setClone(true)}>
            <GitCompareArrows size={16} />
            Copia revisione
          </button>
          <button
            className="primary-button"
            onClick={() => void editor.save()}
            disabled={!editable || editor.saving}
          >
            <Save size={16} />
            {editor.saving ? "Salvataggio…" : "Salva"}
          </button>
        </div>
      </header>
      {groupLibrary && (
        <GroupLibrary
          doc={doc}
          onClose={() => setGroupLibrary(false)}
          onInsert={replace}
        />
      )}
      {ruleLibrary && (
        <RuleLibrary
          doc={doc}
          catalog={catalog}
          onClose={() => setRuleLibrary(false)}
          onSaved={editor.open}
        />
      )}
      {projectLibrary && (
        <ProjectLibrary
          onClose={() => setProjectLibrary(false)}
          onOpen={async (id) => {
            await openRevision(id);
            setProjectLibrary(false);
            setSearch("");
            setSelectedUid(null);
            setFocusId(null);
          }}
          onCreate={async (next) => {
            await refresh();
            editor.open(next);
            localStorage.setItem("ipf-last-revision", String(next.revision.id));
            setProjectLibrary(false);
            setSearch("");
            setSelectedUid(null);
            setSelectedIds([]);
            setFocusId(null);
            setAnalysis(false);
          }}
        />
      )}
      <div className="workspace-body">
        {sidebar && (
          <aside className="sidebar">
            <div className="sidebar-section">
              <small>PROCESSI & REVISIONI</small>
              <select
                aria-label="Revisione corrente"
                value={doc.revision.id}
                onChange={(e) => void openRevision(Number(e.target.value))}
              >
                {revisions
                  .filter((r) => r.modelId === doc.revision.modelId)
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name} · {r.code} · {r.purpose}
                    </option>
                  ))}
              </select>
              <div className="revision-info">
                <span className={`purpose purpose-${doc.revision.purpose}`}>
                  {doc.revision.purpose.replace("_", "-")}
                </span>
                <span>{doc.revision.status}</span>
              </div>
            </div>
            <div className="sidebar-section">
              <div className="section-heading">
                <small>LIBRERIA ELEMENTI</small>
                <span>Trascina sul canvas</span>
              </div>
              <div className="library-switches">
                <button
                  onClick={() => setIconLibrary(!iconLibrary)}
                  aria-pressed={iconLibrary}
                >
                  Mezzi e icone
                </button>
                <button
                  onClick={async () => {
                    if (!editor.dirty || (await editor.save()))
                      setGroupLibrary(true);
                  }}
                >
                  Libreria gruppi
                </button>
              </div>
              {iconLibrary && (
                <div className="means-icon-picker">
                  {meansIcons.map(([kind, label]) => (
                    <button
                      key={kind}
                      disabled={!editable}
                      onClick={() => {
                        const e = newEntity(
                          "MEANS",
                          label,
                          (260 - doc.viewport.x) / doc.viewport.zoom,
                          (120 - doc.viewport.y) / doc.viewport.zoom,
                        );
                        e.properties.MEANS_ICON = kind;
                        dispatch({ type: "upsert", entity: e });
                        select(e);
                        setFocusId(e.id);
                      }}
                    >
                      <MeansIcon kind={kind} />
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
              )}
              <div className="library">
                {catalog.types
                  .filter((t) => t.code !== "INFORMATION_FLOW")
                  .map((t) => (
                    <button
                      key={t.code}
                      draggable={editable}
                      onDragStart={(e) => {
                        e.dataTransfer.setData("application/ipf-type", t.code);
                        e.dataTransfer.effectAllowed = "copy";
                      }}
                      onClick={() => {
                        if (!editable) return;
                        let x = 300,
                          y = 120 + (doc.entities.length % 5) * 140;
                        const width = t.code === "PROCESS_GROUP" ? 460 : 200,
                          height = t.code === "PROCESS_GROUP" ? 240 : 94;
                        if (isType(t.code, "PARTICIPANT", catalog))
                          y =
                            Math.max(
                              110,
                              ...doc.entities
                                .filter((e) =>
                                  isType(e.type, "PARTICIPANT", catalog),
                                )
                                .map(
                                  (e) =>
                                    displayLayouts.get(e.id)!.y +
                                    (displayLayouts.get(e.id)!.height ?? 140),
                                ),
                            ) + 30;
                        else {
                          const obstacles = doc.entities
                            .map((e) => ({
                              ...e,
                              layout: displayLayouts.get(e.id)!,
                            }))
                            .filter(
                              (e) =>
                                e.type !== "INFORMATION_FLOW" &&
                                e.type !== "PROCESS_GROUP" &&
                                !isType(e.type, "PARTICIPANT", catalog),
                            );
                          while (
                            obstacles.some(
                              (e) =>
                                x < e.layout.x + (e.layout.width ?? 200) + 20 &&
                                x + width + 20 > e.layout.x &&
                                y < e.layout.y + (e.layout.height ?? 94) + 20 &&
                                y + height + 20 > e.layout.y,
                            )
                          )
                            x += 240;
                        }
                        const entity = newEntity(t.code, t.name, x, y);
                        dispatch({ type: "upsert", entity });
                        select(entity);
                        setFocusId(entity.id);
                      }}
                    >
                      <span className={`library-icon library-${t.code}`}>
                        <Plus size={15} />
                      </span>
                      <span>{t.name}</span>
                      <span className="drag-dots">⠿</span>
                    </button>
                  ))}
              </div>
            </div>
            <div className="sidebar-section compact-section">
              <small>NAVIGAZIONE</small>
              <div className="search-field">
                <Search size={15} />
                <input
                  placeholder="Cerca nel processo…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  aria-label="Cerca nel processo"
                />
              </div>
              <div className="element-list">
                {[
                  [
                    "Funzioni e partecipanti",
                    (e: Entity) => isType(e.type, "PARTICIPANT", catalog),
                  ],
                  ["Gruppi", (e: Entity) => e.type === "PROCESS_GROUP"],
                  [
                    "Attività e decisioni",
                    (e: Entity) => isType(e.type, "ACTION", catalog),
                  ],
                  ["Informazioni", (e: Entity) => e.type === "INFORMATION"],
                  ["Mezzi", (e: Entity) => e.type === "MEANS"],
                  ["Flussi", (e: Entity) => e.type === "INFORMATION_FLOW"],
                ].map(([label, predicate]) => {
                  const items = doc.entities
                    .filter(predicate as (e: Entity) => boolean)
                    .filter(
                      (e) =>
                        !search ||
                        e.name
                          .toLocaleLowerCase()
                          .includes(search.toLocaleLowerCase()),
                    );
                  if (!items.length) return null;
                  return (
                    <details
                      key={label as string}
                      open={search ? true : undefined}
                    >
                      <summary>
                        {label as string}
                        <span>{items.length}</span>
                      </summary>
                      {items.map((e) => (
                        <button
                          key={e.id}
                          className={selected?.id === e.id ? "active" : ""}
                          onClick={() => {
                            select(e);
                            setFocusId(e.id);
                          }}
                        >
                          <span className={`element-dot dot-${e.type}`} />
                          {e.name}
                          <ChevronRight size={16} />
                        </button>
                      ))}
                    </details>
                  );
                })}
              </div>
            </div>
            <div className="sidebar-footer">
              <div className="legend">
                <span>
                  <i className="legend-critical" />
                  Criticità di flusso
                </span>
                <span>
                  <i className="legend-information" />
                  Informazione
                </span>
              </div>
              <small>Identità stabili · revisioni indipendenti</small>
            </div>
          </aside>
        )}
        <main className="main-workspace">
          <div className="process-heading">
            <div>
              <div className="breadcrumbs">
                Workspace
                <ChevronRight size={12} />
                Processi
                <ChevronRight size={12} />
                {doc.revision.code}
              </div>
              <h1>{doc.revision.name}</h1>
              <p>
                Modella il processo. Comprendi i flussi. Progetta il
                miglioramento.
              </p>
            </div>
            <div className="heading-status">
              <span className={`purpose purpose-${doc.revision.purpose}`}>
                {doc.revision.purpose.replace("_", "-")}
              </span>
              <small>
                {editor.dirty
                  ? "Modifiche da salvare"
                  : editor.lastSaved
                    ? `Salvato ${editor.lastSaved}`
                    : "Database sincronizzato"}
              </small>
            </div>
          </div>
          <div className="workspace-toolbar">
            <div className="toolbar-group">
              <button
                title="Mostra/nascondi libreria"
                onClick={() => setSidebar(!sidebar)}
              >
                {sidebar ? (
                  <PanelLeftClose size={18} />
                ) : (
                  <PanelLeftOpen size={18} />
                )}
              </button>
              <button
                title="Annulla (Ctrl+Z)"
                disabled={!editor.history?.past.length || !editable}
                onClick={editor.undo}
              >
                <Undo2 size={18} />
              </button>
              <button
                title="Ripeti (Ctrl+Shift+Z)"
                disabled={!editor.history?.future.length || !editable}
                onClick={editor.redo}
              >
                <Redo2 size={18} />
              </button>
            </div>
            <div className="toolbar-group">
              <button
                title="Seleziona"
                aria-pressed={!pan}
                className={!pan ? "active" : ""}
                onClick={() => setPan(false)}
              >
                <MousePointer2 size={20} />
                <span>Seleziona</span>
              </button>
              <button
                title="Pan"
                aria-pressed={pan}
                className={pan ? "active" : ""}
                onClick={() => setPan(true)}
              >
                <Hand size={20} />
                <span>Mano</span>
              </button>
              <button
                title="Griglia e snapping"
                className={grid ? "active" : ""}
                onClick={() => setGrid(!grid)}
              >
                <Grid3X3 size={17} />
              </button>
            </div>
            <div className="toolbar-group">
              <button
                title="Raggruppa selezione"
                disabled={!editable || !selectedIds.length}
                onClick={group}
              >
                <Group size={18} />
              </button>
              <button
                title="Separa gruppo"
                disabled={!editable || selected?.type !== "PROCESS_GROUP"}
                onClick={() =>
                  replace({
                    ...doc,
                    relations: doc.relations.filter(
                      (r) =>
                        r.semantic !== "CONTAINS" || r.source !== selected?.id,
                    ),
                  })
                }
              >
                <Layers size={17} />
              </button>
              <button
                title="Allinea a sinistra"
                disabled={!editable || selectedIds.length < 2}
                onClick={() => align()}
              >
                <AlignLeft size={18} />
              </button>
              <button
                title="Distribuisci orizzontalmente"
                disabled={!editable || selectedIds.length < 3}
                onClick={() => align(true)}
              >
                <AlignHorizontalSpaceAround size={18} />
              </button>
              <button
                title="Duplica (Ctrl+D)"
                disabled={!editable || !selectedIds.length}
                onClick={() => duplicate()}
              >
                <Copy size={17} />
              </button>
              <button
                title="Elimina selezione"
                disabled={!editable || !selectedIds.length}
                onClick={remove}
              >
                <Trash2 size={17} />
              </button>
            </div>
            <div className="toolbar-spacer" />
            <button
              className="toolbar-text"
              onClick={() => downloadDocument(doc)}
            >
              <Download size={15} />
              JSON
            </button>
            <button
              title="Importa JSON nella revisione"
              disabled={!editable}
              onClick={() => importInput.current?.click()}
            >
              <Upload size={17} />
            </button>
            <input
              type="file"
              accept="application/json,.json"
              hidden
              ref={importInput}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void importJson(file);
                e.target.value = "";
              }}
            />
            <button
              className="toolbar-text"
              onClick={() => setShowExecutions(true)}
            >
              <FileClock size={16} />
              Storico
            </button>
            <button
              className={`analysis-button ${analysis ? "active" : ""}`}
              onClick={() => setAnalysis(!analysis)}
            >
              <BarChart3 size={17} />
              Analisi
            </button>
          </div>
          {editor.error && (
            <div role="alert" className="error-banner">
              {editor.error}
              <button
                onClick={() => editor.setError("")}
                aria-label="Chiudi errore"
              >
                <X size={16} />
              </button>
            </div>
          )}
          {editor.recovery && (
            <div className="recovery-banner">
              Trovata una copia locale non sincronizzata.
              <button onClick={editor.restoreRecovery}>Recupera</button>
              <button onClick={() => downloadDocument(editor.recovery!)}>
                Esporta recovery
              </button>
              <button onClick={editor.discardRecovery}>Ignora</button>
            </div>
          )}
          {!editable && (
            <div className="readonly-banner">
              Snapshot {doc.revision.status}: sola lettura. Crea una copia per
              modificarlo.
            </div>
          )}
          <div className="editor-body">
            <ReactFlowProvider>
              <EditorCanvas
                doc={doc}
                catalog={catalog}
                dispatch={dispatch}
                onSelect={select}
                onSelection={onSelection}
                onConnect={connect}
                onFlow={(id, connection) => {
                  const rs = doc.relations.filter((r) => r.source === id);
                  setFlow({
                    id,
                    source:
                      connection?.source ??
                      rs.find((r) => r.semantic === "SOURCE")?.target ??
                      "",
                    target:
                      connection?.target ??
                      rs.find((r) => r.semantic === "TARGET")?.target ??
                      "",
                  });
                }}
                onViewport={(v) => {
                  if (
                    editable &&
                    (Math.abs(doc.viewport.x - v.x) > 0.1 ||
                      Math.abs(doc.viewport.y - v.y) > 0.1 ||
                      Math.abs(doc.viewport.zoom - v.zoom) > 0.001)
                  )
                    editor.viewport(v);
                }}
                focusId={focusId}
                grid={grid}
                search={search}
                panMode={pan || space}
              />
            </ReactFlowProvider>
            {selected && selected.type !== "INFORMATION_FLOW" && (
              <Inspector
                entity={selected}
                doc={doc}
                catalog={catalog}
                onSave={saveProperties}
                onClose={() => select(null)}
                onDelete={remove}
              />
            )}
          </div>
          <footer className="status-bar">
            <span>
              <i />
              {doc.entities.length} elementi · {doc.relations.length} relazioni
            </span>
            <span>
              {metrics.actions} attività
              <span className="status-separator" />
              {metrics.handoffs} handoff
              <span className="status-separator" />
              <b className="critical-text">{metrics.criticalities} criticità</b>
            </span>
            <span>UTF-8 · SQLite · autosave</span>
          </footer>
        </main>
        {analysis && (
          <AnalysisPanel
            doc={doc}
            catalog={catalog}
            revisions={revisions}
            onClose={() => setAnalysis(false)}
            onChange={replace}
            onFocus={(id) => {
              setFocusId(id);
              select(doc.entities.find((e) => e.id === id) ?? null);
            }}
          />
        )}
      </div>
      {clone && (
        <Modal
          title="Nuova revisione indipendente"
          onClose={() => setClone(false)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              void (async () => {
                try {
                  const success = await editor.save();
                  if (success === false) return;
                  const result = await api.clone(
                    doc.revision.id,
                    String(data.get("code")),
                    String(data.get("purpose")),
                  );
                  await refresh();
                  editor.open(result);
                  setClone(false);
                } catch (e) {
                  editor.setError(String(e));
                }
              })();
            }}
          >
            <label>
              Codice revisione
              <input
                name="code"
                required
                defaultValue={`TO-BE-${Date.now().toString().slice(-6)}`}
              />
            </label>
            <label>
              Scopo
              <select name="purpose" defaultValue="TO_BE">
                <option value="AS_IS">AS-IS</option>
                <option value="TO_BE">TO-BE</option>
              </select>
            </label>
            <p>
              Preserva identità, proprietà, parametri, regole e layout. Lo
              storico resta invariato.
            </p>
            <button className="primary-button" type="submit">
              Crea revisione
            </button>
          </form>
        </Modal>
      )}
      {flow && (
        <FlowDialog
          initial={flow}
          doc={doc}
          catalog={catalog}
          onClose={() => setFlow(null)}
          onSave={(next) => {
            replace(next);
            setFlow(null);
          }}
          onDelete={() => {
            if (flow.id) dispatch({ type: "delete", ids: [flow.id] });
            setFlow(null);
          }}
        />
      )}
      {connection && (
        <Modal
          title="Semantica del collegamento"
          onClose={() => setConnection(null)}
        >
          {allowedSemantics(
            doc.entities.find((e) => e.id === connection.source)!,
            doc.entities.find((e) => e.id === connection.target)!,
            catalog,
          ).map((sem) => (
            <button
              className="secondary-button full"
              key={sem}
              onClick={() => {
                dispatch({
                  type: "relation",
                  relation: {
                    id: crypto.randomUUID(),
                    semantic: sem,
                    source: connection.source!,
                    target: connection.target!,
                  },
                });
                setConnection(null);
              }}
            >
              {catalog.semantics.find((s) => s.code === sem)?.name ?? sem}
            </button>
          ))}
        </Modal>
      )}
      {showExecutions && (
        <Modal
          title="Storico delle esecuzioni"
          onClose={() => {
            setShowExecutions(false);
            setExecutionData(null);
          }}
        >
          <ExecutionHistory
            modelId={doc.revision.modelId}
            onData={setExecutionData}
          />
          {executionData !== null && <ExecutionDetails data={executionData} />}
          <p>
            Osservazioni e correzioni originali, in sola lettura. Inserimento e
            analisi runtime completa rimangono disponibili nel client Python.
          </p>
        </Modal>
      )}
    </div>
  );
}
function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog ref={ref} className="modal" onCancel={onClose}>
      <div className="panel-heading">
        <h2>{title}</h2>
        <button
          className="icon-button"
          aria-label="Chiudi finestra"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
function FlowDialog({
  initial,
  doc,
  catalog,
  onClose,
  onSave,
  onDelete,
}: {
  initial: { source: string; target: string; id?: string };
  doc: ProcessDocument;
  catalog: Catalog;
  onClose: () => void;
  onSave: (d: ProcessDocument) => void;
  onDelete: () => void;
}) {
  const rs = doc.relations.filter((r) => r.source === initial.id),
    existing = doc.entities.find((e) => e.id === initial.id);
  const [error, setError] = useState("");
  const endpoints = doc.entities.filter(
    (e) =>
      isType(e.type, "ACTION", catalog) ||
      isType(e.type, "PARTICIPANT", catalog),
  );
  return (
    <Modal
      title={
        initial.id ? "Proprietà Information Flow" : "Nuovo Information Flow"
      }
      onClose={onClose}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          try {
            const f = new FormData(e.currentTarget),
              source = String(f.get("source")),
              target = String(f.get("target"));
            if (source === target)
              throw new Error("Seleziona due endpoint diversi.");
            const flow =
              existing ??
              newEntity(
                "INFORMATION_FLOW",
                `${doc.entities.find((e) => e.id === source)?.name} → ${doc.entities.find((e) => e.id === target)?.name}`,
                0,
                0,
              );
            let next = applyCommand(
              doc,
              {
                type: "upsert",
                entity: {
                  ...flow,
                  properties: {
                    ...flow.properties,
                    TARGET_LEAD_TIME: String(f.get("leadTime")) || null,
                  },
                },
              },
              catalog,
            );
            next = {
              ...next,
              relations: next.relations.filter(
                (r) =>
                  r.source !== flow.id ||
                  !["SOURCE", "TARGET", "VIA", "CARRIES"].includes(r.semantic),
              ),
            };
            for (const [semantic, value] of [
              ["SOURCE", source],
              ["TARGET", target],
              ["VIA", String(f.get("means"))],
              ["CARRIES", String(f.get("information"))],
            ])
              if (value)
                next = applyCommand(
                  next,
                  {
                    type: "relation",
                    relation: {
                      id: crypto.randomUUID(),
                      semantic,
                      source: flow.id,
                      target: value,
                    },
                  },
                  catalog,
                );
            onSave(next);
          } catch (e) {
            setError(String(e));
          }
        }}
      >
        <fieldset disabled={doc.revision.status !== "DRAFT"}>
          <label>
            Origine
            <select name="source" defaultValue={initial.source} required>
              {endpoints.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Destinazione
            <select name="target" defaultValue={initial.target} required>
              {endpoints.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
          </label>
          {[
            ["means", "Mezzo", "MEANS", "VIA"],
            ["information", "Informazione", "INFORMATION", "CARRIES"],
          ].map(([name, label, type, semantic]) => (
            <label key={name}>
              {label}
              <select
                name={name}
                defaultValue={
                  rs.find((r) => r.semantic === semantic)?.target ?? ""
                }
              >
                <option value="">Non assegnato</option>
                {doc.entities
                  .filter((e) => e.type === type)
                  .map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.name}
                    </option>
                  ))}
              </select>
            </label>
          ))}
          <label>
            Lead time del flusso
            <input
              name="leadTime"
              placeholder="Es. 30 min, 2h, PT1H"
              defaultValue={String(existing?.properties.TARGET_LEAD_TIME ?? "")}
            />
          </label>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button className="primary-button" type="submit">
            Applica flusso
          </button>
          {initial.id && (
            <button type="button" className="danger-button" onClick={onDelete}>
              Rimuovi flusso
            </button>
          )}
        </fieldset>
      </form>
    </Modal>
  );
}
function ExecutionHistory({
  modelId,
  onData,
}: {
  modelId: number;
  onData: (d: unknown) => void;
}) {
  const [items, setItems] = useState<{ id: number; name: string }[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    void request(`/models/${modelId}/executions`)
      .then((d) => {
        setItems(
          z.array(z.object({ id: z.number(), name: z.string() })).parse(d),
        );
      })
      .catch((e) => setError(String(e)));
  }, [modelId]);
  return (
    <>
      {items.map((i) => (
        <button
          className="secondary-button full"
          key={i.id}
          onClick={() =>
            void request(`/executions/${i.id}`)
              .then(onData)
              .catch((e) => setError(String(e)))
          }
        >
          {i.name}
        </button>
      ))}
      {!items.length && <p>Nessuna esecuzione disponibile.</p>}
      {error && <p className="error">{error}</p>}
    </>
  );
}
