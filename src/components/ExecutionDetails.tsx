import { z } from "zod";
import { valueSchema } from "../domain/model";
const observation = z.object({
  id: z.number(),
  code: z.string(),
  observed_at: z.string(),
  value_text: z.string().nullable(),
  value_integer: z.number().nullable(),
  value_real: z.number().nullable(),
  value_boolean: z.number().nullable(),
});
const schema = z.object({
  instances: z.array(
    z.object({
      id: z.number(),
      identityId: z.number(),
      name: z.string(),
      values: z.record(z.string(), valueSchema),
      observations: z.array(observation),
    }),
  ),
  corrections: z.array(
    z.object({
      correcting_instance_id: z.number(),
      corrected_instance_id: z.number(),
    }),
  ),
});
const labels: Record<string, string> = {
  ACTUAL_START: "Inizio effettivo",
  ACTUAL_END: "Fine effettiva",
  STATUS: "Stato",
  ENABLED_AT: "Abilitata dal",
  AVAILABLE_AT: "Disponibile dal",
  RESULT: "Esito",
};
export function ExecutionDetails({ data }: { data: unknown }) {
  const result = schema.safeParse(data);
  if (!result.success)
    return <p className="error">Formato dello storico non supportato.</p>;
  return (
    <div className="execution-details">
      {result.data.instances.map((i) => (
        <details key={i.id}>
          <summary>
            <strong>{i.name}</strong>
            <span>
              Istanza #{i.id} ·{" "}
              {String(i.values.STATUS ?? "Nessuno stato osservato")}
            </span>
          </summary>
          <table>
            <thead>
              <tr>
                <th>Osservazione</th>
                <th>Valore</th>
                <th>Data</th>
              </tr>
            </thead>
            <tbody>
              {i.observations.map((o) => (
                <tr key={o.id}>
                  <td>{labels[o.code] ?? o.code}</td>
                  <td>
                    {String(
                      o.value_text ??
                        o.value_integer ??
                        o.value_real ??
                        (o.value_boolean === null ? "" : !!o.value_boolean),
                    )}
                  </td>
                  <td>
                    {new Date(o.observed_at).toLocaleString("it-IT", {
                      timeZone: "Europe/Rome",
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {result.data.corrections
            .filter((c) => c.correcting_instance_id === i.id)
            .map((c) => (
              <p key={c.corrected_instance_id}>
                Corregge l’istanza #{c.corrected_instance_id} dello stesso
                elemento.
              </p>
            ))}
        </details>
      ))}
    </div>
  );
}
