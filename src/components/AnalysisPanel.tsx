import { useMemo, useState, useEffect } from "react";
import { X, ArrowRight, AlertTriangle } from "lucide-react";
import { analyze, compare, evaluateStates } from "../domain/analysis";
import { validate } from "../domain/validation";
import type { Catalog, ProcessDocument } from "../domain/model";
import { api, type RevisionEntry } from "../services/api";
import { ParameterForm } from "./ParameterForm";
export function AnalysisPanel({
  doc,
  catalog,
  revisions,
  onClose,
  onFocus,
  onChange,
}: {
  doc: ProcessDocument;
  catalog: Catalog;
  revisions: RevisionEntry[];
  onClose: () => void;
  onFocus: (id: string) => void;
  onChange: (d: ProcessDocument) => void;
}) {
  const [tab, setTab] = useState("metrics"),
    [baseline, setBaseline] = useState<ProcessDocument | null>(null),
    [error, setError] = useState("");
  const metrics = useMemo(
      () => analyze(doc, catalog),
      [doc.entities, doc.relations, doc.rules, catalog],
    ),
    issues = useMemo(
      () => validate(doc, catalog),
      [doc.entities, doc.relations, doc.rules, catalog],
    ),
    states = useMemo(
      () => evaluateStates(doc),
      [doc.entities, doc.rules, doc.parameters],
    );
  useEffect(() => {
    setBaseline(null);
  }, [doc.revision.id]);
  const comparison = baseline ? compare(baseline, doc, catalog) : null;
  return (
    <section className="analysis-panel">
      <div className="panel-heading">
        <div>
          <small>PROCESS INTELLIGENCE</small>
          <h2>Analisi del modello</h2>
        </div>
        <button
          className="icon-button"
          aria-label="Chiudi analisi"
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </div>
      <div className="tabs">
        {[
          ["metrics", "Indicatori"],
          ["validation", `Validazione · ${issues.length}`],
          ["compare", "AS-IS / TO-BE"],
          ["rules", "Stati & regole"],
        ].map(([key, name]) => (
          <button
            key={key}
            className={tab === key ? "active" : ""}
            onClick={() => setTab(key)}
          >
            {name}
          </button>
        ))}
      </div>
      <div className="analysis-content">
        {tab === "metrics" && (
          <>
            <div className="metric-grid">
              {[
                ["Attività", metrics.actions],
                ["Flussi", metrics.flows],
                ["Criticità", metrics.criticalities],
                ["Handoff noti", metrics.handoffs],
                ["Loop strutturali", metrics.loops],
                ["Dipendenze", metrics.dependencies],
              ].map(([name, value]) => (
                <div className="metric-card" key={name}>
                  <small>{name}</small>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <h3>Composizione del valore</h3>
            <div className="value-bars">
              {Object.entries(metrics.values).map(([k, v]) => (
                <div key={k}>
                  <span>{k === "UNCLASSIFIED" ? "Non classificata" : k}</span>
                  <div>
                    <i
                      className={`bar-${k}`}
                      style={{
                        width: `${metrics.actions ? (v / metrics.actions) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <b>{v}</b>
                </div>
              ))}
            </div>
            <div className="analysis-note">
              Somma tempi attività:{" "}
              {(metrics.cycleTimeSeconds / 3600).toLocaleString("it-IT")} h ·
              copertura {metrics.durationCoverage.known}/
              {metrics.durationCoverage.total}. È carico teorico aggregato, non
              lead time di processo. Tempi flussi noti:{" "}
              {(metrics.flowTimeSeconds / 3600).toLocaleString("it-IT")} h (
              {metrics.flowDurationCoverage.known}/
              {metrics.flowDurationCoverage.total}). Handoff con ownership
              sconosciuta: {metrics.unknownHandoffOwners}.
            </div>
          </>
        )}
        {tab === "validation" && (
          <>
            {issues.length === 0 ? (
              <p>Nessuna incoerenza rilevata dalle regole attive.</p>
            ) : (
              issues.map((i, n) => (
                <button
                  className={`issue issue-${i.severity}`}
                  key={n}
                  onClick={() => i.entityId && onFocus(i.entityId)}
                >
                  <AlertTriangle size={16} />
                  <span>
                    <b>{i.code}</b>
                    {i.message}
                  </span>
                  <small>{i.severity}</small>
                </button>
              ))
            )}
          </>
        )}
        {tab === "compare" && (
          <>
            <label>
              Revisione di riferimento
              <select
                aria-label="Revisione di riferimento"
                value={baseline?.revision.id ?? ""}
                onChange={(e) => {
                  if (!e.target.value) {
                    setBaseline(null);
                    return;
                  }
                  void api
                    .read(Number(e.target.value))
                    .then(setBaseline)
                    .catch((e) => setError(String(e)));
                }}
              >
                <option value="">
                  Seleziona AS-IS o una versione precedente
                </option>
                {revisions
                  .filter(
                    (r) =>
                      r.modelId === doc.revision.modelId &&
                      r.id !== doc.revision.id,
                  )
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.code} · {r.purpose} · {r.status}
                    </option>
                  ))}
              </select>
            </label>
            {error && <p className="error">{error}</p>}
            {comparison && (
              <>
                <p className="comparison-heading">
                  {baseline!.revision.code}
                  <ArrowRight size={16} />
                  {doc.revision.code}
                </p>
                <div className="metric-grid">
                  {[
                    ["Aggiunti", comparison.added.length],
                    ["Eliminati", comparison.removed.length],
                    ["Modificati", comparison.modified.length],
                  ].map(([n, v]) => (
                    <div className="metric-card" key={n}>
                      <small>{n}</small>
                      <strong>{v}</strong>
                    </div>
                  ))}
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>Indicatore</th>
                      <th>Riferimento</th>
                      <th>Corrente</th>
                      <th>Delta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(
                      [
                        "actions",
                        "flows",
                        "criticalities",
                        "handoffs",
                        "loops",
                        "dependencies",
                        "decisions",
                      ] as const
                    ).map((k) => (
                      <tr key={k}>
                        <td>
                          {
                            {
                              actions: "Attività",
                              flows: "Flussi",
                              criticalities: "Criticità",
                              handoffs: "Passaggi tra funzioni",
                              loops: "Loop strutturali",
                              dependencies: "Dipendenze",
                              decisions: "Decisioni",
                            }[k]
                          }
                        </td>
                        <td>{comparison.before[k]}</td>
                        <td>{comparison.after[k]}</td>
                        <td>{comparison.after[k] - comparison.before[k]}</td>
                      </tr>
                    ))}
                    {(["VA", "NVA", "NNVA", "UNCLASSIFIED"] as const).map(
                      (k) => (
                        <tr key={k}>
                          <td>{k}</td>
                          <td>{comparison.before.values[k]}</td>
                          <td>{comparison.after.values[k]}</td>
                          <td>
                            {comparison.after.values[k] -
                              comparison.before.values[k]}
                          </td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
                <p>
                  Relazioni aggiunte: {comparison.relationsAdded.length} ·
                  rimosse: {comparison.relationsRemoved.length}. Parametri
                  modificati: {comparison.parametersChanged ? "sì" : "no"}.
                </p>
                {comparison.modified.map((e) => (
                  <button
                    className="result-row"
                    key={e.id}
                    onClick={() => onFocus(e.id)}
                  >
                    {e.name}
                    <small>{e.fields.join(", ")}</small>
                  </button>
                ))}
                {comparison.added.map((e) => (
                  <div className="result-row" key={e.id}>
                    + {e.name}
                  </div>
                ))}
                {comparison.removed.map((e) => (
                  <div className="result-row" key={e.id}>
                    − {e.name}
                  </div>
                ))}
                <p className="analysis-note">
                  Le metriche contano gli elementi del modello. Nessun saving o
                  lead time viene inferito dalla geometria o dalla somma dei
                  tempi. Le attività sono confrontate per identità stabile, non
                  per nome.
                </p>
              </>
            )}
          </>
        )}
        {tab === "rules" && (
          <>
            <ParameterForm doc={doc} onChange={onChange} />
            <p className="analysis-note">
              Scenario della revisione corrente, senza osservazioni runtime. Le
              ricette configurate sono valutate; espressioni legacy non portate
              restano UNKNOWN. Nessuna policy aziendale è incorporata
              nell’engine.
            </p>
            <table>
              <thead>
                <tr>
                  <th>Elemento</th>
                  <th>Applicabilità</th>
                  <th>Requisito</th>
                  <th>Abilitazione</th>
                </tr>
              </thead>
              <tbody>
                {states
                  .filter((s) => doc.rules.some((r) => r.target === s.id))
                  .map((s) => (
                    <tr key={s.id}>
                      <td>
                        <button onClick={() => onFocus(s.id)}>{s.name}</button>
                      </td>
                      <td>{s.applicability}</td>
                      <td>{s.requirement}</td>
                      <td>{s.enablement}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
            {doc.rules.map((r) => (
              <div className="result-row" key={r.id}>
                {r.name}
                <small>
                  {r.purpose} ·{" "}
                  {r.recipe
                    ? "Ricetta supportata"
                    : "Espressione legacy conservata"}
                </small>
              </div>
            ))}
          </>
        )}
      </div>
    </section>
  );
}
