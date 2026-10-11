import { useState, useRef, useCallback, useEffect } from "react";
import {
  documentSchema,
  type Catalog,
  type ProcessDocument,
} from "../domain/model";
import {
  execute,
  undo,
  redo,
  type Command,
  type History,
} from "../domain/commands";
import { api } from "../services/api";

function remapDocument(
  doc: ProcessDocument,
  saved: ProcessDocument,
): ProcessDocument {
  const known = new Map(saved.entities.map((e) => [e.uid, e]));
  const ids = new Map(
    doc.entities.map((e) => [e.id, known.get(e.uid)?.id ?? e.id]),
  );
  return {
    ...doc,
    revision: { ...doc.revision, version: saved.revision.version },
    entities: doc.entities.map((e) => {
      const n = known.get(e.uid);
      return n ? { ...e, id: n.id, definitionId: n.definitionId } : e;
    }),
    relations: doc.relations.map((r) => {
      const source = ids.get(r.source) ?? r.source,
        target = ids.get(r.target) ?? r.target;
      const match = saved.relations.find(
        (s) =>
          s.source === source &&
          s.target === target &&
          s.semantic === r.semantic,
      );
      return { ...r, id: match?.id ?? r.id, source, target };
    }),
  };
}
export function useEditor(catalog: Catalog) {
  const [history, setHistory] = useState<History | null>(null),
    [saving, setSaving] = useState(false),
    [error, setError] = useState(""),
    [lastSaved, setLastSaved] = useState(""),
    [recovery, setRecovery] = useState<ProcessDocument | null>(null);
  const current = useRef<History | null>(null),
    savedSignature = useRef(""),
    busy = useRef(false),
    pending = useRef<Promise<boolean> | null>(null),
    flush = useRef<() => Promise<boolean>>(async () => true);
  const update = useCallback((h: History | null) => {
    current.current = h;
    setHistory(h);
  }, []);
  const open = useCallback(
    (doc: ProcessDocument) => {
      savedSignature.current = JSON.stringify(doc);
      update({ past: [], present: doc, future: [] });
      setError("");
      setLastSaved("");
      const text = localStorage.getItem(`ipf-recovery-${doc.revision.id}`);
      let parsed: ReturnType<typeof documentSchema.safeParse> | null = null;
      try {
        parsed = text ? documentSchema.safeParse(JSON.parse(text)) : null;
      } catch {
        setError("Recovery locale danneggiato; dati SQLite caricati.");
      }
      setRecovery(
        parsed?.success && JSON.stringify(parsed.data) !== JSON.stringify(doc)
          ? parsed.data
          : null,
      );
    },
    [update],
  );
  const dispatch = useCallback(
    (c: Command) => {
      if (!current.current) return;
      try {
        update(execute(current.current, c, catalog));
        setError("");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [catalog, update],
  );
  const save = useCallback(async (): Promise<boolean> => {
    if (pending.current) {
      const ok = await pending.current;
      if (!ok) return false;
      return flush.current();
    }
    const h = current.current;
    if (
      !h ||
      h.present.revision.status !== "DRAFT" ||
      JSON.stringify(h.present) === savedSignature.current
    )
      return true;
    busy.current = true;
    setSaving(true);
    const snapshot = h.present;
    const operation = (async () => {
      try {
        const result = await api.save(snapshot);
        if (current.current?.present.revision.id !== result.revision.id)
          return true;
        const latest = current.current!;
        const same =
          JSON.stringify(latest.present) === JSON.stringify(snapshot);
        const next = {
          past: latest.past.map((d) => remapDocument(d, result)),
          present: same ? result : remapDocument(latest.present, result),
          future: latest.future.map((d) => remapDocument(d, result)),
        };
        savedSignature.current = JSON.stringify(result);
        update(next);
        try {
          localStorage.setItem(
            `ipf-recovery-${result.revision.id}`,
            JSON.stringify(next.present),
          );
        } catch {
          setError("Database salvato; recovery locale non disponibile.");
        }
        setLastSaved(
          new Date().toLocaleTimeString("it-IT", { timeZone: "Europe/Rome" }),
        );
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        return false;
      } finally {
        busy.current = false;
        pending.current = null;
        setSaving(false);
      }
    })();
    pending.current = operation;
    const ok = await operation;
    if (
      ok &&
      current.current?.present.revision.id === snapshot.revision.id &&
      JSON.stringify(current.current.present) !== savedSignature.current
    )
      return flush.current();
    return ok;
  }, [update]);
  flush.current = save;
  const viewport = useCallback(
    (v: ProcessDocument["viewport"]) => {
      if (current.current)
        update({
          ...current.current,
          present: { ...current.current.present, viewport: v },
        });
    },
    [update],
  );
  const dirty =
    !!history && JSON.stringify(history.present) !== savedSignature.current;
  useEffect(() => {
    if (!history || !dirty) return;
    try {
      localStorage.setItem(
        `ipf-recovery-${history.present.revision.id}`,
        JSON.stringify(history.present),
      );
    } catch {
      setError("Recovery locale non disponibile: salvare sul database.");
    }
    const timer = setTimeout(() => {
      void save();
    }, 1200);
    return () => clearTimeout(timer);
  }, [history, dirty, save]);
  useEffect(() => {
    const leave = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
      }
    };
    window.addEventListener("beforeunload", leave);
    return () => window.removeEventListener("beforeunload", leave);
  }, [dirty]);
  return {
    history,
    doc: history?.present ?? null,
    open,
    dispatch,
    viewport,
    save,
    saving,
    dirty,
    error,
    setError,
    lastSaved,
    recovery,
    discardRecovery: () => {
      setRecovery(null);
      if (history)
        localStorage.setItem(
          `ipf-recovery-${history.present.revision.id}`,
          JSON.stringify(history.present),
        );
    },
    restoreRecovery: () => {
      if (!recovery || !history) return;
      if (recovery.revision.version !== history.present.revision.version) {
        setError(
          "Recovery di una versione precedente: esportarlo e confrontarlo prima di importare.",
        );
        return;
      }
      dispatch({ type: "replace", document: recovery });
      setRecovery(null);
    },
    undo: () => {
      if (current.current) update(undo(current.current));
    },
    redo: () => {
      if (current.current) update(redo(current.current));
    },
  };
}
