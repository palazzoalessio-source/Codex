import type { ProcessDocument, Value } from "../domain/model";
export function ParameterForm({
  doc,
  onChange,
}: {
  doc: ProcessDocument;
  onChange: (d: ProcessDocument) => void;
}) {
  return (
    <form
      key={doc.revision.id + JSON.stringify(doc.parameters)}
      onSubmit={(e) => {
        e.preventDefault();
        const form = new FormData(e.currentTarget);
        const parameters: Record<string, Value> = {};
        for (const [code, old] of Object.entries(doc.parameters)) {
          const value = String(form.get(code));
          parameters[code] =
            typeof old === "boolean"
              ? value === "true"
              : typeof old === "number"
                ? Number(value)
                : value;
        }
        onChange({ ...doc, parameters });
      }}
    >
      <h3>Parametri configurabili della revisione</h3>
      <fieldset disabled={doc.revision.status !== "DRAFT"}>
        <div className="param-grid">
          {Object.entries(doc.parameters).map(([code, value]) => (
            <label key={code}>
              {code}
              {typeof value === "boolean" ? (
                <select name={code} defaultValue={String(value)}>
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              ) : (
                <input
                  required
                  name={code}
                  type={typeof value === "number" ? "number" : "text"}
                  step="any"
                  defaultValue={value === null ? "" : String(value)}
                />
              )}
            </label>
          ))}
        </div>
        <button type="submit" className="secondary-button">
          Applica parametri
        </button>
      </fieldset>
    </form>
  );
}
